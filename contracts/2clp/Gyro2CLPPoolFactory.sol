// SPDX-License-Identifier: LicenseRef-Gyro-1.0
// for information on licensing please see the README in the GitHub repository <https://github.com/gyrostable/concentrated-lps>.

pragma solidity 0.7.6;
pragma experimental ABIEncoderV2;

import "@balancer-labs/v2-vault/contracts/interfaces/IVault.sol";

import "@balancer-labs/v2-pool-utils/contracts/factories/BasePoolSplitCodeFactory.sol";
import "@balancer-labs/v2-pool-utils/contracts/factories/FactoryWidePauseWindow.sol";

import "../../interfaces/IGyro2CLPPoolFactory.sol";
import "../../interfaces/ICappedLiquidity.sol";
import "./Gyro2CLPPool.sol";

contract Gyro2CLPPoolFactory is IGyro2CLPPoolFactory, BasePoolSplitCodeFactory, FactoryWidePauseWindow {
    address public immutable gyroConfigAddress;

    uint256 public constant PAUSE_WINDOW_DURATION = 90 days;
    uint256 public constant BUFFER_PERIOD_DURATION = 30 days;

    constructor(IVault vault, address _gyroConfigAddress) BasePoolSplitCodeFactory(vault, type(Gyro2CLPPool).creationCode) {
        _grequire(_gyroConfigAddress != address(0), GyroErrors.ZERO_ADDRESS);
        _grequire(address(vault) != address(0), GyroErrors.ZERO_ADDRESS);
        gyroConfigAddress = _gyroConfigAddress;
    }

    /**
     * @dev Deploys a new `Gyro2CLPPool`.
     */
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
    ) external override returns (address) {
        ExtensibleWeightedPool2Tokens.NewPoolParams memory baseParams = _makePoolParams(
            name,
            symbol,
            tokens,
            swapFeePercentage,
            oracleEnabled,
            owner
        );

        Gyro2CLPPool.GyroParams memory params = Gyro2CLPPool.GyroParams({
            baseParams: baseParams,
            sqrtAlpha: sqrts[0],
            sqrtBeta: sqrts[1],
            capManager: capManager,
            capParams: capParams,
            pauseManager: pauseManager
        });

        return _create(abi.encode(params, gyroConfigAddress));
    }

    function _makePoolParams(
        string memory name,
        string memory symbol,
        IERC20[] memory tokens,
        uint256 swapFeePercentage,
        bool oracleEnabled,
        address owner
    ) internal view returns (ExtensibleWeightedPool2Tokens.NewPoolParams memory) {
        return
            ExtensibleWeightedPool2Tokens.NewPoolParams({
                vault: getVault(),
                name: name,
                symbol: symbol,
                token0: tokens[0],
                token1: tokens[1],
                swapFeePercentage: swapFeePercentage,
                pauseWindowDuration: PAUSE_WINDOW_DURATION,
                bufferPeriodDuration: BUFFER_PERIOD_DURATION,
                oracleEnabled: oracleEnabled,
                owner: owner
            });
    }
}
