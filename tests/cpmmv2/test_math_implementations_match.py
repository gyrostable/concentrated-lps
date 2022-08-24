from decimal import Decimal
from typing import Tuple

import hypothesis.strategies as st
from brownie.test import given
from tests.cpmmv2 import math_implementation
from tests.support.utils import scale, to_decimal

billion_balance_strategy = st.integers(min_value=0, max_value=1_000_000_000)

# this is a multiplicative separation
# This is consistent with tightest price range of 0.9999 - 1.0001
MIN_SQRTPARAM_SEPARATION = to_decimal("1.0001")


def faulty_params(balances, sqrt_alpha, sqrt_beta):
    balances = [to_decimal(b) for b in balances]
    if balances[0] == 0 and balances[1] == 0:
        return True
    return sqrt_beta <= sqrt_alpha * MIN_SQRTPARAM_SEPARATION


@given(
    balances=st.tuples(billion_balance_strategy, billion_balance_strategy),
    sqrt_alpha=st.decimals(min_value="0.02", max_value="0.99995", places=4),
    sqrt_beta=st.decimals(min_value="1.00005", max_value="1.8", places=4),
)
def test_calculate_quadratic_terms(
    gyro_two_math_testing,
    balances: Tuple[int, int],
    sqrt_alpha: Decimal,
    sqrt_beta: Decimal,
):
    if faulty_params(balances, sqrt_alpha, sqrt_beta):
        return

    (a, mb, mc) = math_implementation.calculateQuadraticTerms(
        to_decimal(balances), to_decimal(sqrt_alpha), to_decimal(sqrt_beta)
    )

    (a_sol, mb_sol, mc_sol) = gyro_two_math_testing.calculateQuadraticTerms(
        scale(balances), scale(sqrt_alpha), scale(sqrt_beta)
    )

    assert a_sol == scale(a)
    assert mb_sol == scale(mb)
    assert mc_sol == scale(mc)


@given(
    balances=st.tuples(billion_balance_strategy, billion_balance_strategy),
    sqrt_alpha=st.decimals(min_value="0.02", max_value="0.99995", places=4),
    sqrt_beta=st.decimals(min_value="1.00005", max_value="1.8", places=4),
)
def test_calculate_quadratic(
    gyro_two_math_testing, balances: Tuple[int, int], sqrt_alpha, sqrt_beta
):
    if faulty_params(balances, sqrt_alpha, sqrt_beta):
        return

    (a, mb, mc) = math_implementation.calculateQuadraticTerms(
        to_decimal(balances), to_decimal(sqrt_alpha), to_decimal(sqrt_beta)
    )

    assert not any(v < 0 for v in [a, mb, mc])

    root = math_implementation.calculateQuadratic(a, -mb, -mc)

    root_sol = gyro_two_math_testing.calculateQuadratic(scale(a), scale(mb), scale(mc))

    assert int(root_sol) == scale(root).approxed()


@given(
    balances=st.tuples(billion_balance_strategy, billion_balance_strategy),
    sqrt_alpha=st.decimals(min_value="0.02", max_value="0.99995", places=4),
    sqrt_beta=st.decimals(min_value="1.00005", max_value="1.8", places=4),
)
def test_calculate_quadratic_special(
    gyro_two_math_testing, balances: Tuple[int, int], sqrt_alpha, sqrt_beta
):

    if faulty_params(balances, sqrt_alpha, sqrt_beta):
        return

    (a, mb, mc) = math_implementation.calculateQuadraticTerms(
        to_decimal(balances), to_decimal(sqrt_alpha), to_decimal(sqrt_beta)
    )

    root = math_implementation.calculateQuadraticSpecial(a, mb, mc)

    root_sol = gyro_two_math_testing.calculateQuadratic(scale(a), scale(mb), scale(mc))

    assert int(root_sol) == scale(root).approxed()


@given(
    balances=st.tuples(billion_balance_strategy, billion_balance_strategy),
    sqrt_alpha=st.decimals(min_value="0.02", max_value="0.99995", places=4),
    sqrt_beta=st.decimals(min_value="1.00005", max_value="1.8", places=4),
)
def test_calculate_invariant(
    gyro_two_math_testing, balances: Tuple[int, int], sqrt_alpha, sqrt_beta
):

    if faulty_params(balances, sqrt_alpha, sqrt_beta):
        return

    (a, mb, mc) = math_implementation.calculateQuadraticTerms(
        to_decimal(balances), to_decimal(sqrt_alpha), to_decimal(sqrt_beta)
    )

    invariant = math_implementation.calculateInvariant(
        to_decimal(balances), to_decimal(sqrt_alpha), to_decimal(sqrt_beta)
    )

    invariant_sol = gyro_two_math_testing.calculateInvariant(
        scale(balances), scale(sqrt_alpha), scale(sqrt_beta)
    )

    assert to_decimal(invariant_sol) == scale(invariant).approxed(abs=1e15)


@given(
    invariant=st.decimals(min_value="100", max_value="100000000", places=4),
    sqrt_beta=st.decimals(min_value="1.00005", max_value="1.8", places=4),
)
def test_calculate_virtual_parameter_0(gyro_two_math_testing, sqrt_beta, invariant):

    virtual_parameter = math_implementation.calculateVirtualParameter0(
        to_decimal(invariant), to_decimal(sqrt_beta)
    )

    virtual_parameter_sol = gyro_two_math_testing.calculateVirtualParameter0(
        scale(invariant), scale(sqrt_beta)
    )

    assert to_decimal(virtual_parameter_sol) == scale(virtual_parameter).approxed()


@given(
    invariant=st.decimals(min_value="100", max_value="100000000", places=4),
    sqrt_alpha=st.decimals(min_value="0.02", max_value="0.99995", places=4),
)
def test_calculate_virtual_parameter_1(gyro_two_math_testing, sqrt_alpha, invariant):

    virtual_parameter = math_implementation.calculateVirtualParameter1(
        to_decimal(invariant), to_decimal(sqrt_alpha)
    )

    virtual_parameter_sol = gyro_two_math_testing.calculateVirtualParameter1(
        scale(invariant), scale(sqrt_alpha)
    )

    assert to_decimal(virtual_parameter_sol) == scale(virtual_parameter).approxed()


@given(
    invariant=st.decimals(min_value="100", max_value="100000000", places=4),
    virtual_x=st.decimals(min_value="100", max_value="1000000000", places=4),
)
def test_calculate_sqrt_price(gyro_two_math_testing, invariant, virtual_x):

    sqrt_price = math_implementation.calculateSqrtPrice(
        to_decimal(invariant), to_decimal(virtual_x)
    )

    sqrt_price_sol = gyro_two_math_testing.calculateSqrtPrice(
        scale(invariant), scale(virtual_x)
    )

    assert to_decimal(sqrt_price_sol) == scale(sqrt_price).approxed()


@given(
    balances=st.tuples(billion_balance_strategy, billion_balance_strategy),
    sqrt_alpha=st.decimals(min_value="0.02", max_value="0.99995", places=4),
    sqrt_beta=st.decimals(min_value="1.00005", max_value="1.8", places=4),
    delta_balances=st.tuples(billion_balance_strategy, billion_balance_strategy),
)
def test_liquidity_invariant_update(
    gyro_two_math_testing,
    balances: Tuple[int, int],
    sqrt_alpha,
    sqrt_beta,
    delta_balances: Tuple[int, int],
):

    if faulty_params(balances, sqrt_alpha, sqrt_beta):
        return

    last_invariant = math_implementation.calculateInvariant(
        to_decimal(balances), to_decimal(sqrt_alpha), to_decimal(sqrt_beta)
    )

    new_invariant = math_implementation.liquidityInvariantUpdate(
        to_decimal(balances),
        to_decimal(sqrt_alpha),
        to_decimal(sqrt_beta),
        to_decimal(last_invariant),
        to_decimal(delta_balances),
        True,
    )

    if new_invariant < 0:
        return

    new_invariant_sol = gyro_two_math_testing.liquidityInvariantUpdate(
        scale(balances),
        scale(sqrt_alpha),
        scale(sqrt_beta),
        scale(last_invariant),
        scale(delta_balances),
        True,
    )

    assert to_decimal(new_invariant_sol) == scale(new_invariant).approxed()


@given(input=st.decimals(min_value="0", max_value="100000000", places=4))
def test_calculate_sqrt(gyro_two_math_testing, input):

    sqrt = math_implementation.squareRoot(to_decimal(input))

    sqrt_sol = gyro_two_math_testing.sqrt(scale(input))

    assert to_decimal(sqrt_sol) == scale(sqrt).approxed()


@given(
    balances=st.tuples(billion_balance_strategy, billion_balance_strategy),
    amount_out=st.decimals(min_value="1", max_value="1000000", places=4),
    sqrt_alpha=st.decimals(min_value="0.02", max_value="0.99995", places=4),
    sqrt_beta=st.decimals(min_value="1.00005", max_value="1.8", places=4),
)
def test_calc_in_given_out(
    gyro_two_math_testing, amount_out, balances: Tuple[int, int], sqrt_alpha, sqrt_beta
):

    if amount_out > to_decimal("0.3") * (balances[1]):
        return

    if faulty_params(balances, sqrt_alpha, sqrt_beta):
        return

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
        to_decimal(invariant),
    )

    in_amount_sol = gyro_two_math_testing.calcInGivenOut(
        scale(balances[0]),
        scale(balances[1]),
        scale(amount_out),
        scale(virtual_param_in),
        scale(virtual_param_out),
        scale(invariant),
    )

    assert to_decimal(in_amount_sol) == scale(in_amount).approxed()


@given(
    balances=st.tuples(billion_balance_strategy, billion_balance_strategy),
    amount_in=st.decimals(min_value="1", max_value="1000000", places=4),
    sqrt_alpha=st.decimals(min_value="0.02", max_value="0.99995", places=4),
    sqrt_beta=st.decimals(min_value="1.00005", max_value="1.8", places=4),
)
def test_calc_out_given_in(
    gyro_two_math_testing, amount_in, balances: Tuple[int, int], sqrt_alpha, sqrt_beta
):

    if amount_in > to_decimal("0.3") * (balances[0]):
        return

    if faulty_params(balances, sqrt_alpha, sqrt_beta):
        return

    invariant = math_implementation.calculateInvariant(
        to_decimal(balances), to_decimal(sqrt_alpha), to_decimal(sqrt_beta)
    )

    virtual_param_in = math_implementation.calculateVirtualParameter0(
        to_decimal(invariant), to_decimal(sqrt_beta)
    )

    virtual_param_out = math_implementation.calculateVirtualParameter1(
        to_decimal(invariant), to_decimal(sqrt_alpha)
    )

    in_amount = math_implementation.calcOutGivenIn(
        to_decimal(balances[0]),
        to_decimal(balances[1]),
        to_decimal(amount_in),
        to_decimal(virtual_param_in),
        to_decimal(virtual_param_out),
        to_decimal(invariant),
    )

    in_amount_sol = gyro_two_math_testing.calcOutGivenIn(
        scale(balances[0]),
        scale(balances[1]),
        scale(amount_in),
        scale(virtual_param_in),
        scale(virtual_param_out),
        scale(invariant),
    )

    assert to_decimal(in_amount_sol) == scale(in_amount).approxed()


@given(
    balances=st.tuples(billion_balance_strategy, billion_balance_strategy),
    bpt_amount_out=st.decimals(min_value="1", max_value="1000000", places=4),
    total_bpt=st.decimals(min_value="1", max_value="1000000", places=4),
)
def test_all_tokens_in_given_exact_bpt_out(
    gyro_two_math_testing, balances: Tuple[int, int], bpt_amount_out, total_bpt
):

    if total_bpt < bpt_amount_out:
        return

    amounts_in = math_implementation.calcAllTokensInGivenExactBptOut(
        to_decimal(balances), to_decimal(bpt_amount_out), to_decimal(total_bpt)
    )

    amounts_in_sol = gyro_two_math_testing.calcAllTokensInGivenExactBptOut(
        scale(balances), scale(bpt_amount_out), scale(total_bpt)
    )

    if amounts_in_sol[0] == 1 or amounts_in_sol[1] == 1:
        return

    assert to_decimal(amounts_in_sol[0]) == scale(amounts_in[0]).approxed()
    assert to_decimal(amounts_in_sol[1]) == scale(amounts_in[1]).approxed()


@given(
    balances=st.tuples(billion_balance_strategy, billion_balance_strategy),
    bpt_amount_in=st.decimals(min_value="1", max_value="1000000", places=4),
    total_bpt=st.decimals(min_value="1", max_value="1000000", places=4),
)
def test_tokens_out_given_exact_bpt_in(
    gyro_two_math_testing, balances: Tuple[int, int], bpt_amount_in, total_bpt
):

    if total_bpt < bpt_amount_in:
        return

    amounts_in = math_implementation.calcAllTokensInGivenExactBptOut(
        to_decimal(balances), to_decimal(bpt_amount_in), to_decimal(total_bpt)
    )

    amounts_in_sol = gyro_two_math_testing.calcAllTokensInGivenExactBptOut(
        scale(balances), scale(bpt_amount_in), scale(total_bpt)
    )

    if amounts_in_sol[0] == 1 or amounts_in_sol[1] == 1:
        return

    assert to_decimal(amounts_in_sol[0]) == scale(amounts_in[0]).approxed()
    assert to_decimal(amounts_in_sol[1]) == scale(amounts_in[1]).approxed()


@given(
    balances=st.tuples(billion_balance_strategy, billion_balance_strategy),
    sqrt_alpha=st.decimals(min_value="0.02", max_value="0.99995", places=4),
    delta_balances=st.tuples(billion_balance_strategy, billion_balance_strategy),
    sqrt_beta=st.decimals(min_value="1.00005", max_value="1.8", places=4),
    current_bpt_supply=st.decimals(min_value="1", max_value="1000000", places=4),
    protocol_fee_gyro_portion=st.decimals(min_value="0.00", max_value="0.5", places=4),
    protocol_swap_fee_percentage=st.decimals(
        min_value="0.0", max_value="0.4", places=4
    ),
)
def test_protocol_fees(
    gyro_two_math_testing,
    balances: Tuple[int, int],
    sqrt_alpha,
    sqrt_beta,
    delta_balances: Tuple[int, int],
    current_bpt_supply,
    protocol_swap_fee_percentage,
    protocol_fee_gyro_portion,
):

    if faulty_params(balances, sqrt_alpha, sqrt_beta):
        return

    old_invariant = math_implementation.calculateInvariant(
        to_decimal(balances), to_decimal(sqrt_alpha), to_decimal(sqrt_beta)
    )

    new_invariant = math_implementation.liquidityInvariantUpdate(
        to_decimal(balances),
        to_decimal(sqrt_alpha),
        to_decimal(sqrt_beta),
        to_decimal(old_invariant),
        to_decimal(delta_balances),
        True,
    )

    protocol_fees = math_implementation.calcProtocolFees(
        to_decimal(old_invariant),
        to_decimal(new_invariant),
        to_decimal(current_bpt_supply),
        to_decimal(protocol_swap_fee_percentage),
        to_decimal(protocol_fee_gyro_portion),
    )

    protocol_fees_sol = gyro_two_math_testing.calcProtocolFees(
        scale(old_invariant),
        scale(new_invariant),
        scale(current_bpt_supply),
        scale(protocol_swap_fee_percentage),
        scale(protocol_fee_gyro_portion),
    )

    assert to_decimal(protocol_fees_sol[0]) == scale(protocol_fees[0])
    assert to_decimal(protocol_fees_sol[1]) == scale(protocol_fees[1])
