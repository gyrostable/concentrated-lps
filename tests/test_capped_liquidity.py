import pytest

from brownie.test.managers.runner import RevertContextManager as reverts

from tests.support.types import CapParams
from tests.support.utils import scale


OVER_GLOBAL_CAP = "over global liquidity cap"
OVER_ADDRESS_CAP = "over address liquidity cap"
NOT_AUTHORIZED = "not authorized"
UNCAPPED = "pool is uncapped"


INITIAL_GLOBAL_CAP = scale(10_000)
INITIAL_PER_ADDRESS_CAP = scale(5_000)

INITIAL_CAP_PARAMS = CapParams(
    cap_enabled=True,
    global_cap=int(INITIAL_GLOBAL_CAP),
    per_address_cap=int(INITIAL_PER_ADDRESS_CAP),
)

HIGHER_CAP_PARAMS = CapParams(
    cap_enabled=True,
    global_cap=int(scale(20_000)),
    per_address_cap=int(scale(10_000)),
)


@pytest.fixture(scope="module")
def mock_capped_pool(MockCappedPool, admin):
    return admin.deploy(MockCappedPool, admin, INITIAL_CAP_PARAMS)


def test_params(mock_capped_pool, alice):
    assert CapParams(*mock_capped_pool.capParams()) == INITIAL_CAP_PARAMS

    mock_capped_pool.setCapParams(HIGHER_CAP_PARAMS)

    assert CapParams(*mock_capped_pool.capParams()) == HIGHER_CAP_PARAMS

    with reverts(NOT_AUTHORIZED):
        mock_capped_pool.setCapParams(HIGHER_CAP_PARAMS, {"from": alice})

    new_params = CapParams(cap_enabled=False, global_cap=0, per_address_cap=0)
    mock_capped_pool.setCapParams(new_params)

    assert CapParams(*mock_capped_pool.capParams()) == new_params

    with reverts(UNCAPPED):
        mock_capped_pool.setCapParams(new_params)


def test_per_address_cap(mock_capped_pool, alice, bob):
    tx = mock_capped_pool.joinPool(INITIAL_PER_ADDRESS_CAP, {"from": alice})
    assert tx.events["Transfer"][0]["to"] == alice
    assert tx.events["Transfer"][0]["value"] == INITIAL_PER_ADDRESS_CAP

    with reverts(OVER_ADDRESS_CAP):
        mock_capped_pool.joinPool(1, {"from": alice})

    tx = mock_capped_pool.joinPool(INITIAL_PER_ADDRESS_CAP, {"from": bob})
    assert tx.events["Transfer"][0]["to"] == bob
    assert tx.events["Transfer"][0]["value"] == INITIAL_PER_ADDRESS_CAP

    mock_capped_pool.setCapParams(HIGHER_CAP_PARAMS)
    tx = mock_capped_pool.joinPool(INITIAL_PER_ADDRESS_CAP, {"from": alice})
    assert tx.events["Transfer"][0]["value"] == INITIAL_PER_ADDRESS_CAP


def test_global_cap(mock_capped_pool, admin, alice, bob):
    mock_capped_pool.joinPool(INITIAL_PER_ADDRESS_CAP, {"from": bob})
    mock_capped_pool.joinPool(INITIAL_PER_ADDRESS_CAP, {"from": alice})

    with reverts(OVER_GLOBAL_CAP):
        mock_capped_pool.joinPool(1, {"from": admin})

    mock_capped_pool.setCapParams(HIGHER_CAP_PARAMS)
    tx = mock_capped_pool.joinPool(INITIAL_PER_ADDRESS_CAP, {"from": admin})
    assert tx.events["Transfer"][0]["value"] == INITIAL_PER_ADDRESS_CAP
