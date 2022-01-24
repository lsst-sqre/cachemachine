"""Pytest fixtures to use for testing."""

import asyncio
from typing import Generator
from unittest.mock import patch

import pytest
from kubernetes import config

import cachemachine.cachemachine
import cachemachine.rubinrepoman

from .docker_mock import DockerMock
from .kubernetes_mock import KubernetesMock


@pytest.fixture(autouse=True)
def kubernetes_config() -> Generator:
    """Mocks out load_incluster_config with a noop.

    load_incluster_config is what you are supposed to call running
    in a kubernetes cluster to prepare the client.  This throws an
    exception when run outside of a cluster."""
    with patch.object(config, "load_incluster_config"):
        yield


@pytest.fixture(autouse=True)
def sleep_noop() -> Generator:
    """Mocks out time / waiting.

    Cachemachine will call _wait to wait until the next time it should
    check for changes and update its state.  For testing, we aren't
    waiting on a real kubernetes, so speed up time by nooping this.

    But only for a certain number of iterations.  Because the mock
    kubernetes daemonset only takes 2 iterations to complete, this
    makes all the tests reproducible.  After that number of iterations,
    the test is considered over, so waiting for a while while the
    app is torn down from the test."""
    with patch.object(cachemachine.cachemachine, "_wait") as mock:
        counter = 100

        async def noop() -> None:
            nonlocal counter
            if counter == 0:
                await asyncio.sleep(60)
            else:
                counter -= 1

        # Note: since this is async, we need to use side_effect,
        # not return_value.
        mock.side_effect = noop
        yield


"""Mock docker registry containing tags of a Rubin format and some
pretend hashes.  Note, hashes aren't the correct length, but that
doesn't matter."""
mock_registry = {
    "prepuller_pulled_recommended": "sha256:b0b7d97ff9d62ccd049",
    "recommended": "sha256:b0b7d97ff9d62ccd049",
    "r22_0_0_rc1": "sha256:0000deadbeeffaceffff",
    "r21_0_0": "sha256:b0b7d97ff9d62ccd049",
    "w_2021_22": "sha256:3fc76a592a063b9532f",
    "w_2021_21_c0021.003": "sha256:77cd87542ba742ba407",
    #  Not-known-to-be-alias-tags-that-are-aliases need a little more work.
    #  We need to decide if these count as one image or multiple images and
    #  whether to further resolve the display name if we collapse them into
    #  fewer images.
    #    "w_2021_21_c0021.003_20210514": "sha256:77cd87542ba742ba407",
    #    "w_2021_21_20210514": "sha256:77cd87542ba742ba407",
    "w_2021_19_c0020.001": "sha256:6259c1b6c6a3d042b5",
    "w_2021_03": "sha256:bb16e5ea71bd7139779",
    "d_2021_01_13": "sha256:343b17341d0e961472",
    "d_2021_01_12": "sha256:badb17341d0e961471",
}


@pytest.fixture
def docker_mock() -> Generator:
    """Use the mock docker client."""
    with patch("cachemachine.rubinrepoman.DockerClient") as mock:
        mock.return_value = DockerMock(mock_registry)
        yield mock.return_value


@pytest.fixture
def kubernetes_mock() -> Generator:
    """Use the mock kubernetes client."""
    kube_mock = KubernetesMock(mock_registry)
    with patch("cachemachine.cachemachine.KubernetesClient") as mock:
        mock.return_value = kube_mock
        yield mock.return_value
