from operator import add, sub
from typing import Iterable

import pytest
from tests.support.quantized_decimal import QuantizedDecimal as D

_MAX_IN_RATIO = D("0.3")
_MAX_OUT_RATIO = D("0.3")

prec_convergence = D("1E-18")


def squareRoot(input: D):
    return input.sqrt()


def calculateInvariant(balances: Iterable[D], sqrtAlpha: D, sqrtBeta: D) -> D:
    (a, mb, b_square, mc) = calculateQuadraticTerms(balances, sqrtAlpha, sqrtBeta)
    return calculateQuadraticSpecial(a, mb, b_square, mc)


def calculateQuadraticTerms(
    balances: Iterable[D], sqrtAlpha: D, sqrtBeta: D
) -> tuple[D, D, D, D]:
    x, y = balances
    a = 1 - sqrtAlpha / sqrtBeta
    b = -(y / sqrtBeta + x * sqrtAlpha)
    c = -x * y
    b_square = (
        (x * x) * sqrtAlpha * sqrtAlpha
        + (x * y) * 2 * sqrtAlpha / sqrtBeta
        + (y * y) / (sqrtBeta.mul_up(sqrtBeta))
    )
    return a, -b, b_square, -c


def calculateQuadratic(a: D, b: D, b_square: D, c: D) -> D:
    """
    This function is not a complete match to _calculateQuadratic in GyroTwoMath.sol, this is just general quadratic formula
    This function should match _calculateQuadratic in GyroTwoMath.sol in both inputs and outputs
    when a > 0, b < 0, and c < 0
    """
    assert float(b * b) == pytest.approx(float(b_square))
    assert b_square - c * 4 * a >= 0
    numerator = -b + (b_square - c * 4 * a).sqrt()
    denominator = a.mul_up(D(2))
    return numerator / denominator


# This function should match _calculateQuadratic in GyroTwoMath.sol in both inputs and outputs
# when a > 0, b < 0, and c < 0


def calculateQuadraticSpecial(a: D, mb: D, b_square: D, mc: D) -> D:
    assert a > 0 and mb > 0 and mc >= 0
    return calculateQuadratic(a, -mb, b_square, -mc)


def liquidityInvariantUpdate_fromscratch(
    balances: Iterable[D],
    sqrtAlpha: D,
    sqrtBeta: D,
    lastInvariant: D,
    deltaBalances: Iterable[D],
    isIncreaseLiq: bool,
) -> D:
    """Ignore lastInvariant, just recompute everything from scratch. For testing."""
    op = add if isIncreaseLiq else sub
    return calculateInvariant(map(op, balances, deltaBalances), sqrtAlpha, sqrtBeta)


def calcOutGivenIn(
    balanceIn: D, balanceOut: D, amountIn: D, virtualParamIn: D, virtualParamOut: D
) -> D:
    assert amountIn <= balanceIn * _MAX_IN_RATIO
    virtIn = balanceIn + virtualParamIn
    virtOut = balanceOut + virtualParamOut
    amountOut = virtOut.mul_down(amountIn).div_up(virtIn + amountIn)
    return amountOut


def calcInGivenOut(
    balanceIn: D, balanceOut: D, amountOut: D, virtualParamIn: D, virtualParamOut: D
) -> D:
    assert amountOut <= balanceOut * _MAX_OUT_RATIO
    virtIn = balanceIn + virtualParamIn
    virtOut = balanceOut + virtualParamOut
    amountIn = virtIn.mul_up(amountOut).div_up(virtOut - amountOut)
    return amountIn


def calculateVirtualParameter0(invariant: D, sqrtBeta: D) -> D:
    return invariant / sqrtBeta


def calculateVirtualParameter1(invariant: D, sqrtAlpha: D) -> D:
    return invariant * sqrtAlpha
