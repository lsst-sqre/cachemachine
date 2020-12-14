from typing import Generator
from unittest.mock import patch

import pytest
from kubernetes import config


@pytest.fixture(autouse=True)
def kubernetes_config() -> Generator:
    with patch.object(config, "load_incluster_config"):
        yield
