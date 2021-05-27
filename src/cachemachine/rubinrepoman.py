"""Repository Manager to manage Rubin Observatory images."""

from typing import Any, Dict, List, Set

import structlog

from cachemachine.dockerclient import DockerClient
from cachemachine.rubintag import (
    DOCKER_DEFAULT_TAG,
    RubinHashCache,
    RubinTag,
    RubinTagList,
    RubinTagType,
)
from cachemachine.types import (
    CachedDockerImage,
    DesiredImageList,
    DockerImage,
    DockerImageList,
    RepoMan,
)

DOCKER_REGISTRY_HOST = "registry.hub.docker.com"
logger = structlog.get_logger(__name__)


class RubinRepoMan(RepoMan):
    """This class encapsulates the business logic of picking images based on
    the format of tags created by Rubin Observatory."""

    def __init__(self, body: Dict[str, Any]):
        """Create a new Rubin Repository Manager.

        body: configuration parameters.  Outlined in the post.schema
            registry_url: host of the docker registry to use.  By default, use
              the official docker registry.
            repo: name of the repository to inspect, ex: lsstsqre/sciplat-lab.
            recommended_tag: name of the recommended tag if there is one.
            num_dailies: number of daily images to pull.
            num_weeklies: number of weekly images to pull.
            num_releases: number of release images to pull.
            cycle: SAL XML cycle (optional).  Restrict images to this (integer)
                   cycle, if specified.
            alias_tags: list of tags to be treated as aliases to other images.
                        Optional, usually supplied as the empty list.  No
                        matter what, the DOCKER_DEFAULT_TAG is put into
                        that list, and so is the recommended tag if it exists.
        """
        self.registry_url = body.get("registry_url", DOCKER_REGISTRY_HOST)
        self.repo = body["repo"]
        self.docker_client = DockerClient(self.registry_url, self.repo)
        self.recommended_tag = body.get("recommended_tag", None)
        self.num_dailies: int = body["num_dailies"]
        self.num_weeklies: int = body["num_weeklies"]
        self.num_releases: int = body["num_releases"]
        self.cycle = body.get("cycle", None)
        self.alias_tags = body.get("alias_tags", [])
        # The recommended_tag is by its nature an alias tag, and so is
        # "latest" (DOCKER_DEFAULT_TAG), so add those if they're not there.
        self.alias_tags.append(DOCKER_DEFAULT_TAG)
        if self.recommended_tag:
            self.alias_tags.append(self.recommended_tag)
        # Cheap deduplication
        self.alias_tags = list(set(self.alias_tags))

    async def desired_images(
        self, common_cache: List[CachedDockerImage]
    ) -> DesiredImageList:
        """Retrieve the list of images to pull, based on the registry.

        Parameters
        ----------
        common_cache: The current list of images available on all nodes
        associated with this cachemachine.

        Returns
        -------
        List of docker images to ensure are pulled, some of which may
        already be pulled and in the common cache.
        """
        # Sort the tags lexically and in reverse, which should give the
        # most recent builds above the older builds.  At this point, all
        # the dailies, weeklies, releases, and recommended are in here.
        tags = sorted(await self.docker_client.list_tags(), reverse=True)

        pull_images = DockerImageList()

        all_tags: List[RubinTag] = []

        logger.debug(f"common_cache -> {common_cache}")
        hashcache = RubinHashCache.from_cache(common_cache)
        logger.debug(f"RubinHashCache -> {hashcache}")
        for t in tags:
            # If there are alias tags, we will replace this object later with
            # a richer one containing data from those tags.
            image_url = f"{self.registry_url}/{self.repo}:{t}"
            tagobj = RubinTag.from_tag(
                tag=t,
                image_ref=image_url,
                alias_tags=self.alias_tags,
                override_name="",
                digest=hashcache.tag_to_hash.get(t),
            )
            if t in self.alias_tags:
                image_hash = await self.docker_client.get_image_hash(t)
                # Now use the inverse hash cache we built to get any other
                #  tags corresponding to that digest
                display_name = RubinTag.prettify_tag(t)
                other_tags = hashcache.hash_to_tags.get(image_hash)
                if other_tags:
                    logger.debug(f"Image {image_hash}: more tags {other_tags}")
                    other_tagobjs: Set[RubinTag] = set()
                    for other_tag in other_tags:
                        candidate = RubinTag.from_tag(
                            tag=other_tag,
                            image_ref=(
                                f"{self.registry_url}/{self.repo}"
                                + f":{other_tag}"
                            ),
                            digest=image_hash,
                            alias_tags=self.alias_tags,
                        )
                        if not candidate.is_recognized():
                            continue  # Only add recognized, resolved images
                        other_tagobjs.add(candidate)
                    more_names = sorted(
                        [x.display_name for x in other_tagobjs], reverse=True
                    )
                    display_name += f" ({', '.join(more_names)})"
                # Now that we know more about the tagged image, recreate
                # the RubinTag object with the additional info.
                tagobj = RubinTag.from_tag(
                    tag=t,
                    image_ref=image_url,
                    alias_tags=self.alias_tags,
                    override_name=display_name,
                    digest=image_hash,
                    cycle=self.cycle,
                )
            if t == self.recommended_tag:
                # The point of the "recommended_tag" is that it is always
                # pulled and put at the front of the pulled-image list.
                # We want to do this check after we resolve aliases
                # so that the tag object has a digest and the accurately-
                # resolved display name
                pull_images.insert(
                    0,  # At the front (not that it matters here)
                    DockerImage(
                        image_url=tagobj.image_ref,
                        image_hash=tagobj.digest,
                        name=tagobj.display_name,
                    ),
                )
            # If we are restricting by cycle only add the tag objects that
            #  match the correct cycle.
            if self.cycle is not None:
                if tagobj.cycle != self.cycle:
                    continue
            all_tags.append(tagobj)

        taglist = RubinTagList(all_tags)

        # Note that for the dropdown, we want to display the tag, rather
        # than its associated display name.
        all_images = taglist.to_dockerimagelist(name_is_tag=True)
        pull_images.extend(
            taglist.sorted_images(
                RubinTagType.RELEASE, count=self.num_releases
            )
        )
        pull_images.extend(
            taglist.sorted_images(RubinTagType.WEEKLY, count=self.num_weeklies)
        )
        pull_images.extend(
            taglist.sorted_images(RubinTagType.DAILY, count=self.num_dailies)
        )
        logger.info(f"Returning {pull_images}")
        return DesiredImageList(pull_images, all_images)
