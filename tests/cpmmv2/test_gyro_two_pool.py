import pytest
from brownie import ZERO_ADDRESS
from tests.support.quantized_decimal import QuantizedDecimal as D
from tests.conftest import TOKENS_PER_USER
from tests.cpmmv2 import constants
from tests.support.types import CallJoinPoolGyroParams, SwapKind, SwapRequest
from tests.support.utils import unscale, approxed


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


def test_pool_reg(balancer_vault, balancer_vault_pool, gyro_erc20_funded):
    poolId = balancer_vault_pool.getPoolId()

    # Check pool and token registration
    (token_addresses, token_balances, last_change_block) = balancer_vault.getPoolTokens(
        poolId
    )

    for token in range(constants.NUM_TOKENS):
        assert token_addresses[token] == gyro_erc20_funded[token].address
        assert token_balances[token] == 0

def test_pool_factory(mock_pool_from_factory):
    assert mock_pool_from_factory.name() == "GyroTwoPoolFromFactory"
    assert mock_pool_from_factory.symbol() == "G2PF"
    assert mock_pool_from_factory.getSwapFeePercentage() == D(1) * 10 ** 15

    sqrtParams = mock_pool_from_factory.getSqrtParameters()
    assert sqrtParams[0] == 0.97 * 10 ** 18
    assert sqrtParams[1] == 1.02 * 10 ** 18

def test_pool_constructor(mock_vault_pool):
    assert mock_vault_pool.getSwapFeePercentage() == 1 * 10 ** 15
    assert mock_vault_pool.getNormalizedWeights() == (0.5 * 10 ** 18, 0.5 * 10 ** 18)

    sqrtParams = mock_vault_pool.getSqrtParameters()
    assert sqrtParams[0] == 0.97 * 10 ** 18
    assert sqrtParams[1] == 1.02 * 10 ** 18


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


def test_pool_on_initialize(users, mock_vault_pool, mock_vault):
    balances = (0, 0)
    amountIn = 100 * 10 ** 18

    tx = join_pool(mock_vault, mock_vault_pool.address, users[0], balances, amountIn)

    poolId = mock_vault_pool.getPoolId()

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


def test_pool_on_join(users, mock_vault_pool, mock_vault):
    amount_in = 100 * 10 ** 18

    tx = join_pool(mock_vault, mock_vault_pool.address, users[0], (0, 0), amount_in)

    initial_bpt_tokens = tx.events["Transfer"][1]["value"]

    sqrtParams = mock_vault_pool.getSqrtParameters()
    sqrtAlpha = sqrtParams[0] / (10 ** 18)
    sqrtBeta = sqrtParams[1] / (10 ** 18)

    # Check pool's invariant after initialization
    # NOTE: Calculation is completely unscaled; this is not the math that is actually done by anyone, but it works as a
    # check.
    currentInvariant = mock_vault_pool.getLastInvariant()
    squareInvariant = (amount_in + currentInvariant / sqrtBeta) * (
        amount_in + currentInvariant * sqrtAlpha
    )
    actualSquareInvariant = currentInvariant * currentInvariant
    assert squareInvariant == pytest.approx(actualSquareInvariant)

    poolId = mock_vault_pool.getPoolId()
    (_, initial_balances) = mock_vault.getPoolTokens(poolId)

    ##################################################
    ## Add liqudidity to an already initialized pool
    ##################################################
    tx = join_pool(
        mock_vault,
        mock_vault_pool.address,
        users[1],
        initial_balances,
        amount_in,
        amount_out=mock_vault_pool.totalSupply(),
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

    ## Check new pool's invariant
    newInvariant = mock_vault_pool.getLastInvariant()
    assert newInvariant > currentInvariant

    currentInvariant = mock_vault_pool.getLastInvariant()
    squareInvariant = (balancesAfterJoin[0] + currentInvariant / sqrtBeta) * (
        balancesAfterJoin[1] + currentInvariant * sqrtAlpha
    )
    actualSquareInvariant = currentInvariant * currentInvariant
    assert squareInvariant == pytest.approx(actualSquareInvariant)


def test_exit_pool(users, mock_vault_pool, mock_vault):
    amount_in = 100 * 10 ** 18

    tx = join_pool(mock_vault, mock_vault_pool.address, users[0], (0, 0), amount_in)

    poolId = mock_vault_pool.getPoolId()
    (_, initial_balances) = mock_vault.getPoolTokens(poolId)
    tx = join_pool(
        mock_vault,
        mock_vault_pool.address,
        users[1],
        initial_balances,
        amount_in,
        amount_out=mock_vault_pool.totalSupply(),
    )

    amountOut = 5 * 10 ** 18

    total_supply_before_exit = mock_vault_pool.totalSupply()
    (_, balances_after_join) = mock_vault.getPoolTokens(poolId)
    invariant_after_join = mock_vault_pool.getLastInvariant()

    tx = mock_vault.callExitPoolGyro(
        mock_vault_pool.address,
        0,
        users[0],
        users[0],
        balances_after_join,
        0,
        0,
        mock_vault_pool.balanceOf(users[0]) * amountOut // amount_in,
    )

    assert unscale(tx.events["PoolBalanceChanged"]["deltas"]) == approxed(unscale((amountOut, amountOut)))

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

    sqrt_alpha, sqrtBeta = [v / 10 ** 18 for v in mock_vault_pool.getSqrtParameters()]

    ## Check new pool's invariant
    invariant_after_exit = mock_vault_pool.getLastInvariant()
    assert invariant_after_join > invariant_after_exit
    square_invariant = (balancesAfterExit[0] + invariant_after_exit / sqrtBeta) * (
        balancesAfterExit[1] + invariant_after_exit * sqrt_alpha
    )
    assert square_invariant == pytest.approx(invariant_after_exit ** 2)


def test_swap(
    users, mock_vault_pool, mock_vault, gyro_erc20_funded, gyro_two_math_testing
):
    amount_in = 100 * 10 ** 18

    tx = join_pool(mock_vault, mock_vault_pool.address, users[0], (0, 0), amount_in)

    poolId = mock_vault_pool.getPoolId()
    (_, initial_balances) = mock_vault.getPoolTokens(poolId)
    tx = join_pool(
        mock_vault,
        mock_vault_pool.address,
        users[1],
        initial_balances,
        amount_in,
        amount_out=mock_vault_pool.totalSupply(),
    )

    amount_out = 5 * 10 ** 18

    (_, balances_after_join) = mock_vault.getPoolTokens(poolId)

    tx = mock_vault.callExitPoolGyro(
        mock_vault_pool.address,
        0,
        users[0],
        users[0],
        balances_after_join,
        0,
        0,
        mock_vault_pool.balanceOf(users[0]) * amount_out // amount_in,
    )

    (_, balances_after_exit) = mock_vault.getPoolTokens(poolId)

    amount_to_swap = 10 * 10 ** 18
    (
        current_invariant,
        virtual_param_in,
        virtual_param_out,
    ) = mock_vault_pool.calculateCurrentValues(*balances_after_exit, True)

    fees = amount_to_swap * (0.1 / 100)
    amountToSwapMinusFees = amount_to_swap - fees
    amount_out_expected = gyro_two_math_testing.calcOutGivenIn(
        balances_after_exit[0],  # balanceIn,
        balances_after_exit[1],  # balanceOut,
        amountToSwapMinusFees,  # amountIn,
        virtual_param_in,  # virtualParamIn,
        virtual_param_out,  # virtualParamOut
    )

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
        mock_vault_pool.address,
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

    assert int(amount_out) == pytest.approx(amount_out_expected)
