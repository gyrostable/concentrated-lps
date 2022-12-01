from operator import sub, add

import pytest
from brownie import ZERO_ADDRESS

from tests.geclp.util import params2MathParams
from tests.conftest import TOKENS_PER_USER
from tests.g2clp import constants
from tests.support.types import (
    CallJoinPoolGyroParams,
    SwapKind,
    SwapRequest,
    ECLPMathParams,
)
from tests.support.utils import approxed, unscale, to_decimal

from tests.geclp import eclp as math_implementation
from tests.geclp import eclp_prec_implementation as prec_impl


def test_empty_erc20s(admin, gyro_erc20_empty):
    for token in range(constants.NUM_TOKENS):
        gyro_erc20_empty[token].mint(admin, TOKENS_PER_USER)
        assert gyro_erc20_empty[token].totalSupply() == TOKENS_PER_USER


def test_funded_erc20s(users, gyro_erc20_funded):
    for token in range(constants.NUM_TOKENS):
        assert (
            gyro_erc20_funded[token].totalSupply()
            == TOKENS_PER_USER * constants.NUM_USERS
        )
        for user in range(constants.NUM_USERS):
            assert gyro_erc20_funded[token].balanceOf(users[user]) == TOKENS_PER_USER


def test_pool_reg(mock_vault, eclp_pool, gyro_erc20_funded):
    poolId = eclp_pool.getPoolId()
    print("Pool ID", poolId)

    # Check pool and token registration
    (token_addresses, token_balances) = mock_vault.getPoolTokens(poolId)

    for token in range(constants.NUM_TOKENS):
        assert token_addresses[token] == gyro_erc20_funded[token].address
        assert token_balances[token] == 0


# def test_pool_constructor(eclp_pool):
#     assert eclp_pool.getSwapFeePercentage() == 1 * 10**15
#     assert eclp_pool.getNormalizedWeights() == (0.6 * 10**18, 0.4 * 10**18)


def join_pool(
    vault,
    pool_address,
    sender,
    balances,
    amount_in,
    recipient=None,
    pool_id=0,
    protocol_swap_fees=0,
    last_change_block=0,
    amount_out=0,
):
    if recipient is None:
        recipient = sender
    return vault.callJoinPoolGyro(
        CallJoinPoolGyroParams(
            pool_address,
            pool_id,
            sender,
            recipient,
            balances,
            last_change_block,
            protocol_swap_fees,
            [amount_in, amount_in],
            amount_out,
        )
    )


def test_pool_on_initialize(users, eclp_pool, mock_vault):
    balances = (0, 0)
    amountIn = 100 * 10**18

    tx = join_pool(mock_vault, eclp_pool.address, users[0], balances, amountIn)

    poolId = eclp_pool.getPoolId()

    # Check Pool balance change
    assert tx.events["PoolBalanceChanged"]["poolId"] == poolId
    assert tx.events["PoolBalanceChanged"]["liquidityProvider"] == users[0]

    assert tx.events["PoolBalanceChanged"]["deltas"] == (amountIn, amountIn)
    assert tx.events["PoolBalanceChanged"]["protocolFees"] == (0, 0)

    # Check BPT Token minting
    assert tx.events["Transfer"][1]["from"] == ZERO_ADDRESS
    assert tx.events["Transfer"][1]["to"] == users[0]
    initial_bpt_tokens = tx.events["Transfer"][1]["value"]
    assert initial_bpt_tokens > 0

    # Check that the amountIn is now stored in the pool balance
    (_, initial_balances) = mock_vault.getPoolTokens(poolId)
    assert initial_balances[0] == amountIn
    assert initial_balances[1] == amountIn


def test_pool_view_methods(users, eclp_pool, mock_vault):
    balances = (0, 0)
    amountIn = 100 * 10**18

    tx = join_pool(mock_vault, eclp_pool.address, users[0], balances, amountIn)

    eclp_params = eclp_pool.getECLPParams()
    # Not testing anything here.

    # SOMEDAY when new view methods are added, these should be tested here.


def test_pool_on_join(users, eclp_pool, mock_vault, gyro_eclp_math_testing):
    amount_in = 100 * 10**18

    tx = join_pool(mock_vault, eclp_pool.address, users[0], (0, 0), amount_in)

    initial_bpt_tokens = tx.events["Transfer"][1]["value"]

    sparams, sdparams = eclp_pool.getECLPParams()

    # Check pool's invariant after initialization
    currentInvariant = eclp_pool.getLastInvariant()

    balancesBeforeJoin = [amount_in, amount_in]
    bptSupplyBeforeJoin = eclp_pool.totalSupply()
    sInvariant = gyro_eclp_math_testing.calculateInvariant(
        balancesBeforeJoin, sparams, sdparams
    )

    assert currentInvariant == sInvariant

    poolId = eclp_pool.getPoolId()
    (_, initial_balances) = mock_vault.getPoolTokens(poolId)

    ##################################################
    ## Add liqudidity to an already initialized pool
    ##################################################
    tx = join_pool(
        mock_vault,
        eclp_pool.address,
        users[1],
        initial_balances,
        amount_in,
        amount_out=eclp_pool.totalSupply(),
    )

    ## Check Pool balance Change
    assert tx.events["PoolBalanceChanged"]["liquidityProvider"] == users[1]

    assert tx.events["PoolBalanceChanged"]["deltas"] == (amount_in, amount_in)

    ## Check BTP Token minting
    assert tx.events["Transfer"][0]["from"] == ZERO_ADDRESS
    assert tx.events["Transfer"][0]["to"] == users[1]
    bptTokensNew = tx.events["Transfer"][0]["value"]
    assert bptTokensNew > 0
    assert float(bptTokensNew) == pytest.approx(initial_bpt_tokens)
    # ^ NB this only works b/c we use the same amounts. - Which is ok & the right thing to do, it should be relative!

    (_, balancesAfterJoin) = mock_vault.getPoolTokens(poolId)
    assert balancesAfterJoin[0] == amount_in * 2
    assert balancesAfterJoin[1] == amount_in * 2

    deltaBalances = [amount_in, amount_in]
    assert list(balancesAfterJoin) == list(
        map(add, balancesBeforeJoin, deltaBalances)
    )  # sanity check

    ## Check new pool's invariant
    newInvariant = eclp_pool.getLastInvariant()
    assert newInvariant > currentInvariant

    currentInvariant = newInvariant

    sInvariant = gyro_eclp_math_testing.liquidityInvariantUpdate(
        sInvariant,
        bptSupplyBeforeJoin,
        bptSupplyBeforeJoin,
        True,
    )

    assert currentInvariant == sInvariant


def test_pool_on_exit(users, eclp_pool, mock_vault, gyro_eclp_math_testing):
    amount_in = 100 * 10**18

    tx = join_pool(mock_vault, eclp_pool.address, users[0], (0, 0), amount_in)

    poolId = eclp_pool.getPoolId()
    (_, initial_balances) = mock_vault.getPoolTokens(poolId)
    tx = join_pool(
        mock_vault,
        eclp_pool.address,
        users[1],
        initial_balances,
        amount_in,
        amount_out=eclp_pool.totalSupply(),
    )

    amountOut = 5 * 10**18

    total_supply_before_exit = eclp_pool.totalSupply()
    (_, balances_after_join) = mock_vault.getPoolTokens(poolId)

    invariant_after_join = eclp_pool.getLastInvariant()

    bptTokensToBurn = eclp_pool.balanceOf(users[0]) * amountOut // amount_in
    tx = mock_vault.callExitPoolGyro(
        eclp_pool.address,
        0,
        users[0],
        users[0],
        balances_after_join,
        0,
        0,
        bptTokensToBurn,
    )

    assert unscale(tx.events["PoolBalanceChanged"]["deltas"]) == approxed(
        unscale((amountOut, amountOut))
    )

    (_, balancesAfterExit) = mock_vault.getPoolTokens(poolId)
    assert int(balancesAfterExit[0]) == pytest.approx(
        balances_after_join[0] - amountOut
    )
    assert int(balancesAfterExit[1]) == pytest.approx(
        balances_after_join[1] - amountOut
    )

    ## Check BTP Token minting
    assert tx.events["Transfer"][0]["from"] == users[0]
    assert tx.events["Transfer"][0]["to"] == ZERO_ADDRESS
    bptTokensburnt = tx.events["Transfer"][0]["value"]
    assert bptTokensburnt > 0
    # Check that approx. amount of tokens burnt is proportional to the amount of tokens substracted from the pool
    assert float(bptTokensburnt) == pytest.approx(
        total_supply_before_exit * (amountOut / balances_after_join[0])
    )
    assert bptTokensburnt == bptTokensToBurn

    sparams, sdparams = eclp_pool.getECLPParams()

    ## Check new pool's invariant
    invariant_after_exit = eclp_pool.getLastInvariant()
    assert invariant_after_join > invariant_after_exit

    # This is the value used in _onExitPool(): The invariant is recalculated each time.
    # B/c recalculation isn't perfectly precise, we only match the stored value approximately.
    sInvariant_after_join = gyro_eclp_math_testing.calculateInvariant(
        balances_after_join, sparams, sdparams
    )
    assert unscale(sInvariant_after_join) == unscale(invariant_after_join).approxed()

    sInvariant_after_exit = gyro_eclp_math_testing.liquidityInvariantUpdate(
        sInvariant_after_join, bptTokensToBurn, total_supply_before_exit, False
    )

    assert invariant_after_exit == sInvariant_after_exit


def test_pool_swap(users, eclp_pool, mock_vault, gyro_erc20_funded):
    amount_in = 100 * 10**18

    tx = join_pool(mock_vault, eclp_pool.address, users[0], (0, 0), amount_in)

    poolId = eclp_pool.getPoolId()
    (_, initial_balances) = mock_vault.getPoolTokens(poolId)
    tx = join_pool(
        mock_vault,
        eclp_pool.address,
        users[1],
        initial_balances,
        amount_in,
        amount_out=eclp_pool.totalSupply(),
    )

    amount_out = 5 * 10**18

    (_, balances_after_join) = mock_vault.getPoolTokens(poolId)

    tx = mock_vault.callExitPoolGyro(
        eclp_pool.address,
        0,
        users[0],
        users[0],
        balances_after_join,
        0,
        0,
        eclp_pool.balanceOf(users[0]) * amount_out // amount_in,
    )

    (_, balances_after_exit) = mock_vault.getPoolTokens(poolId)

    amount_to_swap = 10 * 10**18

    fees = amount_to_swap * (to_decimal("0.1") / 100)
    amountToSwapMinusFees = amount_to_swap - fees

    sparams, _ = eclp_pool.getECLPParams()
    mparams = params2MathParams(ECLPMathParams(*unscale(sparams)))
    eclp = math_implementation.ECLP.from_x_y(*unscale(balances_after_exit), mparams)
    amount_out_expected = -eclp.trade_x(unscale(amountToSwapMinusFees), mock=True)

    swapRequest = SwapRequest(
        kind=SwapKind.GivenIn,  # SwapKind - GIVEN_IN
        tokenIn=gyro_erc20_funded[0].address,  # IERC20
        tokenOut=gyro_erc20_funded[1].address,  # IERC20
        amount=amount_to_swap,  # uint256
        poolId=poolId,  # bytes32
        lastChangeBlock=0,  # uint256
        from_aux=users[1],  # address
        to=users[1],  # address
        userData=(0).to_bytes(32, "big"),  # bytes
    )

    tx = mock_vault.callMinimalGyroPoolSwap(
        eclp_pool.address,
        swapRequest,
        balances_after_exit[0],
        balances_after_exit[1],
    )

    assert tx.events["Swap"][0]["tokenIn"] == gyro_erc20_funded[0]
    assert tx.events["Swap"][0]["tokenOut"] == gyro_erc20_funded[1]
    amount_out = tx.events["Swap"][0]["amount"]

    assert amount_out < amount_to_swap

    # Check balances
    (_, balances_after_swap) = mock_vault.getPoolTokens(poolId)
    assert balances_after_swap[0] == balances_after_exit[0] + amount_to_swap
    assert balances_after_swap[1] == balances_after_exit[1] - amount_out

    assert unscale(amount_out) == amount_out_expected.approxed()
