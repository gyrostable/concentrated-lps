from decimal import Decimal
from typing import Tuple

import hypothesis.strategies as st
import numpy as np
from hypothesis import settings, assume, example

import tests.cpmmv3.v3_math_implementation as math_implementation
from brownie import reverts
from brownie.test import given

from tests.support.utils import scale, to_decimal, unscale, qdecimals

from tests.support.quantized_decimal import QuantizedDecimal as D

billion_balance_strategy = st.integers(min_value=0, max_value=100_000_000_000)

ROOT_ALPHA_MAX = "0.99996666555"
ROOT_ALPHA_MIN = "0.2"
MIN_BAL_RATIO = D(0)  # to_decimal("1e-5")


def faulty_params(balances, root_three_alpha):
    balances = [to_decimal(b) for b in balances]
    if balances[0] == 0 and balances[1] == 0 and balances[2] == 0:
        return True
    else:
        return False


@given(
    balances=st.tuples(
        billion_balance_strategy, billion_balance_strategy, billion_balance_strategy
    ),
    root_three_alpha=st.decimals(
        min_value=ROOT_ALPHA_MIN, max_value=ROOT_ALPHA_MAX, places=4
    ),
)
def test_calculate_cubic_terms(
    gyro_three_math_testing, balances: Tuple[int, int], root_three_alpha: Decimal
):
    assume(not faulty_params(balances, root_three_alpha))

    (a, mb, mc, md) = math_implementation.calculateCubicTerms(
        to_decimal(balances), to_decimal(root_three_alpha)
    )

    (a_sol, mb_sol, mc_sol, md_sol) = gyro_three_math_testing.calculateCubicTerms(
        scale(balances), scale(root_three_alpha)
    )

    assert a_sol == scale(a)
    assert mb_sol == scale(mb)
    assert mc_sol == scale(mc)
    assert md_sol == scale(md)


# @given(
#     balances=st.tuples(billion_balance_strategy, billion_balance_strategy, billion_balance_strategy),
#     root_three_alpha=st.decimals(min_value="0.02", max_value="0.99995", places=4),
# )
# def test_calculate_quadratic(gyro_three_math_testing, balances, root_three_alpha):
#     if faulty_params(balances, root_three_alpha):
#         return

#     (a, mb, mc) = math_implementation.calculateQuadraticTerms(
#         to_decimal(balances), to_decimal(root_three_alpha)
#     )

#     assert not any(v < 0 for v in [a, mb, mc])

#     root = math_implementation.calculateQuadratic(a, -mb, -mc)

#     root_sol = gyro_three_math_testing.calculateQuadratic(
#         scale(a), scale(mb), scale(mc)
#     )

#     assert int(root_sol) == scale(root).approxed()


def gen_balances_raw():
    return st.tuples(
        billion_balance_strategy, billion_balance_strategy, billion_balance_strategy
    )


@st.composite
def gen_balances(draw):
    balances = draw(gen_balances_raw())
    assume(balances[0] > 0 and balances[1] > 0 and balances[2] > 0)
    if balances[0] > 0:
        assume(min(balances[1], balances[2]) / balances[0] > MIN_BAL_RATIO)
    if balances[1] > 0:
        assume(min(balances[2], balances[0]) / balances[1] > MIN_BAL_RATIO)
    if balances[2] > 0:
        assume(min(balances[0], balances[1]) / balances[2] > MIN_BAL_RATIO)
    return balances


@st.composite
def gen_params_in_given_out(draw):
    balances = draw(gen_balances_raw())
    assume(balances[0] > 0 and balances[1] > 0 and balances[2] > 0)
    amount_out = draw(qdecimals("0", to_decimal(balances[1])))
    return balances, amount_out


@st.composite
def gen_params_out_given_in(draw):
    balances = draw(gen_balances_raw())
    assume(balances[0] > 0 and balances[1] > 0 and balances[2] > 0)
    amount_in = draw(qdecimals("0", to_decimal(balances[0])))
    return balances, amount_in


@given(
    setup=gen_params_in_given_out(),
    root_three_alpha=st.decimals(
        min_value=ROOT_ALPHA_MIN, max_value=ROOT_ALPHA_MAX, places=4
    ),
)
def test_calc_in_given_out(
    gyro_three_math_testing,
    root_three_alpha,
    setup,
):
    balances, amount_out = setup

    # assume(not faulty_params)

    assume(amount_out < to_decimal("0.3") * (balances[1]))

    invariant = unscale(
        gyro_three_math_testing.calculateInvariant(
            scale(balances), scale(root_three_alpha)
        )
    )

    virtual_offset = invariant * to_decimal(root_three_alpha)

    in_amount = math_implementation.calcInGivenOut(
        to_decimal(balances[0]),
        to_decimal(balances[1]),
        to_decimal(amount_out),
        virtual_offset,
    )

    bal_out_new, bal_in_new = (balances[0] + in_amount, balances[1] - amount_out)
    # if bal_out_new > bal_in_new:
    #     within_bal_ratio = bal_in_new / bal_out_new > MIN_BAL_RATIO
    # else:
    #     within_bal_ratio = bal_out_new / bal_in_new > MIN_BAL_RATIO

    if in_amount <= to_decimal("0.3") * balances[0]:  # and within_bal_ratio:
        in_amount_sol = unscale(
            gyro_three_math_testing.calcInGivenOut(
                scale(balances[0]),
                scale(balances[1]),
                scale(amount_out),
                scale(virtual_offset),
            )
        )
    # elif not within_bal_ratio:
    #     with reverts("BAL#357"):  # MIN_BAL_RATIO
    #         gyro_three_math_testing.calcInGivenOut(
    #             scale(balances[0]),
    #             scale(balances[1]),
    #             scale(amount_out),
    #             scale(virtual_offset),
    #         )
    #     return
    else:
        with reverts("BAL#304"):  # MAX_IN_RATIO
            gyro_three_math_testing.calcInGivenOut(
                scale(balances[0]),
                scale(balances[1]),
                scale(amount_out),
                scale(virtual_offset),
            )
        return

    # We don't get a truly exact match b/c of the safety margin used by the Solidity implementation. (this is not
    # implemented in python)
    assert in_amount_sol >= in_amount
    assert in_amount_sol == in_amount.approxed(abs=D("5e-18"), rel=D("5e-18"))


@given(
    setup=gen_params_out_given_in(),
    root_three_alpha=st.decimals(
        min_value=ROOT_ALPHA_MIN, max_value=ROOT_ALPHA_MAX, places=4
    ),
)
def test_calc_out_given_in(gyro_three_math_testing, root_three_alpha, setup):
    balances, amount_in = setup

    # assume(not faulty_params)
    assume(amount_in < to_decimal("0.3") * (balances[0]))

    invariant = unscale(
        gyro_three_math_testing.calculateInvariant(
            scale(balances), scale(root_three_alpha)
        )
    )

    virtual_offset = invariant * to_decimal(root_three_alpha)

    out_amount = math_implementation.calcOutGivenIn(
        to_decimal(balances[0]),
        to_decimal(balances[1]),
        to_decimal(amount_in),
        virtual_offset,
    )

    bal_out_new, bal_in_new = (balances[0] + amount_in, balances[1] - out_amount)
    # if bal_out_new > bal_in_new:
    #     within_bal_ratio = bal_in_new / bal_out_new > MIN_BAL_RATIO
    # else:
    #     within_bal_ratio = bal_out_new / bal_in_new > MIN_BAL_RATIO

    if (
        out_amount <= to_decimal("0.3") * balances[1]
        # and within_bal_ratio
        and out_amount >= 0
    ):
        out_amount_sol = unscale(
            gyro_three_math_testing.calcOutGivenIn(
                scale(balances[0]),
                scale(balances[1]),
                scale(amount_in),
                scale(virtual_offset),
            )
        )
    elif out_amount < 0:
        with reverts("BAL#001"):  # subtraction overflow when ~ 0 and rounding down
            gyro_three_math_testing.calcOutGivenIn(
                scale(balances[0]),
                scale(balances[1]),
                scale(amount_in),
                scale(virtual_offset),
            )
        return
    # elif not within_bal_ratio:
    #     with reverts("BAL#357"):  # MIN_BAL_RATIO
    #         gyro_three_math_testing.calcOutGivenIn(
    #             scale(balances[0]),
    #             scale(balances[1]),
    #             scale(amount_in),
    #             scale(virtual_offset),
    #         )
    #     return
    else:
        with reverts("BAL#305"):  # MAX_OUT_RATIO
            gyro_three_math_testing.calcOutGivenIn(
                scale(balances[0]),
                scale(balances[1]),
                scale(amount_in),
                scale(virtual_offset),
            )
        return

    # We don't get a truly exact match b/c of the safety margin used by the Solidity implementation. (this is not
    # implemented in python)
    assert out_amount_sol <= out_amount
    assert out_amount_sol == out_amount.approxed(abs=D("5e-18"), rel=D("5e-18"))


@given(
    l=qdecimals("1e12", "1e16"),
    root_three_alpha=st.decimals(
        min_value=ROOT_ALPHA_MIN, max_value=ROOT_ALPHA_MAX, places=4
    ),
)
@example(l=D("651894673872645.123456789012345678"), root_three_alpha=D(ROOT_ALPHA_MAX))
def test_safeLargePow3ADown(l, root_three_alpha, gyro_three_math_testing):
    l3 = l * l * l
    res_math_nod = l3 - l3 * root_three_alpha * root_three_alpha * root_three_alpha
    res_sol_nod = unscale(
        gyro_three_math_testing.safeLargePow3ADown(
            scale(l), scale(root_three_alpha), scale(1)
        )
    )
    assert res_math_nod == res_sol_nod.approxed(abs=D("2e-18"))

    d = (
        l * l * D("0.973894092617384965")
    )  # We only test the right order of magnitude. The factor is arbitrary.
    res_math_d = res_math_nod / d
    res_sol_d = unscale(
        gyro_three_math_testing.safeLargePow3ADown(
            scale(l), scale(root_three_alpha), scale(d)
        )
    )
    assert res_math_d == res_sol_d


@given(
    balances=st.tuples(
        billion_balance_strategy, billion_balance_strategy, billion_balance_strategy
    ),
    root_three_alpha=st.decimals(min_value="0.9", max_value=ROOT_ALPHA_MAX, places=4),
)
@example(balances=[D("1e10"), D(0), D(0)], root_three_alpha=D(ROOT_ALPHA_MAX))
# L = Decimal('99993316741847.981485422976711167')
# This is also *approximately* computed by Solidity. Wtf.
# Crash on L^3, but why?!
# Reason is that this is really too large: It's ≈ 9.99e13 and we can only represent - and calculate - L^3 for like L ≤ 4.8e13. So it's not even close.
# - [ ] Why doesn't it crash for Ari??
def test_calculate_invariant(
    gyro_three_math_testing, balances: Tuple[int, int, int], root_three_alpha
):

    assume(not faulty_params(balances, root_three_alpha))

    invariant = math_implementation.calculateInvariant(
        to_decimal(balances), to_decimal(root_three_alpha)
    )

    (a, b, c, d) = math_implementation.calculateCubicTerms(
        to_decimal(balances), root_three_alpha
    )

    roots = np.roots([a, -b, -c, -d])

    invariant_sol = unscale(
        gyro_three_math_testing.calculateInvariant(
            scale(balances), scale(root_three_alpha)
        )
    )

    assert invariant_sol == invariant.approxed(rel=D("5e-18"), abs=D("5e-18"))


@given(
    balances=gen_balances(),
    root_three_alpha=st.decimals(min_value="0.9", max_value=ROOT_ALPHA_MAX, places=4),
    # rootEst=st.decimals(min_value="1", max_value="100000000000", places=4),
)
def test_calcNewtonDelta(gyro_three_math_testing, balances, root_three_alpha):
    a, mb, mc, md = math_implementation.calculateCubicTerms(balances, root_three_alpha)
    rootEst = math_implementation.calculateCubic(
        a, mb, mc, md, root_three_alpha, balances
    )
    delta_abs, delta_is_pos = math_implementation.calcNewtonDelta(
        a, mb, mc, md, root_three_alpha, rootEst
    )
    delta_abs_sol, delta_is_pos_sol = gyro_three_math_testing.calcNewtonDelta(
        scale(a),
        scale(mb),
        scale(mc),
        scale(md),
        scale(root_three_alpha),
        scale(rootEst),
    )
    delta_abs_sol = unscale(delta_abs_sol)

    assert delta_abs_sol == delta_abs.approxed(abs=D("2e-18"))
    assert delta_is_pos == delta_is_pos_sol or delta_abs <= D("2e-18")
