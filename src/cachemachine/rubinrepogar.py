"""Repository Manager for Rubin Observatory images on Artifact Registry."""

from typing import Any, Dict, List

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
        self.gar_repo = body["gar_repository"]

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

        # Construct parent resource to identify google artifact registry
        parent = (
            f"projects/{self.project_id}/locations/{self.location}/"
            f"repositories/{self.gar_repo}"
        )

        image_base = (
            f"{self.location}-docker.pkg.dev/"
            f"{self.project_id}/{self.gar_repo}/sciplat-lab"
        )

        # Initialize request argument for google artifact registry
        request = artifactregistry_v1.ListDockerImagesRequest(
            parent=parent,
        )

        # Make the request
        image_list = self.client.list_docker_images(request=request)

        # Handle the response
        for response in image_list:

            for tag in response.tags:

                # Parse image digest from image URI and @ from image hash
                # as it does match format from cache
                digest = response.uri.lstrip(image_base).strip("@")

                # Set alias tag if image is alias
                if tag in self.alias_tags:

                    tagobj = RubinTag.from_tag(
                        tag=tag,
                        image_ref=f"{image_base}:{tag}",
                        alias_tags=tag,
                        override_name="",
                        digest=digest,
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
                            # Put ohter alias tags into pull images list.
                            # Alias tags should, I guess, go after recommended
                            # but before the others?
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

        # Note that for the dropdown, we want to display the tag, rather
        # than its associated display name.
        taglist = RubinTagList(all_tags)

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
