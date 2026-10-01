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


def _cands(parts, i, doc):
    """``iter_key_candidates('.'.join(parts[i:]), doc)`` without re-splitting the key."""
    n = len(parts)
    while True:
        if i == n:
            return [doc]
        if doc is None:
            return ()
        if isinstance(doc, list):
            return _cands_list(parts, i, doc)
        if not isinstance(doc, dict):
            return ()
        if i == n - 1:
            return [doc.get(parts[i], NOTHING)]
        doc = doc.get(parts[i], {})
        i += 1


def _cands_list(parts, i, doc):
    sub_key = parts[i]
    try:
        idx = int(sub_key)
    except ValueError:
        idx = None
    if idx is None:
        ret = []
        for sub_doc in doc:
            if isinstance(sub_doc, dict):
                if sub_key in sub_doc:
                    ret.extend(_cands(parts, i + 1, sub_doc[sub_key]))
                else:
                    ret.append(NOTHING)
        return ret
    if idx >= len(doc):
        return ()
    sub_doc = doc[idx]
    if i + 1 < len(parts):
        return _cands(parts, i + 1, sub_doc)
    return [sub_doc]


def key_candidates(key: str):
    """A ``doc -> candidates`` function equal to ``iter_key_candidates(key, doc)``."""
    if not isinstance(key, str) or not key or "" in key.split("."):
        return lambda doc: _iter(key, doc)
    parts = tuple(key.split("."))
    if len(parts) == 1:
        k = parts[0]

        def single(doc):
            if isinstance(doc, dict):
                return (doc.get(k, NOTHING),)
            if doc is None:
                return ()
            if isinstance(doc, list):
                return _cands_list(parts, 0, doc)
            return ()
        return single
    return lambda doc: _cands(parts, 0, doc)


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
        cands = key_candidates(key)
        if keys <= {"$ne", "$nin"}:
            # Negative-only clause: mongomock returns False as soon as one candidate fails,
            # and True when every candidate (possibly none) satisfies all operators.
            if "$nin" in keys and not isinstance(value["$nin"], (list, tuple)):
                return _fallback(key, value)
            nchecks = tuple((_ops[op], arg) for op, arg in value.items())

            def pred(doc, cands=cands, nchecks=nchecks):
                for dv in cands(doc):
                    for fn, arg in nchecks:
                        if not fn(dv, arg):
                            return False
                return True
            return pred
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

            def pred(doc, cands=cands, check=check):
                for dv in cands(doc):
                    if check(dv):
                        return True
                return False
        else:
            def pred(doc, cands=cands, checks=tuple(checks)):
                for dv in cands(doc):
                    if all(c(dv) for c in checks):
                        return True
                return False
        return pred

    if value is None or (isinstance(value, _EQ_SCALARS) and not isinstance(value, ObjectId)):
        # mongomock: list candidate -> `search in dv or search == dv`;
        # otherwise `dv == search or (search is None and dv is NOTHING)`.
        cands = key_candidates(key)
        if value is None:
            def pred(doc, cands=cands):
                for dv in cands(doc):
                    if isinstance(dv, (list, tuple)):
                        if None in dv:
                            return True
                    elif dv is None or dv is NOTHING:
                        return True
                return False
        else:
            def pred(doc, cands=cands, value=value):
                for dv in cands(doc):
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


# ---------------------------------------------------------------------------- sort keys
_resolve_key = filtering.resolve_key
_compare_type = filtering._get_compare_type
_BsonComparable = filtering.BsonComparable
# BSON compare types whose values bson_compare orders with a plain Python ``op(a, b)``.
_NATIVE_TYPES = {10, 15, 35, 40, 45}


class _Unsortable:
    """Type slot for values mongomock cannot sort: comparing it raises like mongomock."""
    __slots__ = ("obj",)

    def __init__(self, obj):
        self.obj = obj

    def __eq__(self, other):
        return False

    __hash__ = None

    def _raise(self, other):
        raise NotImplementedError("Mongomock does not know how to sort '%s' of type '%s'"
                                  % (self.obj, type(self.obj)))

    __lt__ = __gt__ = __le__ = __ge__ = _raise


def _value_key(v):
    if v is None:
        return 5, 0
    try:
        t = _compare_type(v)
    except NotImplementedError:
        return _Unsortable(v), 0
    if t in _NATIVE_TYPES:
        return t, v
    return t, _BsonComparable(v)


def resolve_sort_key(key, doc):
    """Drop-in for mongomock's ``filtering.resolve_sort_key`` with the same ordering.

    mongomock wraps every value in ``BsonComparable`` whose ``__lt__`` runs the generic
    ``bson_compare`` (type lookup, isinstance chain) for EVERY comparison. Here the BSON type
    rank is computed once per document and numbers/strings/bools/datetimes compare natively
    (that is exactly what ``bson_compare`` ends up doing for two values of the same rank);
    other types keep ``BsonComparable``. Within one rank the payload kind is uniform."""
    value = _resolve_key(key, doc)
    if value is NOTHING:
        return 1, 5, 0
    if isinstance(value, (tuple, list)):
        if not value:
            return 0, 5, 0
        value = value[0]
    t, payload = _value_key(value)
    return 1, t, payload


def install_fast_sort() -> None:
    filtering.resolve_sort_key = resolve_sort_key
