// SPDX-License-Identifier: LicenseRef-Gyro-1.0
// for information on licensing please see the README in the GitHub repository <https://github.com/gyrostable/core-protocol>.

pragma solidity ^0.7.0;

import "@balancer-labs/v2-solidity-utils/contracts/test/MockLogCompression.sol";

import "../GyroTwoOracleMath.sol";

contract MockGyroTwoOracleMath is GyroTwoOracleMath, MockLogCompression {
    function calcSpotPrice(
        uint256 balanceA,
        uint256 virtualParameterA,
        uint256 balanceB,
        uint256 virtualParameterB
    ) external pure returns (uint256) {
        return
            GyroTwoOracleMath._calcSpotPrice(
                balanceA,
                virtualParameterA,
                balanceB,
                virtualParameterB
            );
    }

    function calcLogSpotPrice(
        uint256 balanceA,
        uint256 virtualParameterA,
        uint256 balanceB,
        uint256 virtualParameterB
    ) external pure returns (int256) {
        return
            GyroTwoOracleMath._calcLogSpotPrice(
                balanceA,
                virtualParameterA,
                balanceB,
                virtualParameterB
            );
    }

    function calcLogBPTPrice(
        uint256 balanceA,
        uint256 virtualParameterA,
        uint256 balanceB,
        uint256 virtualParameterB,
        int256 logBptTotalSupply
    ) external pure returns (int256) {
        return
            GyroTwoOracleMath._calcLogBPTPrice(
                balanceA,
                virtualParameterA,
                balanceB,
                virtualParameterB,
                logBptTotalSupply
            );
    }
}
