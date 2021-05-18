"""Functions called from the classmethod that builds a RubinTag object.
Because we don't have an object yet, these are functions, rather than methods.
"""

import re
from typing import Dict, List, Match, Optional, Tuple

import structlog
from semver import VersionInfo

from cachemachine.rubintagtypes import RubinTagType

DOCKER_DEFAULT_TAG = "latest"
logger = structlog.get_logger(__name__)

# Build the raw strings for tags and tag components, which can then be
# mixed and matched to some degree.  Cuts down a little on the complexity of
# the TAGTYPE_REGEXPS tuple and prevents some duplication.  We will use named
# group matches to make understanding the tag data easier.
TAG: Dict[str, str] = {
    "release": r"r(?P<major>\d+)_(?P<minor>\d+)_(?P<patch>\d+)",
    "rc": r"r(?P<major>\d+)_(?P<minor>\d+)_(?P<patch>\d+)_rc(?P<pre>\d+)",
    "weekly": r"w_(?P<year>\d+)_(?P<week>\d+)",
    "daily": r"d_(?P<year>\d+)_(?P<month>\d+)_(?P<day>\d+)",
    "experimental": r"exp_(?P<rest>.*)",
    "cycle": r"_(?P<ctag>c|csal)(?P<cycle>\d+\.\d+)",
    "rest": r"_(?P<rest>.*)",
}

# This is the heart of the parser: it's an ordered list of tuples, each of
# which contains a tag type followed by a regular expression defining
# something that matches that type, with named capture groups.
#
# Note that this is matched top to bottom.  In particular, the release
# candidate images must precede the release images, because an RC candidate
# could be a release image with non-empty "rest".
#
TAGTYPE_REGEXPS: List[Tuple[RubinTagType, re.Pattern]] = [
    # r23_0_0_rc1_c0020.001_20210513
    (
        RubinTagType.RELEASE_CANDIDATE,
        re.compile(TAG["rc"] + TAG["cycle"] + TAG["rest"] + r"$"),
    ),
    # r23_0_0_rc1_c0020.001
    (
        RubinTagType.RELEASE_CANDIDATE,
        re.compile(TAG["rc"] + TAG["cycle"] + r"$"),
    ),
    # r23_0_0_rc1_20210513
    (
        RubinTagType.RELEASE_CANDIDATE,
        re.compile(TAG["rc"] + TAG["rest"] + r"$"),
    ),
    # r23_0_0_rc1
    (RubinTagType.RELEASE_CANDIDATE, re.compile(TAG["rc"] + r"$")),
    # r22_0_1_c0019.001_20210513
    (
        RubinTagType.RELEASE,
        re.compile(TAG["release"] + TAG["cycle"] + TAG["rest"] + r"$"),
    ),
    # r22_0_1_c0019.001
    (RubinTagType.RELEASE, re.compile(TAG["release"] + TAG["cycle"] + r"$")),
    # r22_0_1_20210513
    (RubinTagType.RELEASE, re.compile(TAG["release"] + TAG["rest"] + r"$")),
    # r22_0_1
    (RubinTagType.RELEASE, re.compile(TAG["release"] + r"$")),
    # r170 (obsolete) (no new ones, no additional parts)
    (RubinTagType.RELEASE, re.compile(r"r(?P<major>\d\d)(?P<minor>\d)$")),
    # w_2021_13_c0020.001_20210513
    (
        RubinTagType.WEEKLY,
        re.compile(TAG["weekly"] + TAG["cycle"] + TAG["rest"] + r"$"),
    ),
    # w_2021_13_c0020.001
    (RubinTagType.WEEKLY, re.compile(TAG["weekly"] + TAG["cycle"] + r"$")),
    # w_2021_13_20210513
    (RubinTagType.WEEKLY, re.compile(TAG["weekly"] + TAG["rest"] + r"$")),
    # w_2021_13
    (RubinTagType.WEEKLY, re.compile(TAG["weekly"] + r"$")),
    # d_2021_05_13_c0019.001_20210513
    (
        RubinTagType.DAILY,
        re.compile(TAG["daily"] + TAG["cycle"] + TAG["rest"] + r"$"),
    ),
    # d_2021_05_13_c0019.001
    (RubinTagType.DAILY, re.compile(TAG["daily"] + TAG["cycle"] + r"$")),
    # d_2021_05_13_20210513
    (RubinTagType.DAILY, re.compile(TAG["daily"] + TAG["rest"] + r"$")),
    # d_2021_05_13
    (RubinTagType.DAILY, re.compile(TAG["daily"] + r"$")),
    # exp_w_2021_05_13_nosudo
    (RubinTagType.EXPERIMENTAL, re.compile(TAG["experimental"] + r"$")),
]


def extract_metadata(
    match: Match, tag: str, tagtype: RubinTagType
) -> Tuple[str, Optional[VersionInfo], Optional[int]]:
    """Return a display name, semantic version (optional), and cycle
    (optional) from match, tag, and type."""
    md = match.groupdict()
    name = tag
    semver = None
    cycle = md.get("cycle")
    ctag = md.get("ctag")
    cycle_int = None
    rest = md.get("rest")
    # We have our defaults.  The rest is optimistically seeing if we can do
    #  better
    if tagtype == RubinTagType.UNKNOWN:
        # We can't do anything better, but we really shouldn't be extracting
        # from an unknown type.
        pass
    elif tagtype == RubinTagType.ALIAS:
        # We can slightly pretty-print the tag.  Again, we shouldn't be
        # trying an extraction.
        name = titlecase(name)
    elif tagtype == RubinTagType.EXPERIMENTAL:
        # This one is slightly complicated.  Because of the way the build
        # process works, our tag likely looks like exp_<other-legal-tag>.
        # So we try that hypothesis.  If that's not how the tag is constructed,
        # nname will just come back as everything after "exp_".
        if rest is not None:
            # it actually never will be None if the regexp matched, but
            # mypy doesn't know that
            _, nname, _, _ = parse_tag(rest)  # We only care about the name.
            name = f"Experimental {nname}"
    else:
        # Everything else does get an actual semantic version
        build = cycle_and_rest_to_optional_buildstring(cycle, ctag, rest)
        typename = titlecase(tagtype.name)
        restname = name[2:]
        if (
            tagtype == RubinTagType.RELEASE
            or tagtype == RubinTagType.RELEASE_CANDIDATE
        ):
            # This is bulky because we don't want to raise an error here
            # if we cannot extract a required field; instead we let the
            # field be None, and then the semantic version construction fails
            # later.  That's OK too, because we try that in a try/expect block
            # and return None if we can't construct a version.  In *that*
            # case we have a tag without semantic version information--which is
            # allowable.
            major = maybe_int(md.get("major"))
            minor = maybe_int(md.get("minor"))
            patch = maybe_int(md.get("patch", "0"))  # If omitted, it's zero
            restname = f"r{major}.{minor}.{patch}"
            pre = md.get("pre")
            if pre:
                pre = f"rc{pre}"
                restname += f"-{pre}"
        else:  # tagtype is weekly or daily
            year = md.get("year")
            month = md.get("month")
            week = md.get("week")
            day = md.get("day")
            major = maybe_int(year)
            if tagtype == RubinTagType.WEEKLY:
                minor = maybe_int(week)
                patch = 0
                restname = f"{year}_{week}"  # preserve initial string format
            else:
                minor = maybe_int(md.get("month"))
                patch = maybe_int(md.get("day"))
                restname = f"{year}_{month}_{day}"  # preserve string format
            pre = None
        try:
            semver = VersionInfo(
                major=major,
                minor=minor,
                patch=patch,
                prerelease=pre,
                build=build,
            )
        except TypeError as exc:
            logger.warning(f"Could not make semver from tag {tag}: {exc}")
        name = f"{typename} {restname}"  # Glue together display name.
        if cycle:
            name += f"_{ctag}{cycle}"
        if rest:
            name += f"_{rest}"
        cycle_int = maybe_int(cycle)
    return (name, semver, cycle_int)


def maybe_int(n: Optional[str]) -> Optional[int]:
    if n is None:
        return None
    # We do the cast to float first to also catch the cycle case ('0019.001')
    return int(float(n))


def cycle_and_rest_to_optional_buildstring(
    cycle: Optional[str],
    ctag: Optional[str],  # if present, either 'c' or 'csal'
    rest: Optional[str] = None,
) -> Optional[str]:
    if cycle:
        if rest:
            # Cycle must always precede rest
            rest = f"{ctag}{cycle}_{rest}"
        else:
            rest = f"{ctag}{cycle}"
    # We're done with cycle now.
    if not rest:
        return None
    rest = rest.replace("_", ".")
    pat = re.compile(r"[^\w|\.]+")  # Identify all non alphanum, non-dots
    # Throw away all of those after turning underscores to dots.
    rest = pat.sub("", rest)
    if not rest:
        return None  # if we are left with an empty string, return None instead
    return rest


def parse_tag(
    tag: str,
    override_name: str = "",
    alias_tags: List[str] = [],
) -> Tuple[RubinTagType, str, Optional[VersionInfo], Optional[int]]:
    if not tag:
        tag = DOCKER_DEFAULT_TAG  # This is a Docker convention
    if tag != tag.lower():
        logger.warning(
            "Tag is not lower case; flattening may cause "
            + "collision; type is therefore unknown."
        )
        return (RubinTagType.UNKNOWN, tag, None, None)
    if tag in alias_tags:
        tagtype = RubinTagType.ALIAS
        name = titlecase(tag)
        logger.debug(f"Found tag type {tagtype}: {name}")
        if override_name:
            logger.debug(f"Overriding name with {name}")
            name = override_name
        return (tagtype, name, None, None)
    for (tagtype, regexp) in TAGTYPE_REGEXPS:
        match = re.compile(regexp).match(tag)
        if not match:
            continue
        name, semver, cycle = extract_metadata(match, tag, tagtype)
        logger.debug(
            f"Found tag type {tagtype}:"
            + f"{name} | version {semver} | cycle {cycle}"
        )
        if override_name:
            name = override_name
            logger.debug(f"Overriding name with {name}")
        if tagtype == RubinTagType.ALIAS or match:
            return (tagtype, name, semver, cycle)
    # Didn't find any matches
    logger.warning(f"Tag {tag} did not match any regexp; tag type is unknown.")
    return (RubinTagType.UNKNOWN, tag, None, None)


def titlecase(tag: str) -> str:
    """Little convenience wrapper for turning (possibly-underscore-separated)
    tags into prettier title case."""
    return tag.replace("_", " ").title()
