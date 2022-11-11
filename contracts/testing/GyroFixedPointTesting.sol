// SPDX-License-Identifier: for information on licensing please see the README in the GitHub repository <https://github.com/gyrostable/concentrated-lps>. 

pragma solidity ^0.7.0;

import "../../libraries/GyroFixedPoint.sol";

contract GyroFixedPointTesting {
    using GyroFixedPoint for uint256;

    function add(uint256 a, uint256 b) external pure returns (uint256) {
        return a.add(b);
    }

    function sub(uint256 a, uint256 b) external pure returns (uint256) {
        return a.sub(b);
    }

    function mulUp(uint256 a, uint256 b) external pure returns (uint256) {
        return a.mulUp(b);
    }

    function mulUpU(uint256 a, uint256 b) external pure returns (uint256) {
        return a.mulUpU(b);
    }

    function mulDown(uint256 a, uint256 b) external pure returns (uint256) {
        return a.mulDown(b);
    }

    function mulDownU(uint256 a, uint256 b) external pure returns (uint256) {
        return a.mulDownU(b);
    }

    function divUp(uint256 a, uint256 b) external pure returns (uint256) {
        return a.divUp(b);
    }

    function divUpU(uint256 a, uint256 b) external pure returns (uint256) {
        return a.divUpU(b);
    }

    function divDown(uint256 a, uint256 b) external pure returns (uint256) {
        return a.divDown(b);
    }

    function divDownU(uint256 a, uint256 b) external pure returns (uint256) {
        return a.divDownU(b);
    }

    function mulDownLargeSmall(uint256 a, uint256 b) external pure returns (uint256) {
        return a.mulDownLargeSmall(b);
    }

    function mulDownLargeSmallU(uint256 a, uint256 b) external pure returns (uint256) {
        return a.mulDownLargeSmallU(b);
    }

    function divDownLarge(uint256 a, uint256 b) external pure returns (uint256) {
        return a.divDownLarge(b);
    }

    function divDownLargeU(uint256 a, uint256 b) external pure returns (uint256) {
        return a.divDownLargeU(b);
    }

    function divDownLarge(
        uint256 a,
        uint256 b,
        uint256 d,
        uint256 e
    ) external pure returns (uint256) {
        return GyroFixedPoint.divDownLarge(a, b, d, e);
    }

    function divDownLargeU(
        uint256 a,
        uint256 b,
        uint256 d,
        uint256 e
    ) external pure returns (uint256) {
        return GyroFixedPoint.divDownLargeU(a, b, d, e);
    }
}
