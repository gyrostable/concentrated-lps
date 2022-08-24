from logging import warning
from typing import Iterable, List, Tuple

import numpy as np
from tests.support.quantized_decimal import QuantizedDecimal as D

_MAX_IN_RATIO = D("0.3")
_MAX_OUT_RATIO = D("0.3")

prec_convergence = D("1E-18")


def calculateInvariant(balances: Iterable[D], root3Alpha: D) -> D:
    (a, mb, mc, md) = calculateCubicTerms(balances, root3Alpha)
    return calculateCubic(a, mb, mc, md, root3Alpha, balances)


def calculateCubicTerms(balances: Iterable[D], root3Alpha: D) -> tuple[D, D, D, D]:
    x, y, z = balances
    a = D(1) - root3Alpha * root3Alpha * root3Alpha
    b = -(x + y + z) * root3Alpha * root3Alpha
    c = -(x * y + y * z + z * x) * root3Alpha
    d = -x * y * z
    assert a > 0 and b < 0 and c <= 0 and d <= 0
    return a, -b, -c, -d


# Doesn't completely mirror _calculateCubic in GyroThreeMath.sol
def calculateCubic(
    a: D, mb: D, mc: D, md: D, root3Alpha: D, balances: Iterable[D]
) -> D:
    invariant, log_steps = calculateInvariantNewton(
        a, -mb, -mc, -md, root3Alpha, balances
    )
    return invariant


def calculateInvariantNewton(
    a: D, b: D, c: D, d: D, alpha1: D, balances: Iterable[D]
) -> tuple[D, list]:
    log = []
    # def test_calc_out_given_in(gyro_three_math_testing, amount_in, balances, root_three_alpha):

    #     if amount_in > to_decimal('0.3') * (balances[0]):
    #         return

    #     if faulty_params(balances, root_three_alpha):
    #         return

    #     invariant = math_implementation.calculateInvariant(
    #         to_decimal(balances), to_decimal(root_three_alpha))

    #     virtual_param_in = math_implementation.calculateVirtualParameter0(
    #         to_decimal(invariant))
    x, y, z = balances

    lmin = -b / (a * 3) + (b ** 2 - a * c * 3).sqrt() / (
        a * 3
    )  # Sqrt is not gonna make a problem b/c all summands are positive.
    # ^ Local minimum, and also the global minimum of f among l > 0; towards a starting point
    l0 = lmin * D(
        "1.5"
    )  # 1.5 is a magic number, experimentally found; it seems this becomes exact for alpha -> 1.

    l = l0
    delta = D(1)
    delta_pre = None  # Not really used, only to flag the first iteration.

    while True:
        # delta = f(l)/f'(l)
        f_l = a * l ** 3 + b * l ** 2 + c * l + d

        # Compute derived values for comparison:
        # TESTING only; could base the exit condition on this if I really wanted
        gamma = l ** 2 / ((x + l * alpha1) * (y + l * alpha1))  # 3√(px py)
        px = (z + l * alpha1) / (x + l * alpha1)
        py = (z + l * alpha1) / (y + l * alpha1)
        x1 = l * (gamma / px - alpha1)
        y1 = l * (gamma / py - alpha1)
        z1 = l * (gamma - alpha1)

        log.append(dict(l=l, delta=delta, f_l=f_l, dx=x1 - x, dy=y1 - y, dz=z1 - z))

        # if abs(f_l) < prec_convergence:
        if (
            abs(x - x1) < prec_convergence
            and abs(y - y1) < prec_convergence
            and abs(z - z1) < prec_convergence
        ):
            return l, log
        df_l = a * 3 * l ** 2 + b * 2 * l + c
        delta = f_l / df_l

        # delta==0 can happen with poor numerical precision! In this case, this is all we can get.
        if delta_pre is not None and (delta == 0 or f_l < 0):
            warning("Early exit due to numerical instability")
            return l, log

        l -= delta
        delta_pre = delta


def liquidityInvariantUpdate(
    balances: List[D],
    root3Alpha: D,
    lastInvariant: D,
    deltaBalances: List[D],
    isIncreaseLiq: bool,
) -> D:
    indices = maxOtherBalances(balances)
    # virtual offsets
    virtualOffset = lastInvariant * root3Alpha
    # cube root of p_x p_y
    cbrtPxPy = calculateCbrtPrice(lastInvariant, balances[indices[0]] + virtualOffset)
    diffInvariant = deltaBalances[indices[0]] / (cbrtPxPy - root3Alpha)

    if isIncreaseLiq == True:
        invariant = lastInvariant + diffInvariant
    else:
        invariant = lastInvariant - diffInvariant
    return invariant


def maxOtherBalances(balances: List[D]) -> List[int]:
    indices = [0, 0, 0]
    if balances[0] >= balances[1]:
        if balances[0] >= balances[2]:
            indices[0] = 0
            indices[1] = 1
            indices[2] = 2
        else:
            indices[0] = 2
            indices[1] = 0
            indices[2] = 1
    else:
        if balances[1] >= balances[2]:
            indices[0] = 1
            indices[1] = 0
            indices[2] = 2
        else:
            indices[0] = 2
            indices[1] = 1
            indices[2] = 0

    return indices


def calcOutGivenIn(balanceIn: D, balanceOut: D, amountIn: D, virtualOffset: D) -> D:
    assert amountIn <= balanceIn * _MAX_IN_RATIO
    virtIn = balanceIn + virtualOffset
    virtOut = balanceOut + virtualOffset
    # minus b/c amountOut is negative
    amountOut = -(virtIn * virtOut / (virtIn + amountIn) - virtOut)
    assert amountOut <= balanceOut * _MAX_OUT_RATIO
    return amountOut


def calcInGivenOut(balanceIn: D, balanceOut: D, amountOut: D, virtualOffset: D) -> D:
    assert amountOut <= balanceOut * _MAX_OUT_RATIO
    virtIn = balanceIn + virtualOffset
    virtOut = balanceOut + virtualOffset
    amountIn = virtIn * virtOut / (virtOut - amountOut) - virtIn
    assert amountIn <= balanceIn * _MAX_IN_RATIO
    return amountIn


def calcAllTokensInGivenExactBptOut(
    balances: Iterable[D], bptAmountOut: D, totalBPT: D
) -> Tuple[D, D, D]:
    bptRatio = bptAmountOut / totalBPT
    x, y, z = balances
    return x * bptRatio, y * bptRatio, z * bptRatio


def calcTokensOutGivenExactBptIn(
    balances: Iterable[D], bptAmountIn: D, totalBPT: D
) -> Tuple[D, D, D]:
    bptRatio = bptAmountIn / totalBPT
    x, y, z = balances
    return x * bptRatio, y * bptRatio, z * bptRatio


def calcProtocolFees(
    previousInvariant: D,
    currentInvariant: D,
    currentBptSupply: D,
    protocolSwapFeePerc: D,
    protocolFeeGyroPortion: D,
) -> Tuple[D, D]:
    if currentInvariant <= previousInvariant:
        return D(0), D(0)

    diffInvariant = protocolSwapFeePerc * (currentInvariant - previousInvariant)
    numerator = diffInvariant * currentBptSupply
    denominator = currentInvariant - diffInvariant
    deltaS = numerator / denominator

    gyroFees = protocolFeeGyroPortion * deltaS
    balancerFees = deltaS - gyroFees
    return gyroFees, balancerFees


def calculateCbrtPrice(invariant: D, virtualZ: D) -> D:
    return virtualZ / invariant
