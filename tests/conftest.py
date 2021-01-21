from typing import Generator
from unittest.mock import patch

import pytest
from kubernetes import config

from .docker_mock import DockerMock
from .kubernetes_mock import KubernetesMock


@pytest.fixture(autouse=True)
def kubernetes_config() -> Generator:
    with patch.object(config, "load_incluster_config"):
        yield


mock_registry = {
    "recommended": "sha256:b0b7d97ff9d62ccd049",
    "r21_0_0": "sha256:b0b7d97ff9d62ccd049",
    "w_2021_03": "sha256:bb16e5ea71bd7139779",
    "w_2021_02": "sha256:bad6e5ea71bd7139779",
    "d_2021_01_13": "sha256:343b17341d0e961472",
    "d_2021_01_12": "sha256:badb17341d0e961471",
}


@pytest.fixture
def docker_mock() -> Generator:
    with patch("cachemachine.rubinrepoman.DockerClient") as mock:
        mock.return_value = DockerMock(mock_registry)
        yield


@pytest.fixture
def kubernetes_mock() -> Generator:
    kube_mock = KubernetesMock(mock_registry)
    with patch("cachemachine.cachedepositer.KubernetesClient") as m1, patch(
        "cachemachine.cachechecker.KubernetesClient"
    ) as m2:
        m1.return_value = kube_mock
        m2.return_value = kube_mock
        yield
