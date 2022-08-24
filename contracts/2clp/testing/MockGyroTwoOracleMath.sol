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
