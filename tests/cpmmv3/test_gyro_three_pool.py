from math import prod

import pytest
from brownie import ZERO_ADDRESS
from tests.conftest import TOKENS_PER_USER
from tests.cpmmv3 import constants
from tests.support.types import CallJoinPoolGyroParams, SwapKind, SwapRequest
from tests.support.quantized_decimal import QuantizedDecimal as D
from tests.support.utils import unscale, scale, approxed


def test_empty_erc20s(admin, gyro_erc20_empty3):
    for token in range(constants.NUM_TOKENS):
        gyro_erc20_empty3[token].mint(admin, TOKENS_PER_USER)
        assert gyro_erc20_empty3[token].totalSupply() == TOKENS_PER_USER


def test_funded_erc20s(users, gyro_erc20_funded3):
    for token in range(constants.NUM_TOKENS):
        assert (
            gyro_erc20_funded3[token].totalSupply()
            == TOKENS_PER_USER * constants.NUM_USERS
        )
        for user in range(constants.NUM_USERS):
            assert gyro_erc20_funded3[token].balanceOf(users[user]) == TOKENS_PER_USER


def test_pool_reg(balancer_vault, balancer_vault_pool3, gyro_erc20_funded3):
    poolId = balancer_vault_pool3.getPoolId()

    # Check pool and token registration
    (token_addresses, token_balances, last_change_block) = balancer_vault.getPoolTokens(
        poolId
    )

    for token in range(constants.NUM_TOKENS):
        assert token_addresses[token] == gyro_erc20_funded3[token].address
        assert token_balances[token] == 0


def test_pool_constructor(mock_vault_pool3):
    assert mock_vault_pool3.getSwapFeePercentage() == 1 * 10 ** 15
    assert mock_vault_pool3.getRoot3Alpha() == D("0.97") * 10 ** 18

def test_pool_factory(mock_pool3_from_factory):
    assert mock_pool3_from_factory.name() == "GyroThreePoolFromFactory"
    assert mock_pool3_from_factory.symbol() == "G3PF"
    assert mock_pool3_from_factory.getRoot3Alpha() == D("0.97") * 10**18
    assert mock_pool3_from_factory.getSwapFeePercentage() == D(1) * 10**15

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
            amount_in,
            amount_out,
        )
    )


def test_pool_on_initialize(users, mock_vault_pool3, mock_vault):
    balances = (0, 0, 0)
    amountIn = 100 * 10 ** 18

    tx = join_pool(mock_vault, mock_vault_pool3.address, users[0], balances, amountIn)

    poolId = mock_vault_pool3.getPoolId()

    # Check Pool balance change
    assert tx.events["PoolBalanceChanged"]["poolId"] == poolId
    assert tx.events["PoolBalanceChanged"]["liquidityProvider"] == users[0]

    assert tx.events["PoolBalanceChanged"]["deltas"] == (amountIn, amountIn, amountIn)
    assert tx.events["PoolBalanceChanged"]["protocolFees"] == (0, 0, 0)

    # Check BPT Token minting
    assert tx.events["Transfer"][1]["from"] == ZERO_ADDRESS
    assert tx.events["Transfer"][1]["to"] == users[0]
    initial_bpt_tokens = tx.events["Transfer"][1]["value"]
    assert initial_bpt_tokens > 0

    # Check that the amountIn is now stored in the pool balance
    (_, initial_balances) = mock_vault.getPoolTokens(poolId)
    initial_balances = tuple(initial_balances)
    assert initial_balances == (amountIn, amountIn, amountIn)


def test_pool_on_join(users, mock_vault_pool3, mock_vault):
    ##################################################
    ## Initialize pool
    ##################################################
    amount_in = 100 * 10 ** 18

    tx = join_pool(mock_vault, mock_vault_pool3.address, users[0], (0, 0, 0), amount_in)

    initial_bpt_tokens = tx.events["Transfer"][1]["value"]

    root3Alpha = unscale(mock_vault_pool3.getRoot3Alpha())

    # Check pool's invariant after initialization
    currentInvariant = unscale(mock_vault_pool3.getLastInvariant())
    cubeInvariant_calcd = (unscale(amount_in) + currentInvariant * root3Alpha) ** 3
    cubeInvariant_pool = currentInvariant ** 3

    # Approximation is rough here, see the math tests for more fine-grained comparisons.
    assert cubeInvariant_calcd == cubeInvariant_pool.approxed()

    poolId = mock_vault_pool3.getPoolId()
    (_, initial_balances) = mock_vault.getPoolTokens(poolId)

    ##################################################
    ## Add liqudidity to an already initialized pool
    ##################################################
    tx = join_pool(
        mock_vault,
        mock_vault_pool3.address,
        users[1],
        initial_balances,
        0,  # Not used
        amount_out=mock_vault_pool3.totalSupply(),  # say...
    )

    ## Check Pool balance Change
    assert tx.events["PoolBalanceChanged"]["liquidityProvider"] == users[1]

    assert tx.events["PoolBalanceChanged"]["deltas"] == (
        amount_in,
        amount_in,
        amount_in,
    )

    ## Check BPT Token minting
    assert tx.events["Transfer"][0]["from"] == ZERO_ADDRESS
    assert tx.events["Transfer"][0]["to"] == users[1]
    bptTokensNew = tx.events["Transfer"][0]["value"]
    assert bptTokensNew > 0
    assert float(bptTokensNew) == pytest.approx(initial_bpt_tokens)
    # ^ NB this only works b/c we use the same amounts. - Which is ok & the right thing to do, it should be relative!

    (_, balancesAfterJoin) = mock_vault.getPoolTokens(poolId)
    assert balancesAfterJoin[0] == amount_in * 2
    assert balancesAfterJoin[1] == amount_in * 2
    assert balancesAfterJoin[2] == amount_in * 2

    ## Check new pool's invariant
    newInvariant = mock_vault_pool3.getLastInvariant()
    assert newInvariant > currentInvariant

    currentInvariant = unscale(mock_vault_pool3.getLastInvariant())
    cubeInvariant_calcd = prod(
        unscale(balancesAfterJoin[i]) + currentInvariant * root3Alpha for i in range(3)
    )
    cubeInvariant_pool = currentInvariant ** 3
    assert cubeInvariant_calcd == cubeInvariant_pool.approxed()


def test_pool_on_exit(users, mock_vault_pool3, mock_vault):
    ## Initialize Pool
    amount_in = 100 * 10 ** 18

    tx = join_pool(mock_vault, mock_vault_pool3.address, users[0], (0, 0, 0), amount_in)

    poolId = mock_vault_pool3.getPoolId()
    (_, initial_balances) = mock_vault.getPoolTokens(poolId)
    tx = join_pool(
        mock_vault,
        mock_vault_pool3.address,
        users[1],
        initial_balances,
        0,  # Not used
        amount_out=mock_vault_pool3.totalSupply(),  # say...
    )

    amountOut = 5 * 10 ** 18

    total_supply_before_exit = mock_vault_pool3.totalSupply()
    (_, balances_after_exit) = mock_vault.getPoolTokens(poolId)
    invariant_before_exit = mock_vault_pool3.getLastInvariant()

    print(mock_vault_pool3.balanceOf(users[0]))

    tx = mock_vault.callExitPoolGyro(
        mock_vault_pool3.address,
        poolId,
        users[0],
        users[0],
        balances_after_exit,
        0,
        0,
        mock_vault_pool3.balanceOf(users[0]) * amountOut // amount_in,
    )

    assert unscale(tx.events["PoolBalanceChanged"]["deltas"]) == approxed(
        unscale((amountOut, amountOut, amountOut))
    )

    (_, balancesAfterExit) = mock_vault.getPoolTokens(poolId)
    assert int(balancesAfterExit[0]) == pytest.approx(
        balances_after_exit[0] - amountOut
    )
    assert int(balancesAfterExit[1]) == pytest.approx(
        balances_after_exit[1] - amountOut
    )
    assert int(balancesAfterExit[2]) == pytest.approx(
        balances_after_exit[2] - amountOut
    )

    ## Check BTP Token burning
    assert tx.events["Transfer"][0]["from"] == users[0]
    assert tx.events["Transfer"][0]["to"] == ZERO_ADDRESS
    bptTokensburnt = tx.events["Transfer"][0]["value"]
    assert bptTokensburnt > 0
    # Check that approx. amount of tokens burnt is proportional to the amount of tokens substracted from the pool
    assert float(bptTokensburnt) == pytest.approx(
        total_supply_before_exit * (amountOut / balances_after_exit[0])
    )

    root3Alpha = unscale(mock_vault_pool3.getRoot3Alpha())

    ## Check new pool's invariant
    currentInvariant = unscale(mock_vault_pool3.getLastInvariant())
    cubeInvariant_calcd = prod(
        unscale(balancesAfterExit[i]) + currentInvariant * root3Alpha for i in range(3)
    )
    cubeInvariant_pool = currentInvariant ** 3
    assert cubeInvariant_calcd == cubeInvariant_pool.approxed()

    assert currentInvariant < invariant_before_exit


def test_swap(
    users, mock_vault_pool3, mock_vault, gyro_erc20_funded3, gyro_three_math_testing
):
    ## Initialize
    amount_in = 100 * 10 ** 18

    tx = join_pool(mock_vault, mock_vault_pool3.address, users[0], (0, 0, 0), amount_in)

    poolId = mock_vault_pool3.getPoolId()
    (_, initial_balances) = mock_vault.getPoolTokens(poolId)
    tx = join_pool(
        mock_vault,
        mock_vault_pool3.address,
        users[1],
        initial_balances,
        amount_in,
        amount_out=mock_vault_pool3.totalSupply(),
    )

    amount_out = 5 * 10 ** 18

    (_, balances) = mock_vault.getPoolTokens(poolId)

    amount_to_swap = 10 * 10 ** 18
    root3Alpha = unscale(mock_vault_pool3.getRoot3Alpha())
    current_invariant = unscale(mock_vault_pool3.getLastInvariant())

    fees = amount_to_swap * (0.1 / 100)
    amountToSwapMinusFees = int(amount_to_swap - fees)

    amount_out_expected = gyro_three_math_testing.calcOutGivenIn(
        balances[0],  # balanceIn,
        balances[1],  # balanceOut,
        amountToSwapMinusFees,  # amountIn,
        scale(current_invariant * root3Alpha),  # virtualOffsetInOut
    )

    swapRequest = SwapRequest(
        kind=SwapKind.GivenIn,  # SwapKind - GIVEN_IN
        tokenIn=gyro_erc20_funded3[0].address,  # IERC20
        tokenOut=gyro_erc20_funded3[1].address,  # IERC20
        amount=amount_to_swap,  # uint256
        poolId=poolId,  # bytes32
        lastChangeBlock=0,  # uint256
        from_aux=users[1],  # address
        to=users[1],  # address
        userData=(0).to_bytes(32, "big"),  # bytes
    )

    tx = mock_vault.callMinimalGyroPoolSwap(
        mock_vault_pool3.address,
        swapRequest,
        balances[0],
        balances[1],
    )

    assert tx.events["Swap"][0]["tokenIn"] == gyro_erc20_funded3[0]
    assert tx.events["Swap"][0]["tokenOut"] == gyro_erc20_funded3[1]
    amount_out = tx.events["Swap"][0]["amount"]

    assert amount_out < amount_to_swap
    # ^ B/c (1) initial price was 1, and we have some price impact; (2) fees

    # Check balances
    (_, balances_after_swap) = mock_vault.getPoolTokens(poolId)
    assert balances_after_swap[0] == balances[0] + amount_to_swap
    assert balances_after_swap[1] == balances[1] - amount_out
    assert balances_after_swap[2] == balances[2]

    assert unscale(amount_out) == approxed(unscale(amount_out_expected))
