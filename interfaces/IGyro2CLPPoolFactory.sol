// SPDX-License-Identifier: LicenseRef-Gyro-1.0
// for information on licensing please see the README in the GitHub repository <https://github.com/gyrostable/core-protocol>.

pragma solidity 0.7.6;
pragma experimental ABIEncoderV2;

import "@balancer-labs/v2-vault/contracts/interfaces/IVault.sol";
import "./ICappedLiquidity.sol";

interface IGyro2CLPPoolFactory {
    function create(
        string memory name,
        string memory symbol,
        IERC20[] memory tokens,
        uint256[] memory sqrts,
        uint256 swapFeePercentage,
        bool oracleEnabled,
        address owner,
        address capManager,
        ICappedLiquidity.CapParams memory capParams,
        address pauseManager
    ) external returns (address);
}
