import types

import pytest

import config


@pytest.fixture
def cfg():
    """Copy of config.py that a test may change freely."""
    ns = types.SimpleNamespace(**{k: getattr(config, k) for k in dir(config) if k.isupper()})
    ns.CONSOLE_LOG_EVERY = 0
    return ns
