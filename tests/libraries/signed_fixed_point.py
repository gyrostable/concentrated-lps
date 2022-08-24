from typing import Iterable

from tests.support.quantized_decimal import QuantizedDecimal as D


def add_mag(a: D, b: D) -> D:
    if a > 0:
        return a + b
    else:
        return a - b


def mul_array_up(inputs: Iterable[D]) -> D:
    sign = 1
    for i in inputs:
        if i < 0:
            sign = -sign

    prod = inputs[0]
    if sign > 0:
        for i in inputs[1:]:
            prod = prod.mul_up(i)
    else:
        for i in inputs[1:]:
            prod = prod * i
    return prod


def mul_array_down(inputs: Iterable[D]) -> D:
    sign = 1
    for i in inputs:
        if i < 0:
            sign = -sign

    prod = inputs[0]
    if sign < 0:
        for i in inputs[1:]:
            prod = prod.mul_up(i)
    else:
        for i in inputs[1:]:
            prod = prod * i
    return prod


def mul_array(inputs: Iterable[D], round_up: bool) -> D:
    if round_up:
        return mul_array_up(inputs)
    else:
        return mul_array_down(inputs)
