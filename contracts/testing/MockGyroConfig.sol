// SPDX-License-Identifier: for information on licensing please see the README in the GitHub repository <https://github.com/gyrostable/concentrated-lps>. 

pragma solidity 0.7.6;

import "../../interfaces/IGyroConfig.sol";
import "../../libraries/GyroConfigKeys.sol";

contract MockGyroConfig is IGyroConfig {
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
    function getUint(bytes32 key) external pure override returns (uint256) {
        if (key == GyroConfigKeys.PROTOCOL_FEE_GYRO_PORTION_KEY) {
            return 1e18;
        }
        return 0;
    }

    /// @inheritdoc IGyroConfig
    function getAddress(bytes32) external pure override returns (address) {
        return address(0);
    }

    /// @inheritdoc IGyroConfig
    function setUint(bytes32 key, uint256 newValue) external override {
        // solhint-disable-previous-line no-empty-blocks
    }

    /// @inheritdoc IGyroConfig
    function setAddress(bytes32 key, address newValue) external override {
        // solhint-disable-previous-line no-empty-blocks
    }
}
