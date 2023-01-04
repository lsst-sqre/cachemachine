"""Repository Manager for Rubin Observatory images on Artifact Registry."""

from typing import Any, Dict, List, Optional, Set

import structlog
from google.cloud import artifactregistry_v1

from cachemachine.rubintag import RubinTag, RubinTagList, RubinTagType
from cachemachine.types import (
    CachedDockerImage,
    DesiredImageList,
    DockerImage,
    DockerImageList,
    RepoMan,
)

logger = structlog.get_logger(__name__)


class RubinRepoGar(RepoMan):
    """This class encapsulates the business logic of picking images based on
    the format of tags created by Rubin Observatory."""

    def __init__(self, body: Dict[str, Any]):
        """Create a new Rubin Repository Manager.

        body: configuration parameters.  Outlined in the post.schema
            project_id: gcp project id for project hosting artifact registry
            location: region of google artifact registry
            gar_repository: name of google artifact repository
            recommended_tag: name of the recommended tag if there is one.
            num_dailies: number of daily images to pull.
            num_weeklies: number of weekly images to pull.
            num_releases: number of release images to pull.
            cycle: SAL XML cycle (optional).  Restrict images to this (integer)
                   cycle, if specified.
            alias_tags: list of tags to be treated as aliases to other images.
                        Optional, usually supplied as the empty list.  The
                        recommended_tag is added to this list if it exists.
        """

        # gar specific variables. Client uses workload identity for auth
        self.client = artifactregistry_v1.ArtifactRegistryClient()
        self.project_id = body["project_id"]
        self.location = body["location"]
        self.gar_repository = body["gar_repository"]
        self.gar_image = body["gar_image"]

        self.num_dailies: int = body["num_dailies"]
        self.num_weeklies: int = body["num_weeklies"]
        self.num_releases: int = body["num_releases"]
        self.cycle = body.get("cycle", None)
        self.alias_tags = body.get("alias_tags", [])

        # The recommended_tag is by its nature an alias tag.
        # So is "latest" (DOCKER_DEFAULT_TAG), but it's very possible we don't
        # want to pull "latest".  Add recommended if we have it, but the
        # DOCKER_DEFAULT_TAG only if it's already listed in alias_tags.
        self.recommended_tag = body["recommended_tag"]
        if self.recommended_tag:
            self.alias_tags.insert(0, self.recommended_tag)
        # Cheap deduplication
        self.alias_tags = list(set(self.alias_tags))

    async def desired_images(
        self, common_cache: List[CachedDockerImage]
    ) -> DesiredImageList:
        pull_images = DockerImageList()

        all_tags: List[RubinTag] = []
        other_tags = []

        # Construct parent resource to identify google artifact registry
        parent = (
            f"projects/{self.project_id}/locations/{self.location}/"
            f"repositories/{self.gar_repository}"
        )

        image_base = (
            f"{self.location}-docker.pkg.dev/"
            f"{self.project_id}/{self.gar_repository}/{self.gar_image}"
        )

        # Initialize request argument for google artifact registry
        request = artifactregistry_v1.ListDockerImagesRequest(
            parent=parent,
        )

        # Make the request
        image_list = self.client.list_docker_images(request=request)

        # Sort the tags lexically and in reverse, which should give the
        # most recent builds above the older builds.  At this point, all
        # the dailies, weeklies, releases, and recommended are in here.
        # tags = sorted(await self.docker_client.list_tags(), reverse=True)

        # Handle the response
        for response in image_list:
            # Create list of other tags to use later for updating display name
            other_tags = response.tags

            # Parse image digest from image URI and remove @ from image hash
            digest = response.uri.lstrip(image_base).strip("@")

            for tag in response.tags:
                # Set alias tag if image is alias
                if tag in self.alias_tags:
                    tag_cycle: Optional[int] = None

                    display_name = RubinTag.prettify_tag(tag)

                    if other_tags:
                        other_tagobjs: Set[RubinTag] = set()
                        for other_tag in other_tags:
                            candidate = RubinTag.from_tag(
                                tag=other_tag,
                                image_ref=f"{image_base}:{tag}",
                                digest=digest,
                                alias_tags=self.alias_tags,
                            )
                            if candidate.is_recognized():
                                # Only add recognized, resolved images
                                other_tagobjs.add(candidate)
                            # Use the candidate cycle if it is set.
                            # Unless something is really wrong, we won't have
                            # different cycle numbers for the same image
                            if candidate.cycle:
                                tag_cycle = candidate.cycle
                        # Construct display names with multiple tags
                        more_names = sorted(
                            [x.display_name for x in other_tagobjs],
                            reverse=True,
                        )
                        display_name += f" ({', '.join(more_names)})"

                    # Now that we know more about the tagged image, recreate
                    # the RubinTag object with the additional info.
                    tagobj = RubinTag.from_tag(
                        tag=tag,
                        image_ref=f"{image_base}:{tag}",
                        alias_tags=tag,
                        override_name=display_name,
                        digest=digest,
                        override_cycle=tag_cycle,
                    )

                    if self.verify_tagobj_cycle(tagobj):
                        # If we are in a cycle-aware environment, only use the
                        #  recommended or aliased image if the cycle matches.

                        if tag == self.recommended_tag:
                            #  Put recommended image into pull images list.
                            #  The point of the "recommended_tag" is that it is
                            #  alwayspulled and put at the front of the
                            #  pulled-image list. We want to do this check
                            #  after we resolve aliases so that the tag
                            #  object has a digest and the accurately-resolved
                            #  display name.

                            pull_images.insert(
                                0,  # At the front (not that it matters here)
                                DockerImage(
                                    image_url=tagobj.image_ref,
                                    image_hash=tagobj.digest,
                                    name=tagobj.display_name,
                                ),
                            )
                        elif tag in self.alias_tags:
                            # Put other alias tags into pull images list
                            pull_images.append(
                                DockerImage(
                                    image_url=tagobj.image_ref,
                                    image_hash=tagobj.digest,
                                    name=tagobj.display_name,
                                ),
                            )
                else:
                    # Add all other images into all images list
                    tagobj = RubinTag.from_tag(
                        tag=tag,
                        image_ref=f"{image_base}:{tag}",
                        override_name="",
                        digest=digest,
                    )

                all_tags.append(tagobj)

        # sort images in reverse alphabetical for proper display in image list
        tags_sorted = sorted(all_tags, key=str, reverse=True)

        # Note that for the dropdown, we want to display the tag, rather
        # than its associated display name.

        taglist = RubinTagList(tags_sorted)

        # all_images = taglist.sorted_images(img_type=RubinTagType)
        all_images = taglist.to_dockerimagelist(name_is_tag=True)

        pull_images.extend(
            taglist.sorted_images(
                RubinTagType.RELEASE, count=self.num_releases
            )
        )

        # Set pull weekly images
        pull_images.extend(
            taglist.sorted_images(RubinTagType.WEEKLY, count=self.num_weeklies)
        )

        # Set pull daily images
        pull_images.extend(
            taglist.sorted_images(RubinTagType.DAILY, count=self.num_dailies)
        )

        logger.info(f"Returning {pull_images}")

        return DesiredImageList(pull_images, all_images)

    def verify_tagobj_cycle(self, tagobj: RubinTag) -> bool:
        """This is true if either we are not in a cycle-aware environment,
        or, if we are, the cycle on the tagobj matches that of the
        environment."""
        return self.cycle is None or (tagobj.cycle == self.cycle)
