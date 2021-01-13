from typing import Any, Dict, List

import structlog

from cachemachine.types import CachedDockerImage, DockerImageList, RepoMan

logger = structlog.get_logger(__name__)


class SimpleRepoMan(RepoMan):
    def __init__(self, body: Dict[str, Any]):
        self._images = DockerImageList()
        self._images.load(body["images"])

    async def desired_images(
        self, common_cache: List[CachedDockerImage]
    ) -> DockerImageList:
        return self._images
