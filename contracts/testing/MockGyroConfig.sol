// SPDX-License-Identifier: LicenseRef-Gyro-1.0
// for information on licensing please see the README in the GitHub repository <https://github.com/gyrostable/concentrated-lps>.
pragma solidity 0.7.6;

import "../../interfaces/IGyroConfig.sol";
import "../../libraries/GyroConfigKeys.sol";
import "../../libraries/GyroConfigHelpers.sol";

contract MockGyroConfig is IGyroConfig {
    mapping(bytes32 => uint256) internal configUints;
    mapping(bytes32 => bool) internal present;

    constructor() {
        configUints[GyroConfigKeys.PROTOCOL_FEE_GYRO_PORTION_KEY] = 1e18;
    }

    /// @inheritdoc IGyroConfig
    function listKeys() external pure override returns (bytes32[] memory) {
        bytes32[] memory keys = new bytes32[](4);
        keys[0] = GyroConfigKeys.PROTOCOL_SWAP_FEE_PERC_KEY;
        keys[1] = GyroConfigKeys.PROTOCOL_FEE_GYRO_PORTION_KEY;
        keys[2] = GyroConfigKeys.GYRO_TREASURY_KEY;
        keys[3] = GyroConfigKeys.BAL_TREASURY_KEY;
        return keys;
    }

    /// @inheritdoc IGyroConfig
    function getUint(bytes32 key) external view override returns (uint256) {
        return configUints[key];
    }

    /// @inheritdoc IGyroConfig
    function getAddress(bytes32) external pure override returns (address) {
        return address(0);
    }

    /// @inheritdoc IGyroConfig
    function setUint(bytes32 key, uint256 newValue) external override {
        configUints[key] = newValue;
        present[key] = true;
    }

    function hasKey(bytes32 key) external view override returns (bool) {
        return present[key];
    }

    /// @inheritdoc IGyroConfig
    function setAddress(bytes32 key, address newValue) external override {
        // solhint-disable-previous-line no-empty-blocks
    }

    function getSwapFeePercForPool(address poolAddress, bytes32 poolType) external view returns (uint256) {
        return GyroConfigHelpers.getSwapFeePercForPool(this, poolAddress, poolType);
    }

    function getProtocolFeeGyroPortionForPool(address poolAddress, bytes32 poolType) external view returns (uint256) {
        return GyroConfigHelpers.getProtocolFeeGyroPortionForPool(this, poolAddress, poolType);
    }
}
