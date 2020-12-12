from typing import Any, Dict, Optional, Set

import structlog
from docker_registry_client import DockerRegistryClient

from cachemachine.dockercreds import lookup_docker_credentials
from cachemachine.types import DockerImage, DockerImageList, RepoMan

logger = structlog.get_logger(__name__)


class RubinRepoMan(RepoMan):
    def __init__(self, body: Dict[str, Any]):
        self.registry_url = body.get("registry_url", "hub.docker.com")
        self.credentials = lookup_docker_credentials(self.registry_url)
        self.repo = body["repo"]

        self._recommended_image_url = body.get("recommended_image_url", None)

        if self._recommended_image_url:
            self.recommended_tag = self._recommended_image_url.split(":")[1]
        else:
            self.recommended_tag = None

        self.num_dailies: int = body["num_dailies"]
        self.num_weeklies: int = body["num_weeklies"]
        self.num_releases: int = body["num_releases"]

    def recommended_image_url(self) -> Optional[str]:
        return self._recommended_image_url

    def desired_images(self, recommended_names: Set[str]) -> DockerImageList:
        client = DockerRegistryClient(
            "https://" + self.registry_url,
            username=self.credentials.username,
            password=self.credentials.password,
        )

        repo = client.repository(self.repo)

        # Sort the tags lexically and in reverse, which should give the
        # most recent builds above the older builds.  At this point, all
        # the dailies, weeklies, releases, and recommended are in here.
        tags = sorted(repo.tags(), reverse=True)
        logger.debug(f"Registry returned tags: {tags}")

        images = DockerImageList()
        dailies = DockerImageList()
        weeklies = DockerImageList()
        releases = DockerImageList()

        for t in tags:
            if self.registry_url == "hub.docker.com":
                image_url = f"{self.repo}:{t}"
            else:
                image_url = f"{self.registry_url}/{self.repo}:{t}"

            tag_parts = t.split("_")

            if t == self.recommended_tag:
                # For the recommended tag, put it first in the list of
                # images that will be returned.  Also look up other
                # tags that use the same hash that are in the cache to
                # generate the name.
                aka = []
                for n in recommended_names:
                    if (n == self._recommended_image_url) or ("@sha256" in n):
                        continue

                    # Append the tag of this image to the aka list
                    aka.append(n.split(":")[1])

                images.append(
                    DockerImage(image_url=image_url, name=f"Recommended {aka}")
                )

            elif t.startswith("d_"):
                # Ex: d_2020_11_0
                if len(dailies) < self.num_dailies:
                    dailies.append(
                        DockerImage(
                            image_url=image_url,
                            name=f"Daily {tag_parts[2]}/{tag_parts[3]}",
                        )
                    )
            elif t.startswith("w_"):
                # Ex: w_2020_41
                if len(weeklies) < self.num_weeklies:
                    weeklies.append(
                        DockerImage(
                            image_url=image_url, name=f"Weekly {tag_parts[2]}"
                        )
                    )
            elif t.startswith("r"):
                # Ex: r20_0_0, r20_0_0_rc1
                if len(releases) < self.num_releases:
                    name = "Release " + ".".join(tag_parts)
                    releases.append(
                        DockerImage(image_url=image_url, name=name)
                    )

        images.extend(releases)
        images.extend(weeklies)
        images.extend(dailies)
        logger.info(f"Returning {images}")
        return images
