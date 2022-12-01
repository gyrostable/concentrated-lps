// SPDX-License-Identifier: LicenseRef-Gyro-1.0
// for information on licensing please see the README in the GitHub repository <https://github.com/gyrostable/concentrated-lps>.

pragma solidity 0.7.6;
pragma experimental ABIEncoderV2;

import "../GyroECLPOracleMath.sol";
import "@balancer-labs/v2-solidity-utils/contracts/test/MockLogCompression.sol";

contract GyroECLPOracleMathTesting is MockLogCompression {
    function calcLogSpotPrice(uint256 spotPrice) external pure returns (int256 ret) {
        ret = GyroECLPOracleMath._calcLogSpotPrice(spotPrice);
    }

    function calcLogBPTPrice(
        uint256 balanceA,
        uint256 balanceB,
        uint256 spotPriceA,
        int256 logBptTotalSupply
    ) external pure returns (int256 ret) {
        ret = GyroECLPOracleMath._calcLogBPTPrice(balanceA, balanceB, spotPriceA, logBptTotalSupply);
    }

    function calcLogInvariantDivSupply(uint256 invariant, int256 logBptTotalSupply) external pure returns (int256 ret) {
        ret = GyroECLPOracleMath._calcLogInvariantDivSupply(invariant, logBptTotalSupply);
    }
}
