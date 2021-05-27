import pytest
from semver import VersionInfo

from cachemachine.rubintag import RubinPartialTag, RubinTagType

TAGSTR_TO_TAGOBJ = [
    (
        "r21_0_1",
        RubinPartialTag(
            tag="r21_0_1",
            image_type=RubinTagType.RELEASE,
            display_name="Release r21.0.1",
            semantic_version=VersionInfo(
                major=21, minor=0, patch=1, prerelease=None, build=None
            ),
            cycle=None,
        ),
    ),
    (
        "r22_0_0_rc1",
        RubinPartialTag(
            tag="r22_0_0_rc1",
            image_type=RubinTagType.RELEASE_CANDIDATE,
            display_name="Release Candidate r22.0.0-rc1",
            semantic_version=VersionInfo(
                major=22, minor=0, patch=0, prerelease="rc1", build=None
            ),
            cycle=None,
        ),
    ),
    (
        "w_2021_22",
        RubinPartialTag(
            tag="w_2021_22",
            image_type=RubinTagType.WEEKLY,
            display_name="Weekly 2021_22",
            semantic_version=VersionInfo(
                major=2021, minor=22, patch=0, prerelease=None, build=None
            ),
            cycle=None,
        ),
    ),
    (
        "d_2021_05_27",
        RubinPartialTag(
            tag="d_2021_05_27",
            image_type=RubinTagType.DAILY,
            display_name="Daily 2021_05_27",
            semantic_version=VersionInfo(
                major=2021, minor=5, patch=27, prerelease=None, build=None
            ),
            cycle=None,
        ),
    ),
    (
        "r21_0_1_c0020.001",
        RubinPartialTag(
            tag="r21_0_1_c0020.001",
            image_type=RubinTagType.RELEASE,
            display_name="Release r21.0.1_c0020.001",
            semantic_version=VersionInfo(
                major=21, minor=0, patch=1, prerelease=None, build="c0020.001"
            ),
            cycle=20,
        ),
    ),
    (
        "r22_0_0_rc1_c0020.001",
        RubinPartialTag(
            tag="r22_0_0_rc1_c0020.001",
            image_type=RubinTagType.RELEASE_CANDIDATE,
            display_name="Release Candidate r22.0.0-rc1_c0020.001",
            semantic_version=VersionInfo(
                major=22, minor=0, patch=0, prerelease="rc1", build="c0020.001"
            ),
            cycle=20,
        ),
    ),
    (
        "w_2021_22_c0020.001",
        RubinPartialTag(
            tag="w_2021_22_c0020.001",
            image_type=RubinTagType.WEEKLY,
            display_name="Weekly 2021_22_c0020.001",
            semantic_version=VersionInfo(
                major=2021,
                minor=22,
                patch=0,
                prerelease=None,
                build="c0020.001",
            ),
            cycle=20,
        ),
    ),
    (
        "d_2021_05_27_c0020.001",
        RubinPartialTag(
            tag="d_2021_05_27_c0020.001",
            image_type=RubinTagType.DAILY,
            display_name="Daily 2021_05_27_c0020.001",
            semantic_version=VersionInfo(
                major=2021,
                minor=5,
                patch=27,
                prerelease=None,
                build="c0020.001",
            ),
            cycle=20,
        ),
    ),
    (
        "r21_0_1_20210527",
        RubinPartialTag(
            tag="r21_0_1_20210527",
            image_type=RubinTagType.RELEASE,
            display_name="Release r21.0.1_20210527",
            semantic_version=VersionInfo(
                major=21, minor=0, patch=1, prerelease=None, build="20210527"
            ),
            cycle=None,
        ),
    ),
    (
        "r22_0_0_rc1_20210527",
        RubinPartialTag(
            tag="r22_0_0_rc1_20210527",
            image_type=RubinTagType.RELEASE_CANDIDATE,
            display_name="Release Candidate r22.0.0-rc1_20210527",
            semantic_version=VersionInfo(
                major=22, minor=0, patch=0, prerelease="rc1", build="20210527"
            ),
            cycle=None,
        ),
    ),
    (
        "w_2021_22_20210527",
        RubinPartialTag(
            tag="w_2021_22_20210527",
            image_type=RubinTagType.WEEKLY,
            display_name="Weekly 2021_22_20210527",
            semantic_version=VersionInfo(
                major=2021,
                minor=22,
                patch=0,
                prerelease=None,
                build="20210527",
            ),
            cycle=None,
        ),
    ),
    (
        "d_2021_05_27_20210527",
        RubinPartialTag(
            tag="d_2021_05_27_20210527",
            image_type=RubinTagType.DAILY,
            display_name="Daily 2021_05_27_20210527",
            semantic_version=VersionInfo(
                major=2021,
                minor=5,
                patch=27,
                prerelease=None,
                build="20210527",
            ),
            cycle=None,
        ),
    ),
    (
        "r21_0_1_c0020.001_20210527",
        RubinPartialTag(
            tag="r21_0_1_c0020.001_20210527",
            image_type=RubinTagType.RELEASE,
            display_name="Release r21.0.1_c0020.001_20210527",
            semantic_version=VersionInfo(
                major=21,
                minor=0,
                patch=1,
                prerelease=None,
                build="c0020.001.20210527",
            ),
            cycle=20,
        ),
    ),
    (
        "r22_0_0_rc1_c0020.001_20210527",
        RubinPartialTag(
            tag="r22_0_0_rc1_c0020.001_20210527",
            image_type=RubinTagType.RELEASE_CANDIDATE,
            display_name="Release Candidate r22.0.0-rc1_c0020.001_20210527",
            semantic_version=VersionInfo(
                major=22,
                minor=0,
                patch=0,
                prerelease="rc1",
                build="c0020.001.20210527",
            ),
            cycle=20,
        ),
    ),
    (
        "w_2021_22_c0020.001_20210527",
        RubinPartialTag(
            tag="w_2021_22_c0020.001_20210527",
            image_type=RubinTagType.WEEKLY,
            display_name="Weekly 2021_22_c0020.001_20210527",
            semantic_version=VersionInfo(
                major=2021,
                minor=22,
                patch=0,
                prerelease=None,
                build="c0020.001.20210527",
            ),
            cycle=20,
        ),
    ),
    (
        "d_2021_05_27_c0020.001_20210527",
        RubinPartialTag(
            tag="d_2021_05_27_c0020.001_20210527",
            image_type=RubinTagType.DAILY,
            display_name="Daily 2021_05_27_c0020.001_20210527",
            semantic_version=VersionInfo(
                major=2021,
                minor=5,
                patch=27,
                prerelease=None,
                build="c0020.001.20210527",
            ),
            cycle=20,
        ),
    ),
    (
        "recommended",
        RubinPartialTag(
            tag="recommended",
            image_type=RubinTagType.UNKNOWN,
            display_name="recommended",
            semantic_version=None,
            cycle=None,
        ),
    ),
    (
        "exp_random",
        RubinPartialTag(
            tag="exp_random",
            image_type=RubinTagType.EXPERIMENTAL,
            display_name="Experimental random",
            semantic_version=None,
            cycle=None,
        ),
    ),
    (
        "exp_w_2021_22",
        RubinPartialTag(
            tag="exp_w_2021_22",
            image_type=RubinTagType.EXPERIMENTAL,
            display_name="Experimental Weekly 2021_22",
            semantic_version=None,
            cycle=None,
        ),
    ),
    (
        "not_a_normal_format",
        RubinPartialTag(
            tag="not_a_normal_format",
            image_type=RubinTagType.UNKNOWN,
            display_name="not_a_normal_format",
            semantic_version=None,
            cycle=None,
        ),
    ),
    (
        "MiXeD_CaSe_TaG",
        RubinPartialTag(
            tag="MiXeD_CaSe_TaG",
            image_type=RubinTagType.UNKNOWN,
            display_name="MiXeD_CaSe_TaG",
            semantic_version=None,
            cycle=None,
        ),
    ),
]


@pytest.mark.parametrize("test_input,expected", TAGSTR_TO_TAGOBJ)
def test_parse_tag(test_input: str, expected: RubinPartialTag) -> None:
    assert RubinPartialTag.parse_tag(test_input) == expected
