import structlog
from kubernetes.client.api import core_v1_api

logger = structlog.get_logger(__name__)


class CacheChecker:
    def __init__(self, labels):
        self.api = core_v1_api.CoreV1Api()
        self.labels = labels
        self.nodes_exist = False
        self.common_cache = set()

    def check(self):
        nodes = self.api.list_node().items
        logger.debug(f"Inspecting {nodes}")

        common_cache = set()
        nodes_exist = False

        for n in nodes:
            node_name = n.metadata.name

            # This is a bit tricky.  The images is a list,
            # each item containing a particular image, and containing
            # a list of all the names it is known by.
            images = []
            for i in n.status.images:
                images.extend(i.names)

            logger.debug(f"{node_name} images: {images}")

            # If the labels we have are a subset of the labels
            # of the node, include those images.
            logger.debug(f"{node_name} labels: {n.metadata.labels}")
            if self.labels.items() <= n.metadata.labels.items():
                if not nodes_exist:
                    # For the first node we find, that set is the initial
                    # common set.
                    nodes_exist = True
                    common_cache = set(images)
                else:
                    # Take the intersection of all the images on all the
                    # nodes so far.
                    common_cache = common_cache.intersection(images)

        self.common_cache = common_cache
        self.nodes_exist = nodes_exist
