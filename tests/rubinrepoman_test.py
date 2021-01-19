"""Tests for the cachemachine.RubinRepoMan class.

This contains the business logic of going out to the docker
registry, getting the list of available tags, and filtering
that down into a list of images to pull.
"""

from __future__ import annotations

from typing import List

from cachemachine.rubinrepoman import RubinRepoMan
from cachemachine.types import CachedDockerImage

from .docker_mock import DockerMock


async def test_rubinrepoman() -> None:
    """Test RubinRepoMan, including going out to docker

    Note: This test goes over the network, and will make
    sure the business logic is still working with what the
    official repo looks like, and that it still works with
    docker.
    """

    body = {
        "repo": "lsstsqre/sciplat-lab",
        "recommended_tag": "recommended",
        "num_dailies": 1,
        "num_weeklies": 1,
        "num_releases": 1,
    }

    common_cache: List[CachedDockerImage] = []

    r = RubinRepoMan(body)
    di = await r.desired_images(common_cache)
    assert len(di) == 4
    assert di[0].image_url == "lsstsqre/sciplat-lab:recommended"
    assert di[0].name.startswith("Recommended")
    assert di[1].image_url.startswith("lsstsqre/sciplat-lab:r")
    assert di[1].name.startswith("Release ")
    assert di[2].image_url.startswith("lsstsqre/sciplat-lab:w_")
    assert di[2].name.startswith("Weekly ")
    assert di[3].image_url.startswith("lsstsqre/sciplat-lab:d_")
    assert di[3].name.startswith("Daily ")


async def test_rubinrepoman_tag_picking(docker_mock: DockerMock) -> None:
    """Test RubinRepoMan, with a docker mock.

    Note: This doesn't reach out over the network, and uses some
    mocked docker results to test the logic of picking tags out
    of the list.
    """
    body = {
        "repo": "lsstsqre/sciplat-lab",
        "recommended_tag": "recommended",
        "num_dailies": 1,
        "num_weeklies": 1,
        "num_releases": 1,
    }

    # Pretend we're starting from a blank slate, nothing in the
    # cache.
    common_cache: List[CachedDockerImage] = []
    r = RubinRepoMan(body)
    di = await r.desired_images(common_cache)
    assert len(di) == 4
    assert di[0].image_url == "lsstsqre/sciplat-lab:recommended"
    assert di[0].name == "Recommended"
    assert di[1].image_url == "lsstsqre/sciplat-lab:r21_0_0"
    assert di[1].name == "Release r21.0.0"
    assert di[2].image_url == "lsstsqre/sciplat-lab:w_2021_03"
    assert di[2].name == "Weekly 03"
    assert di[3].image_url == "lsstsqre/sciplat-lab:d_2021_01_13"
    assert di[3].name == "Daily 01/13"

    # Now let's pretend we've got the images in the cache.
    # We should be able to notice the other tags that
    # recommended shares in the friendly name of recommended.
    common_cache.extend(
        [
            CachedDockerImage(
                image_url=di[0].image_url,
                image_hash=di[0].image_hash,
                tags={"recommended", "r21_0_0"},
            ),
            CachedDockerImage(
                image_url=di[1].image_url,
                image_hash=di[1].image_hash,
                tags={"recommended", "r21_0_0"},
            ),
        ]
    )

    di = await r.desired_images(common_cache)
    assert len(di) == 4
    assert di[0].image_url == "lsstsqre/sciplat-lab:recommended"
    assert di[0].name == "Recommended (Release r21.0.0)"
    assert di[1].image_url == "lsstsqre/sciplat-lab:r21_0_0"
    assert di[1].name == "Release r21.0.0"
    assert di[2].image_url == "lsstsqre/sciplat-lab:w_2021_03"
    assert di[2].name == "Weekly 03"
    assert di[3].image_url == "lsstsqre/sciplat-lab:d_2021_01_13"
    assert di[3].name == "Daily 01/13"