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
            if t.startswith("d_"):
                dailies.append(t)
            elif t.startswith("w_"):
                weeklies.append(t)
            elif t.startswith("r_"):
                releases.append(t)

        chosen_tags = []

        if "recommended" in tags:
            chosen_tags.append("recommended")

        dailies.sort(reverse=True)
        weeklies.sort(reverse=True)
        releases.sort(reverse=True)

        chosen_tags.extend(self._prune(releases, self.num_releases))
        chosen_tags.extend(self._prune(weeklies, self.num_weeklies))
        chosen_tags.extend(self._prune(dailies, self.num_dailies))

        images = []
        for t in chosen_tags:
            if self.registry_url == "hub.docker.com":
                images.append(f"{self.repo}:{t}")
            else:
                images.append(f"{self.registry_url}/{self.repo}:{t}")

        logger.info(f"Returning {images}")
        return set(images)

    def _prune(self, tags, desired):
        if len(tags) < desired:
            logger.warning(f"{tags} too short to choose {desired}")
            return tags
        else:
            return tags[0:desired]
