// SPDX-License-Identifier: LicenseRef-Gyro-1.0
// for information on licensing please see the README in the GitHub repository <https://github.com/gyrostable/core-protocol>.

pragma solidity 0.7.6;
pragma experimental ABIEncoderV2;

import "../contracts/3clp/Gyro3CLPPool.sol";

interface IGyro3CLPPoolFactory {
    function create(Gyro3CLPPool.NewPoolConfigParams memory config) external returns (address);
}
