import decimal
import operator

import hypothesis.strategies as st
from brownie.test import given

from tests.support.quantized_decimal import QuantizedDecimal
from tests.support.utils import scale

operators = ["add", "sub", "mul", "truediv"]

MAX_UINT = 2 ** 256 - 1


def unscale(x, decimals=18):
    return x / 10 ** decimals


@given(
    a=st.decimals(min_value=0, allow_nan=False, allow_infinity=False),
    b=st.decimals(min_value=0, allow_nan=False, allow_infinity=False),
    ops=st.lists(st.sampled_from(operators), min_size=1),
)
def test_decimal_behavior(math_testing, a, b, ops):
    a, b = QuantizedDecimal(a), QuantizedDecimal(b)
    for op_name in ops:
        op = getattr(operator, op_name)
        if b > a and op_name == "sub":
            b = a
        if b == 0 and op_name == "truediv":
            b = QuantizedDecimal(1)
        try:
            if (
                (op_name == "mul" and a * b > unscale(MAX_UINT, 36))
                or (op_name == "add" and a + b > unscale(MAX_UINT, 18))
                or (op_name == "div" and a > unscale(MAX_UINT, 18))
            ):
                a = QuantizedDecimal(1)
        # failed to quantize because op(a, b) is too large
        except decimal.InvalidOperation:
            a = QuantizedDecimal(1)
        solidity_b = getattr(math_testing, op_name)(scale(a), scale(b))
        a, b = b, op(a, b)
        assert scale(b) == solidity_b
