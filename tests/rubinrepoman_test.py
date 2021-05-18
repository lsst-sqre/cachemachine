"""Tests for the cachemachine.RubinRepoMan class.

This contains the business logic of going out to the docker
registry, getting the list of available tags, and filtering
that down into a list of images to pull.
"""
from __future__ import annotations

from typing import List

from cachemachine.rubinrepoman import RubinRepoMan
from cachemachine.types import CachedDockerImage, DockerImage

from .conftest import mock_registry
from .docker_mock import DockerMock

repo = "registry.hub.docker.com/lsstsqre/sciplat-lab"
expected_names = {
    "prepuller_pulled_recommended": "prepuller_pulled_recommended",
    "recommended": "Recommended (Release r21.0.0)",
    "r22_0_0_rc1": "Release Candidate r22.0.0-rc1",
    "r21_0_0": "Release r21.0.0",
    "w_2021_22": "Weekly 2021_22",
    "w_2021_21_c0021.003": "Weekly 2021_21_c0021.003",
    #    "w_2021_22_c0021.003_20210514": "Weekly 2021_21_c0021.003_20210514",
    #    "w_2021_22_20210514": "Weekly 2021_21_20210514",
    "w_2021_03": "Weekly 2021_03",
    "d_2021_01_13": "Daily 2021_01_13",
    "d_2021_01_12": "Daily 2021_01_12",
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
    "r21_0_0",
    "w_2021_22",
    "d_2021_01_13",
]
unresolved_recommended_name = "Recommended"
expected_desired: List[DockerImage] = []
for t in expected_desired_tags:
    expected_desired.append(
        DockerImage(
            image_url=f"{repo}:{t}",
            image_hash=mock_registry[t],
            name=expected_names[t],
        )
    )
expected_desired_cycle_tags = ["w_2021_21_c0021.003"]
expected_desired_cycle = []
for t in expected_desired_cycle_tags:
    expected_desired_cycle.append(
        DockerImage(
            image_url=f"{repo}:{t}",
            image_hash=mock_registry[t],
            name=expected_names[t],
        )
    )


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
    desired_images = await r.desired_images(common_cache)
    di = desired_images.desired_images
    # Because this uses real data, we don't use our expected data at all.
    assert len(desired_images.all_images) > 0
    assert len(di) == 4
    assert di[0].name.startswith("Recommended")
    assert di[1].image_url.startswith(f"{repo}:r")
    assert di[1].name.startswith("Release ")
    assert di[2].image_url.startswith(f"{repo}:w_")
    assert di[2].name.startswith("Weekly ")
    assert di[3].image_url.startswith(f"{repo}:d_")
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
    desired_images = await r.desired_images(common_cache)
    di = desired_images.desired_images
    ai = desired_images.all_images

    assert len(di) == len(expected_desired)
    for didx, dimg in enumerate(di):
        expected = expected_desired[didx]
        assert dimg.image_url == expected.image_url
        if dimg.image_url == f"{repo}:recommended":
            assert dimg.name == unresolved_recommended_name
        else:
            assert dimg.name == expected.name

    assert len(ai) == len(expected_all)
    for aidx, aimg in enumerate(ai):
        expected = expected_all[aidx]
        assert aimg.image_url == expected.image_url
        assert aimg.name == expected.name

    # Now let's pretend we've got the images in the cache.
    # We should be able to notice the other tags that
    # recommended shares in the friendly name of recommended.
    # In the case of the mock data, recommended is release 21.
    common_cache.extend(
        [
            CachedDockerImage(
                image_url=di[0].image_url,
                image_hash=di[0].image_hash,
                tags=["r21_0_0"],
            ),
            CachedDockerImage(
                image_url=di[1].image_url,
                image_hash=di[1].image_hash,
                tags=["recommended"],
            ),
        ]
    )

    desired_images = await r.desired_images(common_cache)
    di = desired_images.desired_images
    # Note that this also checks rejection of the RC release image, since
    # it occurs prior to r21 in the list, but is not selected as the
    # release image.
    assert len(desired_images.all_images) == len(expected_all)
    assert len(di) == len(expected_desired)
    for didx, dimg in enumerate(di):
        expected = expected_desired[didx]
        assert dimg.image_url == expected.image_url
        assert dimg.name == expected.name


async def test_rubinrepoman_cycle(docker_mock: DockerMock) -> None:
    """Test RubinRepoMan, with a docker mock, restricting by cycle.

    Note: This doesn't reach out over the network, and uses some
    mocked docker results to test the logic of picking tags out
    of the list.
    """
    body = {
        "repo": "lsstsqre/sciplat-lab",
        "num_releases": 0,
        "num_weeklies": 1,
        "num_dailies": 0,
        "cycle": 21,
    }

    # Pretend we're starting from a blank slate, nothing in the
    # cache.
    common_cache: List[CachedDockerImage] = []
    r = RubinRepoMan(body)
    desired_images = await r.desired_images(common_cache)
    di = desired_images.desired_images
    # This should only match images with Cycle 21
    assert len(di) == len(expected_desired_cycle)
    for didx, dimg in enumerate(di):
        expected = expected_desired_cycle[didx]
        assert dimg.image_url == expected.image_url
        assert dimg.name == expected.name
