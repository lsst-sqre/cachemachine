from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional, Set


class DockerRegistryError(Exception):
    pass


class KubernetesDaemonsetNotFound(Exception):
    pass


class TellerNotFoundError(Exception):
    pass


@dataclass
class CachedDockerImage:
    image_url: str
    image_hash: str
    tags: Set[str]


@dataclass
class DockerImage:
    image_url: str
    image_hash: Optional[str]
    name: str


class DockerImageList(list):
    def load(self, data: List[Dict[str, str]]) -> None:
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
        return [asdict(i) for i in self]


class RepoMan(ABC):
    @abstractmethod
    async def desired_images(
        self, common_cache: List[CachedDockerImage]
    ) -> DockerImageList:
        pass
