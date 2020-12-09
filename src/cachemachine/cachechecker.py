from collections import defaultdict
from typing import Dict, List, Set

import structlog
from kubernetes.client.api import core_v1_api

logger = structlog.get_logger(__name__)


class CacheChecker:
    def __init__(
        self, labels: Dict[str, str], recommended_image_urls: List[str]
    ):
        self.api = core_v1_api.CoreV1Api()
        self.labels = labels
        self.recommended_image_urls = recommended_image_urls
        self._reset()

    def _reset(self) -> None:
        self.common_cache: Set[str] = set()
        self.nodes_exist = False
        self.recommended_names: Dict[str, Set[str]] = defaultdict(set)

    def check(self) -> None:
        self._reset()

        nodes = self.api.list_node().items
        logger.debug(f"Inspecting {nodes}")

        for n in nodes:
            node_name = n.metadata.name

            # This is a bit tricky.  The images is a list,
            # each item containing a particular image, and containing
            # a list of all the names it is known by.
            images = []
            recommended_names: Dict[str, Set[str]] = defaultdict(set)
            for i in n.status.images:
                for url in self.recommended_image_urls:
                    if url in i.names:
                        recommended_names[url] |= set(i.names)

                images.extend(i.names)

            logger.debug(f"{node_name} images: {images}")
            logger.debug(f"{node_name} recommended: {recommended_names}")

            # If the labels we have are a subset of the labels
            # of the node, include those images.
            logger.debug(f"{node_name} labels: {n.metadata.labels}")
            if self.labels.items() <= n.metadata.labels.items():
                if not self.nodes_exist:
                    # For the first node we find, that set is the initial
                    # common set.
                    self.nodes_exist = True
                    self.common_cache = set(images)
                    self.recommended_names = recommended_names
                else:
                    # Take the intersection of all the images on all the
                    # nodes so far.
                    self.common_cache &= set(images)

                    for u in self.recommended_image_urls:
                        self.recommended_names[u] &= recommended_names[u]
