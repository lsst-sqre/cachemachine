"""Tests for the RubinImageInfo class."""

import semver
from pytest import raises

from cachemachine.rubinimageinfo import RubinImageInfo, RubinImageType
from cachemachine.types import IncomparableImagesError


def test_basic_info() -> None:
    ref = "registry.hub.docker.com/lsstsqre/sciplat-lab:w_2021_19"
    obj = RubinImageInfo.from_reference(ref)
    assert obj.host == "registry.hub.docker.com"
    assert obj.repo == "lsstsqre"
    assert obj.name == "sciplat-lab"
    assert obj.digest is None
    assert obj.tag == "w_2021_19"
    assert obj.image_type == RubinImageType.WEEKLY
    assert obj.semantic_version == semver.VersionInfo(2021, 19, 0)
    assert obj.display_name == "Weekly 2021_19"


def test_implicit_info() -> None:
    ref = "lsstsqre/sciplat-lab"
    obj = RubinImageInfo.from_reference(ref)
    assert obj.host == "docker.io"
    assert obj.repo == "lsstsqre"
    assert obj.name == "sciplat-lab"
    assert obj.tag == "latest"


def test_cycle() -> None:
    ref = "lsstts/sal-sciplat-lab:w_2021_18_c0019.001"
    obj = RubinImageInfo.from_reference(ref)
    assert obj.cycle == 19
    assert obj.semantic_version.build == "c0019.001"


def test_embedded_digest() -> None:
    ref = "registry.hub.docker.com/lsstsqre/sciplat-lab:w_2021_13@sha256:419c4b7e14603711b25fa9e0569460a753c4b2449fe275bb5f89743b01794a30"  # noqa: E501
    obj = RubinImageInfo.from_reference(ref)
    assert (
        obj.digest
        == "sha256:419c4b7e14603711b25fa9e0569460a753c4b2449fe275bb5f89743b01794a30"  # noqa: E501
    )


def test_separate_digest() -> None:
    ref = "registry.hub.docker.com/lsstsqre/sciplat-lab:w_2021_13"
    digest = "sha256:419c4b7e14603711b25fa9e0569460a753c4b2449fe275bb5f89743b01794a30"  # noqa: E501
    obj = RubinImageInfo.from_reference(ref, digest=digest)
    assert (
        obj.digest
        == "sha256:419c4b7e14603711b25fa9e0569460a753c4b2449fe275bb5f89743b01794a30"  # noqa: E501
    )


def test_default_recommended() -> None:
    ref = "lsstsqre/sciplat-lab:recommended"
    obj = RubinImageInfo.from_reference(ref)
    assert obj.image_type == RubinImageType.RECOMMENDED
    assert obj.display_name == "Recommended"


def test_forced_recommended() -> None:
    recommended_tag = "perfectly_cromulent"
    ref = f"lsstsqre/sciplat-lab:{recommended_tag}"
    obj = RubinImageInfo.from_reference(ref, recommended_tag=recommended_tag)
    assert obj.image_type == RubinImageType.RECOMMENDED
    assert obj.display_name == "Perfectly Cromulent"


def test_latest() -> None:
    ref = "lsstsqre/sciplat-lab:latest"
    obj = RubinImageInfo.from_reference(ref)
    assert obj.image_type == RubinImageType.LATEST
    assert obj.display_name == "Latest"


def test_implicit_latest() -> None:
    ref = "lsstsqre/sciplat-lab"
    obj = RubinImageInfo.from_reference(ref)
    assert obj.image_type == RubinImageType.LATEST
    assert obj.display_name == "Latest"


def test_latest_sometype() -> None:
    ref = "lsstts/sal-sciplat-lab:latest_weekly"
    obj = RubinImageInfo.from_reference(ref)
    assert obj.image_type == RubinImageType.LATEST_SOMETYPE
    assert obj.display_name == "Latest Weekly"


def test_experimental() -> None:
    ref = "lsstsqre/sciplat-lab:exp_w_2021_19_nosudo"
    obj = RubinImageInfo.from_reference(ref)
    assert obj.image_type == RubinImageType.EXPERIMENTAL
    assert obj.display_name == "Experimental Weekly 2021_19_nosudo"


def test_release() -> None:
    ref = "lsstsqre/sciplat-lab:r21_0_0"
    obj = RubinImageInfo.from_reference(ref)
    assert obj.image_type == RubinImageType.RELEASE
    assert obj.display_name == "Release r21.0.0"


def test_release_candidate() -> None:
    ref = "lsstsqre/sciplat-lab:r22_0_0_rc1"
    obj = RubinImageInfo.from_reference(ref)
    assert obj.image_type == RubinImageType.RELEASE_CANDIDATE
    assert obj.display_name == "Release Candidate r22.0.0-rc1"


def test_generic_image_no_tag() -> None:
    ref = "ubuntu"  # short for docker.io/library/ubuntu:latest
    obj = RubinImageInfo.from_reference(ref)
    assert obj.name == "ubuntu"
    assert obj.repo == "library"
    assert obj.tag == "latest"
    assert obj.host == "docker.io"
    assert obj.image_type == RubinImageType.LATEST


def test_malformed_tag() -> None:
    ref = "lsstsqre/sciplat-lab:bad_tag"
    obj = RubinImageInfo.from_reference(ref)
    assert obj.image_type == RubinImageType.MALFORMED_TAG
    assert obj.display_name == "Malformed Tag bad_tag"


def test_compare() -> None:
    ref1 = "lsstsqre/sciplat-lab:w_2021_18"
    ref2 = "lsstsqre/sciplat-lab:w_2021_19"
    obj1 = RubinImageInfo.from_reference(ref1)
    obj2 = RubinImageInfo.from_reference(ref2)
    assert obj1 < obj2


def test_incomparable() -> None:
    ref1 = "lsstsqre/sciplat-lab:w_2021_18"
    ref2 = "lsstsqre/sciplat-lab:d_2021_05_01"
    obj1 = RubinImageInfo.from_reference(ref1)
    obj2 = RubinImageInfo.from_reference(ref2)
    with raises(IncomparableImagesError):
        obj1.compare(obj2)


def test_incomparable_latest() -> None:
    ref1 = "lsstsqre/sciplat-lab:latest_weekly"
    ref2 = "lsstsqre/sciplat-lab:latest_daily"
    obj1 = RubinImageInfo.from_reference(ref1)
    obj2 = RubinImageInfo.from_reference(ref2)
    with raises(IncomparableImagesError):
        obj1.compare(obj2)


def test_trivial_comparison() -> None:
    ref = "lsstsqre/sciplat-lab"
    obj1 = RubinImageInfo.from_reference(ref)
    obj2 = RubinImageInfo.from_reference(ref)
    assert obj1 == obj2


def test_experimental_comparison() -> None:
    ref1 = "lsstsqre/sciplat-lab:exp_w_2021_19_nosudo"
    ref2 = "lsstsqre/sciplat-lab:exp_d_2021_05_13_nosudo"
    obj1 = RubinImageInfo.from_reference(ref1)
    obj2 = RubinImageInfo.from_reference(ref2)
    assert obj1 > obj2  # Lexical sort
