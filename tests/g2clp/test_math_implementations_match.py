from decimal import Decimal
from typing import Tuple

import hypothesis.strategies as st
from brownie import reverts
from brownie.test import given
from hypothesis import assume
from tests.g2clp import math_implementation
from tests.libraries import pool_math_implementation
from tests.support.utils import scale, to_decimal, unscale

from tests.support.quantized_decimal import QuantizedDecimal as D

billion_balance_strategy = st.integers(min_value=0, max_value=100_000_000_000)

# this is a multiplicative separation
# This is consistent with tightest price range of 0.9999 - 1.0001
MIN_SQRTPARAM_SEPARATION = to_decimal("1.0001")
MIN_BAL_RATIO = to_decimal("0")


def faulty_params(balances, sqrt_alpha, sqrt_beta):
    balances = [to_decimal(b) for b in balances]
    if balances[0] == 0 and balances[1] == 0:
        return True
    return sqrt_beta <= sqrt_alpha * MIN_SQRTPARAM_SEPARATION


@given(
    balances=st.tuples(billion_balance_strategy, billion_balance_strategy),
    sqrt_alpha=st.decimals(min_value="0.02", max_value="0.99995"),
    sqrt_beta=st.decimals(min_value="1.00005", max_value="1.8"),
)
def test_calculate_quadratic_terms(
    gyro_two_math_testing,
    balances: Tuple[int, int],
    sqrt_alpha: Decimal,
    sqrt_beta: Decimal,
):
    assume(not faulty_params(balances, sqrt_alpha, sqrt_beta))

    (a, mb, b_square, mc) = math_implementation.calculateQuadraticTerms(
        to_decimal(balances), to_decimal(sqrt_alpha), to_decimal(sqrt_beta)
    )

    (
        a_sol,
        mb_sol,
        b_square_sol,
        mc_sol,
    ) = gyro_two_math_testing.calculateQuadraticTerms(
        scale(balances), scale(sqrt_alpha), scale(sqrt_beta)
    )

    assert a_sol == scale(a)
    assert mb_sol == scale(mb)
    assert b_square_sol == scale(b_square)
    assert mc_sol == scale(mc)


@given(
    balances=st.tuples(billion_balance_strategy, billion_balance_strategy),
    sqrt_alpha=st.decimals(min_value="0.02", max_value="0.99995"),
    sqrt_beta=st.decimals(min_value="1.00005", max_value="1.8"),
)
def test_calculate_quadratic(
    gyro_two_math_testing, balances: Tuple[int, int], sqrt_alpha, sqrt_beta
):
    assume(not faulty_params(balances, sqrt_alpha, sqrt_beta))

    (a, mb, b_square, mc) = math_implementation.calculateQuadraticTerms(
        to_decimal(balances), to_decimal(sqrt_alpha), to_decimal(sqrt_beta)
    )

    assert not any(v < 0 for v in [a, mb, mc])

    root = math_implementation.calculateQuadratic(a, -mb, b_square, -mc)

    root_sol = gyro_two_math_testing.calculateQuadratic(
        scale(a), scale(mb), scale(b_square), scale(mc)
    )

    assert int(root_sol) == scale(root).approxed(abs=D("5"))


@given(
    balances=st.tuples(billion_balance_strategy, billion_balance_strategy),
    sqrt_alpha=st.decimals(min_value="0.02", max_value="0.99995"),
    sqrt_beta=st.decimals(min_value="1.00005", max_value="1.8"),
)
def test_calculate_quadratic_special(
    gyro_two_math_testing, balances: Tuple[int, int], sqrt_alpha, sqrt_beta
):

    assume(not faulty_params(balances, sqrt_alpha, sqrt_beta))

    (a, mb, b_square, mc) = math_implementation.calculateQuadraticTerms(
        to_decimal(balances), to_decimal(sqrt_alpha), to_decimal(sqrt_beta)
    )

    root = math_implementation.calculateQuadraticSpecial(a, mb, b_square, mc)

    root_sol = gyro_two_math_testing.calculateQuadratic(
        scale(a), scale(mb), scale(b_square), scale(mc)
    )

    assert int(root_sol) == scale(root).approxed(abs=D("5"))


@given(
    balances=st.tuples(billion_balance_strategy, billion_balance_strategy),
    sqrt_alpha=st.decimals(min_value="0.02", max_value="0.99995"),
    sqrt_beta=st.decimals(min_value="1.00005", max_value="1.8"),
)
def test_calculate_invariant(
    gyro_two_math_testing, balances: Tuple[int, int], sqrt_alpha, sqrt_beta
):

    assume(not faulty_params(balances, sqrt_alpha, sqrt_beta))

    invariant = math_implementation.calculateInvariant(
        to_decimal(balances), to_decimal(sqrt_alpha), to_decimal(sqrt_beta)
    )

    invariant_sol = gyro_two_math_testing.calculateInvariant(
        scale(balances), scale(sqrt_alpha), scale(sqrt_beta)
    )

    assert D(invariant_sol) <= scale(invariant)
    assert D(invariant_sol) == scale(invariant).approxed(abs=D("5"))


@given(
    invariant=st.decimals(min_value="100", max_value="100000000"),
    sqrt_beta=st.decimals(min_value="1.00005", max_value="1.8"),
)
def test_calculate_virtual_parameter_0(gyro_two_math_testing, sqrt_beta, invariant):

    virtual_parameter = math_implementation.calculateVirtualParameter0(
        to_decimal(invariant), to_decimal(sqrt_beta)
    )

    virtual_parameter_sol = gyro_two_math_testing.calculateVirtualParameter0(
        scale(invariant), scale(sqrt_beta)
    )

    assert to_decimal(virtual_parameter_sol) == scale(virtual_parameter)


@given(
    invariant=st.decimals(min_value="100", max_value="100000000"),
    sqrt_alpha=st.decimals(min_value="0.02", max_value="0.99995"),
)
def test_calculate_virtual_parameter_1(gyro_two_math_testing, sqrt_alpha, invariant):

    virtual_parameter = math_implementation.calculateVirtualParameter1(
        to_decimal(invariant), to_decimal(sqrt_alpha)
    )

    virtual_parameter_sol = gyro_two_math_testing.calculateVirtualParameter1(
        scale(invariant), scale(sqrt_alpha)
    )

    assert to_decimal(virtual_parameter_sol) == scale(virtual_parameter)


@given(input=st.decimals(min_value="0", max_value="100000000"))
def test_calculate_sqrt(gyro_two_math_testing, input):

    sqrt = math_implementation.squareRoot(to_decimal(input))

    sqrt_sol = gyro_two_math_testing.sqrt(scale(input))

    assert to_decimal(sqrt_sol) == scale(sqrt).approxed(abs=D("5"))


@given(
    balances=st.tuples(billion_balance_strategy, billion_balance_strategy),
    amount_out=st.decimals(min_value="1", max_value="1000000"),
    sqrt_alpha=st.decimals(min_value="0.02", max_value="0.99995"),
    sqrt_beta=st.decimals(min_value="1.00005", max_value="1.8"),
)
def test_calc_in_given_out(
    gyro_two_math_testing, amount_out, balances: Tuple[int, int], sqrt_alpha, sqrt_beta
):
    assume(amount_out <= (balances[1]))
    assume(balances[0] > 0 and balances[1] > 0)

    assume(not faulty_params(balances, sqrt_alpha, sqrt_beta))

    invariant = math_implementation.calculateInvariant(
        to_decimal(balances), to_decimal(sqrt_alpha), to_decimal(sqrt_beta)
    )

    virtual_param_in = math_implementation.calculateVirtualParameter0(
        to_decimal(invariant), to_decimal(sqrt_beta)
    )

    virtual_param_out = math_implementation.calculateVirtualParameter1(
        to_decimal(invariant), to_decimal(sqrt_alpha)
    )

    in_amount = math_implementation.calcInGivenOut(
        to_decimal(balances[0]),
        to_decimal(balances[1]),
        to_decimal(amount_out),
        to_decimal(virtual_param_in),
        to_decimal(virtual_param_out),
    )

    in_amount_sol = unscale(
        gyro_two_math_testing.calcInGivenOut(
            scale(balances[0]),
            scale(balances[1]),
            scale(amount_out),
            scale(virtual_param_in),
            scale(virtual_param_out),
        )
    )

    # We don't get a truly exact match b/c of the safety margin used by the Solidity implementation. (this is not
    # implemented in python)
    assert in_amount_sol >= in_amount
    assert in_amount_sol == in_amount.approxed(abs=D("5e-18"), rel=D("5e-18"))


@given(
    balances=st.tuples(billion_balance_strategy, billion_balance_strategy),
    amount_in=st.decimals(min_value="1", max_value="1000000"),
    sqrt_alpha=st.decimals(min_value="0.02", max_value="0.99995"),
    sqrt_beta=st.decimals(min_value="1.00005", max_value="1.8"),
)
def test_calc_out_given_in(
    gyro_two_math_testing, amount_in, balances: Tuple[int, int], sqrt_alpha, sqrt_beta
):
    assume(balances[0] > 0 and balances[1] > 0)

    assume(not faulty_params(balances, sqrt_alpha, sqrt_beta))

    invariant = math_implementation.calculateInvariant(
        to_decimal(balances), to_decimal(sqrt_alpha), to_decimal(sqrt_beta)
    )

    virtual_param_in = math_implementation.calculateVirtualParameter0(
        to_decimal(invariant), to_decimal(sqrt_beta)
    )

    virtual_param_out = math_implementation.calculateVirtualParameter1(
        to_decimal(invariant), to_decimal(sqrt_alpha)
    )

    out_amount = math_implementation.calcOutGivenIn(
        to_decimal(balances[0]),
        to_decimal(balances[1]),
        to_decimal(amount_in),
        to_decimal(virtual_param_in),
        to_decimal(virtual_param_out),
    )

    if out_amount <= balances[1] and out_amount >= 0:
        out_amount_sol = unscale(
            gyro_two_math_testing.calcOutGivenIn(
                scale(balances[0]),
                scale(balances[1]),
                scale(amount_in),
                scale(virtual_param_in),
                scale(virtual_param_out),
            )
        )
    elif out_amount < 0:
        with reverts("BAL#001"):  # subtraction overflow when ~ 0 and rounding down
            gyro_two_math_testing.calcOutGivenIn(
                scale(balances[0]),
                scale(balances[1]),
                scale(amount_in),
                scale(virtual_param_in),
                scale(virtual_param_out),
            )
        return
    else:
        with reverts("GYR#357"):  # ASSET_BOUNDS_EXCEEDED
            gyro_two_math_testing.calcOutGivenIn(
                scale(balances[0]),
                scale(balances[1]),
                scale(amount_in),
                scale(virtual_param_in),
                scale(virtual_param_out),
            )
        return

    # We don't get a truly exact match b/c of the safety margin used by the Solidity implementation. (this is not
    # implemented in python)
    assert out_amount_sol <= out_amount
    assert out_amount_sol == out_amount.approxed(abs=D("5e-18"), rel=D("5e-18"))
