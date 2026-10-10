import pytest

from captive.config import load_config


@pytest.fixture(scope="session")
def base_cfg():
    return load_config()


@pytest.fixture
def small_cfg(base_cfg):
    """Base config with fewer simulations so the suite runs in seconds."""
    import copy

    cfg = copy.deepcopy(base_cfg)
    cfg["meta"]["n_sims"] = 20_000
    return cfg
