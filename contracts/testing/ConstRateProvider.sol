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

// Copy of MockRateProvider.sol, but Ownable authorization to change the rate. For live on-chain testing.
// Probably not useful in production.

pragma solidity ^0.7.0;

import "@balancer-labs/v2-solidity-utils/contracts/math/FixedPoint.sol";

import "@balancer-labs/v2-pool-utils/contracts/interfaces/IRateProvider.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

contract ConstRateProvider is IRateProvider, Ownable {
    uint256 internal _rate;

    constructor() {
        _rate = FixedPoint.ONE;
    }

    function getRate() external view override returns (uint256) {
        return _rate;
    }

    function setRate(uint256 newRate) external onlyOwner {
        _rate = newRate;
    }
}
