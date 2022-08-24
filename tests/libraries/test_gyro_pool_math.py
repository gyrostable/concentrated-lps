from decimal import Decimal
from typing import Tuple

import hypothesis.strategies as st
from brownie import reverts
from brownie.test import given
from hypothesis import assume
from tests.libraries import pool_math_implementation
from tests.support.utils import scale, to_decimal, qdecimals, unscale
from tests.support.quantized_decimal import QuantizedDecimal as D


billion_balance_strategy = st.integers(min_value=0, max_value=1_000_000_000)


def faulty_params(balances):
    balances = [to_decimal(b) for b in balances]
    if sum(balances) == 0:
        return True


def calc_delta_balances(balances, delta_bal_scaling):
    delta_balances = [b * delta_bal_scaling for b in balances]
    return tuple(delta_balances)


@st.composite
def gen_params_liquidityUpdate(draw):
    balances = draw(st.tuples(billion_balance_strategy, billion_balance_strategy))
    assume(not faulty_params(balances))
    bpt_supply = draw(qdecimals(D("1e-4") * max(balances), D("1e6") * max(balances)))
    isIncrease = draw(st.booleans())
    if isIncrease:
        dsupply = draw(qdecimals(D("1e-5"), D("1e4") * bpt_supply))
    else:
        dsupply = draw(qdecimals(D("1e-5"), D("0.99") * bpt_supply))
    return balances, bpt_supply, isIncrease, dsupply


#######################################
@given(
    params=gen_params_liquidityUpdate(),
    invariant=st.decimals(min_value="100", max_value="1000000000000000000"),
)
def test_liquidity_invariant_update_deltaBptTokens(
    gyro_two_math_testing, params, invariant
):
    balances, bpt_supply, isIncrease, dsupply = params
    new_invariant = pool_math_implementation.liquidityInvariantUpdate_deltaBptTokens(
        invariant, dsupply, bpt_supply, isIncrease
    )

    new_invariant_sol = gyro_two_math_testing.liquidityInvariantUpdate(
        scale(invariant), scale(dsupply), scale(bpt_supply), isIncrease
    )

    assert unscale(new_invariant_sol) == D(new_invariant)


# #######################################
# @given(
#     balances=st.tuples(billion_balance_strategy, billion_balance_strategy),
#     last_invariant=st.decimals(
#         min_value="100", max_value="1000000000000000000"
#     ),
#     delta_bal_scaling=st.decimals(min_value="0", max_value="10"),
# )
# def test_liquidity_invariant_update_add(
#     gyro_two_math_testing,
#     balances: Tuple[int, int],
#     last_invariant,
#     delta_bal_scaling,
# ):

#     assume(not faulty_params(balances))
#     delta_balances = calc_delta_balances(balances, delta_bal_scaling)

#     new_invariant = pool_math_implementation.liquidityInvariantUpdate_deltaBalances(
#         to_decimal(balances),
#         to_decimal(last_invariant),
#         to_decimal(delta_balances),
#         True,
#     )

#     new_invariant_sol = gyro_two_math_testing.liquidityInvariantUpdate(
#         scale(balances),
#         scale(last_invariant),
#         scale(delta_balances),
#         True,
#     )

#     assert to_decimal(new_invariant_sol) == scale(new_invariant)


# #######################################
# @given(
#     balances=st.tuples(billion_balance_strategy, billion_balance_strategy),
#     last_invariant=st.decimals(
#         min_value="100", max_value="1000000000000000000"
#     ),
#     delta_bal_scaling=st.decimals(min_value="0", max_value="0.99"),
# )
# def test_liquidity_invariant_update_remove(
#     gyro_two_math_testing,
#     balances: Tuple[int, int],
#     last_invariant,
#     delta_bal_scaling,
# ):

#     assume(not faulty_params(balances))
#     delta_balances = calc_delta_balances(balances, delta_bal_scaling)

#     new_invariant = pool_math_implementation.liquidityInvariantUpdate_deltaBalances(
#         to_decimal(balances),
#         to_decimal(last_invariant),
#         to_decimal(delta_balances),
#         False,
#     )

#     new_invariant_sol = gyro_two_math_testing.liquidityInvariantUpdate(
#         scale(balances),
#         scale(last_invariant),
#         scale(delta_balances),
#         False,
#     )

#     assert to_decimal(new_invariant_sol) == scale(new_invariant)


#######################################
@given(
    balances=st.tuples(billion_balance_strategy, billion_balance_strategy),
    bpt_amount_out=st.decimals(min_value="1", max_value="1000000"),
    total_bpt=st.decimals(min_value="1", max_value="100000000000"),
)
def test_all_tokens_in_given_exact_bpt_out(
    gyro_two_math_testing, balances: Tuple[int, int], bpt_amount_out, total_bpt
):
    assume(total_bpt > bpt_amount_out)
    assume(not faulty_params(balances))

    amounts_in = pool_math_implementation.calcAllTokensInGivenExactBptOut(
        to_decimal(balances), to_decimal(bpt_amount_out), to_decimal(total_bpt)
    )

    amounts_in_sol = gyro_two_math_testing.calcAllTokensInGivenExactBptOut(
        scale(balances), scale(bpt_amount_out), scale(total_bpt)
    )

    assert to_decimal(amounts_in_sol[0]) == scale(amounts_in[0])
    assert to_decimal(amounts_in_sol[1]) == scale(amounts_in[1])


#######################################
@given(
    balances=st.tuples(billion_balance_strategy, billion_balance_strategy),
    bpt_amount_in=st.decimals(min_value="1", max_value="1000000"),
    total_bpt=st.decimals(min_value="1", max_value="100000000000"),
)
def test_tokens_out_given_exact_bpt_in(
    gyro_two_math_testing, balances: Tuple[int, int], bpt_amount_in, total_bpt
):
    assume(total_bpt > bpt_amount_in)
    assume(not faulty_params(balances))

    amounts_out = pool_math_implementation.calcTokensOutGivenExactBptIn(
        to_decimal(balances), to_decimal(bpt_amount_in), to_decimal(total_bpt)
    )

    amounts_out_sol = gyro_two_math_testing.calcTokensOutGivenExactBptIn(
        scale(balances), scale(bpt_amount_in), scale(total_bpt)
    )

    assert to_decimal(amounts_out_sol[0]) == scale(amounts_out[0])
    assert to_decimal(amounts_out_sol[1]) == scale(amounts_out[1])


#######################################
@given(
    old_invariant=st.decimals(min_value="100", max_value="1000000000000000000"),
    new_invariant=st.decimals(min_value="100", max_value="1000000000000000000"),
    current_bpt_supply=st.decimals(min_value="1", max_value="1000000"),
    protocol_fee_gyro_portion=st.decimals(min_value="0.00", max_value="0.5"),
    protocol_swap_fee_percentage=st.decimals(min_value="0.0", max_value="0.4"),
)
def test_protocol_fees(
    gyro_two_math_testing,
    old_invariant,
    new_invariant,
    current_bpt_supply,
    protocol_swap_fee_percentage,
    protocol_fee_gyro_portion,
):
    protocol_fees = pool_math_implementation.calcProtocolFees(
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


########### also test with 3 assets
#######################################
# @given(
#     balances=st.tuples(
#         billion_balance_strategy, billion_balance_strategy, billion_balance_strategy
#     ),
#     last_invariant=st.decimals(
#         min_value="100", max_value="1000000000000000000"
#     ),
#     delta_bal_scaling=st.decimals(min_value="0", max_value="10"),
# )
# def test_liquidity_invariant_update_add_3(
#     gyro_three_math_testing,
#     balances: Tuple[int, int, int],
#     last_invariant,
#     delta_bal_scaling,
# ):

#     assume(not faulty_params(balances))
#     delta_balances = calc_delta_balances(balances, delta_bal_scaling)

#     new_invariant = pool_math_implementation.liquidityInvariantUpdate_deltaBalances(
#         to_decimal(balances),
#         to_decimal(last_invariant),
#         to_decimal(delta_balances),
#         True,
#     )

#     new_invariant_sol = gyro_three_math_testing.liquidityInvariantUpdate(
#         scale(balances),
#         scale(last_invariant),
#         scale(delta_balances),
#         True,
#     )

#     assert to_decimal(new_invariant_sol) == scale(new_invariant)


# #######################################
# @given(
#     balances=st.tuples(
#         billion_balance_strategy, billion_balance_strategy, billion_balance_strategy
#     ),
#     last_invariant=st.decimals(
#         min_value="100", max_value="1000000000000000000"
#     ),
#     delta_bal_scaling=st.decimals(min_value="0", max_value="0.99"),
# )
# def test_liquidity_invariant_update_remove_3(
#     gyro_three_math_testing,
#     balances: Tuple[int, int, int],
#     last_invariant,
#     delta_bal_scaling,
# ):

#     assume(not faulty_params(balances))
#     delta_balances = calc_delta_balances(balances, delta_bal_scaling)

#     new_invariant = pool_math_implementation.liquidityInvariantUpdate_deltaBalances(
#         to_decimal(balances),
#         to_decimal(last_invariant),
#         to_decimal(delta_balances),
#         False,
#     )

#     new_invariant_sol = gyro_three_math_testing.liquidityInvariantUpdate(
#         scale(balances),
#         scale(last_invariant),
#         scale(delta_balances),
#         False,
#     )

#     assert to_decimal(new_invariant_sol) == scale(new_invariant)


#######################################
@given(
    balances=st.tuples(
        billion_balance_strategy, billion_balance_strategy, billion_balance_strategy
    ),
    bpt_amount_out=st.decimals(min_value="1", max_value="1000000"),
    total_bpt=st.decimals(min_value="1", max_value="100000000000"),
)
def test_all_tokens_in_given_exact_bpt_out_3(
    gyro_three_math_testing, balances: Tuple[int, int, int], bpt_amount_out, total_bpt
):
    assume(total_bpt > bpt_amount_out)
    assume(not faulty_params(balances))

    amounts_in = pool_math_implementation.calcAllTokensInGivenExactBptOut(
        to_decimal(balances), to_decimal(bpt_amount_out), to_decimal(total_bpt)
    )

    amounts_in_sol = gyro_three_math_testing.calcAllTokensInGivenExactBptOut(
        scale(balances), scale(bpt_amount_out), scale(total_bpt)
    )

    assert to_decimal(amounts_in_sol[0]) == scale(amounts_in[0])
    assert to_decimal(amounts_in_sol[1]) == scale(amounts_in[1])
    assert to_decimal(amounts_in_sol[2]) == scale(amounts_in[2])


#######################################
@given(
    balances=st.tuples(
        billion_balance_strategy, billion_balance_strategy, billion_balance_strategy
    ),
    bpt_amount_in=st.decimals(min_value="1", max_value="1000000"),
    total_bpt=st.decimals(min_value="1", max_value="1000000"),
)
def test_tokens_out_given_exact_bpt_in_3(
    gyro_three_math_testing, balances: Tuple[int, int, int], bpt_amount_in, total_bpt
):
    assume(total_bpt > bpt_amount_in)
    assume(not faulty_params(balances))

    amounts_out = pool_math_implementation.calcTokensOutGivenExactBptIn(
        to_decimal(balances), to_decimal(bpt_amount_in), to_decimal(total_bpt)
    )

    amounts_out_sol = gyro_three_math_testing.calcTokensOutGivenExactBptIn(
        scale(balances), scale(bpt_amount_in), scale(total_bpt)
    )

    assert to_decimal(amounts_out_sol[0]) == scale(amounts_out[0])
    assert to_decimal(amounts_out_sol[1]) == scale(amounts_out[1])
    assert to_decimal(amounts_out_sol[2]) == scale(amounts_out[2])
