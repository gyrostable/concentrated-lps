// SPDX-License-Identifier: LicenseRef-Gyro-1.0
// for information on licensing please see the README in the GitHub repository <https://github.com/gyrostable/concentrated-lps>.

pragma solidity 0.7.6;

import "@balancer-labs/v2-solidity-utils/contracts/test/MockLogCompression.sol";

import "../Gyro2CLPOracleMath.sol";

contract MockGyro2CLPOracleMath is Gyro2CLPOracleMath, MockLogCompression {
    function calcSpotPrice(
        uint256 balanceA,
        uint256 virtualParameterA,
        uint256 balanceB,
        uint256 virtualParameterB
    ) external pure returns (uint256) {
        return Gyro2CLPOracleMath._calcSpotPrice(balanceA, virtualParameterA, balanceB, virtualParameterB);
    }

    function calcLogSpotPrice(
        uint256 balanceA,
        uint256 virtualParameterA,
        uint256 balanceB,
        uint256 virtualParameterB
    ) external pure returns (int256) {
        return Gyro2CLPOracleMath._calcLogSpotPrice(balanceA, virtualParameterA, balanceB, virtualParameterB);
    }

    function calcLogBPTPrice(
        uint256 balanceA,
        uint256 virtualParameterA,
        uint256 balanceB,
        uint256 virtualParameterB,
        int256 logBptTotalSupply
    ) external pure returns (int256) {
        return Gyro2CLPOracleMath._calcLogBPTPrice(balanceA, virtualParameterA, balanceB, virtualParameterB, logBptTotalSupply);
    }
}
