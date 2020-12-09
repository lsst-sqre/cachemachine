from typing import Any, Dict, List, Set

import structlog

from cachemachine.types import RepoMan

logger = structlog.get_logger(__name__)


class SimpleRepoMan(RepoMan):
    def __init__(self, body: Dict[str, Any]):
        self._images = body["images"]

    def desired_images(
        self, recommended_names: Set[str]
    ) -> List[Dict[str, str]]:
        return self._images

    def recommended_image_url(self) -> str:
        return ""
