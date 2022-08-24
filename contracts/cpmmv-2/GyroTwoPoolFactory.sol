// SPDX-License-Identifier: LicenseRef-Gyro-1.0
// for information on licensing please see the README in the GitHub repository <https://github.com/gyrostable/core-protocol>.

pragma solidity ^0.7.0;
pragma experimental ABIEncoderV2;

import "@balancer-labs/v2-vault/contracts/interfaces/IVault.sol";

import "@balancer-labs/v2-pool-utils/contracts/factories/BasePoolSplitCodeFactory.sol";
import "@balancer-labs/v2-pool-utils/contracts/factories/FactoryWidePauseWindow.sol";

import "./GyroTwoPool.sol";

contract GyroTwoPoolFactory is BasePoolSplitCodeFactory, FactoryWidePauseWindow {
    address public immutable gyroConfigAddress;

    constructor(IVault vault, address _gyroConfigAddress)
        BasePoolSplitCodeFactory(vault, type(GyroTwoPool).creationCode)
    {
        gyroConfigAddress = _gyroConfigAddress;
    }

    /**
     * @dev Deploys a new `GyroTwoPool`.
     */
    function create(
        string memory name,
        string memory symbol,
        IERC20[] memory tokens,
        uint256[] memory weights,
        uint256[] memory sqrts,
        uint256 swapFeePercentage,
        bool oracleEnabled,
        address owner
    ) external returns (address) {
        (uint256 pauseWindowDuration, uint256 bufferPeriodDuration) = getPauseConfiguration();

        GyroTwoPool.GyroParams memory params = GyroTwoPool.GyroParams({
            baseParams: ExtensibleWeightedPool2Tokens.NewPoolParams({
                vault: getVault(),
                name: name,
                symbol: symbol,
                token0: tokens[0],
                token1: tokens[1],
                normalizedWeight0: weights[0],
                normalizedWeight1: weights[1],
                swapFeePercentage: swapFeePercentage,
                pauseWindowDuration: pauseWindowDuration,
                bufferPeriodDuration: bufferPeriodDuration,
                oracleEnabled: oracleEnabled,
                owner: owner
            }),
            sqrtAlpha: sqrts[0],
            sqrtBeta: sqrts[1]
        });

        return _create(abi.encode(params, gyroConfigAddress));
    }
}
