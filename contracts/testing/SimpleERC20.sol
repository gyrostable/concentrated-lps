// SPDX-License-Identifier: MIT
pragma solidity ^0.7.0;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

contract SimpleERC20 is ERC20, Ownable {
    constructor() ERC20("MyToken", "MTK") {
        // solhint-disable-previous-line no-empty-blocks
    }

    function mint(address to, uint256 amount) public onlyOwner {
        _mint(to, amount);
    }
}
