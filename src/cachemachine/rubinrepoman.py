"""Repository Manager to manage Rubin Observatory images."""

from typing import Any, Dict, List

import structlog

from cachemachine.dockerclient import DockerClient
from cachemachine.types import (
    CachedDockerImage,
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
    ) -> DockerImageList:
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

        images = DockerImageList()
        dailies = DockerImageList()
        weeklies = DockerImageList()
        releases = DockerImageList()

        for t in tags:
            logger.debug(f"Checking tag: {t}")

            if self.registry_url == DOCKER_REGISTRY_HOST:
                image_url = f"{self.repo}:{t}"
            else:
                image_url = f"{self.registry_url}/{self.repo}:{t}"

            if t == self.recommended_tag:
                # Logic for generating the name of the recommended tag here.
                aka: List[str] = []

                # Get the hash of the recommended image.
                image_hash = await self.docker_client.get_image_hash(t)

                # Find all other images in the common cache that have the
                # same image hash (which means the same image data), and
                # combine the list of known tags into one.  All of these
                # are valid tags that point to the same image, but only
                # exist if the image was pulled by that tag.
                for i in common_cache:
                    if i.image_hash == image_hash:
                        for x in i.tags:
                            if x != self.recommended_tag and x not in aka:
                                aka.append(x)

                # Generate the name based on what other tags it is known by.
                if aka:
                    friendly_names = [self._friendly_name(a) for a in aka]
                    name = f"Recommended ({','.join(friendly_names)})"
                else:
                    name = "Recommended"

                images.append(
                    DockerImage(
                        image_url=image_url,
                        image_hash=image_hash,
                        name=name,
                    )
                )
            elif t.startswith("d_"):
                # Ex: d_2020_11_0
                if len(dailies) < self.num_dailies:
                    image_hash = await self.docker_client.get_image_hash(t)
                    dailies.append(
                        DockerImage(
                            image_url=image_url,
                            image_hash=image_hash,
                            name=self._friendly_name(t),
                        )
                    )
            elif t.startswith("w_"):
                # Ex: w_2020_41
                if len(weeklies) < self.num_weeklies:
                    image_hash = await self.docker_client.get_image_hash(t)
                    weeklies.append(
                        DockerImage(
                            image_url=image_url,
                            image_hash=image_hash,
                            name=self._friendly_name(t),
                        )
                    )
            elif t.startswith("r"):
                # Ex: r20_0_0, r20_0_0_rc1
                if len(releases) < self.num_releases:
                    image_hash = await self.docker_client.get_image_hash(t)
                    releases.append(
                        DockerImage(
                            image_url=image_url,
                            image_hash=image_hash,
                            name=self._friendly_name(t),
                        )
                    )
            else:
                logger.debug(f"Not processing {t}")

        images.extend(releases)
        images.extend(weeklies)
        images.extend(dailies)
        logger.info(f"Returning {images}")
        return images

    def _friendly_name(self, tag: str) -> str:
        """Generate the friendly name of an image based on its tag.

        Parameters
        ----------
        tag: tag to generate the friendly name of.  Only works on
          release, weekly, and daily tags.

        Returns
        -------
        The friendly name of the tag.
        """
        tag_parts = tag.split("_")

        if tag.startswith("d_"):
            return f"Daily {tag_parts[2]}/{tag_parts[3]}"
        elif tag.startswith("w_"):
            return f"Weekly {tag_parts[2]}"
        elif tag.startswith("r"):
            return "Release " + ".".join(tag_parts)
        else:
            # Should never reach here...
            raise Exception(f"Unexpected tag name {tag}")
