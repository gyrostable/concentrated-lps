// SPDX-License-Identifier: GPL-3.0-or-later
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.

// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.

// You should have received a copy of the GNU General Public License
// along with this program.  If not, see <http://www.gnu.org/licenses/>.

pragma solidity ^0.7.0;

import "@balancer-labs/v2-solidity-utils/contracts/math/FixedPoint.sol";
import "@balancer-labs/v2-solidity-utils/contracts/math/Math.sol";
import "@balancer-labs/v2-solidity-utils/contracts/helpers/InputHelpers.sol";

library GyroPoolMath {
    using FixedPoint for uint256;

    uint256 private constant SQRT_1E_NEG_1 = 316227766016837933;
    uint256 private constant SQRT_1E_NEG_3 = 31622776601683793;
    uint256 private constant SQRT_1E_NEG_5 = 3162277660168379;
    uint256 private constant SQRT_1E_NEG_7 = 316227766016837;
    uint256 private constant SQRT_1E_NEG_9 = 31622776601683;
    uint256 private constant SQRT_1E_NEG_11 = 3162277660168;
    uint256 private constant SQRT_1E_NEG_13 = 316227766016;
    uint256 private constant SQRT_1E_NEG_15 = 31622776601;
    uint256 private constant SQRT_1E_NEG_17 = 316227766;

    uint256 private constant MIN_NEWTON_STEP_SIZE = 5;

    /** @dev Implements square root algorithm using Newton's method and a first-guess optimisation **/
    function _sqrt(uint256 input, uint256 tolerance) internal pure returns (uint256) {
        if (input == 0) {
            return 0;
        }

        uint256 guess = _makeInitialGuess(input);

        // 7 iterations
        guess = (guess + ((input * FixedPoint.ONE) / guess)) / 2;
        guess = (guess + ((input * FixedPoint.ONE) / guess)) / 2;
        guess = (guess + ((input * FixedPoint.ONE) / guess)) / 2;
        guess = (guess + ((input * FixedPoint.ONE) / guess)) / 2;
        guess = (guess + ((input * FixedPoint.ONE) / guess)) / 2;
        guess = (guess + ((input * FixedPoint.ONE) / guess)) / 2;
        guess = (guess + ((input * FixedPoint.ONE) / guess)) / 2;

        // Check in some epsilon range
        // Check square is more or less correct
        uint256 guessSquared = guess.mulDown(guess);
        require(guessSquared <= input.add(guess.mulUp(tolerance)) && guessSquared >= input.sub(guess.mulUp(tolerance)), "_sqrt FAILED");

        return guess;
    }

    function _makeInitialGuess(uint256 input) internal pure returns (uint256) {
        if (input >= FixedPoint.ONE) {
            return (1 << (_intLog2Halved(input / FixedPoint.ONE))) * FixedPoint.ONE;
        } else {
            if (input < 10) {
                return SQRT_1E_NEG_17;
            }
            if (input < 1e2) {
                return 1e10;
            }
            if (input < 1e3) {
                return SQRT_1E_NEG_15;
            }
            if (input < 1e4) {
                return 1e11;
            }
            if (input < 1e5) {
                return SQRT_1E_NEG_13;
            }
            if (input < 1e6) {
                return 1e12;
            }
            if (input < 1e7) {
                return SQRT_1E_NEG_11;
            }
            if (input < 1e8) {
                return 1e13;
            }
            if (input < 1e9) {
                return SQRT_1E_NEG_9;
            }
            if (input < 1e10) {
                return 1e14;
            }
            if (input < 1e11) {
                return SQRT_1E_NEG_7;
            }
            if (input < 1e12) {
                return 1e15;
            }
            if (input < 1e13) {
                return SQRT_1E_NEG_5;
            }
            if (input < 1e14) {
                return 1e16;
            }
            if (input < 1e15) {
                return SQRT_1E_NEG_3;
            }
            if (input < 1e16) {
                return 1e17;
            }
            if (input < 1e17) {
                return SQRT_1E_NEG_1;
            }
            return input;
        }
    }

    function _intLog2Halved(uint256 x) public pure returns (uint256 n) {
        if (x >= 1 << 128) {
            x >>= 128;
            n += 64;
        }
        if (x >= 1 << 64) {
            x >>= 64;
            n += 32;
        }
        if (x >= 1 << 32) {
            x >>= 32;
            n += 16;
        }
        if (x >= 1 << 16) {
            x >>= 16;
            n += 8;
        }
        if (x >= 1 << 8) {
            x >>= 8;
            n += 4;
        }
        if (x >= 1 << 4) {
            x >>= 4;
            n += 2;
        }
        if (x >= 1 << 2) {
            x >>= 2;
            n += 1;
        }
    }
}
