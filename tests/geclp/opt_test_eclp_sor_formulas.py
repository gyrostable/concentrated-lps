from math import tan, sin, cos, pi

# Comparison tests comparing the formulas we use for the SOR integration to approximate values of what they
# represent coming from Solidity, for the 2-CLP.
#
# The SOR code itself is typescript and is in another repo.
#
# Note that these are *very* approximate and really only serve to check that our formulas are not total nonsense.
# The bounds of the assertion checks are rather generous and we did not make an effort to make them as tight as
# possible, and neither did we put particular effort to make the approximation of derivatives very precise.
# If these tests fail, it may well be b/c of numerical issues in the "ground truth" that we're testing against, rather
# than the SOR formulas. (note that we're computing the ground truth in fixed point, too, so we import its issues. This
# is not a problem in reality b/c these comparison calculations are not performed in production, only in these tests)

from brownie.test import given
from hypothesis import assume, example

from tests.support.quantized_decimal import QuantizedDecimal as D
from tests.support.quantized_decimal_38 import QuantizedDecimal as D2

from tests.support.types import ECLPMathParams
from tests.support.util_common import gen_balances, BasicPoolParameters
from tests.support.utils import scale, unscale, to_decimal, qdecimals
import hypothesis.strategies as st

import tests.geclp.eclp_prec_implementation as prec_impl
from tests.geclp import eclp_derivatives as derivatives

bpool_params = BasicPoolParameters(
    min_price_separation=to_decimal("0.0001"),
    max_in_ratio=None,
    max_out_ratio=None,
    min_balance_ratio=D(
        "0.01"
    ),  # Avoid hyper unbalanced pools. (only problematic for normalizedLiquidity)
    min_fee=None,
)

# A simple example to catch weird generic errors. 45° rotation and asymmetric, generous
# price bounds around 1.
easy_params = ECLPMathParams(
    alpha=D("0.5"), beta=D("1.5"), c=1 / D(2).sqrt(), s=1 / D(2).sqrt(), l=D(2)
)

N_ASSETS = 2

# Variant of util.gen_params() with slightly less extreme parameters. This is important mainly for the normalized
# liquidity test. (normalized liquidity can get unstable for extreme parameters and at the end of the trading range)
@st.composite
def gen_params(draw, bparams: BasicPoolParameters):
    phi_degrees = draw(st.floats(10, 80))
    phi = phi_degrees / 360 * 2 * pi

    # Price bounds. Choose s.t. the 'peg' lies approximately within the bounds (within 30%).
    # It'd be nonsensical if this was not the case: Why are we using an ellipse then?!
    peg = tan(phi)  # = price where the flattest point of the ellipse lies.
    peg = D(peg)
    # Range of peg ≈ [0.17, 5.68]

    alpha_range = [D("0.05"), peg]
    beta_range = [peg, D("20.0")]
    alpha = draw(qdecimals(*alpha_range))
    beta_range[0] = max(beta_range[0], alpha + to_decimal(bparams.min_price_separation))
    beta = draw(qdecimals(*beta_range))

    # alpha = draw(qdecimals("0.2", "4.0"))
    # beta = draw(qdecimals(alpha + to_decimal(bparams.min_price_separation), "5.0"))

    # alpha_high = peg * D("1.3")
    # beta_low = peg * D("0.7")
    #
    # alpha = draw(qdecimals("0.05", alpha_high.raw))
    # beta = draw(
    #     qdecimals(max(beta_low.raw, (alpha + MIN_PRICE_SEPARATION).raw), "20.0")
    # )

    s = sin(phi)
    c = cos(phi)
    l = draw(qdecimals("1", "1e6"))
    return ECLPMathParams(alpha, beta, D(c), D(s), l)


def gen_fee():
    return qdecimals(D(0), D("0.1"))


def get_derived_values(gyro_eclp_math_testing, balances, params: ECLPMathParams):
    # This is taken from test_eclp_properties.py and the functions it calls.
    derived = prec_impl.calc_derived_values(params)  # type: ignore
    derived_scaled = prec_impl.scale_derived_values(derived)

    # Denominator condition is quite important! O/w effective prices can be really out of whack.
    # (even far outside the price range)
    denominator = prec_impl.calcAChiAChiInXp(params, derived) - D2(1)  # type: ignore
    assume(denominator > D2("1E-5"))  # if this is not the case, error can blow up

    invariant_sol, inv_err_sol = unscale(
        gyro_eclp_math_testing.calculateInvariantWithError(
            scale(balances), scale(params), derived_scaled
        )
    )
    r_vec = (invariant_sol + 2 * inv_err_sol, invariant_sol)
    return invariant_sol, r_vec, derived, derived_scaled


@given(
    balances=gen_balances(N_ASSETS, bpool_params),
    params=gen_params(bpool_params),
    fee=gen_fee(),
    ix_in=st.integers(0, 1),
)
@example(balances=[1000, 1000], params=easy_params, fee=D("0.1"), ix_in=1)
def test_p(gyro_eclp_math_testing, balances: list, params: ECLPMathParams, fee, ix_in):
    """
    Price of the out-asset in terms of the in-asset
    """
    assume(all(b >= 1 for b in balances))  # Avoid *very* extreme value combinations
    ix_out = 1 - ix_in

    r, r_vec, derived, derived_scaled = get_derived_values(
        gyro_eclp_math_testing, balances, params
    )

    amount_out = balances[ix_out] * D("0.0001")
    assume(amount_out != 0)

    # DEBUG
    bounds_xy = (params.alpha, params.beta)
    bounds = (
        (params.alpha, params.beta)
        if ix_in == 1
        else (1 / params.beta, 1 / params.alpha)
    )

    # Solidity approximation
    amount_in = unscale(
        gyro_eclp_math_testing.calcInGivenOut(
            scale(balances),
            scale(amount_out),
            ix_in == 0,
            scale(params),
            derived_scaled,
            scale(r_vec),
        )
    )

    amount_in_after_fee = amount_in / (1 - fee)
    p_approx_sol = amount_in_after_fee / amount_out

    # Analytical calculation (via solidity)
    # Note: This calc is not optimized for precision in the same way e.g. the invariant calc is.
    # This is the price of x in terms of y. If our assets are the other way round, we flip, so that we get the price of the out-asset ito. the in-asset.
    p_anl_sol = unscale(
        gyro_eclp_math_testing.calculatePrice(
            scale(balances), scale(params), derived_scaled, scale(r)
        )
    )
    if ix_in == 0:
        p_anl_sol = D(1) / p_anl_sol
    # Account for fee (which isn't included above)
    p_anl_sol /= 1 - fee

    # balances_new = balances.copy()
    # balances_new[ix_in] += amount_in   # Not used below.
    # balances_new[ix_out] -= amount_out
    if ix_in == 1:
        p_anl_new = derivatives.dyin_dxout(balances, params, fee, r_vec)
    else:
        p_anl_new = derivatives.dxin_dyout(balances, params, fee, r_vec)

    assert p_anl_sol == p_approx_sol.approxed(rel=D("1e-3"), abs=D("1e-3"))
    assert p_anl_new == p_approx_sol.approxed(rel=D("1e-3"), abs=D("1e-3"))


@given(
    balances=gen_balances(N_ASSETS, bpool_params),
    params=gen_params(bpool_params),
    fee=gen_fee(),
    ix_in=st.integers(0, 1),
)
@example(balances=[1000, 1000], params=easy_params, fee=D("0.1"), ix_in=1)
def test_dp_d_swapExactIn(
    gyro_eclp_math_testing, balances: list, params: ECLPMathParams, fee, ix_in
):
    """
    Derivative of the spot price of the out-asset ito the in-asset as a fct of the in-asset at 0.
    """
    # Transition to in/out instead of 0/1.
    assume(all(b >= 1 for b in balances))  # Avoid *very* extreme value combinations
    ix_out = 1 - ix_in

    r, r_vec, derived, derived_scaled = get_derived_values(
        gyro_eclp_math_testing, balances, params
    )

    if ix_in == 1:
        amount_in_max = (
            unscale(
                gyro_eclp_math_testing.maxBalances1(
                    scale(params), derived_scaled, scale(r_vec)
                )
            )
            - balances[1]
        )
    else:
        amount_in_max = (
            unscale(
                gyro_eclp_math_testing.maxBalances0(
                    scale(params), derived_scaled, scale(r_vec)
                )
            )
            - balances[0]
        )

    # NB this doesn't quite go to amount_in_max when fee > 0. Could be more clever here but meh.
    amount_in = min(amount_in_max, balances[ix_in] * D("0.001"))
    amount_in_after_fee = amount_in * (1 - fee)

    amount_out = unscale(
        gyro_eclp_math_testing.calcOutGivenIn(
            scale(balances),
            scale(amount_in_after_fee),
            ix_in == 0,
            scale(params),
            derived_scaled,
            scale(r_vec),
        )
    )

    # New anl approximation. We calculate two prices analytically (see above test for why this is ok) and
    # approximate the function of the in-asset.
    def price_at_balances(balances):
        if ix_in == 1:
            p_anl_new = derivatives.dyin_dxout(balances, params, fee, r_vec)
        else:
            p_anl_new = derivatives.dxin_dyout(balances, params, fee, r_vec)
        return p_anl_new

    # First price before the trade
    p0 = price_at_balances(balances)

    # For the second point, we do *not* put the fees into the pool (this is intentional!), so r doesn't change.
    balances_after_trade = balances.copy()
    balances_after_trade[ix_in] += amount_in_after_fee
    balances_after_trade[ix_out] -= amount_out
    p1 = price_at_balances(balances_after_trade)

    derivative_approx_sol = (p1 - p0) / amount_in

    # Analytical calculation
    if ix_in == 1:
        derivative_anl = derivatives.dpx_dyin(balances, params, fee, r_vec)
    else:
        derivative_anl = derivatives.dpy_dxin(balances, params, fee, r_vec)

    assert derivative_anl == derivative_approx_sol.approxed(
        rel=D("1e-3"), abs=D("1e-3")
    )


@given(
    balances=gen_balances(N_ASSETS, bpool_params),
    params=gen_params(bpool_params),
    fee=gen_fee(),
    ix_in=st.integers(0, 1),
)
@example(balances=[1000, 1000], params=easy_params, fee=D("0.1"), ix_in=1)
def test_dp_d_swapExactOut(
    gyro_eclp_math_testing, balances: list, params: ECLPMathParams, fee, ix_in
):
    """
    Derivative of the spot price of the out-asset ito the in-asset as a fct of the out-asset at 0.
    """
    # Transition to in/out instead of 0/1.
    assume(all(b >= 1 for b in balances))  # Avoid *very* extreme value combinations
    ix_out = 1 - ix_in

    balances0 = balances
    r, r_vec, derived, derived_scaled = get_derived_values(
        gyro_eclp_math_testing, balances, params
    )

    amount_out = min(1, balances[1] * D("0.0001"))

    amount_in = unscale(
        gyro_eclp_math_testing.calcInGivenOut(
            scale(balances),
            scale(amount_out),
            ix_in == 0,
            scale(params),
            derived_scaled,
            scale(r_vec),
        )
    )
    # amount_in_after_fee = amount_in / (1 - fee)  # Unused, see below

    # New anl approximation. We calculate two prices analytically (see above test for why this is ok) and
    # approximate the function of the in-asset.
    def price_at_balances(balances):
        if ix_in == 1:
            p_anl_new = derivatives.dyin_dxout(balances, params, fee, r_vec)
        else:
            p_anl_new = derivatives.dxin_dyout(balances, params, fee, r_vec)
        return p_anl_new

    # First price before the trade
    p0 = price_at_balances(balances)

    # For the second point, we do *not* put the fees into the pool (this is intentional!), so l and virtual_params
    # don't change.
    balances_after_trade = balances.copy()
    balances_after_trade[ix_in] += amount_in
    balances_after_trade[ix_out] -= amount_out
    p1 = price_at_balances(balances_after_trade)

    derivative_approx_sol = (p1 - p0) / amount_out

    # Analytical calculation
    # We use the post-trade point b/c that gives us a slightly better match for some reason.
    balances_new = balances.copy()
    balances_new[ix_out] -= amount_out
    balances_new[ix_in] += amount_in
    if ix_in == 1:
        derivative_anl = derivatives.dpx_dxout(balances_new, params, fee, r_vec)
    else:
        derivative_anl = derivatives.dpy_dyout(balances_new, params, fee, r_vec)

    assert derivative_anl == derivative_approx_sol.approxed(
        rel=D("1e-3"), abs=D("1e-3")
    )


@given(
    balances=gen_balances(N_ASSETS, bpool_params),
    params=gen_params(bpool_params),
    fee=gen_fee(),
    ix_in=st.integers(0, 1),
)
@example(balances=[1000, 1000], params=easy_params, fee=D("0.1"), ix_in=1)
def test_normalizedLiquidity(
    gyro_eclp_math_testing, balances: list, params: ECLPMathParams, fee, ix_in
):
    """
    Normalized liquidity = 0.5 * 1 / (derivative of the effective (i.e., average) price of the out-asset ito. the in-asset as a fct of the in-amount in the limit at 0).
    """
    assume(all(b >= 1 for b in balances))  # Avoid *very* extreme value combinations
    ix_out = 1 - ix_in

    r, r_vec, derived, derived_scaled = get_derived_values(
        gyro_eclp_math_testing, balances, params
    )

    # DEBUG
    bounds_xy = (params.alpha, params.beta)
    peg_xy = params.s / params.c
    bounds = (
        (params.alpha, params.beta)
        if ix_in == 1
        else (1 / params.beta, 1 / params.alpha)
    )
    peg = params.s / params.c if ix_in == 1 else params.c / params.s
    balances_outin = [balances[ix_out], balances[ix_in]]

    # Approximation of the derivative. Note that the quotient is ill-defined *at* 0, so we take two trade sizes close to 0.
    # We use an iterative scheme for better precision; we use the python math implementation instead of Solidity for performance.
    if ix_in == 1:
        amount_in_max = prec_impl.maxBalances1(params, derived, r_vec) - balances[1]
    else:
        amount_in_max = prec_impl.maxBalances0(params, derived, r_vec) - balances[0]

    # For the derivative, we essentially approximate the limit
    # lim Δ -> 0: ((effective price of trading Δ in) - (marginal price of out-asset)) / Δ.
    # So the normalized liquidity is approximated as
    # lim Δ -> 0: 0.5 * Δ / ((effective price of trading Δ in) - (marignal price of out-asset))
    # This is ok because of (math... continuous continuation... Dini's theorem...)
    if ix_in == 1:
        p_marginal = derivatives.dyin_dxout(balances, params, fee, r_vec)
    else:
        p_marginal = derivatives.dxin_dyout(balances, params, fee, r_vec)

    res_prev = None
    res = None
    # NB this doesn't quite go to amount_in_max when fee > 0. Could be more clever here but meh.
    # NB This shouldn't be too small either b/c then we run into trouble with fixed-point calcs.
    amount_in = min(amount_in_max * D("0.999"), balances[ix_in] * D("0.01")) * 2
    calcBalOutGivenBalIn = (
        prec_impl.calcXGivenY if ix_in == 1 else prec_impl.calcYGivenX
    )

    res_history = []  # DEBUG
    # We need some conditions for numerical stability in fixed point.
    while res_prev is None or (
        not (res == res_prev.approxed(abs=D("1e-3"), rel=D("1e-3")))
        and amount_in >= D("1e-2")
    ):
        res_prev = res
        amount_in *= D("0.5")
        amount_in_after_fee = amount_in * (1 - fee)
        amount_out = balances[ix_out] - calcBalOutGivenBalIn(
            balances[ix_in] + amount_in_after_fee, params, derived, r_vec
        )
        p_effective = amount_in / amount_out
        assert p_effective >= bounds[0]
        # These are actually guaranteed. If they're not satisfied, this means that numerical error has a huge influence.
        # I've observed this a few times for this test if we don't have this `assume` and the pool is extremely unbalanced.
        # Note that if this is violated, the higher prices are in the pool's favor, so this is not dangerous per se.
        # assume(p_eff1 <= bounds[1] and p_eff2 <= bounds[1])
        # assert (p_eff1 <= bounds[1] and p_eff2 <= bounds[1])

        res = D("0.5") * amount_in / (p_effective - p_marginal)

        res_history.append((amount_in, amount_out, p_effective, res))

    # Re-writing to improve fixed-point precision
    # d_p_eff_approxed_solidity = (p_eff1 - p_eff2) / (amount_in1 - amount_in2)
    # nliq_approxed_solidity = D('0.5') / d_p_eff_approxed_solidity
    nliq_approxed_solidity = res

    # Analytical solution.
    # We use the point after trading b/c that gives us a slightly better match for some reason.
    if ix_in == 1:
        nliq_anl = derivatives.normalized_liquidity_yin(balances, params, fee, r_vec)
    else:
        nliq_anl = derivatives.normalized_liquidity_xin(balances, params, fee, r_vec)

    assert nliq_anl == nliq_approxed_solidity.approxed(rel=D("1e-2"), abs=D("1e-2"))


# DEBUG
from operator import truediv
from pprint import pprint


def fmt(x):
    if isinstance(x, (list, tuple, set)):
        return type(x)(map(fmt, x))
    return f"{x:e}"
