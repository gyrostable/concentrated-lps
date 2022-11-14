// SPDX-License-Identifier: LicenseRef-Gyro-1.0
// for information on licensing please see the README in the GitHub repository <https://github.com/gyrostable/concentrated-lps>.

pragma solidity 0.7.6;

library Buffer {
    // The buffer is a circular storage structure with 1024 slots.
    // solhint-disable-next-line private-vars-leading-underscore
    uint256 internal constant SIZE = 1024;

    /**
     * @dev Returns the index of the element before the one pointed by `index`.
     */
    function prev(uint256 index) internal pure returns (uint256) {
        return sub(index, 1);
    }

    /**
     * @dev Returns the index of the element after the one pointed by `index`.
     */
    function next(uint256 index) internal pure returns (uint256) {
        return add(index, 1);
    }

    /**
     * @dev Returns the index of an element `offset` slots after the one pointed by `index`.
     */
    function add(uint256 index, uint256 offset) internal pure returns (uint256) {
        return (index + offset) % SIZE;
    }

    /**
     * @dev Returns the index of an element `offset` slots before the one pointed by `index`.
     */
    function sub(uint256 index, uint256 offset) internal pure returns (uint256) {
        return (index + SIZE - offset) % SIZE;
    }
}
