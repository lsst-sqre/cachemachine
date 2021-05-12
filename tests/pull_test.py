"""Basic pull test for cachemachine.

This uses the API to create a cachemachine, which will then
use the mocks to simulate looking at docker, and pulling an
image to the local kubernetes nodes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aiohttp.pytest_plugin.test_utils import TestClient

import asyncio

import structlog

from cachemachine.app import create_app
from cachemachine.types import KubernetesLabels

from .docker_mock import DockerMock
from .kubernetes_mock import KubernetesMock

logger = structlog.get_logger(__name__)


async def test_pull(
    aiohttp_client: TestClient,
    docker_mock: DockerMock,
    kubernetes_mock: KubernetesMock,
) -> None:
    """Send a POST to the API and make sure images are pulled."""
    app = create_app()
    client = await aiohttp_client(app)

    HOST = "registry.hub.docker.com"

    expected_images = [
        {
            "image_url": f"{HOST}/lsstsqre/sciplat-lab:recommended",
            "image_hash": "sha256:b0b7d97ff9d62ccd049",
            "name": "Recommended (Release r21.0.0)",
        },
        {
            "image_url": f"{HOST}/lsstsqre/sciplat-lab:r21_0_0",
            "image_hash": "sha256:b0b7d97ff9d62ccd049",
            "name": "Release r21.0.0",
        },
        {
            "image_url": f"{HOST}/lsstsqre/sciplat-lab:w_2021_18_c0020.001",
            "image_hash": "sha256:0123456789abcdef",
            "name": "Weekly 2021_18_c0020.001",
        },
        {
            "image_url": f"{HOST}/lsstsqre/sciplat-lab:d_2021_01_13",
            "image_hash": "sha256:343b17341d0e961472",
            "name": "Daily 2021_01_13",
        },
    ]

    post_data = {
        "name": "jupyter",
        "labels": {"k1": "v1"},
        "repomen": [
            {
                "type": "RubinRepoMan",
                "repo": "lsstsqre/sciplat-lab",
                "recommended_tag": "recommended",
                "num_releases": 1,
                "num_weeklies": 1,
                "num_dailies": 1,
            }
        ],
    }

    # Create a cachemachine with the post data
    response = await client.post("/cachemachine/", json=post_data)
    logger.debug(response)
    assert response.status == 200

    # Let the engine run through its iterations, then check results.
    await asyncio.sleep(0.1)

    # Check the status of the cachemachine.
    response = await client.get("/cachemachine/jupyter")
    logger.debug(response)
    assert response.status == 200
    data = await response.json()
    logger.debug(data)

    # Check results.
    assert data["name"] == post_data["name"]
    assert data["labels"] == post_data["labels"]
    assert data["desired_images"] == expected_images
    assert data["available_images"] == expected_images

    # Delete cachemachine.
    response = await client.delete("/cachemachine/jupyter")
    assert response.status == 200


async def test_fight_prepull(
    aiohttp_client: TestClient,
    docker_mock: DockerMock,
    kubernetes_mock: KubernetesMock,
) -> None:
    """Now this shouldn't cause a problem...

    Sometimes both the prepullers might be running.  While this may be
    additional work it shouldn't cause a problem.  But we noticed some
    issues with parsing images that the prepuller got to first in testing.
    """

    # First, let's use the kubernetes mock to pretend to pull some
    # images like the prepuller would...
    kubernetes_mock.daemonset_create(
        "prepuller",
        "docker.io/lsstsqre/sciplat-lab:prepuller_pulled_recommended",
        "pull-secret",
        KubernetesLabels({"k1": "v1"}),
    )
    kubernetes_mock.daemonset_finished("prepuller")
    assert kubernetes_mock.daemonset_finished("prepuller")

    # Now it should be in the cache.
    # Run the normal test.
    await test_pull(aiohttp_client, docker_mock, kubernetes_mock)
