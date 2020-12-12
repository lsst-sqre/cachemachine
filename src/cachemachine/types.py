from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional, Set


class TellerNotFoundError(Exception):
    pass


@dataclass
class DockerCredentials:
    username: Optional[str] = None
    password: Optional[str] = None


@dataclass
class DockerImage:
    image_url: str
    name: str


class DockerImageList(list):
    def load(self, data: List[Dict[str, str]]) -> None:
        self.extend(
            [
                DockerImage(image_url=i["image_url"], name=i["name"])
                for i in data
            ]
        )

    def dump(self) -> List[Dict[str, str]]:
        return [asdict(i) for i in self]


class RepoMan(ABC):
    @abstractmethod
    def desired_images(self, recommended_names: Set[str]) -> DockerImageList:
        pass

    @abstractmethod
    def recommended_image_url(self) -> Optional[str]:
        pass
