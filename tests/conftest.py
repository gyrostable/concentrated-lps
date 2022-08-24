from tests.support.quantized_decimal import QuantizedDecimal as D
import pytest

from tests.support.types import TwoPoolBaseParams, TwoPoolParams

TOKENS_PER_USER = 1000 * 10 ** 18


@pytest.fixture(scope="module")
def admin(accounts):
    return accounts[0]


@pytest.fixture(scope="module")
def users(accounts):
    return (accounts[1], accounts[2])


@pytest.fixture(scope="module")
def gyro_two_math_testing(admin, GyroTwoMathTesting):
    return admin.deploy(GyroTwoMathTesting)


@pytest.fixture(scope="module")
def gyro_three_math_testing(admin, GyroThreeMathTesting):
    return admin.deploy(GyroThreeMathTesting)


@pytest.fixture(scope="module")
def mock_gyro_config(admin, MockGyroConfig):
    return admin.deploy(MockGyroConfig)


@pytest.fixture(scope="module")
def gyro_erc20_empty(admin, SimpleERC20):
    return (admin.deploy(SimpleERC20), admin.deploy(SimpleERC20))


@pytest.fixture(scope="module")
def gyro_erc20_funded(admin, SimpleERC20, users):
    gyro_erc20_0 = admin.deploy(SimpleERC20)
    gyro_erc20_1 = admin.deploy(SimpleERC20)

    gyro_erc20_0.mint(users[0], TOKENS_PER_USER)
    gyro_erc20_1.mint(users[0], TOKENS_PER_USER)
    gyro_erc20_0.mint(users[1], TOKENS_PER_USER)
    gyro_erc20_1.mint(users[1], TOKENS_PER_USER)

    # tokens must be ordered when deploying the GyroTwoPool
    if gyro_erc20_0.address.lower() < gyro_erc20_1.address.lower():
        return (gyro_erc20_0, gyro_erc20_1)
    else:
        return (gyro_erc20_1, gyro_erc20_0)


@pytest.fixture(scope="module")
def authorizer(admin, Authorizer):
    return admin.deploy(Authorizer, admin)


@pytest.fixture(scope="module")
def mock_vault(admin, MockVault, authorizer):
    return admin.deploy(MockVault, authorizer)


@pytest.fixture(scope="module")
def balancer_vault(admin, BalancerVault, SimpleERC20, authorizer):
    weth9 = admin.deploy(SimpleERC20)
    return admin.deploy(BalancerVault, authorizer.address, weth9.address, 0, 0)


@pytest.fixture(scope="module")
def balancer_vault_pool(
    admin,
    GyroTwoPool,
    gyro_erc20_funded,
    balancer_vault,
    QueryProcessor,
    mock_gyro_config,
):
    admin.deploy(QueryProcessor)
    args = TwoPoolParams(
        baseParams=TwoPoolBaseParams(
            vault=balancer_vault.address,
            name="GyroTwoPool",  # string
            symbol="GTP",  # string
            token0=gyro_erc20_funded[0].address,  # IERC20
            token1=gyro_erc20_funded[1].address,  # IERC20
            normalizedWeight0=D("0.6") * 10 ** 18,  # uint256
            normalizedWeight1=D("0.4") * 10 ** 18,  # uint256
            swapFeePercentage=1 * 10 ** 15,  # 0.5%
            pauseWindowDuration=0,  # uint256
            bufferPeriodDuration=0,  # uint256
            oracleEnabled=False,  # bool
            owner=admin,  # address
        ),
        sqrtAlpha=D("0.97") * 10 ** 18,  # uint256
        sqrtBeta=D("1.02") * 10 ** 18,  # uint256
    )
    return admin.deploy(GyroTwoPool, args, mock_gyro_config.address)


@pytest.fixture(scope="module")
def mock_vault_pool(
    admin, GyroTwoPool, gyro_erc20_funded, mock_vault, QueryProcessor, mock_gyro_config
):
    admin.deploy(QueryProcessor)
    args = TwoPoolParams(
        baseParams=TwoPoolBaseParams(
            vault=mock_vault.address,
            name="GyroTwoPool",  # string
            symbol="GTP",  # string
            token0=gyro_erc20_funded[0].address,  # IERC20
            token1=gyro_erc20_funded[1].address,  # IERC20
            normalizedWeight0=D("0.6") * 10 ** 18,  # uint256
            normalizedWeight1=D("0.4") * 10 ** 18,  # uint256
            swapFeePercentage=D(1) * 10 ** 15,  # 0.5%
            pauseWindowDuration=0,  # uint256
            bufferPeriodDuration=0,  # uint256
            oracleEnabled=False,  # bool
            owner=admin,  # address
        ),
        sqrtAlpha=D("0.97") * 10 ** 18,  # uint256
        sqrtBeta=D("1.02") * 10 ** 18,  # uint256
    )
    return admin.deploy(GyroTwoPool, args, mock_gyro_config.address)


@pytest.fixture(scope="module")
def math_testing(admin, MathTesting):
    return admin.deploy(MathTesting)


@pytest.fixture(scope="module")
def mock_gyro_two_oracle_math(admin, MockGyroTwoOracleMath):
    return admin.deploy(MockGyroTwoOracleMath)


@pytest.fixture(scope="module")
def pool_factory(admin, GyroTwoPoolFactory, gyro_config):
    return admin.deploy(GyroTwoPoolFactory, balancer_vault, gyro_config.address)


@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass
