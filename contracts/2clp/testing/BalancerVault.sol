// SPDX-License-Identifier: GPL-3.0-or-later

pragma solidity 0.7.6;
pragma experimental ABIEncoderV2;

import "@balancer-labs/v2-vault/contracts/Vault.sol";
import "../../testing/Authorizer.sol";

contract BalancerVault is Vault {
    constructor(
        IAuthorizer authorizer,
        IWETH weth,
        uint256 pauseWindowDuration,
        uint256 bufferPeriodDuration
    ) Vault(authorizer, weth, pauseWindowDuration, bufferPeriodDuration) {
        // solhint-disable-previous-line no-empty-blocks
    }
}

// contract VaultTestingMock {
//     enum PoolBalanceChangeKind {
//         JOIN,
//         EXIT
//     }

//     function joinPool(
//         IBasePool gyroTwoPool,
//         bytes32 poolId,
//         address sender,
//         address recipient,
//         uint256[] memory balances,
//         uint256 lastChangeBlock,
//         uint256 protocolSwapFeePercentage,
//         uint256 amountIn
//     )
//         public
//         returns (
//             uint256[] memory amountsIn,
//             uint256[] memory dueProtocolFeeAmounts
//         )
//     {
//         //(, amountsIn, minBPTAmountOut) = abi.decode(self, (JoinKind, uint256[], uint256));
//         uint256[] memory amountsInStr = new uint256[](2);
//         amountsInStr[0] = amountIn;
//         amountsInStr[2] = amountIn;

//         bytes memory userData = abi.encode(
//             PoolBalanceChangeKind.JOIN,
//             amountsInStr,
//             0
//         );

//         return
//             gyroTwoPool.onJoinPool(
//                 poolId,
//                 sender,
//                 recipient,
//                 balances,
//                 lastChangeBlock,
//                 protocolSwapFeePercentage,
//                 userData
//             );
//     }
// }
