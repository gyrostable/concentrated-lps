// SPDX-License-Identifier: LicenseRef-Gyro-1.0
// for information on licensing please see the README in the GitHub repository <https://github.com/gyrostable/core-protocol>.

pragma solidity ^0.7.0;

// solhint-disable

library Gyro2PoolErrors {
    // Math
    uint256 internal constant SQRT_PARAMS_WRONG = 350;
    uint256 internal constant ASSET_BOUNDS_EXCEEDED = 357; //NB this is the same as the CEMM
}
