"""Helper types and errors for cachemachine."""

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional


class DockerRegistryError(Exception):
    """Unknown error working with the docker registry."""

    pass


class KubernetesDaemonsetNotFound(Exception):
    """Kubernetes daemonset does not exist."""

    pass


class CacheMachineNotFoundError(Exception):
    """Cachemachine does not exist."""

    pass


@dataclass
class CachedDockerImage:
    """Container for docker image that is already pulled."""

    """URL of the image.  Can either be a full URL or short name,
      ex. lsstsqre/sciplat-lab:recommended,
      ex. registry.hub.docker.com/lsstsqre/sciplat-lab:recommended
      ex. ts-dockerhub.lsst.org/lsstsqre/sciplat-lab:recommended.
    """
    image_url: str

    """SHA256 hash of the pulled image."""
    image_hash: str

    """List of tags this docker image is known by."""
    tags: List[str]


@dataclass
class DockerImage:
    """Container for docker image to pull."""

    """URL of the image.  Can either be a full URL or short name,
      ex. lsstsqre/sciplat-lab:recommended,
      ex. registry.hub.docker.com/lsstsqre/sciplat-lab:recommended
      ex. ts-dockerhub.lsst.org/lsstsqre/sciplat-lab:recommended.
    """
    image_url: str

    """SHA256 hash of the pulled image.

    Optional: if provided, will ensure the image with that hash is pulled.
    Otherwise any image present with that url is fine.
    """
    image_hash: Optional[str]

    """Friendly name to present to the user when referring to this image."""
    name: str


class DockerImageList(list):
    """Container for a list of DockerImages.

    Helpful for serializing to and from json.
    """

    def load(self, data: List[Dict[str, str]]) -> None:
        """Extend this list of images with the provided data.

        Parameters
        ----------
        data: List of dictionaries that contain fields of
          DockerImage.
        """
        self.extend(
            [
                DockerImage(
                    image_url=i["image_url"],
                    image_hash=i.get("image_hash", None),
                    name=i["name"],
                )
                for i in data
            ]
        )

    def dump(self) -> List[Dict[str, str]]:
        """Dump the data of this list as a list of dictionaries.

        This list can be easily converted to JSON.
        """
        return [asdict(i) for i in self]


class KubernetesLabels(dict):
    """Container for a set of Kubernetes labels.

    Provides a helper function to see if a set of labels
    matches the labels on a node.
    """

    def matches(self, node_labels: Dict[str, str]) -> bool:
        """Check if these labels match the labels of the node.

        Parameters
        ----------
        node_labels: Kubernetes labels on the node.

        Returns
        -------
        True: this set of labels matches the node.
        False: this set of labels does not match the node.
        """
        return self.items() <= node_labels.items()


class RepoMan(ABC):
    @abstractmethod
    async def desired_images(
        self, common_cache: List[CachedDockerImage]
    ) -> DockerImageList:
        pass
