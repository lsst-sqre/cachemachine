from typing import List, Optional

import pytest

from cachemachine.rubintag import RubinTag, RubinTagType

# Set up all our input tags

base_semver_tags = ["r21_0_1", "r22_0_0_rc1", "w_2021_22", "d_2021_05_27"]
cycle_tag = "c0020.001"
rest_tag = "20210527"

cycle_tags = [f"{x}_{cycle_tag}" for x in base_semver_tags]
rest_tags = [f"{x}_{rest_tag}" for x in base_semver_tags]
both_tags = [f"{x}_{cycle_tag}_{rest_tag}" for x in base_semver_tags]

alias_tag = "recommended"
experimental_tag_basic = "exp_random"
experimental_tag_resolvable = "exp_w_2021_22"
unknown_tag = "not_a_normal_format"
mixed_case_tag = "MiXeD_CaSe_TaG"

semver_tags = []
for tt in [base_semver_tags, cycle_tags, rest_tags, both_tags]:
    semver_tags.extend(tt)

non_semver_tags = [
    alias_tag,
    experimental_tag_basic,
    experimental_tag_resolvable,
    unknown_tag,
    mixed_case_tag,
]

tags = []
for tt in [semver_tags, non_semver_tags]:
    tags.extend(tt)

# Make RubinTag objects from our tag list

tagobjs = [RubinTag.from_tag(x, alias_tags=[alias_tag]) for x in tags]

# Set up our expected tag types
expected_semver_base_types = [
    RubinTagType.RELEASE,
    RubinTagType.RELEASE_CANDIDATE,
    RubinTagType.WEEKLY,
    RubinTagType.DAILY,
]
expected_semver_types = expected_semver_base_types * 4
expected_non_semver_types = [
    RubinTagType.ALIAS,
    RubinTagType.EXPERIMENTAL,
    RubinTagType.EXPERIMENTAL,
    RubinTagType.UNKNOWN,
    RubinTagType.UNKNOWN,
]
expected_tag_types = []
for xt in [expected_semver_types, expected_non_semver_types]:
    expected_tag_types.extend(xt)

# Set up our expected semantic version strings

expected_semver_base_strings = [
    "21.0.1",
    "22.0.0-rc1",
    "2021.22.0",
    "2021.5.27",
]
expected_semver_cycle_strings = [
    f"{x}+{cycle_tag}" for x in expected_semver_base_strings
]
expected_semver_build_strings = [
    f"{x}+{rest_tag}" for x in expected_semver_base_strings
]
expected_semver_both_strings = [
    f"{x}+{cycle_tag}.{rest_tag}" for x in expected_semver_base_strings
]
expected_non_semver_strings = ["None"] * 5

expected_semver = []
for xs in [
    expected_semver_base_strings,
    expected_semver_cycle_strings,
    expected_semver_build_strings,
    expected_semver_both_strings,
    expected_non_semver_strings,
]:
    expected_semver.extend(xs)

# Set up our expected display names
expected_base_semver_display_names = [
    "Release r21.0.1",
    "Release Candidate r22.0.0-rc1",
    "Weekly 2021_22",
    "Daily 2021_05_27",
]

cycle_names = [f"{x}_{cycle_tag}" for x in expected_base_semver_display_names]
build_names = [f"{x}_{rest_tag}" for x in expected_base_semver_display_names]
both_names = [
    f"{x}_{cycle_tag}_{rest_tag}" for x in expected_base_semver_display_names
]

expected_non_semver_display_names = [
    "Recommended",
    "Experimental random",
    "Experimental Weekly 2021_22",
    "not_a_normal_format",
    "MiXeD_CaSe_TaG",
]

expected_display_names = []
for dn in [
    expected_base_semver_display_names,
    cycle_names,
    build_names,
    both_names,
    expected_non_semver_display_names,
]:
    expected_display_names.extend(dn)

expected_cycle = 20

expected_cycles: List[Optional[int]] = []
for t in [
    [None] * 4,
    [expected_cycle] * 4,
    [None] * 4,
    [expected_cycle] * 4,
    [None] * 5,
]:
    expected_cycles.extend(t)  # type: ignore[arg-type]

###
#      Run our tests
###


def test_input_viability() -> None:
    assert len(tagobjs) == len(expected_tag_types)
    assert len(tagobjs) == len(expected_semver)
    assert len(tagobjs) == len(expected_display_names)
    assert len(tagobjs) == len(expected_cycles)


@pytest.mark.parametrize(
    "test_input,expected", zip(tagobjs, expected_tag_types)
)
def test_tag_types(test_input: RubinTag, expected: RubinTagType) -> None:
    assert test_input.image_type == expected


@pytest.mark.parametrize("test_input,expected", zip(tagobjs, expected_semver))
def test_tag_semver(test_input: RubinTag, expected: str) -> None:
    assert f"{test_input.semantic_version}" == expected


@pytest.mark.parametrize(
    "test_input,expected", zip(tagobjs, expected_display_names)
)
def test_tag_display_name(test_input: RubinTag, expected: str) -> None:
    assert test_input.display_name == expected


@pytest.mark.parametrize("test_input,expected", zip(tagobjs, expected_cycles))
def test_tag_cycle(test_input: RubinTag, expected: Optional[int]) -> None:
    assert test_input.cycle == expected
