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
    def __init__(self, body: Dict[str, Any]):
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
                aka: List[str] = []
                image_hash = await self.docker_client.get_image_hash(t)

                for i in common_cache:
                    if i.image_hash == image_hash:
                        for x in i.tags:
                            if x != self.recommended_tag and x not in aka:
                                aka.append(x)

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
