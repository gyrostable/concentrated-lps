// SPDX-License-Identifier: UNLICENSE

pragma solidity ^0.7.0;

import "@balancer-labs/v2-solidity-utils/contracts/math/FixedPoint.sol";

contract MathTesting {
    using FixedPoint for uint256;

    function add(uint256 a, uint256 b) external pure returns (uint256) {
        return a.add(b);
    }

    function sub(uint256 a, uint256 b) external pure returns (uint256) {
        return a.sub(b);
    }

    function mul(uint256 a, uint256 b) external pure returns (uint256) {
        return a.mulDown(b);
    }

    function truediv(uint256 a, uint256 b) external pure returns (uint256) {
        return a.divDown(b);
    }
}
