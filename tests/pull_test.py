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

    expected_images = [
        {
            "image_url": "lsstsqre/sciplat-lab:recommended",
            "image_hash": "sha256:b0b7d97ff9d62ccd049",
            "name": "Recommended",
        },
        {
            "image_url": "lsstsqre/sciplat-lab:r21_0_0",
            "image_hash": "sha256:b0b7d97ff9d62ccd049",
            "name": "Release r21.0.0",
        },
        {
            "image_url": "lsstsqre/sciplat-lab:w_2021_03",
            "image_hash": "sha256:bb16e5ea71bd7139779",
            "name": "Weekly 03",
        },
        {
            "image_url": "lsstsqre/sciplat-lab:d_2021_01_13",
            "image_hash": "sha256:343b17341d0e961472",
            "name": "Daily 01/13",
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

    response = await client.post("/cachemachine/", json=post_data)
    logger.debug(response)
    assert response.status == 200

    # Let the engine run through its iterations, then check results.
    await asyncio.sleep(0.1)

    response = await client.get("/cachemachine/jupyter")
    logger.debug(response)
    assert response.status == 200
    data = await response.json()
    logger.debug(data)

    assert data["name"] == post_data["name"]
    assert data["labels"] == post_data["labels"]
    assert data["desired_images"] == expected_images
    assert data["available_images"] == expected_images

    response = await client.delete("/cachemachine/jupyter")
    assert response.status == 200
