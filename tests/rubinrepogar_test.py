"""Tests for the cachemachine.RubinRepoMan class.

This contains the business logic of going out to the docker
registry, getting the list of available tags, and filtering
that down into a list of images to pull.
"""
from __future__ import annotations

from typing import List

import pytest

from cachemachine.rubinrepogar import RubinRepoGar
from cachemachine.types import CachedDockerImage, DockerImage

from .conftest import mock_registry

repo = (
    "us-central1-docker.pkg.dev/rubin-shared-services-71ec/sciplat/sciplat-lab"
)

expected_names = {
    "prepuller_pulled_recommended": "prepuller_pulled_recommended",
    "recommended": "Recommended (Release r21.0.0)",
    "r23_0_1_rc4": "Release Candidate r23.0.1-rc4",
    "r23_0_0": "Release r23.0.0",
    "w_2022_10": "Weekly 2022_10",
    "d_2022_03_04": "Daily 2022_03_04"
    # "w_2021_21_c0021.003": "Weekly 2021_21 (SAL Cycle 0021, Build 003)",
    # "w_2021_22_c0021.003_20210514": "Weekly 2021_21_20210514 (SAL Cycle 0021, Build 003)",  # noqa: E501
    # "w_2021_22_20210514": "Weekly 2021_21_20210514",
    # "w_2021_03": "Weekly 2021_03",
    # "d_2021_01_13": "Daily 2021_01_13",
    # "d_2021_01_12": "Daily 2021_01_12",
}

expected_all: List[DockerImage] = []
for t in sorted(list(mock_registry.keys()), reverse=True):
    expected_all.append(
        # all_tags uses tag as name in dropdown
        DockerImage(
            image_url=f"{repo}:{t}", image_hash=mock_registry[t], name=t
        )
    )

expected_desired_tags = [
    "recommended",
    "r23_0_0",
    "w_2022_10",
    "d_2022_03_04",
]

expected_desired: List[DockerImage] = []
for t in expected_desired_tags:
    expected_desired.append(
        DockerImage(
            image_url=f"{repo}:{t}",
            image_hash=mock_registry[t],
            name=expected_names[t],
        )
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
