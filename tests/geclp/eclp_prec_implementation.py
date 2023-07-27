from operator import add, sub
from typing import Iterable, NamedTuple, Tuple

import pytest
from tests.support.quantized_decimal import QuantizedDecimal as D
from tests.support.quantized_decimal_38 import QuantizedDecimal as D2
from tests.support.quantized_decimal_100 import QuantizedDecimal as D3
from tests.libraries.signed_fixed_point import add_mag, mul_array

# from tests.support.types import ECLPMathDerivedParamsQD38, ECLPMathParamsQD
# from tests.support.utils import scale, unscale

_MAX_IN_RATIO = D("0.3")
_MAX_OUT_RATIO = D("0.3")


# Params = ECLPMathParamsQD
# DerivedParams = ECLPMathDerivedParamsQD38
class Params(NamedTuple):
    alpha: D
    beta: D
    c: D
    s: D
    l: D


class DerivedParams(NamedTuple):
    tauAlpha: Tuple[D2, D2]
    tauBeta: Tuple[D2, D2]
    u: D2
    v: D2
    w: D2
    z: D2
    dSq: D2
    # dAlpha: D2
    # dBeta: D2


class Vector2(NamedTuple):
    # Note: the types should really be "Any numeric type, but types have to match".
    x: D2
    y: D2

    # For compatibility with tuple representation
    def __getitem__(self, ix):
        if ix not in (0, 1):
            return KeyError(f"Only indices 0, 1 supported. Given: {ix}")
        return (self.x, self.y)[ix]


def virtualOffset0(p: Params, d: DerivedParams, r: Iterable[D]) -> D:
    termXp = D2(d.tauBeta[0]) / d.dSq
    if d.tauBeta[0] > 0:
        a = mulUpXpToNp(D(r[0]).mul_up(p.l).mul_up(p.c), termXp)
    else:
        a = mulUpXpToNp(D(r[1]) * p.l * p.c, termXp)
    termXp = D2(d.tauBeta[1]) / d.dSq
    a += mulUpXpToNp(D(r[0]).mul_up(p.s), termXp)
    return a


def virtualOffset1(p: Params, d: DerivedParams, r: Iterable[D]) -> D:
    termXp = D2(d.tauAlpha[0]) / d.dSq
    if d.tauAlpha[0] < 0:
        b = mulUpXpToNp(D(r[0]).mul_up(p.l).mul_up(p.s), -termXp)
    else:
        b = mulUpXpToNp(-D(r[1]) * p.l * p.s, termXp)
    termXp = D2(d.tauAlpha[1]) / d.dSq
    b += mulUpXpToNp(D(r[0]).mul_up(p.c), termXp)
    return b


def maxBalances0(p: Params, d: DerivedParams, r: Iterable[D]) -> D:
    termXp1 = (D2(d.tauBeta[0]) - d.tauAlpha[0]) / d.dSq
    termXp2 = (D2(d.tauBeta[1]) - d.tauAlpha[1]) / d.dSq
    xp = mulDownXpToNp(D(r[1]) * p.l * p.c, termXp1)
    termNp = D(r[1]) * p.s if termXp2 > 0 else D(r[0]).mul_up(p.s)
    xp += mulDownXpToNp(termNp, termXp2)
    return xp


def maxBalances1(p: Params, d: DerivedParams, r: Iterable[D]) -> D:
    termXp1 = (D2(d.tauBeta[0]) - d.tauAlpha[0]) / d.dSq
    termXp2 = (D2(d.tauAlpha[1]) - d.tauBeta[1]) / d.dSq
    yp = mulDownXpToNp(D(r[1]) * p.l * p.s, termXp1)
    termNp = D(r[1]) * p.c if termXp2 > 0 else D(r[0]).mul_up(p.c)
    yp += mulDownXpToNp(termNp, termXp2)
    return yp


def calcAtAChi(x: D, y: D, p: Params, d: DerivedParams) -> D:
    w, z, u, v, lam, dSq = (
        D2(d.w),
        D2(d.z),
        D2(d.u),
        D2(d.v),
        D2(D(p.l).raw),
        D2(d.dSq),
    )
    dSq2 = dSq * dSq

    termXp = (w / lam + z) / lam / dSq2
    termNp = D(x) * p.c - D(y) * p.s
    val = mulDownXpToNp(termNp, termXp)

    termNp = D(x) * p.l * p.s + D(y) * p.l * p.c
    termXp = u / dSq2
    val += mulDownXpToNp(termNp, termXp)

    termNp = D(x) * p.s + D(y) * p.c
    termXp = v / dSq2
    val += mulDownXpToNp(termNp, termXp)
    return val


def calcAChiAChi(p: Params, d: DerivedParams) -> D:
    w, z, u, v, lam, dSq = (
        D2(d.w),
        D2(d.z),
        D2(d.u),
        D2(d.v),
        D2(D(p.l).raw),
        D2(d.dSq),
    )
    termXp = ((2 * u) * v) / dSq / dSq / dSq
    val = mulUpXpToNp(p.l, termXp)

    termXp = (u + D2("1e-38")) * (u + D2("1e-38")) / dSq / dSq / dSq
    val += mulUpXpToNp(D(p.l).mul_up(p.l), termXp)

    val += D((v * v / dSq / dSq / dSq - D2("1e-38")).raw) + D("1e-18")

    termXp = w.div_up(lam) + z
    val += D((termXp * termXp / dSq / dSq / dSq - D2("1e-38")).raw) + D("1e-18")
    return val


def calcAChiAChiInXp(p: Params, d: DerivedParams) -> D2:
    w, z, u, v, lam, dSq = (
        D2(d.w),
        D2(d.z),
        D2(d.u),
        D2(d.v),
        D2(D(p.l).raw),
        D2(d.dSq),
    )
    dSq3 = dSq * dSq * dSq

    termXp = ((2 * u) * v) / dSq3
    val = lam.mul_up(termXp)

    termXp = (u + D2("1e-38")) * (u + D2("1e-38")) / dSq3
    val += termXp.mul_up(lam).mul_up(lam)

    val += v * v / dSq3

    termXp = w.div_up(lam) + z
    val += termXp * termXp / dSq3
    return val


def calcMinAtxAChiySqPlusAtxSq(x: D, y: D, p: Params, d: DerivedParams) -> D:
    w, z, u, v, lam, dSq = (
        D2(d.w),
        D2(d.z),
        D2(d.u),
        D2(d.v),
        D2(D(p.l).raw),
        D2(d.dSq),
    )
    termNp = D(x).mul_up(x).mul_up(p.c).mul_up(p.c) + D(y).mul_up(y).mul_up(p.s).mul_up(
        p.s
    )
    termNp -= x * y * (2 * p.c) * p.s

    termXp = u * u + (2 * u) * v / lam + v * v / lam / lam
    termXp = termXp / (dSq * dSq * dSq * dSq)
    val = mulDownXpToNp(-termNp, termXp)

    termXp = D2(1) / dSq
    termNp = (termNp - D("9e-18")) / p.l / p.l
    val = val + mulDownXpToNp(termNp, termXp)
    return val


def calc2AtxAtyAChixAChiy(x: D, y: D, p: Params, d: DerivedParams) -> D:
    w, z, u, v, lam, dSq = (
        D2(d.w),
        D2(d.z),
        D2(d.u),
        D2(d.v),
        D2(D(p.l).raw),
        D2(d.dSq),
    )
    xy = D(y) * (2 * D(x))
    termNp = (
        (D(x) * x - D(y).mul_up(y)) * (2 * p.c) * p.s + xy * p.c * p.c - xy * p.s * p.s
    )

    termXp = z * u + (w * u + z * v) / lam + w * v / lam / lam
    termXp = termXp / (dSq * dSq * dSq * dSq)

    return mulDownXpToNp(termNp, termXp)


def calcMinAtyAChixSqPlusAtySq(x: D, y: D, p: Params, d: DerivedParams) -> D:
    w, z, u, v, lam, dSq = (
        D2(d.w),
        D2(d.z),
        D2(d.u),
        D2(d.v),
        D2(D(p.l).raw),
        D2(d.dSq),
    )
    termNp = D(x).mul_up(x).mul_up(p.s).mul_up(p.s) + D(y).mul_up(y).mul_up(p.c).mul_up(
        p.c
    )
    termNp += D(x).mul_up(y).mul_up(p.s * 2).mul_up(p.c)

    termXp = z * z + w * w / lam / lam + (2 * z) * w / lam
    termXp = termXp / (dSq * dSq * dSq * dSq)
    val = mulDownXpToNp(-termNp, termXp)

    termXp = D2(1) / dSq
    termNp = termNp - D("9e-18")
    val = val + mulDownXpToNp(termNp, termXp)
    return val


def calcInvariantSqrt(x: D, y: D, p: Params, d: DerivedParams) -> tuple[D, D]:
    val = (
        calcMinAtxAChiySqPlusAtxSq(x, y, p, d)
        + calc2AtxAtyAChixAChiy(x, y, p, d)
        + calcMinAtyAChixSqPlusAtySq(x, y, p, d)
    )

    err = (D(x).mul_up(x) + D(y).mul_up(y)) / D("1e38")
    if val < 0:
        val = 0
    return D(val).sqrt(), err


# def calculateInvariantWithError(
#     balances: Iterable[D], p: Params, d: DerivedParams
# ) -> tuple[D, D]:
#     x, y = (D(balances[0]), D(balances[1]))
#     AtAChi = calcAtAChi(x, y, p, d)
#     sqrt, err = calcInvariantSqrt(x, y, p, d)
#     if sqrt > 0:
#         err = D(err + D("1e-18")).div_up(2 * sqrt)
#     else:
#         err = D(err).sqrt() if err > 0 else D("1e-9")

#     err = (D(p.l).mul_up(x + y) / D("1e38") + err + D("1e-18")) * 20

#     denominator = calcAChiAChi(p, d) - D(1)
#     assert denominator > 0
#     invariant = (AtAChi + sqrt - err) / denominator
#     # error scales if denominator is small
#     err = err if denominator > 1 else err.div_up(D(denominator))
#     err = err + (D(invariant) * 10).div_up(denominator) / D("1e18")
#     return invariant, err


def calculateInvariantWithError(
    balances: Iterable[D], p: Params, d: DerivedParams
) -> tuple[D, D]:
    x, y = (D(balances[0]), D(balances[1]))
    AtAChi = calcAtAChi(x, y, p, d)
    sqrt, err = calcInvariantSqrt(x, y, p, d)
    if sqrt > 0:
        err = D(err + D("1e-18")).div_up(2 * sqrt)
    else:
        err = D(err).sqrt() if err > 0 else D("1e-9")

    err = (D(p.l).mul_up(x + y) / D("1e38") + err + D("1e-18")) * 20

    denominator = calcAChiAChiInXp(p, d) - D2(1)
    mulDenominator = D2(1) / denominator
    assert denominator > 0
    invariant = mulDownXpToNp(AtAChi + sqrt - err, mulDenominator)
    # error scales if denominator is small
    err = mulUpXpToNp(err, mulDenominator)
    err_div = D(int(p.l * p.l))
    err = (
        err
        + mulUpXpToNp(D(invariant), mulDenominator) * err_div * 40 / D("1e38")
        + D("1e-18")
    )
    return invariant, err


def calculateInvariant(balances: Iterable[D], p: Params, d: DerivedParams) -> D:
    invariant, err = calculateInvariantWithError(balances, p, d)
    return invariant


def calcXpXpDivLambdaLambda(
    x: D, r: Iterable[D], lam: D, s: D, c: D, tauBeta: Iterable[D2], dSq: D2
) -> D:
    dSq2 = dSq * dSq

    val = D(r[0]).mul_up(r[0]).mul_up(c).mul_up(c)
    val = mulUpXpToNp(val, tauBeta[0] * tauBeta[0] / dSq2 + D2("7e-38"))

    termXp = tauBeta[0] * tauBeta[1] / dSq2
    if termXp > 0:
        q_a = D(r[0]).mul_up(r[0]).mul_up(2 * s).mul_up(c)
        q_a = mulUpXpToNp(q_a, termXp + D2("7e-38"))
    else:
        q_a = D(r[1]) * r[1] * (2 * s) * c
        q_a = mulUpXpToNp(q_a, termXp)

    termXp = tauBeta[0] / dSq
    if tauBeta[0] < 0:
        q_b = D(r[0]).mul_up(x).mul_up(2 * c)
        q_b = mulUpXpToNp(q_b, -termXp + D2("3e-38"))
    else:
        q_b = -D(r[1]) * x * (2 * c)
        q_b = mulUpXpToNp(q_b, termXp)
    q_a = q_a + q_b

    termXp = tauBeta[1] * tauBeta[1] / dSq2 + D2("7e-38")
    q_b = D(r[0]).mul_up(r[0]).mul_up(s).mul_up(s)
    q_b = mulUpXpToNp(q_b, termXp)

    q_c = -D(r[1]) * x * (2 * s)
    q_c = mulUpXpToNp(q_c, tauBeta[1] / dSq)

    q_b = q_b + q_c + D(x).mul_up(x)

    q_b = D(q_b).div_up(lam) if q_b > 0 else q_b / lam

    q_a = q_a + q_b
    q_a = D(q_a).div_up(lam) if q_a > 0 else q_a / lam
    return val + q_a


def solveQuadraticSwap(
    lam: D,
    x: D,
    s: D,
    c: D,
    r: Iterable[D],
    ab: Iterable[D],
    tauBeta: Iterable[D2],
    dSq: D2,
) -> D:
    lam2 = D2(D(lam).raw)
    lamBar = (D2(1) - (D2(1) / lam2 / lam2), D2(1) - D2(1).div_up(lam2).div_up(lam2))
    xp = x - ab[0]
    if xp > 0:
        qb = -xp * s * c
        qb = mulUpXpToNp(qb, lamBar[1] / dSq)
    else:
        qb = -D(xp).mul_up(s).mul_up(c)
        qb = mulUpXpToNp(qb, lamBar[0] / dSq + D2("1e-38"))

    s2 = D2(D(s).raw)
    sTerm = (
        D2(1) - lamBar[1] * s2 * s2 / dSq,
        D2(1) - lamBar[0].mul_up(s2).mul_up(s2) / (dSq + D2("1e-38")) - D2("1e-38"),
    )

    qc = -calcXpXpDivLambdaLambda(x, r, lam, s, c, tauBeta, dSq)
    qc += mulDownXpToNp(r[1] * r[1], sTerm[1])
    if qc < 0:
        qc = 0
    qc = D(qc).sqrt()

    if qb - qc > 0:
        qa = mulUpXpToNp(qb - qc, D2(1) / sTerm[1] + D2("1e-38"))
        return qa + ab[1]
    else:
        qa = mulUpXpToNp(qb - qc, D2(1) / sTerm[0])
        return qa + ab[1]


def calcYGivenX(x: D, p: Params, d: DerivedParams, r: Iterable[D]) -> D:
    a = virtualOffset0(p, d, r)
    b = virtualOffset1(p, d, r)
    y = solveQuadraticSwap(p.l, x, p.s, p.c, r, (a, b), d.tauBeta, d.dSq)
    return y


def calcXGivenY(y: D, p: Params, d: DerivedParams, r: Iterable[D]) -> D:
    a = virtualOffset0(p, d, r)
    b = virtualOffset1(p, d, r)
    tau_beta = (-d.tauAlpha[0], d.tauAlpha[1])
    x = solveQuadraticSwap(p.l, y, p.c, p.s, r, (b, a), tau_beta, d.dSq)
    return x


def invariantOverestimate(rDown: D) -> D:
    return D(rDown) + D(rDown).mul_up(D("1e-12"))


def mulXp(a: int, b: int) -> int:
    product = int(a) * int(b) // int(D("1e38"))
    return product


def divXp(a: int, b: int) -> int:
    if a == 0:
        return 0
    a_inflated = int(a) * int(D("1e38"))
    return a_inflated // int(b)


def mulDownXpToNp(a: D, b: D2) -> D:
    a = int(D(a) * D("1e18"))
    b = int(b * D2("1e38"))
    b1 = b // int(D("1e19"))
    b2 = b - b1 * int(D("1e19")) if b1 != 0 else b
    prod1 = a * b1
    prod2 = a * b2
    if prod1 >= 0 and prod2 >= 0:
        prod = (prod1 + prod2 // int(D("1e19"))) // int(D("1e19"))
    else:
        # have to use double minus signs b/c of how // operator works
        prod = -((-prod1 - prod2 // int(D("1e19")) - 1) // int(D("1e19"))) - 1
    return D(prod) / D("1e18")


def mulUpXpToNp(a: D, b: D2) -> D:
    a = int(D(a) * D("1e18"))
    b = int(b * D2("1e38"))
    b1 = b // int(D("1e19"))
    b2 = b - b1 * int(D("1e19")) if b1 != 0 else b
    prod1 = a * b1
    prod2 = a * b2
    if prod1 <= 0 and prod2 <= 0:
        # have to use double minus signs b/c of how // operator works
        prod = -((-prod1 + -prod2 // int(D("1e19"))) // int(D("1e19")))
    else:
        prod = (prod1 + prod2 // int(D("1e19")) - 1) // int(D("1e19")) + 1
    return D(prod) / D("1e18")


def tauXp(p: Params, px: D, dPx: D2) -> tuple[D2, D2]:
    tauPx = [0, 0]
    tauPx[0] = (D2(px) * D2(p.c) - D2(p.s)) * dPx
    tauPx[1] = ((D2(p.s) * D2(px) + D2(p.c)) / D2(p.l)) * dPx
    return tuple(tauPx)


def calc_derived_values(p: Params) -> DerivedParams:
    s, c, lam, alpha, beta = (
        D(p.s).raw,
        D(p.c).raw,
        D(p.l).raw,
        D(p.alpha).raw,
        D(p.beta).raw,
    )
    s, c, lam, alpha, beta = (
        D3(s),
        D3(c),
        D3(lam),
        D3(alpha),
        D3(beta),
    )
    dSq = c * c + s * s
    d = dSq.sqrt()
    dAlpha = D3(1) / (
        ((c / d + alpha * s / d) ** 2 / lam**2 + (alpha * c / d - s / d) ** 2).sqrt()
    )
    dBeta = D3(1) / (
        ((c / d + beta * s / d) ** 2 / lam**2 + (beta * c / d - s / d) ** 2).sqrt()
    )
    tauAlpha = [0, 0]
    tauAlpha[0] = (alpha * c - s) * dAlpha
    tauAlpha[1] = (c + s * alpha) * dAlpha / lam

    tauBeta = [0, 0]
    tauBeta[0] = (beta * c - s) * dBeta
    tauBeta[1] = (c + s * beta) * dBeta / lam

    w = s * c * (tauBeta[1] - tauAlpha[1])
    z = c * c * tauBeta[0] + s * s * tauAlpha[0]
    u = s * c * (tauBeta[0] - tauAlpha[0])
    v = s * s * tauBeta[1] + c * c * tauAlpha[1]

    tauAlpha38 = (D2(tauAlpha[0].raw), D2(tauAlpha[1].raw))
    tauBeta38 = (D2(tauBeta[0].raw), D2(tauBeta[1].raw))
    derived = DerivedParams(
        tauAlpha=(tauAlpha38[0], tauAlpha38[1]),
        tauBeta=(tauBeta38[0], tauBeta38[1]),
        u=D2(u.raw),
        v=D2(v.raw),
        w=D2(w.raw),
        z=D2(z.raw),
        dSq=D2(dSq.raw),
        # dAlpha=D2(dAlpha.raw),
        # dBeta=D2(dBeta.raw),
    )
    return derived


def scale_derived_values(d: DerivedParams) -> DerivedParams:
    derived = DerivedParams(
        tauAlpha=Vector2(d.tauAlpha[0] * D2("1e38"), d.tauAlpha[1] * D2("1e38")),
        tauBeta=Vector2(d.tauBeta[0] * D2("1e38"), d.tauBeta[1] * D2("1e38")),
        u=d.u * D2("1e38"),
        v=d.v * D2("1e38"),
        w=d.w * D2("1e38"),
        z=d.z * D2("1e38"),
        dSq=d.dSq * D2("1e38"),
        # dAlpha=d.dAlpha * D2("1e38"),
        # dBeta=d.dBeta * D2("1e38"),
    )
    return derived


def calc_invariant_error(params, derived, balances):
    x, y = (D(balances[0]), D(balances[1]))
    if D(x) > D("1e11") or D(y) > D("1e11"):
        err = (D(x) * x + D(y) * y) / D("1e38") * D("100e-18")
    else:
        err = D("100e-18")
    err = err * 10  # error in sqrt is O(error in square)
    denominator = calcAChiAChi(params, derived) - D(1)
    # error scales if denominator is small
    err = err if denominator > 1 else err / D(denominator)
    return err


# def mkDerivedParmasXp(p: Params) -> DerivedParams:
#     tauAlpha = tauXp(p, p.alpha, p.dAlpha)
#     tauBeta = tauXp(p, p.beta, p.dBeta)
