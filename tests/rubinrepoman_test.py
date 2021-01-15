"""Tests for the cachemachine.RubinRepoMan class.

This contains the business logic of going out to the docker
registry, getting the list of available tags, and filtering
that down into a list of images to pull.
"""

from __future__ import annotations

from typing import Dict, List
from unittest.mock import patch

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


class MockDockerClient:
    def __init__(self, data: Dict[str, str]) -> None:
        self.data = data

    async def list_tags(self, authenticate: bool = True) -> List[str]:
        return list(self.data.keys())

    async def get_image_hash(self, tag: str, authenticate: bool = True) -> str:
        return self.data[tag]


async def test_rubinrepoman_tag_picking() -> None:
    """Test RubinRepoMan, with a mock docker

    Note: This doesn't reach out over the network, and uses some
    mocked docker results to test the logic of picking tags out
    of the list.
    """
    mock_registry = {
        "recommended": "sha256:b0b7d97ff9d62ccd049",
        "r21_0_0": "sha256:b0b7d97ff9d62ccd049",
        "w_2021_03": "sha256:bb16e5ea71bd7139779",
        "w_2021_02": "sha256:bad6e5ea71bd7139779",
        "d_2021_01_13": "sha256:343b17341d0e961472",
        "d_2021_01_12": "sha256:badb17341d0e961471",
    }

    with patch("cachemachine.rubinrepoman.DockerClient") as mock:
        mock.return_value = MockDockerClient(mock_registry)

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
        assert di[0].name == "Recommended set()"
        assert di[1].image_url == "lsstsqre/sciplat-lab:r21_0_0"
        assert di[1].name == "Release r21.0.0"
        assert di[2].image_url == "lsstsqre/sciplat-lab:w_2021_03"
        assert di[2].name == "Weekly 03"
        assert di[3].image_url == "lsstsqre/sciplat-lab:d_2021_01_13"
        assert di[3].name == "Daily 01/13"

        # Now let's pretend we've got the recommended and r21, which share
        # the same hash.  We should be able to notice the other tags that
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
        assert di[0].name == "Recommended {'r21_0_0', 'recommended'}"
        assert di[1].image_url == "lsstsqre/sciplat-lab:r21_0_0"
        assert di[1].name == "Release r21.0.0"
        assert di[2].image_url == "lsstsqre/sciplat-lab:w_2021_03"
        assert di[2].name == "Weekly 03"
        assert di[3].image_url == "lsstsqre/sciplat-lab:d_2021_01_13"
        assert di[3].name == "Daily 01/13"
