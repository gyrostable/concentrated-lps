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
pragma experimental ABIEncoderV2;

import "@balancer-labs/v2-vault/contracts/interfaces/IVault.sol";

import "@balancer-labs/v2-pool-utils/contracts/factories/BasePoolSplitCodeFactory.sol";
import "@balancer-labs/v2-pool-utils/contracts/factories/FactoryWidePauseWindow.sol";

import "../../interfaces/ICappedLiquidity.sol";
import "../../interfaces/IGyro3CLPPoolFactory.sol";

import "./Gyro3CLPPool.sol";

contract Gyro3CLPPoolFactory is IGyro3CLPPoolFactory, BasePoolSplitCodeFactory, FactoryWidePauseWindow {
    address public immutable gyroConfigAddress;

    uint256 public constant PAUSE_WINDOW_DURATION = 90 days;
    uint256 public constant BUFFER_PERIOD_DURATION = 30 days;

    constructor(IVault vault, address _gyroConfigAddress) BasePoolSplitCodeFactory(vault, type(Gyro3CLPPool).creationCode) {
        gyroConfigAddress = _gyroConfigAddress;
    }

    /**
     * @dev Deploys a new `Gyro3CLPPool`.
     */
    function create(Gyro3CLPPool.NewPoolConfigParams memory config) external override returns (address) {
        Gyro3CLPPool.NewPoolParams memory params = Gyro3CLPPool.NewPoolParams({
            vault: getVault(),
            configAddress: gyroConfigAddress,
            pauseWindowDuration: PAUSE_WINDOW_DURATION,
            bufferPeriodDuration: BUFFER_PERIOD_DURATION,
            config: config
        });

        return _create(abi.encode(params));
    }
}
