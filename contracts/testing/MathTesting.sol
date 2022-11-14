// SPDX-License-Identifier: LicenseRef-Gyro-1.0
// for information on licensing please see the README in the GitHub repository <https://github.com/gyrostable/concentrated-lps>.

pragma solidity 0.7.6;

// import "@balancer-labs/v2-solidity-utils/contracts/math/FixedPoint.sol";
import "../../libraries/GyroFixedPoint.sol";
import "../../libraries/GyroPoolMath.sol";

contract MathTesting {
    using GyroFixedPoint for uint256;

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

    function sqrt(uint256 a) external pure returns (uint256) {
        //        return a.powDown(FixedPoint.ONE / 2);
        return a.powUp(GyroFixedPoint.ONE / 2);
    }

    function sqrtNewton(uint256 input, uint256 tolerance) external pure returns (uint256) {
        return GyroPoolMath._sqrt(input, tolerance);
    }

    function sqrtNewtonInitialGuess(uint256 input) external pure returns (uint256) {
        return GyroPoolMath._makeInitialGuess(input);
    }
}
