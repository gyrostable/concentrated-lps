from decimal import Decimal
from typing import Iterable, List, Tuple, Union, overload, NamedTuple, Optional

from tests.support.quantized_decimal import DecimalLike, QuantizedDecimal

from hypothesis import strategies as st


def scalar_to_decimal(x: DecimalLike):
    assert isinstance(x, (Decimal, int, str, QuantizedDecimal))
    if isinstance(x, QuantizedDecimal):
        return x
    return QuantizedDecimal(x)


@overload
def to_decimal(x: DecimalLike) -> QuantizedDecimal:
    ...


@overload
def to_decimal(x: Iterable[DecimalLike]) -> List[QuantizedDecimal]:
    ...


def to_decimal(x):
    if isinstance(x, (list, tuple)):
        return [scalar_to_decimal(v) for v in x]
    return scalar_to_decimal(x)


def scale_scalar(x: DecimalLike, decimals: int = 18) -> QuantizedDecimal:
    return (to_decimal(x) * 10**decimals).floor()


def unscale_scalar(x: DecimalLike, decimals: int = 18) -> QuantizedDecimal:
    # This is necessary to support very large integers; otherwise, we get an error at
    # to_decimal(x) already.
    if isinstance(x, int):
        return (
            to_decimal(x // 10**decimals)
            + to_decimal(x % 10**decimals) / 10**decimals
        )
    return to_decimal(x) / 10**decimals


@overload
def scale(x: DecimalLike, decimals=...) -> QuantizedDecimal:
    ...


@overload
def scale(x: Iterable[DecimalLike], decimals=...) -> List[QuantizedDecimal]:
    ...


@overload
def scale(x: NamedTuple, decimals: Optional[int]) -> NamedTuple:
    ...


def isinstance_namedtuple(obj) -> bool:
    return (
        isinstance(obj, tuple) and hasattr(obj, "_asdict") and hasattr(obj, "_fields")
    )


def scale(x, decimals=18):
    if isinstance(x, (list, tuple)):
        return [scale(v, decimals) for v in x]
    if isinstance_namedtuple(x):
        return type(x)(*[scale(v, decimals) for v in x])
    return scale_scalar(x, decimals)


@overload
def unscale(x: DecimalLike, decimals=...) -> QuantizedDecimal:
    ...


@overload
def unscale(x: Iterable[DecimalLike], decimals=...) -> List[QuantizedDecimal]:
    ...


def unscale(x, decimals=18):
    if isinstance(x, (list, tuple)):
        return [unscale_scalar(v, decimals) for v in x]
    return unscale_scalar(x, decimals)


def approxed(x, abs=None, rel=None):
    if isinstance(x, (list, tuple)):
        return [approxed(v, abs, rel) for v in x]
    return to_decimal(x).approxed()


def apply_deep(x, f):
    # Order matters b/c named tuples are tuples.
    if isinstance_namedtuple(x):
        return type(x)(*[apply_deep(y, f) for y in x])
    if isinstance(x, (list, tuple)):
        return type(x)([apply_deep(y, f) for y in x])
    return f(x)


def qdecimals(
    min_value=None, max_value=None, allow_nan=False, allow_infinity=False, **kwargs
) -> st.SearchStrategy[QuantizedDecimal]:
    if isinstance(min_value, QuantizedDecimal):
        min_value = min_value.raw
    if isinstance(max_value, QuantizedDecimal):
        max_value = max_value.raw
    return st.decimals(
        min_value,
        max_value,
        allow_nan=allow_nan,
        allow_infinity=allow_infinity,
        **kwargs
    ).map(QuantizedDecimal)
