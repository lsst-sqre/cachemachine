"""Tests for the cachemachine.RubinRepoMan class.

This contains the business logic of going out to the docker
registry, getting the list of available tags, and filtering
that down into a list of images to pull.
"""

from __future__ import annotations

from typing import List

from cachemachine.rubinrepoman import RubinRepoMan
from cachemachine.types import CachedDockerImage


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
    assert di[0].name.startswith("Recommended ")
    assert di[1].image_url.startswith("lsstsqre/sciplat-lab:r")
    assert di[1].name.startswith("Release ")
    assert di[2].image_url.startswith("lsstsqre/sciplat-lab:w_")
    assert di[2].name.startswith("Weekly ")
    assert di[3].image_url.startswith("lsstsqre/sciplat-lab:d_")
    assert di[3].name.startswith("Daily ")
