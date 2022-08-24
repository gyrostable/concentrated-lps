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
    return (to_decimal(x) * 10 ** decimals).floor()


def unscale_scalar(x: DecimalLike, decimals: int = 18) -> QuantizedDecimal:
    return to_decimal(x) / 10 ** decimals


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


def qdecimals(
    *args, allow_nan=False, allow_infinity=False, **kwargs
) -> st.SearchStrategy[QuantizedDecimal]:
    return st.decimals(
        *args, allow_nan=allow_nan, allow_infinity=allow_infinity, **kwargs
    ).map(QuantizedDecimal)
