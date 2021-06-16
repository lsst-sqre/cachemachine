"""Classes to hold all the semantic data and metadata we can extract from a
tag in the format specified by https://sqr-059.lsst.io."""

import re
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, List, Match, Optional, Set, Tuple, Union

import structlog
from semver import VersionInfo

from cachemachine.types import CachedDockerImage, DockerImageList


class RubinTagType(Enum):
    """Enum specifying different tag types for Rubin Science Platform Lab
    images, and an Exception for attempted comparison between
    incomparable types.

    """

    DAILY = auto()
    WEEKLY = auto()
    RELEASE = auto()
    RELEASE_CANDIDATE = auto()
    EXPERIMENTAL = auto()
    ALIAS = auto()
    UNKNOWN = auto()


DOCKER_DEFAULT_TAG = "latest"
logger = structlog.get_logger(__name__)

# Build the raw strings for tags and tag components, which can then be
# mixed and matched to some degree.  Cuts down a little on the complexity of
# the TAGTYPE_REGEXPS tuple and prevents some duplication.  We will use named
# group matches to make understanding the tag data easier.
TAG: Dict[str, str] = {
    # r22_0_1
    "release": r"r(?P<major>\d+)_(?P<minor>\d+)_(?P<patch>\d+)",
    # r23_0_0_rc1
    "rc": r"r(?P<major>\d+)_(?P<minor>\d+)_(?P<patch>\d+)_rc(?P<pre>\d+)",
    # w_2021_13
    "weekly": r"w_(?P<year>\d+)_(?P<week>\d+)",
    # d_2021_05_13
    "daily": r"d_(?P<year>\d+)_(?P<month>\d+)_(?P<day>\d+)",
    # exp_flattened_build
    "experimental": r"(?:exp)",
    # c0020.002
    "cycle": r"_(?P<ctag>c|csal)(?P<cycle>\d+)\.(?P<cbuild>\d+)",
    # _whatever_your_little_heart_desires
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
    (
        RubinTagType.EXPERIMENTAL,
        re.compile(TAG["experimental"] + TAG["rest"] + r"$"),
    ),
]

# Two convenience type aliases
# ForwardHashCache maps an image tag to an image digest
ForwardHashCache = Dict[str, str]

# InvertedHashCache maps an image digest to a set of image tags
InvertedHashCache = Dict[str, Set[str]]


@dataclass(frozen=True)
class RubinHashCache:
    """Immutable, once constructed, the primary method of construction
    is the from_cache classmethod.  The RubinHashCache holds both forward
    and inverted dicts mapping a cachemachine common_cache to known image
    tags.
    """

    tag_to_hash: ForwardHashCache
    """Maps a Docker image tag to a hash.
    """

    hash_to_tags: InvertedHashCache
    """Maps a hash to a set of Docker tags.
    """

    @classmethod
    def from_cache(
        cls, common_cache: List[CachedDockerImage]
    ) -> "RubinHashCache":
        fwd_hashcache: ForwardHashCache = {}
        inverted_hashcache: InvertedHashCache = defaultdict(set)
        for entry in common_cache:
            img_hash = entry.image_hash
            alltags = entry.tags.copy()
            # The tags in the common_cache object do not include the tag
            # contained in its image_url; that is in some sense the
            # primary key, so extract it...
            tag = cls._tag_from_ref(entry.image_url)
            # ...and put it first in the list.
            alltags.insert(0, tag)
            if img_hash and alltags:
                for tag in alltags:
                    inverted_hashcache[img_hash].add(tag)
                    if tag in fwd_hashcache:
                        # It's not clear whether the first or last should
                        # win if we have different values for the digest
                        # for a given tag, so we pick one (first) but squawk
                        # about it.  Hopefully this is rare.
                        if fwd_hashcache[tag] != img_hash:
                            logger.error(
                                f"Tag {tag} has hash {fwd_hashcache[tag]}"
                                + f" ... not updating with hash {img_hash}"
                            )
                    else:
                        fwd_hashcache[tag] = img_hash
        return cls(tag_to_hash=fwd_hashcache, hash_to_tags=inverted_hashcache)

    @staticmethod
    def _tag_from_ref(ref: str) -> str:
        """Extract the tag from a full Docker reference string.

        https://github.com/distribution/distribution/blob/main/reference/reference.go  # noqa: E501

        The two main formats of references we have to handle are:

        - ``<name>:<tag>``
        - ``<name>:<tag>@<digest-algo>:<digest>``

        Disambiguate by knowing that the tag cannot contain ``@``.

        Any image reference that does not have a tag implicitly has the tag
        "latest", which we keep in DOCKER_DEFAULT_TAG.
        """
        match = re.compile(r"[^:]+:([^@]+)(?:\Z|@.*)").match(ref)
        if match:
            return match.group(1)
        # Nope, didn't match a tag, so therefore implicitly the default tag.
        return DOCKER_DEFAULT_TAG


@dataclass(frozen=True)
class RubinPartialTag:
    """Immutable, once constructed, the primary method of construction is the
    parse_tag classmethod.  The RubinPartialTag holds the data that comes
    from the tag, but not the associated data such as image_digest or
    image_ref.  It does construct the display name, but does not know
    about alias tags."""

    tag: str
    """This is the tag on a given image.  Because of cachemachine's design,
    we can safely assume that in any given cachemachine instance, there is
    one and only one host/repository/name tuple for all our tags.  If we
    need access to multiple image names, repositories, or hosts, they will
    be in different cachemachine instances.

    example: w_2021_22
    """

    image_type: RubinTagType
    """Rubin-specific RSP Lab image type.

    example: RubinTagType.WEEKLY
    """

    display_name: str
    """Human-readable display name corresponding to a tag.

    example: Weekly 2021_22
    """

    semantic_version: Optional[VersionInfo]
    """Semantic version constructed from a tag.  Only extant for Daily,
    Weekly, Release, and Release Candidate image types.  Only meaningful for
    comparison within a type.

    example: VersionInfo(2021,22,0)
    """

    cycle: Optional[int]
    """XML Cycle for a given image.  Only used in T&S builds.

    example: 20
    """

    @classmethod
    def parse_tag(
        cls,
        tag: str,
    ) -> "RubinPartialTag":
        if not tag:
            tag = DOCKER_DEFAULT_TAG  # This is a Docker convention
        for (tagtype, regexp) in TAGTYPE_REGEXPS:
            match = re.compile(regexp).match(tag)
            if not match:
                continue
            display_name, semver, cycle = RubinPartialTag.extract_metadata(
                match, tag, tagtype
            )
            return cls(
                tag=tag,
                image_type=tagtype,
                display_name=display_name,
                semantic_version=semver,
                cycle=cycle,
            )
        # Didn't find any matches
        return cls(
            tag=tag,
            image_type=RubinTagType.UNKNOWN,
            display_name=tag,
            semantic_version=None,
            cycle=None,
        )

    """Some static methods that are used, ultimately, by parse_tag.
    """

    @staticmethod
    def prettify_tag(tag: str) -> str:
        """Little convenience wrapper for turning
        (possibly-underscore-separated) tags into prettier space-separated
        title case."""
        return tag.replace("_", " ").title()

    @staticmethod
    def extract_metadata(
        match: Match, tag: str, tagtype: RubinTagType
    ) -> Tuple[str, Optional[VersionInfo], Optional[int]]:
        """Return a display name, semantic version (optional), and cycle
        (optional) from match, tag, and type."""
        md = match.groupdict()
        name = tag
        semver = None
        ctag = md.get("ctag")
        cycle = md.get("cycle")
        cbuild = md.get("cbuild")
        cycle_int = None
        rest = md.get("rest")
        # We have our defaults.  The rest is optimistically seeing if we can
        # do better
        if tagtype == RubinTagType.UNKNOWN:
            # We can't do anything better, but we really shouldn't be
            # extracting from an unknown type.
            pass
        elif tagtype == RubinTagType.EXPERIMENTAL:
            # This one is slightly complicated.  Because of the way the build
            # process works, our tag likely looks like exp_<other-legal-tag>.
            # So we try that hypothesis.  If that's not how the tag is
            # constructed, nname will just come back as everything
            # after "exp_".
            if rest is not None:
                # it actually never will be None if the regexp matched, but
                # mypy doesn't know that
                temp_ptag = RubinPartialTag.parse_tag(rest)
                # We only care about the display name, not any other fields.
                name = f"Experimental {temp_ptag.display_name}"
        else:
            # Everything else does get an actual semantic version
            build = RubinPartialTag.trailing_parts_to_semver_build_component(
                cycle, cbuild, ctag, rest
            )
            typename = RubinPartialTag.prettify_tag(tagtype.name)
            restname = name[2:]
            if (
                tagtype == RubinTagType.RELEASE
                or tagtype == RubinTagType.RELEASE_CANDIDATE
            ):
                # This is bulky because we don't want to raise an error here
                # if we cannot extract a required field; instead we let the
                # field be None, and then the semantic version construction
                # fails later.  That's OK too, because we try that in a
                # try/expect block and return None if we can't construct
                # a version.  In *that* case we have a tag without semantic
                # version information--which is allowable.
                major = RubinPartialTag.maybe_int(md.get("major"))
                minor = RubinPartialTag.maybe_int(md.get("minor"))
                patch = RubinPartialTag.maybe_int(
                    md.get("patch", "0")
                )  # If omitted, it's zero
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
                major = RubinPartialTag.maybe_int(year)
                if tagtype == RubinTagType.WEEKLY:
                    minor = RubinPartialTag.maybe_int(week)
                    patch = 0
                    restname = (
                        f"{year}_{week}"  # preserve initial string format
                    )
                else:
                    minor = RubinPartialTag.maybe_int(md.get("month"))
                    patch = RubinPartialTag.maybe_int(md.get("day"))
                    restname = (
                        f"{year}_{month}_{day}"  # preserve string format
                    )
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
                name += f" (SAL Cycle {cycle}, Build {cbuild})"
            if rest:
                name += f" [{rest}]"
            cycle_int = RubinPartialTag.maybe_int(cycle)
        return (name, semver, cycle_int)

    @staticmethod
    def maybe_int(n: Optional[str]) -> Optional[int]:
        if n is None:
            return None
        return int(n)

    @staticmethod
    def trailing_parts_to_semver_build_component(
        cycle: Optional[str],
        cbuild: Optional[str],
        ctag: Optional[str],  # if present, either 'c' or 'csal'
        rest: Optional[str] = None,
    ) -> Optional[str]:
        """This takes care of massaging the cycle components, and 'rest', into
        a semver-compatible buildstring, which is dot-separated and can only
        contain alphanumerics.  See SQR-059 for how it's used.
        (https://github.com/lsst-sqre/sqr-059)
        """
        if cycle:
            if rest:
                # Cycle must always precede rest
                rest = f"{ctag}{cycle}.{cbuild}_{rest}"
            else:
                rest = f"{ctag}{cycle}.{cbuild}"
        # We're done with cycle components now.
        if not rest:
            return None
        rest = rest.replace("_", ".")
        pat = re.compile(r"[^\w|\.]+")  # Identify all non alphanum, non-dots
        # Throw away all of those after turning underscores to dots.
        rest = pat.sub("", rest)
        if not rest:  # if we are left with an empty string, return None
            return None
        return rest

    def compare(self, other: "RubinPartialTag") -> int:
        """This is modelled after semver.compare, but raises an exception
        if the images do not have the same image_type."""
        if self.image_type != other.image_type:
            raise IncomparableImageTypesError(
                f"Tag '{self.tag}' of type {self.image_type} cannot be "
                + f"compared to '{other.tag}' of type {other.image_type}."
            )
        # The easy case: we have a type with a semantic_version attribute.
        # Use it.
        if (
            self.semantic_version is not None
            and other.semantic_version is not None
        ):
            return self.semantic_version.compare(other.semantic_version)
        # Otherwise, all we can do is sort lexigraphically by tag.
        # Experimentals can be sorted only by tag.
        if self.tag == other.tag:
            return 0
        if self.tag < other.tag:
            return -1
        return 1

    """Implement comparison operators."""

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RubinPartialTag):
            return NotImplemented
        return self.compare(other) == 0

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __gt__(self, other: "RubinPartialTag") -> bool:
        return self.compare(other) == 1

    def __le__(self, other: "RubinPartialTag") -> bool:
        return not self.__gt__(other)

    def __lt__(self, other: "RubinPartialTag") -> bool:
        return self.compare(other) == -1

    def __ge__(self, other: "RubinPartialTag") -> bool:
        return not self.__lt__(other)


@dataclass(frozen=True)
class RubinTag(RubinPartialTag):
    """Immutable, once constructed, the primary method of construction
    is the from_tag classmethod.  The RubinTag holds all the metadata
    encoded within a particular tag (in its base class) and also additional
    metadata known and/or calculated via outside sources, such as the
    image digest, whether the image is an alias, and the image reference.
    """

    image_ref: str
    """This is the Docker reference for this particular image.  It's not
    actually used within this class, but it's useful as general image
    metadata, since it's required to pull the image.

    example: index.docker.io/lsstsqre/sciplat-lab:w_2021_22
    """

    digest: Optional[str]
    """Image digest for a particular image.

    example: "sha256:419c4b7e14603711b25fa9e0569460a753c4b2449fe275bb5f89743b01794a30"  # noqa: E501
    """

    # We use a classmethod here rather than just allowing specification of
    # the fields because we want a frozen class where most of the attributes
    # are derived.
    @classmethod
    def from_tag(
        cls,
        tag: str,
        image_ref: str = "",
        alias_tags: List[str] = [],
        override_name: str = "",
        digest: Optional[str] = None,
        override_cycle: Optional[int] = None,
    ) -> "RubinTag":
        """Create a RubinTag object from a tag and a list of alias tags.
        Allow overriding name rather than generating one, and allow an
        optional digest parameter."""
        partial_tag = RubinPartialTag.parse_tag(tag)
        image_type = partial_tag.image_type
        display_name = partial_tag.display_name
        cycle = partial_tag.cycle
        # Here's where we glue in the alias knowledge
        if tag in alias_tags:
            logger.debug(f"Tag '{tag}' is an alias tag.")
            image_type = RubinTagType.ALIAS
            display_name = RubinPartialTag.prettify_tag(tag)
        # And here we override the name if appropriate.
        if override_name:
            logger.debug(
                f"Overriding display name '{display_name}'"
                + f"with '{override_name}'"
            )
            display_name = override_name
        # Override cycle if appropriate
        if override_cycle:
            logger.debug(f"Overriding cycle '{cycle}' with '{override_cycle}'")
            cycle = override_cycle
        return cls(
            tag=tag,
            image_ref=image_ref,
            digest=digest,
            image_type=image_type,
            display_name=display_name,
            semantic_version=partial_tag.semantic_version,
            cycle=cycle,
        )

    def is_recognized(self) -> bool:
        """Only return true if the image is a known type that is not known
        to be an alias.  It's possible that we also want to exclude
        experimental images.
        """
        img_type = self.image_type
        unrecognized = [RubinTagType.UNKNOWN, RubinTagType.ALIAS]
        if img_type in unrecognized:
            return False
        return True


@dataclass(frozen=True)
class RubinTagList:
    """This is a class to hold tag objects and return sorted lists of them
    for construction of the image menu.  It also allows compactification
    of its input list, which may contain null objects--this is in order to
    support image consolidation based on hash, if we decide to do that.
    """

    all_tags: Union[List[RubinTag], List[Optional[RubinTag]]]

    def sorted_images(
        self, img_type: RubinTagType, count: Optional[int] = None
    ) -> DockerImageList:
        """This returns a sorted list of images for a given type, highest
        version (and thus most recent) at the top.  The optional count
        parameter specifies how many images should be in the list; leaving it
        None will return the entire list.
        """
        imgs = sorted(
            [
                t
                for t in self.all_tags
                if (t is not None and img_type == t.image_type)
            ],
            reverse=True,
        )
        if count is not None:
            imgs = imgs[:count]
        taglist = RubinTagList(imgs)
        return taglist.to_dockerimagelist()

    def to_dockerimagelist(self, name_is_tag: bool = False) -> DockerImageList:
        image_list = DockerImageList()
        nonempty_tags = [t for t in self.all_tags.copy() if t is not None]
        image_list.load(
            [
                {
                    "image_url": t.image_ref,
                    "image_hash": (t.digest or ""),
                    "name": (
                        lambda name_is_tag: t.tag
                        if name_is_tag
                        else t.display_name
                    )(name_is_tag),
                }
                for t in nonempty_tags
            ]
        )
        return image_list


class IncomparableImageTypesError(Exception):
    pass
