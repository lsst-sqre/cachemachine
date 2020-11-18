import structlog
from docker_registry_client import DockerRegistryClient

from cachemachine.dockercreds import DockerCreds

logger = structlog.get_logger(__name__)


class RubinRepoMan:
    def __init__(self, body):
        self.registry_url = body.get("registry_url", "hub.docker.com")
        (self.username, self.password) = DockerCreds.lookup(self.registry_url)
        self.repo = body["repo"]

        self.num_dailies = body["num_dailies"]
        self.num_weeklies = body["num_weeklies"]
        self.num_releases = body["num_releases"]

    def desired_images(self):
        client = DockerRegistryClient(
            "https://" + self.registry_url,
            username=self.username,
            password=self.password,
        )

        repo = client.repository(self.repo)
        tags = repo.tags()

        dailies = []
        weeklies = []
        releases = []

        for t in tags:
            if self.registry_url == "hub.docker.com":
                image_url = f"{self.repo}:{t}"
            else:
                image_url = f"{self.registry_url}/{self.repo}:{t}"

            image_meta = {"tag": t, "image_url": image_url}

            tag_parts = t.split("_")

            if t.startswith("d_"):
                # Ex: d_2020_11_02
                image_meta["name"] = f"Daily {tag_parts[2]}/{tag_parts[3]}"
                dailies.append(image_meta)
            elif t.startswith("w_"):
                # Ex: w_2020_41
                image_meta["name"] = f"Weekly {tag_parts[2]}"
                weeklies.append(image_meta)
            elif t.startswith("r") and t != "recommended":
                # Ex: r20_0_0, r20_0_0_rc1
                image_meta["name"] = "Release " + ".".join(tag_parts)
                releases.append(image_meta)

        images = []
        images.extend(self._prune(releases, self.num_releases))
        images.extend(self._prune(weeklies, self.num_weeklies))
        images.extend(self._prune(dailies, self.num_dailies))
        logger.info(f"Returning {images}")
        return images

    def _prune(self, image_metas, num_desired):
        def take_tag(element):
            return element["tag"]

        image_metas = sorted(image_metas, key=take_tag, reverse=True)

        if len(image_metas) < num_desired:
            logger.warning(f"{image_metas} too short to choose {num_desired}")
            return image_metas
        else:
            return image_metas[0:num_desired]
