// SPDX-License-Identifier: GPL-3.0-or-later
pragma solidity ^0.7.0;

interface ILocallyPausable {
    event PausedLocally();
    event UnpausedLocally();
    event PauseManagerChanged(address oldPauseManager, address newPauseManager);

    /// @notice Changes the account that is allowed to pause a pool.
    function changePauseManager(address _pauseManager) external;

    /// @notice Pauses the pool.
    /// Can only be called by the pause manager.
    function pause() external;

    /// @notice Unpauses the pool.
    /// Can only be called by the pause manager.
    function unpause() external;
}
