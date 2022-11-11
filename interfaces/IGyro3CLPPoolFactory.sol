// SPDX-License-Identifier: for information on licensing please see the README in the GitHub repository <https://github.com/gyrostable/concentrated-lps>. 

pragma solidity 0.7.6;
pragma experimental ABIEncoderV2;

import "../contracts/3clp/Gyro3CLPPool.sol";

interface IGyro3CLPPoolFactory {
    function create(Gyro3CLPPool.NewPoolConfigParams memory config) external returns (address);
}
