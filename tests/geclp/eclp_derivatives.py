from typing import Optional

from tests.support.types import ECLPMathParams
from tests.support.quantized_decimal import QuantizedDecimal as D
from tests.geclp import eclp_prec_implementation as prec_impl

# Derivative calculations used in the SOR. See `E-CLP SOR derivatives.pdf`. These calculations are all in 18 decimals
# and they have *not* been optimized for precision. So don't expect super high prec from them (which we also don't
# need)

# Note: There are four ways of computing the price of x as a derivative, and they are pairwise equal and pairwise
# different by a factor 1/f where f=1-fee. Also, there are a lot of almost-duplications of code b/c of the inherent
# symmetries. We did not unify most of them here (except the calculation of R, which comes up many times),
# but this could be done, too.


def _setup(
    balances: list[D],
    params: ECLPMathParams,
    fee: D,
    r_vec: tuple[D, D],
    r: Optional[D],
    ix_var: int,
) -> tuple:
    """
    Convenience function extracts some values we need again and again.

    ix_var: 0 if our variable is x, 1 if it's y.
    """
    if r is None:
        r = r_vec[1]  # Kinda arbitrary choice

    _, _, c, s, l = params
    x0, y0 = balances

    derived = prec_impl.calc_derived_values(params)
    # The 'None' case allows ppl to pass None for balances that aren't actually used in the calculation, which can be
    # convenient.
    a = prec_impl.virtualOffset0(params, derived, r_vec)
    b = prec_impl.virtualOffset1(params, derived, r_vec)

    ls = 1 - 1 / l**2
    f = 1 - fee

    if ix_var == 0:
        R = (r**2 * (1 - ls * s**2) - (x0 - a) ** 2 / l**2).sqrt()
    else:
        R = (r**2 * (1 - ls * c**2) - (y0 - b) ** 2 / l**2).sqrt()

    return x0, y0, c, s, l, a, b, ls, f, r, R


def dyin_dxout(
    balances: list[D],
    params: ECLPMathParams,
    fee: D,
    r_vec: tuple[D, D],
    r: Optional[D] = None,
):
    """
    Derivative of yin as a function of xout at 0. Accounts for fees.
    = d yin / d xout
    = Price of x ito. y including fees.

    r: If given, must be one of the elements of r_vec.

    Only x0 := balances[0] is used.
    """
    x0, y0, c, s, l, a, b, ls, f, r, R = _setup(balances, params, fee, r_vec, r, 0)
    ret = 1 / (f * (1 - ls * s**2)) * (ls * s * c - (x0 - a) / (l**2 * R))
    return ret


def dxin_dyout(
    balances: list[D],
    params: ECLPMathParams,
    fee: D,
    r_vec: tuple[D, D],
    r: Optional[D] = None,
):
    """
    Derivative of xin as a function of yout at 0. Accounts for fees.
    = d xin / d yout
    = Price of x ito. y including fees.

    Only y0 := balances[1] is used.
    """
    x0, y0, c, s, l, a, b, ls, f, r, R = _setup(balances, params, fee, r_vec, r, 1)
    ret = 1 / (f * (1 - ls * c**2)) * (ls * s * c - (y0 - b) / (l**2 * R))
    return ret


def dyout_dxin(
    balances: list[D],
    params: ECLPMathParams,
    fee: D,
    r_vec: tuple[D, D],
    r: Optional[D] = None,
):
    x0, y0, c, s, l, a, b, ls, f, r, R = _setup(balances, params, fee, r_vec, r, 0)
    ret = f / (1 - ls * s**2) * (ls * s * c - (x0 - a) / (l**2 * R))
    return ret


def dxout_dyin(
    balances: list[D],
    params: ECLPMathParams,
    fee: D,
    r_vec: tuple[D, D],
    r: Optional[D] = None,
):
    x0, y0, c, s, l, a, b, ls, f, r, R = _setup(balances, params, fee, r_vec, r, 1)
    ret = f / (1 - ls * c**2) * (ls * s * c - (y0 - b) / (l**2 * R))
    return ret


def dpx_dxout(
    balances: list[D],
    params: ECLPMathParams,
    fee: D,
    r_vec: tuple[D, D],
    r: Optional[D] = None,
):
    """
    Derivative of (Derivative of yin as a fct of xout) as a fct of xout at 0.
    = d^2 yin / d xout^2

    Accounts for fees but *not* for the compounding of fees. This is what you use to analyze slippage for the purpose
    I, but it'd probably be wrong to use it for the behavior of the pool over time.

    Only x0 := balances[0] is used.
    """
    x0, y0, c, s, l, a, b, ls, f, r, R = _setup(balances, params, fee, r_vec, r, 0)
    ret = (
        1
        / (f * (1 - ls * s**2))
        * (1 / (l**2 * R) + (x0 - a) ** 2 / (l**4 * R**3))
    )
    return ret


def dpy_dyout(
    balances: list[D],
    params: ECLPMathParams,
    fee: D,
    r_vec: tuple[D, D],
    r: Optional[D] = None,
):
    """
    Derivative of (price of y ito. x) as a fct of yout at 0
    = Derivative of (Derivative of xin as a fct of yout) as a fct of yout at 0.
    = d^2 xin / d yout^2

    Accounts for fees but *not* for the compounding of fees.

    Only y0 := balances[1] is used.
    """
    x0, y0, c, s, l, a, b, ls, f, r, R = _setup(balances, params, fee, r_vec, r, 1)
    ret = (
        1
        / (f * (1 - ls * c**2))
        * (1 / (l**2 * R) + (y0 - b) ** 2 / (l**4 * R**3))
    )
    return ret


def dpy_dxin(
    balances: list[D],
    params: ECLPMathParams,
    fee: D,
    r_vec: tuple[D, D],
    r: Optional[D] = None,
):
    """
    Derivative of (price of y ito x incl fees as a fct of xin) as a fct of xin at 0.
    = d (1 / (d yout / d xin)) / dxin at 0
    """
    x0, y0, c, s, l, a, b, ls, f, r, R = _setup(balances, params, fee, r_vec, r, 0)
    ret = (
        (1 - ls * s**2)
        * (1 / (l**2 * R) + (x0 - a) ** 2 / (l**4 * R**3))
        / (ls * s * c - (x0 - a) / (l**2 * R)) ** 2
    )
    return ret


def dpx_dyin(
    balances: list[D],
    params: ECLPMathParams,
    fee: D,
    r_vec: tuple[D, D],
    r: Optional[D] = None,
):
    """
    Derivative of (price of x ito y incl fees as a fct of yin) as a fct of yin at 0.
    = d (1 / (d xout / d yin)) / d yin at 0
    """
    x0, y0, c, s, l, a, b, ls, f, r, R = _setup(balances, params, fee, r_vec, r, 1)
    ret = (
        (1 - ls * c**2)
        * (1 / (l**2 * R) + (y0 - b) ** 2 / (l**4 * R**3))
        / (ls * s * c - (y0 - b) / (l**2 * R)) ** 2
    )
    return ret


def normalized_liquidity_yin(
    balances: list[D],
    params: ECLPMathParams,
    fee: D,
    r_vec: tuple[D, D],
    r: Optional[D] = None,
):
    """
    0.5 * 1 / (Derivative of (effective price of x ito y incl fees as a fct of yin)) as a fct of yin in the limit yin -> 0.
    = 0.5 * 1 / (d (yin / xout) / d yin) in the limit yin -> 0.

    Note that (d (yin / xout) / d yin) is *not* the same as dpx_dyin (i.e., the derivative of the *marginal* price.
    Because math...)
    """
    x0, y0, c, s, l, a, b, ls, f, r, R = _setup(balances, params, fee, r_vec, r, 1)
    ret = (
        1
        / (1 - ls * c**2)
        * (R * (ls * s * c * l**2 * R - (y0 - b)) ** 2)
        / (l**2 * R**2 + (y0 - b) ** 2)
    )
    return ret


def normalized_liquidity_xin(
    balances: list[D],
    params: ECLPMathParams,
    fee: D,
    r_vec: tuple[D, D],
    r: Optional[D] = None,
):
    """
    See normalized_normalized_liquidity_yin. Here with yout and xin.
    """
    x0, y0, c, s, l, a, b, ls, f, r, R = _setup(balances, params, fee, r_vec, r, 0)
    ret = (
        1
        / (1 - ls * s**2)
        * (R * (ls * s * c * l**2 * R - (x0 - a)) ** 2)
        / (l**2 * R**2 + (x0 - a) ** 2)
    )
    return ret
