import decimal
import operator

import hypothesis.strategies as st
from hypothesis import example, settings
from brownie.test import given

from tests.support.quantized_decimal import QuantizedDecimal as D
from tests.support.utils import scale, qdecimals
from math import floor, log2

operators = ["add", "sub", "mul", "truediv"]

MAX_UINT = 2**256 - 1


def unscale(x, decimals=18):
    return x / 10**decimals


@given(
    a=st.decimals(min_value=0, allow_nan=False, allow_infinity=False),
    b=st.decimals(min_value=0, allow_nan=False, allow_infinity=False),
    ops=st.lists(st.sampled_from(operators), min_size=1),
)
def test_decimal_behavior(math_testing, a, b, ops):
    a, b = D(a), D(b)
    for op_name in ops:
        op = getattr(operator, op_name)
        if b > a and op_name == "sub":
            b = a
        if b == 0 and op_name == "truediv":
            b = D(1)
        try:
            if (
                (op_name == "mul" and a * b > unscale(MAX_UINT, 36))
                or (op_name == "add" and a + b > unscale(MAX_UINT, 18))
                or (op_name == "div" and a > unscale(MAX_UINT, 18))
            ):
                a = D(1)
        # failed to quantize because op(a, b) is too large
        except decimal.InvalidOperation:
            a = D(1)
        solidity_b = getattr(math_testing, op_name)(scale(a), scale(b))
        a, b = b, op(a, b)
        assert scale(b) == solidity_b

@settings(max_examples=1_000)
@given(a=qdecimals(0))
@example(a=D(1))
@example(a=D(0))
@example(a=D('1E-18'))
def test_sqrt(math_testing, a):
    # Note that errors are relatively large, with, e.g., 5 decimals for sqrt(1)
    res_math = a.sqrt()
    res_sol = math_testing.sqrt(scale(a))
    # Absolute error tolerated in the last decimal + the default relative error.
    assert int(res_sol) == scale(res_math).approxed(abs=D("5"), rel=D("5e-14"))


@given(a=qdecimals(0).filter(lambda a: a > 0))
@example(a=D(1))
def test_sqrtNewton(math_testing, a):
    res_math = a.sqrt()
    res_sol = math_testing.sqrtNewton(scale(a), 5)

    assert int(res_sol) == scale(res_math).approxed(abs=D("5"))


@given(a=qdecimals(0).filter(lambda a: a > 0))
@example(a=D(1))
def test_sqrtNewtonInitialGuess(math_testing, a):

    if a >= 1:
        assert 2 ** (floor(log2(a) / 2)) == unscale(
            math_testing.sqrtNewtonInitialGuess(scale(a))
        )
    else:
        assert 1 == unscale(math_testing.sqrtNewtonInitialGuess(scale(a)))
