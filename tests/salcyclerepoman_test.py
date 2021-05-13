"""Tests for the cachemachine.SALCycleRepoMan class.

This tests filtering by cycle, which is the only way in which SALCycleRepoMan
differs from RubinRepoMan
"""

from __future__ import annotations

from typing import List

from cachemachine.salcyclerepoman import SALCycleRepoMan
from cachemachine.types import CachedDockerImage

from .docker_mock import DockerMock

HOST = "registry.hub.docker.com"


async def test_salcyclerepoman_tag_picking(docker_mock: DockerMock) -> None:
    """Test SALCycleRepoMan, with a docker mock and a specified XML cycle.

    Note: This doesn't reach out over the network, and uses some
    mocked docker results to test the logic of picking tags out
    of the list.
    """
    body = {
        "repo": "lsstts/sal-sciplat-lab",
        "recommended_tag": "recommended",
        "num_dailies": 1,
        "num_weeklies": 1,
        "num_releases": 1,
        "cycle": 20,
    }

    # Pretend we're starting from a blank slate, nothing in the
    # cache.
    common_cache: List[CachedDockerImage] = []
    s = SALCycleRepoMan(body)
    desired_images = await s.desired_images(common_cache)
    di = desired_images.desired_images
    ai = desired_images.all_images

    print(di)
    print(ai)
    assert len(di) == 1
    assert (
        di[0].image_url == f"{HOST}/lsstts/sal-sciplat-lab:w_2021_18_c0020.001"
    )
    assert di[0].name == "Weekly 2021_18_c0020.001"
    assert len(ai) == 1
    assert (
        ai[0].image_url == f"{HOST}/lsstts/sal-sciplat-lab:w_2021_18_c0020.001"
    )
    assert ai[0].name == "w_2021_18_c0020.001"
