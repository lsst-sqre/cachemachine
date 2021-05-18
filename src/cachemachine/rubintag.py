"""Class to hold all the semantic data and metadata we can extract from a
tag in the format specified by https://sqr-059.lsst.io."""

from dataclasses import dataclass
from typing import List, Optional

from semver import VersionInfo

from cachemachine.rubintagfuncs import parse_tag
from cachemachine.rubintagtypes import (
    IncomparableImageTypesError,
    RubinTagType,
)


@dataclass(frozen=True)
class RubinTag:
    tag: str
    """This is the tag on a given image.  Because of cachemachine's design,
    we can safely assume that in any given cachemachine instance, there is
    one and only one host/repository/name tuple for all our tags.  If we
    need access to multiple image names, repositories, or hosts, they will
    be in different cachemachine instances.

    example: w_2021_13
    """

    image_ref: str
    """This is the Docker reference for this particular image.  It's not
    actually used within this class, but it's useful as general image
    metadata, since it's required to pull the image.

    example: index.docker.io/lsstsqre/sciplat-lab:w_2021_13
    """

    digest: Optional[str]
    """Image digest for a particular image.

    example: "sha256:419c4b7e14603711b25fa9e0569460a753c4b2449fe275bb5f89743b01794a30"  # noqa: E501
    """

    image_type: RubinTagType
    """Rubin-specific RSP Lab image type.

    example: RubinTagType.WEEKLY
    """

    display_name: str
    """Human-readable display name corresponding to a tag.
    """

    semantic_version: Optional[VersionInfo]
    """Semantic version constructed from a tag.  Only extant for Daily,
    Weekly, Release, and Release Candidate image types.  Only meaningful for
    comparison within a type.
    """

    cycle: Optional[int]
    """XML Cycle for a given image.  Only used in T&S builds.
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
        cycle: Optional[int] = None,
    ) -> "RubinTag":
        """Create a RubinTag object from a tag and a list of alias tags.
        Allow overriding name rather than generating one, and allow an
        optional digest parameter."""
        image_type, display_name, semver, cycle = parse_tag(
            tag,
            override_name=override_name,
            alias_tags=alias_tags,
        )
        return cls(
            tag=tag,
            image_ref=image_ref,
            digest=digest,
            image_type=image_type,
            semantic_version=semver,
            display_name=display_name,
            cycle=cycle,
        )

    def compare(self, other: "RubinTag") -> int:
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
        if (
            self.image_type == RubinTagType.UNKNOWN
            or self.image_type == RubinTagType.ALIAS
        ):
            # Unknown and alias types can only be compared for equality by
            #  tag.
            if self.tag == other.tag:
                return 0
            raise IncomparableImageTypesError(
                f"{self.tag} cannot be compared " f"to {other.tag}"
            )
        elif self.image_type == RubinTagType.EXPERIMENTAL:
            # Experimentals can be sorted only by tag.
            if self.tag == other.tag:
                return 0
            if self.tag < other.tag:
                return -1
            return 1
        # We should not be able to get here, but the typechecker can't
        # prove that.
        raise IncomparableImageTypesError(
            f"{self.tag} cannot be compared " f"to {other.tag}"
        )

    """Implement comparison operators."""

    def __eq__(self, other: "RubinTag") -> bool:  # type: ignore[override]  # noqa: E501
        return self.compare(other) == 0

    def __ne__(self, other: "RubinTag") -> bool:  # type: ignore[override]  # noqa: E501
        return not self.__eq__(other)

    def __gt__(self, other: "RubinTag") -> bool:
        return self.compare(other) == 1

    def __le__(self, other: "RubinTag") -> bool:
        return not self.__gt__(other)

    def __lt__(self, other: "RubinTag") -> bool:
        return self.compare(other) == -1

    def __ge__(self, other: "RubinTag") -> bool:
        return not self.__lt__(other)
