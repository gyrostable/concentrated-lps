// SPDX-License-Identifier: GPL-3.0-or-later

pragma solidity 0.7.6;
pragma experimental ABIEncoderV2;

import "@balancer-labs/v2-solidity-utils/contracts/openzeppelin/ERC20.sol";

import "../CappedLiquidity.sol";

contract MockCappedPool is ERC20, CappedLiquidity {
    constructor(address capManager, CapParams memory capParams) ERC20("Dummy", "DUM") CappedLiquidity(capManager, capParams) {}

    function joinPool(uint256 amount) external {
        if (_capParams.capEnabled) {
            _ensureCap(amount, balanceOf(msg.sender), totalSupply());
        }
        _mint(msg.sender, amount);
    }
}
