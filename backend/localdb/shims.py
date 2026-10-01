"""Small extensions to mongomock's aggregation engine for operators the app uses but
mongomock 4.3 lacks:

* expression operators ``$toDouble``, ``$toDate``, ``$toBool``, ``$toObjectId``
* ``$lookup`` with ``let`` + ``pipeline`` (correlated sub-pipelines), with a pre-filter
  extracted from ``$expr`` equality clauses so the foreign lookup can use the hash index
* stages ``$replaceWith``, ``$unset``, ``$sortByCount``
"""
from __future__ import annotations

import copy
import datetime
import decimal

import bson
from bson import ObjectId

from mongomock import OperationFailure, aggregate, helpers

_APPLIED = False


def _to_double(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, bson.decimal128.Decimal128):
        return float(v.to_decimal())
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, datetime.datetime):
        v = helpers.patch_datetime_awareness_in_document(v)
        return (v - datetime.datetime(1970, 1, 1)).total_seconds() * 1000.0
    if isinstance(v, str):
        try:
            return float(v.strip())
        except ValueError as e:
            raise OperationFailure("Failed to parse number '%s' in $convert" % v) from e
    raise OperationFailure("Unsupported conversion from %s to double" % type(v).__name__)


def _parse_date_string(s: str) -> datetime.datetime:
    s = s.strip()
    if s.endswith("Z") or s.endswith("z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.datetime.fromisoformat(s)
    except ValueError:
        try:
            from dateutil import parser as _p  # python-dateutil is a backend dependency
            dt = _p.isoparse(s)
        except Exception as e:  # noqa: BLE001
            raise OperationFailure("Error parsing date string '%s'" % s) from e
    if dt.tzinfo is not None:
        dt = (dt - dt.utcoffset()).replace(tzinfo=None)
    return dt.replace(microsecond=(dt.microsecond // 1000) * 1000)


def _to_date(v):
    if v is None:
        return None
    if isinstance(v, datetime.datetime):
        return helpers.patch_datetime_awareness_in_document(v)
    if isinstance(v, ObjectId):
        return v.generation_time.replace(tzinfo=None)
    if isinstance(v, bool):
        raise OperationFailure("can't convert from BSON type bool to Date")
    if isinstance(v, (int, float)):
        return datetime.datetime(1970, 1, 1) + datetime.timedelta(milliseconds=v)
    if isinstance(v, str):
        return _parse_date_string(v)
    raise OperationFailure("Unsupported conversion from %s to date" % type(v).__name__)


def _to_bool(v):
    if v is None:
        return None
    return helpers.mongodb_to_bool(v)


def _to_object_id(v):
    if v is None:
        return None
    if isinstance(v, ObjectId):
        return v
    try:
        return ObjectId(v)
    except Exception as e:  # noqa: BLE001
        raise OperationFailure("Failed to parse objectId '%s' in $convert" % v) from e


_CONVERTERS = {
    "$toDouble": _to_double,
    "$toDate": _to_date,
    "$toBool": _to_bool,
    "$toObjectId": _to_object_id,
}


def _patch_type_conversions():
    for op in _CONVERTERS:
        if op not in aggregate.type_convertion_operators:
            aggregate.type_convertion_operators.append(op)
    orig = aggregate._Parser._handle_type_convertion_operator

    def handler(self, operator, values):
        conv = _CONVERTERS.get(operator)
        if conv is None:
            return orig(self, operator, values)
        if isinstance(values, list) and len(values) == 1:
            values = values[0]
        try:
            parsed = self.parse(values)
        except KeyError:
            return None
        return conv(parsed)

    aggregate._Parser._handle_type_convertion_operator = handler


# --------------------------------------------------------- extra expression operators
_EPOCH = datetime.datetime(1970, 1, 1)
_TYPE_CODES = {1: "double", 2: "string", 7: "objectId", 8: "bool", 9: "date", 16: "int",
               18: "long", 19: "decimal"}


def _tzinfo(tz):
    if tz is None:
        return None
    if isinstance(tz, str):
        t = tz.strip()
        if t in ("UTC", "GMT", "Z", "+00:00", "+0000", "+00"):
            return datetime.timezone.utc
        if t[:1] in "+-":
            sign = 1 if t[0] == "+" else -1
            digits = t[1:].replace(":", "")
            hh = int(digits[:2] or 0)
            mm = int(digits[2:4] or 0)
            return datetime.timezone(sign * datetime.timedelta(hours=hh, minutes=mm))
        from zoneinfo import ZoneInfo
        return ZoneInfo(t)
    raise OperationFailure("timezone must be a string")


def _to_local(dt, tz):
    """naive-UTC datetime -> naive local datetime in ``tz``."""
    tzi = _tzinfo(tz)
    if tzi is None:
        return dt
    return dt.replace(tzinfo=datetime.timezone.utc).astimezone(tzi).replace(tzinfo=None)


def _bson_type_name(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, bson.int64.Int64):
        return "long"
    if isinstance(v, int):
        return "int" if -2**31 <= v < 2**31 else "long"
    if isinstance(v, float):
        return "double"
    if isinstance(v, str):
        return "string"
    if isinstance(v, datetime.datetime):
        return "date"
    if isinstance(v, ObjectId):
        return "objectId"
    if isinstance(v, (list, tuple)):
        return "array"
    if isinstance(v, dict):
        return "object"
    if isinstance(v, bson.decimal128.Decimal128):
        return "decimal"
    if isinstance(v, (bytes, bson.binary.Binary)):
        return "binData"
    if isinstance(v, (bson.regex.Regex,)) or hasattr(v, "pattern"):
        return "regex"
    return "object"


def _p(parser, expr, default=None, missing=None):
    try:
        return parser.parse(expr)
    except KeyError:
        return missing


def _convert_value(v, to):
    if isinstance(to, (int, float)) and not isinstance(to, bool):
        to = _TYPE_CODES.get(int(to), str(to))
    to = str(to)
    if to in ("double", "decimal"):
        return _to_double(v)
    if to in ("int", "long"):
        if isinstance(v, bool):
            return int(v)
        if isinstance(v, (int, float)):
            return int(v)
        if isinstance(v, bson.decimal128.Decimal128):
            return int(v.to_decimal())
        if isinstance(v, datetime.datetime):
            return int((v - _EPOCH).total_seconds() * 1000)
        if isinstance(v, str):
            t = v.strip()
            try:
                return int(t)
            except ValueError as e:
                raise OperationFailure("Failed to parse number '%s' in $convert" % v) from e
        raise OperationFailure("Unsupported conversion to %s" % to)
    if to == "string":
        return _to_string(v)
    if to == "bool":
        return helpers.mongodb_to_bool(v)
    if to == "date":
        return _to_date(v)
    if to == "objectId":
        return _to_object_id(v)
    raise OperationFailure("Unknown type name: %s" % to)


def _to_string(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        if v.is_integer() and abs(v) < 1e15:
            return str(int(v))
        return repr(v)
    if isinstance(v, datetime.datetime):
        v = helpers.patch_datetime_awareness_in_document(v)
        return v.strftime("%Y-%m-%dT%H:%M:%S.") + "%03dZ" % (v.microsecond // 1000)
    return str(v)


def _op_convert(parser, args):
    if not isinstance(args, dict) or "input" not in args or "to" not in args:
        raise OperationFailure("$convert requires 'input' and 'to'")
    v = _p(parser, args["input"])
    to = _p(parser, args["to"])
    if v is None:
        return _p(parser, args["onNull"]) if "onNull" in args else None
    try:
        return _convert_value(v, to)
    except Exception:  # noqa: BLE001
        if "onError" in args:
            return _p(parser, args["onError"])
        raise


def _simple(conv):
    def handler(parser, args):
        if isinstance(args, list) and len(args) == 1:
            args = args[0]
        v = _p(parser, args)
        if v is None:
            return None
        return conv(v)
    return handler


def _op_type(parser, args):
    if isinstance(args, list) and len(args) == 1:
        args = args[0]
    try:
        v = parser.parse(args)
    except KeyError:
        return "missing"
    return _bson_type_name(v)


def _substr_bytes(parser, args):
    s, start, length = (_p(parser, a) for a in args)
    if s is None:
        return ""
    if not isinstance(s, str):
        s = _to_string(s) or ""
    b = s.encode("utf-8")
    start = int(start or 0)
    length = int(length)
    end = len(b) if length < 0 else start + length
    return b[start:end].decode("utf-8", errors="ignore")


def _op_reduce(parser, args):
    arr = _p(parser, args.get("input"))
    if arr is None:
        return None
    acc = _p(parser, args.get("initialValue"))
    for item in arr:
        sub = aggregate._Parser(parser._doc_dict,
                                dict(parser._user_vars, value=acc, this=item),
                                ignore_missing_keys=parser._ignore_missing_keys)
        try:
            acc = sub.parse(args["in"])
        except KeyError:
            acc = None
    return acc


def _op_merge_objects(parser, args):
    if not isinstance(args, list):
        args = [args]
    out = {}
    for a in args:
        v = _p(parser, a)
        if v is None:
            continue
        if not isinstance(v, dict):
            raise OperationFailure("$mergeObjects requires object inputs")
        out.update(v)
    return out


def _op_date_from_string(parser, args):
    s = _p(parser, args.get("dateString"))
    if s is None:
        return _p(parser, args["onNull"]) if "onNull" in args else None
    try:
        fmt = _p(parser, args.get("format"))
        tz = _p(parser, args.get("timezone"))
        if fmt:
            pyfmt = fmt.replace("%L", "%f")
            dt = datetime.datetime.strptime(s, pyfmt)
        else:
            dt = None
            t = s.strip()
            if t.endswith(("Z", "z")):
                t = t[:-1] + "+00:00"
            dt = datetime.datetime.fromisoformat(t)
        if dt.tzinfo is None and tz:
            dt = dt.replace(tzinfo=_tzinfo(tz))
        if dt.tzinfo is not None:
            dt = (dt - dt.utcoffset()).replace(tzinfo=None)
        return dt.replace(microsecond=(dt.microsecond // 1000) * 1000)
    except Exception as e:  # noqa: BLE001
        if "onError" in args:
            return _p(parser, args["onError"])
        raise OperationFailure("Error parsing date string '%s': %s" % (s, e)) from e


def _op_date_to_string(parser, args):
    d = _p(parser, args.get("date"))
    if d is None:
        return _p(parser, args["onNull"]) if "onNull" in args else None
    if isinstance(d, ObjectId):
        d = d.generation_time.replace(tzinfo=None)
    if not isinstance(d, datetime.datetime):
        raise OperationFailure("$dateToString requires a date, found %s" % type(d).__name__)
    d = helpers.patch_datetime_awareness_in_document(d)
    fmt = _p(parser, args.get("format")) or "%Y-%m-%dT%H:%M:%S.%LZ"
    tz = _p(parser, args.get("timezone"))
    local = _to_local(d, tz)
    out = []
    i = 0
    while i < len(fmt):
        ch = fmt[i]
        if ch == "%" and i + 1 < len(fmt):
            code = fmt[i + 1]
            i += 2
            if code == "L":
                out.append("%03d" % (local.microsecond // 1000))
            elif code == "%":
                out.append("%")
            elif code == "z":
                off = _tzinfo(tz).utcoffset(local) if tz else datetime.timedelta(0)
                mins = int(off.total_seconds() // 60)
                out.append("%s%02d%02d" % ("+" if mins >= 0 else "-", abs(mins) // 60,
                                           abs(mins) % 60))
            elif code == "Z":
                off = _tzinfo(tz).utcoffset(local) if tz else datetime.timedelta(0)
                out.append(str(int(off.total_seconds() // 60)))
            elif code == "u":
                out.append(str(local.isoweekday()))
            elif code == "w":
                out.append(str(local.isoweekday() % 7 + 1))
            elif code in "YmdHMSjUVG":
                out.append(local.strftime("%" + code))
            else:
                raise OperationFailure("Invalid format character '%%%s'" % code)
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _trim_factory(mode):
    def handler(parser, args):
        v = _p(parser, args.get("input"))
        if v is None:
            return None
        chars = _p(parser, args.get("chars")) if "chars" in args else None
        if mode == "both":
            return v.strip(chars) if chars is not None else v.strip()
        if mode == "left":
            return v.lstrip(chars) if chars is not None else v.lstrip()
        return v.rstrip(chars) if chars is not None else v.rstrip()
    return handler


def _op_index_of_array(parser, args):
    vals = [_p(parser, a) for a in args]
    arr, search = vals[0], vals[1]
    if arr is None:
        return None
    start = int(vals[2]) if len(vals) > 2 and vals[2] is not None else 0
    end = int(vals[3]) if len(vals) > 3 and vals[3] is not None else len(arr)
    for i in range(start, min(end, len(arr))):
        if arr[i] == search:
            return i
    return -1


def _case(fn):
    def handler(parser, args):
        if isinstance(args, list) and len(args) == 1:
            args = args[0]
        v = _p(parser, args)
        if v is None:
            return ""
        return fn(_to_string(v))
    return handler


def _op_concat(parser, args):
    parts = []
    for a in args:
        try:
            v = parser.parse(a)
        except KeyError:
            return None
        if v is None:
            return None
        if not isinstance(v, str):
            raise OperationFailure("$concat only supports strings, not %s" % type(v).__name__)
        parts.append(v)
    return "".join(parts)


def _op_str_len_cp(parser, args):
    if isinstance(args, list) and len(args) == 1:
        args = args[0]
    v = _p(parser, args)
    if not isinstance(v, str):
        raise OperationFailure("$strLenCP requires a string argument")
    return len(v)


def _op_str_len_bytes(parser, args):
    if isinstance(args, list) and len(args) == 1:
        args = args[0]
    v = _p(parser, args)
    if not isinstance(v, str):
        raise OperationFailure("$strLenBytes requires a string argument")
    return len(v.encode("utf-8"))


def _num(v):
    if isinstance(v, bson.decimal128.Decimal128):
        return float(v.to_decimal())
    return v


def _parse_args(parser, args):
    if not isinstance(args, list):
        args = [args]
    out = []
    for a in args:
        try:
            out.append(_num(parser.parse(a)))
        except KeyError:
            out.append(None)
    return out


def _is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) or isinstance(v, bool)


def _op_add(parser, args):
    vals = _parse_args(parser, args)
    if any(v is None for v in vals):
        return None
    date = None
    total = 0
    for v in vals:
        if isinstance(v, datetime.datetime):
            if date is not None:
                raise OperationFailure("only one date allowed in an $add expression")
            date = v
        elif isinstance(v, (int, float)):
            total += v
        else:
            raise OperationFailure("$add only supports numeric or date types, not %s"
                                   % _bson_type_name(v))
    if date is not None:
        return date + datetime.timedelta(milliseconds=total)
    return total


def _op_subtract(parser, args):
    a, b = _parse_args(parser, args)
    if a is None or b is None:
        return None
    if isinstance(a, datetime.datetime) and isinstance(b, datetime.datetime):
        return int((a - b).total_seconds() * 1000)
    if isinstance(a, datetime.datetime) and isinstance(b, (int, float)):
        return a - datetime.timedelta(milliseconds=b)
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a - b
    raise OperationFailure("can't $subtract %s from %s" % (_bson_type_name(b),
                                                           _bson_type_name(a)))


def _op_multiply(parser, args):
    vals = _parse_args(parser, args)
    if any(v is None for v in vals):
        return None
    out = 1
    for v in vals:
        if not isinstance(v, (int, float)):
            raise OperationFailure("$multiply only supports numeric types, not %s"
                                   % _bson_type_name(v))
        out *= v
    return out


def _op_divide(parser, args):
    a, b = _parse_args(parser, args)
    if a is None or b is None:
        return None
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        raise OperationFailure("$divide only supports numeric types")
    if b == 0:
        raise OperationFailure("can't $divide by zero")
    return a / b


def _op_round(parser, args):
    vals = _parse_args(parser, args)
    v = vals[0]
    place = int(vals[1]) if len(vals) > 1 and vals[1] is not None else 0
    if v is None:
        return None
    d = decimal.Decimal(repr(v)).quantize(decimal.Decimal(1).scaleb(-place),
                                         rounding=decimal.ROUND_HALF_EVEN)
    return int(d) if isinstance(v, int) or place <= 0 and isinstance(v, int) else float(d)


def _op_mod(parser, args):
    a, b = _parse_args(parser, args)
    if a is None or b is None:
        return None
    if b == 0:
        raise OperationFailure("can't $mod by zero")
    import math
    return math.fmod(a, b) if isinstance(a, float) or isinstance(b, float) else \
        int(math.fmod(a, b))


def _unary_math(fn):
    def handler(parser, args):
        v = _parse_args(parser, args)[0]
        if v is None:
            return None
        return fn(v)
    return handler


def _bson_key(v):
    from mongomock import filtering
    return filtering.BsonComparable(v)


def _numeric(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, bson.decimal128.Decimal128):
        return float(v.to_decimal())
    if isinstance(v, decimal.Decimal):
        return float(v)
    return None


def _acc_sum(vals):
    total = 0
    for v in vals:
        n = _numeric(v)
        if n is not None:
            total += n
    return total


def _acc_avg(vals):
    nums = [n for n in (_numeric(v) for v in vals) if n is not None]
    return (sum(nums) / len(nums)) if nums else None


def _acc_max(vals):
    vals = [v for v in vals if v is not None]
    return max(vals, key=_bson_key) if vals else None


def _acc_min(vals):
    vals = [v for v in vals if v is not None]
    return min(vals, key=_bson_key) if vals else None


def _expr_accumulator(fn):
    def handler(parser, args):
        if isinstance(args, list) and len(args) != 1:
            vals = [_p(parser, a) for a in args]
        else:
            if isinstance(args, list):
                args = args[0]
            v = _p(parser, args)
            vals = v if isinstance(v, list) else [v]
        return fn(vals)
    return handler


def _expr_first_last(index):
    def handler(parser, args):
        if isinstance(args, list) and len(args) == 1:
            args = args[0]
        v = _p(parser, args)
        if not isinstance(v, list) or not v:
            return None
        return v[index]
    return handler


def _accumulate_group(output_fields, group_list):
    """Mongo-faithful $group accumulators (mongomock turns falsy $addToSet values into None,
    lacks $count and compares mixed types with Python ordering)."""
    doc_dict = {}
    for field, value in output_fields.items():
        if field == "_id":
            continue
        for operator, key in value.items():
            if operator == "$count":
                doc_dict[field] = len(group_list)
                continue
            values = []
            missing = []
            for doc in group_list:
                try:
                    values.append(aggregate._parse_expression(key, doc))
                    missing.append(False)
                except KeyError:
                    missing.append(True)
            if operator == "$sum":
                doc_dict[field] = _acc_sum(values)
            elif operator == "$avg":
                doc_dict[field] = _acc_avg(values)
            elif operator == "$max":
                doc_dict[field] = _acc_max(values)
            elif operator == "$min":
                doc_dict[field] = _acc_min(values)
            elif operator in ("$first", "$last"):
                if not group_list:
                    doc_dict[field] = None
                    continue
                i = 0 if operator == "$first" else -1
                # missing value in the first/last document -> null (MongoDB semantics)
                if missing[i]:
                    doc_dict[field] = None
                else:
                    doc_dict[field] = values[0] if i == 0 else values[-1]
            elif operator == "$push":
                doc_dict.setdefault(field, [])
                doc_dict[field].extend(values)
            elif operator == "$addToSet":
                out = []
                for v in values:
                    if v not in out:
                        out.append(v)
                doc_dict[field] = out
            elif operator == "$mergeObjects":
                merged = {}
                for v in values:
                    if isinstance(v, dict):
                        merged.update(v)
                doc_dict[field] = merged
            else:
                raise NotImplementedError("Group operator %s is not supported by localdb"
                                          % operator)
    return doc_dict


_MISSING = object()


def _cmp_key(v):
    from mongomock import filtering
    if v is _MISSING:
        return (0, 0)
    return (1, filtering.BsonComparable(v))


def _bson_cmp(a, b):
    ka, kb = _cmp_key(a), _cmp_key(b)
    if ka[0] != kb[0]:
        return -1 if ka[0] < kb[0] else 1
    if ka[0] == 0:
        return 0
    if ka[1] < kb[1]:
        return -1
    if kb[1] < ka[1]:
        return 1
    return 0


def _comparison(test):
    def handler(parser, args):
        if not isinstance(args, list) or len(args) != 2:
            raise OperationFailure("comparison operators take exactly 2 arguments")
        a = _p(parser, args[0], missing=_MISSING)
        b = _p(parser, args[1], missing=_MISSING)
        return test(_bson_cmp(a, b))
    return handler


def _op_filter(parser, args):
    arr = _p(parser, args.get("input"))
    if arr is None:
        return None
    if not isinstance(arr, list):
        raise OperationFailure("input to $filter must be an array")
    name = args.get("as", "this")
    out = []
    for item in arr:
        sub = aggregate._Parser(parser._doc_dict, dict(parser._user_vars, **{name: item}),
                                ignore_missing_keys=parser._ignore_missing_keys)
        try:
            ok = helpers.mongodb_to_bool(sub.parse(args["cond"]))
        except KeyError:
            ok = False
        if ok:
            out.append(item)
    limit = args.get("limit")
    if limit is not None:
        out = out[:int(_p(parser, limit))]
    return out


_EXTRA_OPERATORS = {
    "$convert": _op_convert,
    "$toString": _simple(_to_string),
    "$toInt": _simple(lambda v: _convert_value(v, "int")),
    "$toLong": _simple(lambda v: _convert_value(v, "long")),
    "$toDouble": _simple(_to_double),
    "$toDecimal": _simple(_to_double),
    "$toDate": _simple(_to_date),
    "$toBool": _simple(_to_bool),
    "$toObjectId": _simple(_to_object_id),
    "$type": _op_type,
    "$substr": _substr_bytes,
    "$substrBytes": _substr_bytes,
    "$reduce": _op_reduce,
    "$mergeObjects": _op_merge_objects,
    "$dateFromString": _op_date_from_string,
    "$dateToString": _op_date_to_string,
    "$trim": _trim_factory("both"),
    "$ltrim": _trim_factory("left"),
    "$rtrim": _trim_factory("right"),
    "$indexOfArray": _op_index_of_array,
    "$toLower": _case(str.lower),
    "$toUpper": _case(str.upper),
    "$concat": _op_concat,
    "$strLenCP": _op_str_len_cp,
    "$strLenBytes": _op_str_len_bytes,
    "$add": _op_add,
    "$subtract": _op_subtract,
    "$multiply": _op_multiply,
    "$divide": _op_divide,
    "$round": _op_round,
    "$mod": _op_mod,
    "$abs": _unary_math(abs),
    "$sum": _expr_accumulator(_acc_sum),
    "$avg": _expr_accumulator(_acc_avg),
    "$max": _expr_accumulator(_acc_max),
    "$min": _expr_accumulator(_acc_min),
    "$eq": _comparison(lambda c: c == 0),
    "$ne": _comparison(lambda c: c != 0),
    "$gt": _comparison(lambda c: c > 0),
    "$gte": _comparison(lambda c: c >= 0),
    "$lt": _comparison(lambda c: c < 0),
    "$lte": _comparison(lambda c: c <= 0),
    "$cmp": _comparison(lambda c: c),
    "$filter": _op_filter,
    "$first": _expr_first_last(0),
    "$last": _expr_first_last(-1),
}


def _patch_parser():
    orig_parse = aggregate._Parser.parse

    def parse(self, expression):
        if isinstance(expression, dict) and len(expression) == 1:
            for k in expression:
                h = _EXTRA_OPERATORS.get(k)
                if h is not None:
                    return h(self, expression[k])
        return orig_parse(self, expression)

    aggregate._Parser.parse = parse


# ------------------------------------------------------------------- $lookup pipeline
_SCALARS = (str, int, float, type(None), ObjectId, datetime.datetime, bool)


def _literal(value):
    if isinstance(value, str) and value.startswith("$"):
        return {"$literal": value}
    if isinstance(value, (dict, list)):
        return {"$literal": value}
    return value


def _substitute(node, variables):
    """Replace ``$$var`` / ``$$var.path`` references to ``let`` variables with literals."""
    if isinstance(node, str) and node.startswith("$$"):
        name, _, rest = node[2:].partition(".")
        if name in variables:
            val = variables[name]
            if rest:
                try:
                    val = helpers.get_value_by_dot(val, rest, can_generate_array=True) \
                        if isinstance(val, (dict, list)) else None
                except KeyError:
                    val = None
            return _literal(val)
        return node
    if isinstance(node, dict):
        return {k: _substitute(v, variables) for k, v in node.items()}
    if isinstance(node, list):
        return [_substitute(v, variables) for v in node]
    return node


def _literal_value(x):
    if isinstance(x, dict) and list(x.keys()) == ["$literal"]:
        x = x["$literal"]
        return (True, x) if isinstance(x, _SCALARS) else (False, None)
    if isinstance(x, str) and x.startswith("$"):
        return False, None
    if isinstance(x, _SCALARS):
        return True, x
    return False, None


def _expr_prefilter(expr):
    """Necessary equality conditions implied by an ``$expr`` (to narrow candidates)."""
    out = {}
    if not isinstance(expr, dict) or len(expr) != 1:
        return out
    (op, args), = expr.items()
    if op == "$and" and isinstance(args, list):
        for sub in args:
            for k, v in _expr_prefilter(sub).items():
                out.setdefault(k, v)
        return out
    if op == "$eq" and isinstance(args, list) and len(args) == 2:
        a, b = args
        for field, other in ((a, b), (b, a)):
            if isinstance(field, str) and field.startswith("$") and not field.startswith("$$"):
                ok, val = _literal_value(other)
                if ok and val is not None:
                    out[field[1:]] = val
                    break
    return out


def _with_prefilter(pipeline):
    if not pipeline or list(pipeline[0].keys()) != ["$match"]:
        return pipeline
    match = pipeline[0]["$match"]
    if not isinstance(match, dict) or "$expr" not in match:
        return pipeline
    pre = _expr_prefilter(match["$expr"])
    pre = {k: v for k, v in pre.items() if k not in match}
    if not pre:
        return pipeline
    return [{"$match": dict(pre, **match)}] + list(pipeline[1:])


def _handle_lookup_stage(in_collection, database, options):
    if "pipeline" not in options:
        return _orig_lookup(in_collection, database, options)
    foreign = database.get_collection(options["from"])
    let = options.get("let") or {}
    pipeline = options["pipeline"]
    as_field = options["as"]
    local_field = options.get("localField")
    foreign_field = options.get("foreignField")
    cache = {}
    agg = getattr(foreign, "aggregate_list", None)
    for doc in in_collection:
        variables = {}
        for k, expr in let.items():
            try:
                variables[k] = aggregate._parse_expression(expr, doc, ignore_missing_keys=True)
            except KeyError:
                variables[k] = None
        sub = _substitute(pipeline, variables)
        if local_field and foreign_field:
            try:
                lv = helpers.get_value_by_dot(doc, local_field)
            except KeyError:
                lv = None
            cond = {"$in": lv} if isinstance(lv, list) else lv
            sub = [{"$match": {foreign_field: cond}}] + list(sub)
        sub = _with_prefilter(sub)
        try:
            ck = bson.encode({"p": sub})
        except Exception:  # noqa: BLE001 - unencodable values: no caching
            ck = None
        if ck is not None and ck in cache:
            doc[as_field] = copy.deepcopy(cache[ck])
            continue
        if agg is not None:
            result = agg(sub)
        else:
            result = list(foreign.aggregate(sub))
        if ck is not None:
            cache[ck] = result
            result = copy.deepcopy(result)
        doc[as_field] = result
    return in_collection


_orig_lookup = aggregate._handle_lookup_stage


# --------------------------------------------------------------------------- stages
def _handle_replace_with(in_collection, database, options):
    return aggregate._handle_replace_root_stage(in_collection, database, {"newRoot": options})


def _handle_unset_stage(in_collection, database, options):
    fields = [options] if isinstance(options, str) else list(options)
    out = []
    for doc in in_collection:
        doc = copy.deepcopy(doc)
        for f in fields:
            try:
                helpers.delete_value_by_dot(doc, f)
            except (KeyError, TypeError):
                pass
        out.append(doc)
    return out


def _handle_sort_by_count(in_collection, database, options):
    grouped = aggregate._handle_group_stage(in_collection, database,
                                            {"_id": options, "count": {"$sum": 1}})
    return aggregate._handle_sort_stage(grouped, database, {"count": -1})


def apply():
    global _APPLIED
    if _APPLIED:
        return
    _APPLIED = True
    _patch_type_conversions()
    _patch_parser()
    aggregate._accumulate_group = _accumulate_group
    aggregate._PIPELINE_HANDLERS["$lookup"] = _handle_lookup_stage
    aggregate._PIPELINE_HANDLERS["$replaceWith"] = _handle_replace_with
    aggregate._PIPELINE_HANDLERS["$unset"] = _handle_unset_stage
    aggregate._PIPELINE_HANDLERS["$sortByCount"] = _handle_sort_by_count
