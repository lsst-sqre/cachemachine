from typing import Any, Dict, Optional, Set

import structlog

from cachemachine.types import DockerImageList, RepoMan

logger = structlog.get_logger(__name__)


class SimpleRepoMan(RepoMan):
    def __init__(self, body: Dict[str, Any]):
        self._images = DockerImageList()
        self._images.load(body["images"])

    def desired_images(self, recommended_names: Set[str]) -> DockerImageList:
        return self._images

    def recommended_image_url(self) -> Optional[str]:
        return None
