from math import cos, sin, pi
from pprint import pprint

from brownie import (
    accounts,
    Gyro3CLPPool,
    Gyro3CLPMathTesting,
    Gyro3CLPMath,
    MockVault,
    Authorizer,
    MockGyroConfig,
    SimpleERC20,
    Contract,
    QueryProcessor,
    history,
)
from brownie.network.transaction import TransactionReceipt

from tests.support.quantized_decimal import QuantizedDecimal as D
from tests.support.types import (
    CallJoinPoolGyroParams,
    SwapKind,
    SwapRequest,
    TwoPoolBaseParams,
    ThreePoolParams,
    ThreePoolFactoryCreateParams,
)

from tests.support.trace_analyzer import Tracer

from tests.support.utils import scale, unscale

from tabulate import tabulate

################ Config ###################

# All of these values are unscaled.

alpha = D("0.97")

swapFeePercentage = D("0.1") / D(100)
protocolSwapFeePercentage = D("0.5") / D(100)
# protocolSwapFeePercentage = 0

# The following just has to be large enough
TOKENS_PER_USER = 1000

init_amounts_in = [100, 100, 100]

###########################################

root_3_alpha = alpha ** (D(1) / D(3))

# MOCK POOL FROM FACTORY
admin = accounts[0]

# For experiments with external library calls. Not normally needed.
# admin.deploy(GyroCEMMMath)

authorizer = admin.deploy(Authorizer, admin)

mock_vault = admin.deploy(MockVault, authorizer)

mock_gyro_config = admin.deploy(MockGyroConfig)

gyro_three_math_testing = admin.deploy(Gyro3CLPMathTesting)

gyro_erc20_0 = admin.deploy(SimpleERC20)
gyro_erc20_1 = admin.deploy(SimpleERC20)
users = (accounts[1], accounts[2], accounts[3])

gyro_erc20_0.mint(users[0], scale(TOKENS_PER_USER))
gyro_erc20_1.mint(users[0], scale(TOKENS_PER_USER))
gyro_erc20_0.mint(users[1], scale(TOKENS_PER_USER))
gyro_erc20_1.mint(users[1], scale(TOKENS_PER_USER))

# Copied from conftest.py::gyro_erc20_funded3
npools = 3
gyro_erc20s = [admin.deploy(SimpleERC20) for _ in range(npools)]
for i in range(2):
    for gyro_erc20 in gyro_erc20s:
        gyro_erc20.mint(users[i], scale(TOKENS_PER_USER))
gyro_erc20s.sort(key=lambda p: p.address.lower())
gyro_erc20_funded = tuple(gyro_erc20s)

# Not used in code, but needs to be deployed.
admin.deploy(QueryProcessor)

admin.deploy(Gyro3CLPMath)

# MOCK POOL

args = ThreePoolParams(
    vault=mock_vault.address,
    config=ThreePoolFactoryCreateParams(
        name="Gyro3CLPPool",  # string
        symbol="G3P",  # string
        tokens=list(gyro_erc20_funded),
        swapFeePercentage=scale(swapFeePercentage),
        owner=admin,  # address
        root3Alpha=scale(root_3_alpha),
    ),
    pauseWindowDuration=0,  # uint256
    bufferPeriodDuration=0,  # uint256
    config_address=mock_gyro_config.address,
)

mock_vault_pool = admin.deploy(Gyro3CLPPool, args)

# Set to an integer to only show that deep of traces. Nice to avoid visual overload.
MAXLVL = None


def main():
    poolId = mock_vault_pool.getPoolId()

    ##################################################
    ## Add initial liquidity
    ##################################################
    label = "1: Join (Initial)"
    print(f"----- {label} -----\n")

    tx_total = mock_vault.callJoinPoolGyro(
        CallJoinPoolGyroParams(
            mock_vault_pool.address,
            poolId,
            users[0],
            users[0],
            (0, 0, 0),  # current balances
            0,
            protocolSwapFeePercentage * 10**18,
            scale(init_amounts_in),
            0,  # amount_out not used for init
        )
    )

    tracer = Tracer.load()
    summary_headers = ("Operation", "Function", "Gas")
    summary_table = []

    def go(tx):
        #
        print(f"Total Gas: {tx.gas_used}")
        print()
        # The gas tracer isn't super reliable, so we just let it crash if it has to; we still get the totals without it
        # at least.
        try:
            ctx = tracer.trace_tx(tx)
            assert len(ctx.children) == 1
            ctx1 = ctx.children[0][1]
            summary_table.append(
                (label, ctx1.qualified_function_name, ctx1.total_gas_consumed)
            )
            print(ctx.format(maxlvl=MAXLVL))
        except:
            summary_table.append((label, "(total tx)", tx.gas_used))
        print()

    go(tx_total)

    ##################################################
    ## Add liqudidity to an already initialized pool
    ##################################################
    label = "2: Join (Non-Initial After Initial)"
    print(f"----- {label} -----\n")
    (_, balances) = mock_vault.getPoolTokens(poolId)
    bpt_amount_out = unscale(mock_vault_pool.totalSupply()) * D("0.2")
    tx_total = mock_vault.callJoinPoolGyro(
        CallJoinPoolGyroParams(
            mock_vault_pool.address,
            poolId,
            users[1],
            users[1],
            balances,  # current balances
            0,
            protocolSwapFeePercentage * 10**18,
            [0, 0, 0],  # amounts in not used outside init
            scale(bpt_amount_out),
        )
    )

    go(tx_total)

    ##################################################
    ## Conduct swaps
    ##################################################
    label = "3: Swap (After Join)"
    print(f"----- {label} -----\n")

    (_, balances) = mock_vault.getPoolTokens(poolId)

    amount_to_swap = 10

    swapRequest = SwapRequest(
        kind=SwapKind.GivenIn,  # SwapKind - GIVEN_IN
        tokenIn=gyro_erc20_funded[0].address,  # IERC20
        tokenOut=gyro_erc20_funded[1].address,  # IERC20
        amount=scale(amount_to_swap),  # uint256
        poolId=poolId,  # bytes32
        lastChangeBlock=0,  # uint256
        from_aux=users[1],  # address
        to=users[1],  # address
        userData=(0).to_bytes(32, "big"),  # bytes
    )

    tx_total = mock_vault.callMinimalGyroPoolSwap(
        mock_vault_pool.address,
        swapRequest,
        balances[0],
        balances[1],
    )

    go(tx_total)

    label = "4: Swap (After Swap)"
    print(f"----- {label} -----\n")
    (_, balances) = mock_vault.getPoolTokens(poolId)

    amount_to_swap = 10

    swapRequest = SwapRequest(
        kind=SwapKind.GivenIn,  # SwapKind - GIVEN_IN
        tokenIn=gyro_erc20_funded[1].address,  # IERC20
        tokenOut=gyro_erc20_funded[2].address,  # IERC20
        amount=scale(amount_to_swap),  # uint256
        poolId=poolId,  # bytes32
        lastChangeBlock=0,  # uint256
        from_aux=users[1],  # address
        to=users[1],  # address
        userData=(0).to_bytes(32, "big"),  # bytes
    )

    tx_total = mock_vault.callMinimalGyroPoolSwap(
        mock_vault_pool.address,
        swapRequest,
        balances[1],
        balances[2],
    )

    go(tx_total)

    ##################################################
    ## Add liqudidity after swap
    ##################################################
    label = "5: Join (After Swap)"
    print(f"----- {label} -----\n")

    (_, balances) = mock_vault.getPoolTokens(poolId)
    bpt_amount_out = unscale(mock_vault_pool.totalSupply()) * D("1.2")
    tx_total = mock_vault.callJoinPoolGyro(
        CallJoinPoolGyroParams(
            mock_vault_pool.address,
            poolId,
            users[1],
            users[1],
            balances,  # current balances
            0,
            protocolSwapFeePercentage * 10**18,
            [0, 0],  # amounts in not used outside init
            scale(bpt_amount_out),
        )
    )

    go(tx_total)

    ##################################################
    ## Another swap
    ##################################################
    label = "6: Swap (Again After Join)"
    print(f"----- {label} -----\n")

    (_, balances) = mock_vault.getPoolTokens(poolId)

    amount_to_swap = 10

    swapRequest = SwapRequest(
        kind=SwapKind.GivenIn,  # SwapKind - GIVEN_IN
        tokenIn=gyro_erc20_funded[0].address,  # IERC20
        tokenOut=gyro_erc20_funded[1].address,  # IERC20
        amount=scale(amount_to_swap),  # uint256
        poolId=poolId,  # bytes32
        lastChangeBlock=0,  # uint256
        from_aux=users[1],  # address
        to=users[1],  # address
        userData=(0).to_bytes(32, "big"),  # bytes
    )

    tx_total = mock_vault.callMinimalGyroPoolSwap(
        mock_vault_pool.address,
        swapRequest,
        balances[0],
        balances[1],
    )

    go(tx_total)

    ##################################################
    ## Exit pool
    ##################################################
    label = "7: Exit (After Swap)"
    print(f"----- {label} -----\n")

    (_, balances) = mock_vault.getPoolTokens(poolId)
    bpt_amount_in = unscale(mock_vault_pool.balanceOf(users[0])) * D("0.7")

    tx_total = mock_vault.callExitPoolGyro(
        mock_vault_pool.address,
        0,
        users[0],
        users[0],
        balances,
        0,
        0,
        bpt_amount_in,
    )

    go(tx_total)

    #### Summary Table
    print("Summary:\n")
    print(tabulate(summary_table, headers=summary_headers))
    print()
