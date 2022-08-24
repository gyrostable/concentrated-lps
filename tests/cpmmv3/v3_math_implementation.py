from logging import warning
from math import sqrt
from typing import Iterable, List, Tuple, Callable

from tests.support.utils import scale, to_decimal, unscale, qdecimals

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

    # Lower-order special case
    # if d == 0:
    #     # ac = c - c * alpha1 * alpha1 * alpha1
    #     ac = a * c
    #     l = (-b + (b**2 - ac * 4).sqrt()) / (2 * a)
    #     return l, log


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
        l3 = l**3
        l2 = l**2

        # Ordering optimization. This is crucial to get us the final couple decimals precision.
        # f_l = a * l3 + b * l2 + c * l + d
        f_l = l3 - l3 * alpha1 * alpha1 * alpha1 + l2 * b + c * l + d

        # Compute derived values for comparison:
        # (slightly more involved exit condition here)
        dx, dy, dz = invariantErrorsInAssets(l, balances, alpha1)

        log.append(dict(l=l, delta=delta, f_l=f_l, dx=dx, dy=dy, dz=dz))

        # if abs(f_l) < prec_convergence:
        if (
            abs(dx) < prec_convergence
            and abs(dy) < prec_convergence
            and abs(dz) < prec_convergence
        ):
            return l, log

        # Ordering optimization. Doesn't seem to matter as much as the first one above.
        # df_l = a * 3 * l ** 2 + b * 2 * l + c
        df_l = 3 * l2 - 3 * l2 * alpha1 * alpha1 * alpha1 + l * b * 2 + c
        delta = - f_l / df_l

        # delta==0 can happen with poor numerical precision! In this case, this is all we can get.
        if delta_pre is not None and (delta == 0 or f_l < 0):
            # warning("Early exit due to numerical instability")
            return l, log

        l += delta
        delta_pre = delta


def invariantErrorsInAssets(l, balances: Iterable, root3Alpha):
    """Error of l measured in assets. This is ONE way to do it.

    We have invariantErrorsInAssets(l, ...) == 0 iff l is the correct invariant. But this scales differently.

    Type agnostic: Pass D to get D calculations or float to get float calculations."""
    x, y, z = balances

    gamma = l ** 2 / ((x + l * root3Alpha) * (y + l * root3Alpha))  # 3√(px py)
    px = (z + l * root3Alpha) / (x + l * root3Alpha)
    py = (z + l * root3Alpha) / (y + l * root3Alpha)
    x1 = l * (gamma / px - root3Alpha)
    y1 = l * (gamma / py - root3Alpha)
    z1 = l * (gamma - root3Alpha)

    return x1 - x, y1 - y, z1 - z


def invariantFunctionsFloat(
    balances: Iterable[D], root3Alpha: D
) -> tuple[Callable, Callable]:
    a, mb, mc, md = calculateCubicTermsFloat(map(float, balances), float(root3Alpha))

    def f(l):
        # res = a * l**3 - mb * l**2 - mc * l - md
        # To prevent catastrophic elimination. Note this makes a BIG difference ito f values, but not ito computed l
        # values.
        res = ((a * l - mb) * l - mc) * l - md
        # print(f" f({l})".ljust(22) + f"= {res}")  # DEBUG OUTPUT
        return res

    def df(l):
        # res = 3 * a * l**2 - 2 * mb * l - mc
        res = (3 * a * l - 2 * mb) * l - mc
        # print(f"df({l})".ljust(22) + f"= {res}")  # DEBUG OUTPUT
        return res

    return f, df


def calculateInvariantAltFloatWithInfo(balances: Iterable[D], root3Alpha: D):
    """Alternative implementation of the invariant calculation that can't be done in Solidity. Should match
    calculateInvariant() to a high degree of accuracy.

    Version that also returns debug info.

    Don't rely on anything but the 'root' component!"""
    from scipy.optimize import root_scalar

    f, df = invariantFunctionsFloat(balances, root3Alpha)
    a, mb, mc, md = calculateCubicTermsFloat(map(float, balances), float(root3Alpha))

    # See CPMMV writeup, appendix A.1
    l_m = mb / (3 * a)
    l_plus = l_m + sqrt(l_m ** 2 + mc)
    l_0 = 1.5 * l_plus

    res = root_scalar(f, fprime=df, x0=l_0, rtol=1e-18, xtol=1e-18)

    return dict(root=res.root, f=f, root_results=res, l_0=l_0)


def calculateInvariantAltFloat(balances: Iterable[D], root3Alpha: D) -> float:
    return calculateInvariantAltFloatWithInfo(balances, root3Alpha)["root"]


def calculateCubicTermsFloat(
    balances: Iterable[float], root3Alpha: float
) -> tuple[float, float, float, float]:
    x, y, z = balances
    a = 1 - root3Alpha * root3Alpha * root3Alpha
    b = -(x + y + z) * root3Alpha * root3Alpha
    c = -(x * y + y * z + z * x) * root3Alpha
    d = -x * y * z
    assert a > 0 and b < 0 and c <= 0 and d <= 0
    return a, -b, -c, -d


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
    amountOut = virtOut.mul_down(amountIn).div_up(virtIn + amountIn)
    # assert amountOut <= balanceOut * _MAX_OUT_RATIO
    return amountOut


def calcInGivenOut(balanceIn: D, balanceOut: D, amountOut: D, virtualOffset: D) -> D:
    assert amountOut <= balanceOut * _MAX_OUT_RATIO
    virtIn = balanceIn + virtualOffset
    virtOut = balanceOut + virtualOffset
    amountIn = virtIn.mul_up(amountOut).div_up(virtOut - amountOut)
    # assert amountIn <= balanceIn * _MAX_IN_RATIO
    return amountIn


def calcNewtonDelta(a: D, mb: D, mc: D, md: D, alpha1: D, l: D) -> tuple[D, bool]:
    a, mb, mc, md, l = map(to_decimal, (a, mb, mc, md, l))

    # Copied from the Newton iteration.

    b, c, d = -mb, -mc, -md

    l3 = l ** 3
    l2 = l ** 2
    f_l = l3 - l3 * alpha1 * alpha1 * alpha1 + l2 * b + c * l + d
    df_l = 3 * l2 - 3 * l2 * alpha1 * alpha1 * alpha1 + l * b * 2 + c
    delta = - f_l / df_l

    return abs(delta), delta >= 0


def calcNewtonDeltaDown(a: D, mb: D, mc: D, md: D, rootEst: D) -> tuple[D, bool]:
    (a, mb, mc, md, rootEst) = (D(a), D(mb), D(mc), D(md), D(rootEst))
    # dfRootEst = rootEst * rootEst * (D(3) * a) - rootEst.mul_up(D(2) * mb) - mc
    # deltaMinus = rootEst.mul_up(rootEst).mul_up(rootEst).mul_up(a).div_up(dfRootEst)
    # deltaPlus = (rootEst * rootEst * mb + rootEst * mc) / dfRootEst + md / dfRootEst
    dfRootEst = rootEst.mul_up(rootEst).mul_up(D(3) * a) - rootEst.mul_down(D(2) * mb) - mc
    deltaMinus = rootEst.mul_down(rootEst).mul_down(rootEst).mul_down(a).div_down(dfRootEst)
    deltaPlus = (rootEst.mul_up(rootEst).mul_up(mb) + rootEst.mul_up(mc)).div_up(dfRootEst) + md.div_up(dfRootEst)

    # DEBUG
    print(f"df        = {dfRootEst}")
    print(f"deltaPlus = {deltaPlus}")
    print(f"deltaMinus= {deltaMinus}")

    if deltaPlus >= deltaMinus:
        deltaAbs = deltaPlus - deltaMinus
        deltaIsPos = True
    else:
        deltaAbs = deltaMinus - deltaPlus
        deltaIsPos = False
    return deltaAbs, deltaIsPos



def calcNewtonDelta1(a: D, mb: D, mc: D, md: D, rootEst: D) -> tuple[D, bool]:
    """Alternative implementation with slightly different rounding behavior."""
    l = rootEst
    # Signs: "minus" refers to the delta, not to f(l)!
    f_l_minus = a * l ** 3
    f_l_plus = mb * l ** 2 + mc * l + md
    f_l = f_l_minus - f_l_plus
    df_l = a * 3 * l ** 2 - mb * 2 * l - mc
    print(f"f_l = {f_l}")
    print(f"df_l = {df_l}")
    print(f"f_l_plus / df_l = {f_l_plus / df_l}")
    print(f"f_l_minus / df_l = {f_l_minus / df_l}")
    delta = (f_l_plus - f_l_minus) / df_l
    return abs(delta), delta >= 0


def finalIteration(a: D, mb: D, mc: D, md: D, rootEst: D) -> tuple[D, bool]:
    (a, mb, mc, md, rootEst) = (D(a), D(mb), D(mc), D(md), D(rootEst))
    if isInvariantUnderestimated(a, mb, mc, md, rootEst):
        return (rootEst, True)
    else:
        (deltaAbs, deltaIsPos) = calcNewtonDelta(a, mb, mc, md, rootEst)
        step = rootEst.mul_up(unscale(D("1e4")))
        if step <= deltaAbs:
            step = deltaAbs
        rootEst = rootEst - step
        return (rootEst, isInvariantUnderestimated(a, mb, mc, md, rootEst))


def isInvariantUnderestimated(a: D, mb: D, mc: D, md: D, L: D) -> bool:
    (a, mb, mc, md, L) = (D(a), D(mb), D(mc), D(md), D(L))
    return L.mul_up(L).mul_up(L).mul_up(a) - L * L * mb - L * mc - md <= 0
