from typing import Any, Dict, List, Optional, Set

import structlog
from docker_registry_client import DockerRegistryClient

from cachemachine.dockercreds import DockerCreds
from cachemachine.types import RepoMan

logger = structlog.get_logger(__name__)


class RubinRepoMan(RepoMan):
    def __init__(self, body: Dict[str, Any]):
        self.registry_url = body.get("registry_url", "hub.docker.com")
        (self.username, self.password) = DockerCreds.lookup(self.registry_url)
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
                    if (n == self._recommended_image_url) or ("@sha256" in n):
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
        image_metas = sorted(image_metas, key=lambda i: i["tag"], reverse=True)

        if len(image_metas) < num_desired:
            return image_metas
        else:
            return image_metas[0:num_desired]
