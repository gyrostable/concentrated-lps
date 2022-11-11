// SPDX-License-Identifier: for information on licensing please see the README in the GitHub repository <https://github.com/gyrostable/concentrated-lps>. 

/*
This is a dummy contract that does nothing but pull in QueryProcessor as a dependency. To work around a brownie bug where QueryProcessor would not be available unless a contract that depends on it is recompiled.

To use, rm build/contracts/DependencyDummy.json before the brownie operation you want to do. Brownie will recompile this contract (which is trivial) and QueryProcessor.
*/

pragma solidity 0.7.6;

import "@balancer-labs/v2-pool-utils/contracts/oracle/QueryProcessor.sol";

contract DependencyDummy {}
