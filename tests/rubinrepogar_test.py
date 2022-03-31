"""Tests for the cachemachine.RubinRepoMan class.

This contains the business logic of going out to the docker
registry, getting the list of available tags, and filtering
that down into a list of images to pull.
"""
from __future__ import annotations

from typing import List

import pytest

from cachemachine.rubinrepogar import RubinRepoGar
from cachemachine.types import CachedDockerImage

repo = (
    "us-central1-docker.pkg.dev/rubin-shared-services-71ec/sciplat/sciplat-lab"
)


@pytest.mark.asyncio
async def test_rubinrepogar() -> None:

    """Test RubinRepoMan, including going out to google artifact registry
    Note: This test goes over the network, and will make
    sure the business logic is still working with what the
    official repo looks like, and that it still works with
    docker.
    """

    body = {
        "project_id": "rubin-shared-services-71ec",
        "location": "us-central1",
        "gar_repository": "sciplat",
        "num_releases": 1,
        "num_weeklies": 1,
        "num_dailies": 1,
        "cycle": None,
        # "alias_tags": [
        #    "recommended",
        #    "latest",
        #    "latest_daily",
        #    "latest_weekly"
        # ],
        "recommended_tag": "recommended",
    }

    common_cache: List[CachedDockerImage] = []

    r = RubinRepoGar(body)
    desired_images = await r.desired_images(common_cache)
    di = desired_images.desired_images

    assert len(desired_images.all_images) > 0

    assert len(di) == 4
    assert di[0].name.startswith("Recommended")
    assert di[1].image_url.startswith(f"{repo}:r")
    assert di[1].name.startswith("Release ")
    assert di[2].image_url.startswith(f"{repo}:w_")
    assert di[2].name.startswith("Weekly ")
    assert di[3].image_url.startswith(f"{repo}:d_")
    assert di[3].name.startswith("Daily ")
