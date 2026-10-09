import types

import pytest

import config


@pytest.fixture
def cfg():
    """Copy of config.py that a test may change freely."""
    ns = types.SimpleNamespace(**{k: getattr(config, k) for k in dir(config) if k.isupper()})
    ns.CONSOLE_LOG_EVERY = 0
    # Короткий маршрут для скорости тестов (в сцене 1 плечо 56.6 м, см. config.py)
    ns.TARGET_OFFSET_X, ns.TARGET_OFFSET_Y = 20.0, 8.0
    return ns
