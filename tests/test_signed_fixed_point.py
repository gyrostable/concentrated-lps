import decimal
import operator

import hypothesis.strategies as st
from brownie.test import given
from brownie import reverts
from hypothesis import settings, note

from tests.support.quantized_decimal import QuantizedDecimal as D
from tests.support.utils import scale, unscale

operators = ["add", "sub", "mul", "truediv"]

MIN_INT = -(2**255)
MAX_INT = 2**255 - 1


@given(
    a=st.decimals(allow_nan=False, allow_infinity=False),
    b=st.decimals(allow_nan=False, allow_infinity=False),
    op_name=st.sampled_from(operators),
)
def test_decimal_behavior(signed_math_testing, a, b, op_name):
    a, b = D(a), D(b)

    op = getattr(operator, op_name)
    if b == 0 and op_name == "truediv":
        b = D(1)
    try:
        c = op(a, b)
        if (
            (
                op_name == "mul"
                and (a * b > D(MAX_INT // 10**36) or a * b < D(MIN_INT // 10**36))
            )
            or (
                op_name == "add"
                and (a + b > D(MAX_INT // 10**18) or a + b < D(MIN_INT // 10**18))
            )
            or (
                op_name == "div"
                and (a > D(MAX_INT // 10**18) or a < D(MIN_INT // 10**18))
            )
        ):
            raise decimal.InvalidOperation()
    except decimal.InvalidOperation:
        with reverts():
            getattr(signed_math_testing, op_name)(scale(a), scale(b))
        return
    solidity_c = getattr(signed_math_testing, op_name)(scale(a), scale(b))
    note(f"solidity: {solidity_c}")
    assert c.raw * 10**18 == solidity_c
