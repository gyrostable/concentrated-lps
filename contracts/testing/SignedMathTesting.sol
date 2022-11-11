// SPDX-License-Identifier: for information on licensing please see the README in the GitHub repository <https://github.com/gyrostable/concentrated-lps>. 

pragma solidity 0.7.6;

import "../../libraries/SignedFixedPoint.sol";

contract SignedMathTesting {
    using SignedFixedPoint for int256;

    function add(int256 a, int256 b) external pure returns (int256) {
        return a.add(b);
    }

    function sub(int256 a, int256 b) external pure returns (int256) {
        return a.sub(b);
    }

    function mul(int256 a, int256 b) external pure returns (int256) {
        return a.mulDownMag(b);
    }

    function truediv(int256 a, int256 b) external pure returns (int256) {
        return a.divDownMag(b);
    }

    function mulUp(int256 a, int256 b) external pure returns (int256) {
        return a.mulUpMag(b);
    }

    function mulUpU(int256 a, int256 b) external pure returns (int256) {
        return a.mulUpMagU(b);
    }

    function mulDown(int256 a, int256 b) external pure returns (int256) {
        return a.mulDownMag(b);
    }

    function mulDownU(int256 a, int256 b) external pure returns (int256) {
        return a.mulDownMagU(b);
    }

    function divUp(int256 a, int256 b) external pure returns (int256) {
        return a.divUpMag(b);
    }

    function divUpU(int256 a, int256 b) external pure returns (int256) {
        return a.divUpMagU(b);
    }

    function divDown(int256 a, int256 b) external pure returns (int256) {
        return a.divDownMag(b);
    }

    function divDownU(int256 a, int256 b) external pure returns (int256) {
        return a.divDownMagU(b);
    }

    function addMag(int256 a, int256 b) external pure returns (int256) {
        return SignedFixedPoint.addMag(a, b);
    }

    function mulXp(int256 a, int256 b) external pure returns (int256) {
        return SignedFixedPoint.mulXp(a, b);
    }

    function mulXpU(int256 a, int256 b) external pure returns (int256) {
        return SignedFixedPoint.mulXpU(a, b);
    }

    function divXp(int256 a, int256 b) external pure returns (int256) {
        return SignedFixedPoint.divXp(a, b);
    }

    function divXpU(int256 a, int256 b) external pure returns (int256) {
        return SignedFixedPoint.divXpU(a, b);
    }

    function mulDownXpToNp(int256 a, int256 b) external pure returns (int256) {
        return SignedFixedPoint.mulDownXpToNp(a, b);
    }

    function mulDownXpToNpU(int256 a, int256 b) external pure returns (int256) {
        return SignedFixedPoint.mulDownXpToNpU(a, b);
    }

    function mulUpXpToNp(int256 a, int256 b) external pure returns (int256) {
        return SignedFixedPoint.mulUpXpToNp(a, b);
    }

    function mulUpXpToNpU(int256 a, int256 b) external pure returns (int256) {
        return SignedFixedPoint.mulUpXpToNpU(a, b);
    }
}
