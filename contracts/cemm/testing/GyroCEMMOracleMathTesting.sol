// SPDX-License-Identifier: GPL-3.0-or-later

pragma solidity ^0.7.0;
pragma experimental ABIEncoderV2;

import "../GyroCEMMOracleMath.sol";
import "@balancer-labs/v2-solidity-utils/contracts/test/MockLogCompression.sol";

contract GyroCEMMOracleMathTesting is GyroCEMMOracleMath, MockLogCompression {
    function calcLogSpotPrice(uint256 spotPrice) external pure returns (int256 ret) {
        ret = GyroCEMMOracleMath._calcLogSpotPrice(spotPrice);
    }

    function calcLogBPTPrice(
        uint256 balanceA,
        uint256 balanceB,
        uint256 spotPriceA,
        int256 logBptTotalSupply
    ) external pure returns (int256 ret) {
        ret = GyroCEMMOracleMath._calcLogBPTPrice(
            balanceA,
            balanceB,
            spotPriceA,
            logBptTotalSupply
        );
    }

    function calcLogInvariantDivSupply(uint256 invariant, int256 logBptTotalSupply)
        external
        pure
        returns (int256 ret)
    {
        ret = GyroCEMMOracleMath._calcLogInvariantDivSupply(invariant, logBptTotalSupply);
    }
}
