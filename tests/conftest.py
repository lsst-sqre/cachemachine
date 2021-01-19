from typing import Generator
from unittest.mock import patch

import pytest
from kubernetes import config

from .docker_mock import DockerMock


@pytest.fixture(autouse=True)
def kubernetes_config() -> Generator:
    with patch.object(config, "load_incluster_config"):
        yield


@pytest.fixture
def docker_mock() -> Generator:
    mock_registry = {
        "recommended": "sha256:b0b7d97ff9d62ccd049",
        "r21_0_0": "sha256:b0b7d97ff9d62ccd049",
        "w_2021_03": "sha256:bb16e5ea71bd7139779",
        "w_2021_02": "sha256:bad6e5ea71bd7139779",
        "d_2021_01_13": "sha256:343b17341d0e961472",
        "d_2021_01_12": "sha256:badb17341d0e961471",
    }

    with patch("cachemachine.rubinrepoman.DockerClient") as mock:
        mock.return_value = DockerMock(mock_registry)
        yield
