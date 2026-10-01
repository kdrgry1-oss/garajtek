"""Compiled query predicates for localdb.

mongomock's ``filter_applies`` re-interprets the whole filter for every document: it
re-validates operators, copies ``$regex``/``$options`` dicts and re-compiles regexes per
document and per clause. A storefront search (17 ``$regex`` clauses in an ``$or``) over a few
thousand products spends almost all its time there.

``compile_filter(spec)`` turns a filter into a Python closure ONCE per query. It is exact by
construction: logical operators (``$and``/``$or``/``$nor``) and positive per-field operator
clauses are evaluated with mongomock's own operator functions in the same order and with the
same candidate-value semantics (``iter_key_candidates``); every clause it does not fully
understand (negations, ``$not``, ``$all``, ``$expr``, embedded-document/array equality,
regex objects, ...) is delegated unchanged to ``filter_applies({key: value}, doc)``.
Splitting a filter per key is equivalent because mongomock ANDs top-level keys
independently.
"""
from __future__ import annotations

import datetime
import re
import uuid
from typing import Callable

from bson import ObjectId
from mongomock import OperationFailure, filtering
from sentinels import NOTHING

Predicate = Callable[[dict], bool]

_iter = filtering.iter_key_candidates
_ops = filtering._filterer_inst._operator_map  # mongomock's own operator implementations

# Operators whose match is "some candidate value satisfies all operators" in mongomock's
# loop (no negative-match handling, no special pre-processing).
_POSITIVE_OPS = {"$eq", "$in", "$exists", "$gt", "$gte", "$lt", "$lte", "$size", "$type",
                 "$elemMatch", "$regex"}

# Scalars for which mongomock's plain-equality branch is a simple ``==``.
_EQ_SCALARS = (str, int, float, bool, datetime.datetime, uuid.UUID)


def _fallback(key, value) -> Predicate:
    clause = {key: value}
    apply = filtering.filter_applies
    return lambda doc: apply(clause, doc)


def _compile_regex(spec: dict):
    """Pre-compile {'$regex': str, '$options': str} exactly like _combine_regex_options +
    _regex do; None when the shape is unusual (left to mongomock)."""
    pattern = spec.get("$regex")
    if not isinstance(pattern, str):
        return None
    opts = spec.get("$options")
    flags = 0
    if opts is not None:
        if not isinstance(opts, str):
            return None
        for o in opts:
            if o in "imxs":
                flags |= getattr(re, o.upper())
    try:
        return re.compile(pattern, flags)
    except re.error:
        return None


def _regex_match(doc_val, rx) -> bool:
    if isinstance(doc_val, str):
        return rx.search(doc_val) is not None
    if isinstance(doc_val, list):  # mongomock's _regex ignores tuples
        return any(isinstance(x, str) and rx.search(x) is not None for x in doc_val)
    return False


def _compile_field(key: str, value) -> Predicate:
    if isinstance(value, dict):
        if not value or not all(isinstance(k, str) and k.startswith("$") for k in value):
            return _fallback(key, value)  # embedded document equality / empty
        if value == {"$exists": False}:
            return _fallback(key, value)  # has a dedicated pre-check in mongomock
        keys = set(value)
        if not keys <= (_POSITIVE_OPS | {"$options"}):
            return _fallback(key, value)
        if "$options" in keys and "$regex" not in keys:
            return _fallback(key, value)
        checks = []
        for op, arg in value.items():
            if op == "$options":
                continue
            if op == "$regex":
                rx = _compile_regex(value)
                if rx is None:
                    return _fallback(key, value)
                checks.append(lambda dv, rx=rx: dv is not NOTHING and _regex_match(dv, rx))
            elif op == "$in":
                if not isinstance(arg, (list, tuple)):
                    return _fallback(key, value)
                fn = _ops["$in"]
                checks.append(lambda dv, fn=fn, arg=arg: fn(dv, arg))
            else:
                fn = _ops[op]
                checks.append(lambda dv, fn=fn, arg=arg: fn(dv, arg))
        if len(checks) == 1:
            check = checks[0]

            def pred(doc, key=key, check=check):
                for dv in _iter(key, doc):
                    if check(dv):
                        return True
                return False
        else:
            def pred(doc, key=key, checks=tuple(checks)):
                for dv in _iter(key, doc):
                    if all(c(dv) for c in checks):
                        return True
                return False
        return pred

    if value is None or (isinstance(value, _EQ_SCALARS) and not isinstance(value, ObjectId)):
        # mongomock: list candidate -> `search in dv or search == dv`;
        # otherwise `dv == search or (search is None and dv is NOTHING)`.
        if value is None:
            def pred(doc, key=key):
                for dv in _iter(key, doc):
                    if isinstance(dv, (list, tuple)):
                        if None in dv:
                            return True
                    elif dv is None or dv is NOTHING:
                        return True
                return False
        else:
            def pred(doc, key=key, value=value):
                for dv in _iter(key, doc):
                    if isinstance(dv, (list, tuple)):
                        if value in dv:
                            return True
                    elif dv == value:
                        return True
                return False
        return pred
    return _fallback(key, value)


def compile_filter(spec) -> Predicate:
    """Return predicate(doc) -> bool equivalent to ``filter_applies(spec, doc)``."""
    if not isinstance(spec, dict):
        raise OperationFailure("the match filter must be an expression in an object")
    preds = []
    for key, value in spec.items():
        if key == "$comment":
            continue
        if key in ("$and", "$or", "$nor"):
            if not isinstance(value, (list, tuple)) or not value or \
                    not all(isinstance(q, dict) for q in value):
                preds.append(_fallback(key, value))
                continue
            subs = tuple(compile_filter(q) for q in value)
            if key == "$and":
                preds.append(lambda d, subs=subs: all(p(d) for p in subs))
            elif key == "$or":
                preds.append(lambda d, subs=subs: any(p(d) for p in subs))
            else:
                preds.append(lambda d, subs=subs: not any(p(d) for p in subs))
            continue
        if key.startswith("$"):
            preds.append(_fallback(key, value))
            continue
        preds.append(_compile_field(key, value))
    if not preds:
        return lambda doc: True
    if len(preds) == 1:
        return preds[0]
    preds = tuple(preds)
    return lambda doc: all(p(doc) for p in preds)
