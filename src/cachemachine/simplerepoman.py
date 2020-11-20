from typing import Any, Dict, List, Set

import structlog

logger = structlog.get_logger(__name__)


class SimpleRepoMan:
    recommended_image_url: str = ""

    def __init__(self, body: Dict[str, Any]):
        self.images = body["images"]

    def desired_images(
        self, recommended_names: Set[str]
    ) -> List[Dict[str, str]]:
        return self.images
