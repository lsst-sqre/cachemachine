import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

import semver
from docker_image import reference

from .types import IncomparableImagesError

DEFAULT_TAG = "latest"  # Docker convention
DEFAULT_RECOMMENDED_TAG = "recommended"


class RubinImageType(Enum):
    """Class to capture the different kinds of image types possible in a
    Rubin Lab Image container, given our standard tag set."""

    RECOMMENDED = auto()
    LATEST = auto()
    LATEST_SOMETYPE = auto()
    RELEASE = auto()
    WEEKLY = auto()
    DAILY = auto()
    RELEASE_CANDIDATE = auto()
    EXPERIMENTAL = auto()
    MALFORMED_TAG = auto()


# Helper functions that don't rely on any part of the class object and thus
# are not methods.


def _check_tag_is_lowercase(tag: str) -> bool:
    if tag != tag.lower():
        return False
    return True


def _type_from_tag(tag: str, recommended_tag: str) -> RubinImageType:
    """This constructs the image type from the tag.  It is inherently
    Rubin tag-specific."""
    if not _check_tag_is_lowercase(tag):
        return RubinImageType.MALFORMED_TAG
    if tag == recommended_tag:
        return RubinImageType.RECOMMENDED
    if tag == DEFAULT_TAG:
        return RubinImageType.LATEST
    if tag.startswith("latest_"):
        # It's latest *something*
        ttag = tag[7:]
        if ttag in ("weekly", "daily", "release"):
            return RubinImageType.LATEST_SOMETYPE
        return RubinImageType.MALFORMED_TAG
    if tag.startswith("w_"):
        return RubinImageType.WEEKLY
    if tag.startswith("d_"):
        return RubinImageType.DAILY
    if tag.startswith("exp_"):
        return RubinImageType.EXPERIMENTAL
    if tag.startswith("r"):
        # If there are any non-numeric characters in the tag after the inital
        # 'r', it's a release candidate; if not, we claim it's a real release.
        # Thus, r22_0_0_rc1 is a release candidate, but r21_0_1 is a release.
        tagtext = tag[1:].replace("_", "")
        if tagtext.isdigit():
            return RubinImageType.RELEASE
        return RubinImageType.RELEASE_CANDIDATE
    return RubinImageType.MALFORMED_TAG


def _semver_from_tag(tag_type: RubinImageType, tag: str) -> semver.VersionInfo:
    if (
        tag_type == RubinImageType.EXPERIMENTAL
        or tag_type == RubinImageType.RECOMMENDED
        or tag_type == RubinImageType.LATEST
        or tag_type == RubinImageType.LATEST_SOMETYPE
        or tag_type == RubinImageType.MALFORMED_TAG
    ):
        # The "latest" tags are by their nature singletons.
        # Experimentals and malformed tags do not have meaningful
        # semantic versioning and are compared purely lexigraphically by tag.
        return semver.VersionInfo(0, 0, 1)
    tag = _canonicalize_tag(tag_type, tag)
    tagparts = tag.split("_")
    major = int(tagparts[1])
    minor = int(tagparts[2])
    patch = 0
    bldidx = 3  # Index of tag part where build version starts
    if tag_type != RubinImageType.WEEKLY:
        if len(tagparts) > 3:
            patch = int(tagparts[3])
            bldidx = 4
    pre = None
    build = None
    if len(tagparts) > bldidx:
        if tag_type == RubinImageType.RELEASE_CANDIDATE:
            # The fourth part of the tag starts with 'rc' and contains
            #  a prerelease number.
            pre = tagparts[4][2:]
            bldidx = 5
        # And everything that's left is a build tag
        build = ".".join(tagparts[bldidx:])
    return semver.VersionInfo(
        major=major, minor=minor, patch=patch, prerelease=pre, build=build
    )


def _cycle_from_semver(semantic_version: semver.VersionInfo) -> Optional[int]:
    """T&S SAL builds use a convention where they append _cXYZ.ABC to the
    tag, where XYZ is the 'cycle' of XML they're using."""
    retval = None
    build = semantic_version.build
    if build:
        buildparts = build.split(".")
        for bp in buildparts:
            # look for c<digits> or csal<digits>
            # and capture the first group of <digits>
            s = re.search(r"^csal|c(\d+)$", bp)
            if s and s.groups():
                retval = int(s.groups()[0])
                break
    return retval


def _canonicalize_tag(image_type: RubinImageType, tag: str) -> str:
    if (
        image_type == RubinImageType.RELEASE
        or image_type == RubinImageType.RELEASE_CANDIDATE
    ):
        # Releases/rcs do not have an underscore between the type and the
        # numbering, unlike every other type.  To make parsing easier, we
        # just force tag into the canonical format.
        if "_" not in tag:
            # This is the ridiculously obsolete format, rxyz (e.g. "r170")
            tag = "_".join(list(tag))
        else:
            tag = "r_" + tag[1:]
    return tag


def _display_name_from_tag(
    image_type: RubinImageType, tag: str, recommended_tag: Optional[str]
) -> str:
    """Given a Rubin-format tag, construct a human-readable display name
    from it."""
    typename = image_type.name.replace("_", " ").title()
    ctag = _canonicalize_tag(image_type, tag)
    ctparts = ctag.split("_")
    dtag = "_".join(ctparts[1:])
    if recommended_tag is None:
        recommended_tag = DEFAULT_RECOMMENDED_TAG
    if image_type == RubinImageType.RECOMMENDED:
        return recommended_tag.replace("_", " ").title()
    if image_type == RubinImageType.LATEST:
        return "Latest"
    if image_type == RubinImageType.LATEST_SOMETYPE:
        ttag = tag[7:].title()
        return f"Latest {ttag}"
    if (
        image_type == RubinImageType.RELEASE
        or image_type == RubinImageType.RELEASE_CANDIDATE
    ):
        tagparts = tag.split("_")
        rdigits = tagparts[0:3]
        dtag = ".".join(rdigits)
        if len(tagparts) > 3:
            dtag += "-" + "_".join(tagparts[3:])
    if image_type == RubinImageType.EXPERIMENTAL:
        # Try running the stuff after exp_ through.  This is to handle the
        #  common case of exp_<regular-tag>_something
        etag = tag[4:]
        etype = _type_from_tag(etag, recommended_tag)
        if etype != RubinImageType.MALFORMED_TAG:
            etname = etype.name.title()
            cetag = _canonicalize_tag(etype, etag)
            cetagparts = cetag.split("_")
            etag = "_".join(cetagparts[1:])
            dtag = f"{etname} {etag}"
    if image_type == RubinImageType.MALFORMED_TAG:
        dtag = tag  # Totally unparseable.
    return f"{typename} {dtag}"


@dataclass(frozen=True)
class RubinImageInfo:
    reference: str
    """reference is a docker image reference.
    See:
     https://github.com/distribution/distribution/blob/main/reference/reference.go  # noqa: E501

    Example: "registry.hub.docker.com/lsstsqre/sciplat-lab:w_2021_13@sha256:419c4b7e14603711b25fa9e0569460a753c4b2449fe275bb5f89743b01794a30"  # noqa: E501
    """

    host: str
    """host is the host from which the image can be pulled.

    Example: "registry.hub.docker.com"
    """

    repo: str
    """image repository at a particular host.

    Example: "lsstsqre"
    """

    name: str
    """image name within a particular image repository.

    example: "sciplat-lab"
    """

    tag: str
    """image tag for a particular image.

    Example: "w_2021_13"
    """

    digest: Optional[str]
    """image digest for a particular image.

    Example: "sha256:419c4b7e14603711b25fa9e0569460a753c4b2449fe275bb5f89743b01794a30"  # noqa: E501
    """

    reference_obj: reference.Reference
    """field containing the results of parsing the reference string with the
    docker_image class.
    """

    image_type: RubinImageType
    """Rubin-specific image type

    Example: RubinImageType.WEEKLY
    """

    semantic_version: semver.VersionInfo
    """Semantic version constructed from a tag.  Only comparable between
    RubinImageInfo instances of the same host, repo, name, and image_type.
    """

    display_name: str
    """Human-readable display name corresponding to a tag."""

    cycle: Optional[int]
    """Cycle (used only in T&S SAL builds)."""

    @classmethod
    def from_reference(
        cls,
        ref: str,
        recommended_tag: Optional[str] = None,
        digest: Optional[str] = None,
    ) -> "RubinImageInfo":
        """Create a RubinImageInfo object from a reference string."""
        # Delegate basic parsing to the image reference class
        if not recommended_tag:
            recommended_tag = DEFAULT_RECOMMENDED_TAG
        reference_obj = reference.Reference.parse(ref)
        # An empty tag should be interpreted as 'latest'
        if not reference_obj["tag"]:
            reference_obj["tag"] = "latest"
        tag = reference_obj["tag"]
        # If we supplied digest separately, glue it in to the reference
        #  object as well as the RubinImageInfo object
        if digest and not reference_obj["digest"]:
            reference_obj["digest"] = digest
        contingent_name = reference_obj["name"]
        host, canonical_name = reference_obj.split_docker_domain(
            contingent_name
        )
        repo, name = canonical_name.split("/", 2)
        # From here down it is Rubin-specific fields
        image_type = _type_from_tag(tag, recommended_tag)
        semver = _semver_from_tag(image_type, tag)
        display_name = _display_name_from_tag(image_type, tag, recommended_tag)
        cycle = _cycle_from_semver(semver)
        return cls(
            reference=ref,
            reference_obj=reference_obj,
            host=host,
            repo=repo,
            name=name,
            tag=tag,
            digest=reference_obj["digest"],
            image_type=image_type,
            semantic_version=semver,
            display_name=display_name,
            cycle=cycle,
        )

    def compare(self, other: "RubinImageInfo") -> int:
        """This is modeled after semver.compare, but raises an exception
        if the images are not from the same host, repo, and name, or their
        image_types are incomparable.
        """
        if (
            self.host != other.host
            or self.repo != other.repo
            or self.name != other.name
        ):  # noqa E129
            raise IncomparableImagesError(
                "Comparable images must agree in host, repo, and name; "
                + f"'{self.reference}' and '{other.reference}' do not."
            )
        if self.image_type != other.image_type:
            raise IncomparableImagesError(
                f"Image {self.reference} of type {self.image_type} cannot be "
                + f"compared to {other.reference} of type {other.image_type}."
            )
        if (
            self.image_type == RubinImageType.EXPERIMENTAL
            or self.image_type == RubinImageType.MALFORMED_TAG
        ):
            # Experimentals are only sorted lexigraphically by tag.
            if self.tag == other.tag:
                return 0
            if self.tag < other.tag:
                return -1
            return 1
        if self.image_type == RubinImageType.LATEST_SOMETYPE:
            if self.tag != other.tag:
                raise IncomparableImagesError(
                    "'latest' tags cannot be compared."
                )
        return self.semantic_version.compare(other.semantic_version)

    """Implement comparison operators.  Raise IncomparableImagesError in
    underlying comparison operator."""

    def __eq__(self, other: "RubinImageInfo") -> bool:  # type: ignore[override]  # noqa: E501
        return self.compare(other) == 0

    def __ne__(self, other: "RubinImageInfo") -> bool:  # type: ignore[override]  # noqa: E501
        return not self.__eq__(other)

    def __gt__(self, other: "RubinImageInfo") -> bool:
        return self.compare(other) == 1

    def __le__(self, other: "RubinImageInfo") -> bool:
        return not self.__gt__(other)

    def __lt__(self, other: "RubinImageInfo") -> bool:
        return self.compare(other) == -1

    def __ge__(self, other: "RubinImageInfo") -> bool:
        return not self.__lt__(other)
