from typing import Any, Dict, List, Set

import structlog
from docker_registry_client import DockerRegistryClient

from cachemachine.dockercreds import DockerCreds

logger = structlog.get_logger(__name__)


class RubinRepoMan:
    registry_url: str
    recommended_image_url: str
    recommended_tag: str
    num_dailies: int
    num_weeklies: int
    num_releases: int

    def __init__(self, body: Dict[str, Any]):
        self.registry_url = body.get("registry_url", "hub.docker.com")
        (self.username, self.password) = DockerCreds.lookup(self.registry_url)
        self.repo = body["repo"]

        self.recommended_image_url = body.get("recommended_image_url", " : ")
        self.recommended_tag = self.recommended_image_url.split(":")[1]
        self.num_dailies = body["num_dailies"]
        self.num_weeklies = body["num_weeklies"]
        self.num_releases = body["num_releases"]

    def desired_images(
        self, recommended_names: Set[str]
    ) -> List[Dict[str, str]]:
        client = DockerRegistryClient(
            "https://" + self.registry_url,
            username=self.username,
            password=self.password,
        )

        repo = client.repository(self.repo)
        tags = repo.tags()
        logger.debug(f"Registry returned tags: {tags}")

        dailies = []
        weeklies = []
        releases = []

        images = []
        for t in tags:
            if self.registry_url == "hub.docker.com":
                image_url = f"{self.repo}:{t}"
            else:
                image_url = f"{self.registry_url}/{self.repo}:{t}"

            image_meta = {"tag": t, "image_url": image_url}

            tag_parts = t.split("_")

            if t == self.recommended_tag:
                # For the recommended tag, put it first in the list of
                # images that will be returned.  Also look up other
                # tags that use the same hash that are in the cache to
                # generate the name.
                aka = []
                for n in recommended_names:
                    if (n == self.recommended_image_url) or ("@sha256" in n):
                        continue

                    # Append the tag of this image to the aka list
                    aka.append(n.split(":")[1])

                image_meta["name"] = f"Recommended {aka}"
                images.append(image_meta)
            elif t.startswith("d_"):
                # Ex: d_2020_11_02
                image_meta["name"] = f"Daily {tag_parts[2]}/{tag_parts[3]}"
                dailies.append(image_meta)
            elif t.startswith("w_"):
                # Ex: w_2020_41
                image_meta["name"] = f"Weekly {tag_parts[2]}"
                weeklies.append(image_meta)
            elif t.startswith("r"):
                # Ex: r20_0_0, r20_0_0_rc1
                image_meta["name"] = "Release " + ".".join(tag_parts)
                releases.append(image_meta)

        images.extend(self._prune(releases, self.num_releases))
        images.extend(self._prune(weeklies, self.num_weeklies))
        images.extend(self._prune(dailies, self.num_dailies))
        logger.info(f"Returning {images}")
        return images

    def _prune(
        self, image_metas: List[Dict[str, str]], num_desired: int
    ) -> List[Dict[str, str]]:
        def take_tag(element: Dict[str, str]) -> str:
            return element["tag"]

        image_metas = sorted(image_metas, key=take_tag, reverse=True)

        if len(image_metas) < num_desired:
            logger.warning(f"{image_metas} too short to choose {num_desired}")
            return image_metas
        else:
            return image_metas[0:num_desired]
