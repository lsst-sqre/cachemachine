from typing import Any, Dict, List

import structlog
from dxf import DXF

from cachemachine.dockercreds import lookup_docker_credentials
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
        self.credentials = lookup_docker_credentials(self.registry_url)
        self.repo = body["repo"]
        self.recommended_tag = body.get("recommended_tag", None)
        self.num_dailies: int = body["num_dailies"]
        self.num_weeklies: int = body["num_weeklies"]
        self.num_releases: int = body["num_releases"]

    def desired_images(
        self, common_cache: List[CachedDockerImage]
    ) -> DockerImageList:
        def __docker_auth(dxf, response) -> None:
            dxf.authenticate(
                self.credentials.username,
                self.credentials.password,
                response=response,
            )

        client = DXF(self.registry_url, self.repo, __docker_auth)

        # Sort the tags lexically and in reverse, which should give the
        # most recent builds above the older builds.  At this point, all
        # the dailies, weeklies, releases, and recommended are in here.
        tags = sorted(client.list_aliases(), reverse=True)

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

            tag_parts = t.split("_")

            if t == self.recommended_tag:
                aka = set()
                image_hash = client.get_digest(t)

                for i in common_cache:
                    if i.image_hash == image_hash:
                        aka = i.tags

                images.append(
                    DockerImage(
                        image_url=image_url,
                        image_hash=image_hash,
                        name=f"Recommended {aka}",
                    )
                )
            elif t.startswith("d_"):
                # Ex: d_2020_11_0
                if len(dailies) < self.num_dailies:
                    dailies.append(
                        DockerImage(
                            image_url=image_url,
                            image_hash=client.get_digest(t),
                            name=f"Daily {tag_parts[2]}/{tag_parts[3]}",
                        )
                    )
            elif t.startswith("w_"):
                # Ex: w_2020_41
                if len(weeklies) < self.num_weeklies:
                    weeklies.append(
                        DockerImage(
                            image_url=image_url,
                            image_hash=client.get_digest(t),
                            name=f"Weekly {tag_parts[2]}",
                        )
                    )
            elif t.startswith("r"):
                # Ex: r20_0_0, r20_0_0_rc1
                if len(releases) < self.num_releases:
                    name = "Release " + ".".join(tag_parts)
                    releases.append(
                        DockerImage(
                            image_url=image_url,
                            image_hash=client.get_digest(t),
                            name=name,
                        )
                    )
            else:
                logger.debug(f"Not processing {t}")

        images.extend(releases)
        images.extend(weeklies)
        images.extend(dailies)
        logger.info(f"Returning {images}")
        return images
