from operator import add, sub
from typing import Iterable

from tests.support.quantized_decimal import QuantizedDecimal as D

_MAX_IN_RATIO = D("0.3")
_MAX_OUT_RATIO = D("0.3")

prec_convergence = D("1E-18")


def squareRoot(input: D):
    return input.sqrt()


def calculateInvariant(balances: Iterable[D], sqrtAlpha: D, sqrtBeta: D) -> D:
    (a, mb, mc) = calculateQuadraticTerms(balances, sqrtAlpha, sqrtBeta)
    return calculateQuadraticSpecial(a, mb, mc)


def calculateQuadraticTerms(
    balances: Iterable[D], sqrtAlpha: D, sqrtBeta: D
) -> tuple[D, D, D]:
    x, y = balances
    a = 1 - sqrtAlpha / sqrtBeta
    b = -(y / sqrtBeta + x * sqrtAlpha)
    c = -x * y
    return a, -b, -c


def calculateQuadratic(a: D, b: D, c: D) -> D:
    """
    This function is not a complete match to _calculateQuadratic in GyroTwoMath.sol, this is just general quadratic formula
    This function should match _calculateQuadratic in GyroTwoMath.sol in both inputs and outputs
    when a > 0, b < 0, and c < 0
    """
    assert b * b - 4 * a * c >= 0
    numerator = -b + (b * b - 4 * a * c).sqrt()
    denominator = a * 2
    return numerator / denominator


# This function should match _calculateQuadratic in GyroTwoMath.sol in both inputs and outputs
# when a > 0, b < 0, and c < 0


def calculateQuadraticSpecial(a: D, mb: D, mc: D) -> D:
    assert a > 0 and mb > 0 and mc >= 0
    return calculateQuadratic(a, -mb, -mc)


def liquidityInvariantUpdate(
    balances: Iterable[D],
    sqrtAlpha: D,
    sqrtBeta: D,
    lastInvariant: D,
    deltaBalances: Iterable[D],
    isIncreaseLiq: bool,
) -> D:
    x, y = balances
    dx, dy = deltaBalances
    virtualX = x + lastInvariant / sqrtBeta
    sqrtPx = calculateSqrtPrice(lastInvariant, virtualX)
    if x <= y:
        diffInvariant = dy / (sqrtPx - sqrtAlpha)
    else:
        diffInvariant = dx / (1 / sqrtPx - 1 / sqrtBeta)
    if isIncreaseLiq == True:
        invariant = lastInvariant + diffInvariant
    else:
        invariant = lastInvariant - diffInvariant
    return invariant


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
    balanceIn: D,
    balanceOut: D,
    amountIn: D,
    virtualParamIn: D,
    virtualParamOut: D,
    currentInvariant: D,
) -> D:
    assert amountIn <= balanceIn * _MAX_IN_RATIO
    virtIn = balanceIn + virtualParamIn
    virtOut = balanceOut + virtualParamOut
    return virtOut - currentInvariant * currentInvariant / (virtIn + amountIn)


def calcInGivenOut(
    balanceIn: D,
    balanceOut: D,
    amountOut: D,
    virtualParamIn: D,
    virtualParamOut: D,
    currentInvariant: D,
) -> D:
    assert amountOut <= balanceOut * _MAX_OUT_RATIO
    virtOut = balanceOut + virtualParamOut
    virtIn = balanceIn + virtualParamIn
    return currentInvariant * currentInvariant / (virtOut - amountOut) - virtIn


def calcAllTokensInGivenExactBptOut(
    balances: Iterable[D], bptAmountOut: D, totalBPT: D
) -> tuple[D, D]:
    bptRatio = bptAmountOut / totalBPT
    x, y = balances
    return x * bptRatio, y * bptRatio


def calcTokensOutGivenExactBptIn(
    balances: Iterable[D], bptAmountIn: D, totalBPT: D
) -> tuple[D, D]:
    bptRatio = bptAmountIn / totalBPT
    x, y = balances
    return x * bptRatio, y * bptRatio


def calcProtocolFees(
    previousInvariant: D,
    currentInvariant: D,
    currentBptSupply: D,
    protocolSwapFeePerc: D,
    protocolFeeGyroPortion: D,
) -> tuple[D, D]:
    if currentInvariant <= previousInvariant:
        return D(0), D(0)

    if protocolSwapFeePerc == 0:
        return D(0), D(0)

    diffInvariant = protocolSwapFeePerc * (currentInvariant - previousInvariant)
    numerator = diffInvariant * currentBptSupply
    denominator = currentInvariant - diffInvariant
    deltaS = numerator / denominator

    gyroFees = protocolFeeGyroPortion * deltaS
    balancerFees = deltaS - gyroFees
    return gyroFees, balancerFees


def calculateVirtualParameter0(invariant: D, sqrtBeta: D) -> D:
    return invariant / sqrtBeta


def calculateVirtualParameter1(invariant: D, sqrtAlpha: D) -> D:
    return invariant * sqrtAlpha


def calculateSqrtPrice(invariant: D, virtualX: D) -> D:
    return invariant / virtualX
