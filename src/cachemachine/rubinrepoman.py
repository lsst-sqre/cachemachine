"""Repository Manager to manage Rubin Observatory images."""

from typing import Any, Dict, List, Optional

import structlog

from cachemachine.dockerclient import DockerClient
from cachemachine.rubinimageinfo import RubinImageInfo, RubinImageType
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
        """
        self.registry_url = body.get("registry_url", DOCKER_REGISTRY_HOST)
        self.repo = body["repo"]
        self.docker_client = DockerClient(self.registry_url, self.repo)
        self.recommended_tag = body.get("recommended_tag", None)
        self.num_dailies: int = body["num_dailies"]
        self.num_weeklies: int = body["num_weeklies"]
        self.num_releases: int = body["num_releases"]

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

        logger.debug(f"Registry returned tags: {tags}")

        pull_images = DockerImageList()
        all_images = DockerImageList()

        img_info_list: List[RubinImageInfo] = []
        img_info_list = [
            RubinImageInfo.from_reference(
                f"{self.registry_url}/{self.repo}:{t}",
                recommended_tag=self.recommended_tag,
            )
            for t in tags
        ]
        # Categorize images by type and then sort each type
        imgmap: Dict[str, List[RubinImageInfo]] = {
            "daily": [],
            "weekly": [],
            "release": [],
        }
        for img in img_info_list:
            logger.debug(f"Checking image: {img.reference}")
            image_url = img.reference
            img_type = img.image_type
            if not self._allow_image(img):
                # Pretend it's not there at all
                continue
            if img.image_type == RubinImageType.RECOMMENDED:
                # This is the complicated one.
                # Get the hash of the recommended image.
                image_hash = await self.docker_client.get_image_hash(img.tag)
                # Find all other images in the common cache that have the
                # same image hash (which means the same image data), and
                # combine the list of known tags into one.  All of these
                # are valid tags that point to the same image, but only
                # exist if the image was pulled by that tag.
                aka: List[str] = []
                for i in common_cache:
                    if i.image_hash == image_hash:
                        for x in i.tags:
                            if x != self.recommended_tag and x not in aka:
                                aka.append(x)

                # Generate the name based on what other tags it is known by.
                more_name_str = ""
                more_names = []
                if aka:
                    for alias in aka:
                        akaimg = RubinImageInfo.from_reference(
                            f"{self.registry_url}/{self.repo}:{alias}",
                            recommended_tag=self.recommended_tag,
                            digest=image_hash,
                        )
                        more_names.append(akaimg.display_name)
                if more_names:
                    more_name_str = " (" + ", ".join(more_names) + ")"
                name = f"{img.display_name}{more_name_str}"
                h_image = RubinImageInfo.from_reference(
                    img.reference,
                    recommended_tag=self.recommended_tag,
                    digest=image_hash,
                )
                pull_images.append(
                    self._docker_image_from_image_info(
                        h_image, override_name=name
                    )
                )
            elif img_type == RubinImageType.DAILY:
                imgmap["daily"].append(
                    RubinImageInfo.from_reference(
                        image_url, recommended_tag=self.recommended_tag
                    )
                )
            elif img_type == RubinImageType.WEEKLY:
                imgmap["weekly"].append(
                    RubinImageInfo.from_reference(
                        image_url, recommended_tag=self.recommended_tag
                    )
                )
            elif img_type == RubinImageType.RELEASE:
                imgmap["release"].append(
                    RubinImageInfo.from_reference(
                        image_url, recommended_tag=self.recommended_tag
                    )
                )
            all_images.append(
                self._docker_image_from_image_info(img, override_name=img.tag)
            )

        # At this point, "all_images" is populated.  pull_images has
        #  "recommended" and its aliases.  Both of these are modulo whatever
        #  was filtered out in _allow_image (which is nothing for this class,
        #  but might be overridden in a subclass).

        # Now we're going to sort each of the daily/weekly/release lists,
        #  and take the requested number of them.  For each of those we will
        #  get the hash (this is why we're processing the list twice: that's
        #  an expensive operation, and we only want to bother getting the
        #  digest for the prepulled images).  Sorting reverse=True will put
        #  the most recent ones (with the highest semvers) on top.

        for k, v in {
            "release": self.num_releases,
            "weekly": self.num_weeklies,
            "daily": self.num_dailies,
        }.items():
            inputlist = sorted(imgmap[k][:v], reverse=True)
            for img in inputlist:
                image_hash = await self.docker_client.get_image_hash(img.tag)
                h_image = RubinImageInfo.from_reference(
                    img.reference,
                    recommended_tag=self.recommended_tag,
                    digest=image_hash,
                )
                pull_images.append(self._docker_image_from_image_info(h_image))
        logger.info(f"Returning {pull_images}")
        return DesiredImageList(pull_images, all_images)

    def _docker_image_from_image_info(
        self, img: RubinImageInfo, override_name: Optional[str] = None
    ) -> DockerImage:
        name = img.display_name
        if override_name:
            name = override_name
        return DockerImage(
            image_url=img.reference, image_hash=img.digest, name=name
        )

    def _allow_image(self, img: RubinImageInfo) -> bool:
        """Override this in a subclass to filter out some images.
        Return False if you do not want the image.  You don't have the
        digest value here, necessarily, so you probably don't want to
        discriminate based on the digest."""
        return True
