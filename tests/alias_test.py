"""Tests for the cachemachine.RubinRepoMan class.

This contains the business logic of going out to the docker
registry, getting the list of available tags, and filtering
that down into a list of images to pull.
"""
from typing import Generator, List
from unittest.mock import patch

import pytest

from cachemachine.rubinrepoman import RubinRepoMan
from cachemachine.types import CachedDockerImage, DockerImage

from .docker_mock import DockerMock

"""Mock docker registry containing tags of a Rubin format and some
pretend hashes, all with cycle information.
Note, hashes aren't the correct length, but that doesn't matter."""
mock_cycle_registry = {
    "w_2021_21_c0020.002": "sha256:21c20",
    "w_2021_22_c0020.003": "sha256:22c20",
    "d_2021_06_14_c0020.004": "sha256:614c20",
    "d_2021_06_15_c0020.005": "sha256:615c20",
    "latest_weekly": "sha256:22c20",
    "latest_daily": "sha256:615c20",
    "recommended": "sha256:22c20",
    "w_2021_21_c0021.002": "sha256:21c21",
    "w_2021_22_c0021.003": "sha256:22c21",
    "d_2021_06_14_c0021.004": "sha256:614c21",
    "d_2021_06_15_c0021.005": "sha256:615c21",
}


@pytest.fixture
def cycle_docker_mock() -> Generator:
    """Use the mock docker client."""
    with patch("cachemachine.rubinrepoman.DockerClient") as mock:
        mock.return_value = DockerMock(mock_cycle_registry)
        yield mock.return_value


@pytest.mark.asyncio
async def test_alias_tag_picking(cycle_docker_mock: DockerMock) -> None:
    """Test RubinRepoMan, with a docker mock.

    Note: This doesn't reach out over the network, and uses some
    mocked docker results to test the logic of picking tags out
    of the list.
    """
    body = {
        "repo": "lsstsqre/sciplat-lab",
        "recommended_tag": "recommended",
        "num_dailies": 2,
        "num_weeklies": 2,
        "num_releases": 0,
        "cycle": 20,
        "alias_tags": ["latest_daily", "latest_weekly"],
    }

    expected_tags_to_display_names = {
        "recommended": "Recommended (Weekly 2021_22 (SAL Cycle 0020, Build 003))",  # noqa: E501
        "latest_weekly": "Latest Weekly (Weekly 2021_22 (SAL Cycle 0020, Build 003))",  # noqa: E501
        "latest_daily": "Latest Daily (Daily 2021_06_15 (SAL Cycle 0020, Build 005))",  # noqa: E501
        "w_2021_22_c0020.003": "Weekly 2021_22 (SAL Cycle 0020, Build 003)",
        "w_2021_21_c0020.002": "Weekly 2021_21 (SAL Cycle 0020, Build 002)",
        "d_2021_06_15_c0020.005": "Daily 2021_06_15 (SAL Cycle 0020, Build 005)",  # noqa: E501
        "d_2021_06_14_c0020.004": "Daily 2021_06_14 (SAL Cycle 0020, Build 004)",  # noqa: E501
    }

    expected_desired_cycle = []
    for t in expected_tags_to_display_names:
        expected_desired_cycle.append(
            DockerImage(
                image_url=f"registry.hub.docker.com/{body['repo']}:{t}",  # noqa: E501
                image_hash=mock_cycle_registry[t],
                name=expected_tags_to_display_names[t],
            )
        )

    unresolved_recommended_name = "Recommended"

    # pretend we have all images in cache
    common_cache: List[CachedDockerImage] = [
        CachedDockerImage(
            image_url=f"https://registry.hub.docker.com/{body['repo']}:{t}",  # noqa: E501
            image_hash=mock_cycle_registry[t],
            tags=[t],
        )
        for t in list(mock_cycle_registry.keys())
    ]
    r = RubinRepoMan(body)
    desired_images = await r.desired_images(common_cache)
    print(desired_images)
    di = desired_images.desired_images
    # ai = desired_images.all_images

    assert len(di) == len(expected_desired_cycle)
    for didx, dimg in enumerate(di):
        expected = expected_desired_cycle[didx]
        assert dimg.image_url == expected.image_url
        if dimg.image_url == f"{body['repo']}:recommended":
            assert dimg.name == unresolved_recommended_name
        else:
            assert dimg.name == expected.name


#    assert len(ai) == len(expected_all)
#    for aidx, aimg in enumerate(ai):
#        expected = expected_all[aidx]
#        assert aimg.image_url == expected.image_url
#        assert aimg.name == expected.name
