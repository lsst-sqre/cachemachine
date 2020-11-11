import structlog
from kubernetes.client.api import core_v1_api

logger = structlog.get_logger(__name__)


class CacheChecker:
    def __init__(self, label):
        self.api = core_v1_api.CoreV1Api()
        self.label = label
        self.label_exists = False
        self.common_cache = set()

    def check(self):
        nodes = self.api.list_node().items
        logger.debug(f"Inspecting {nodes}")

        common_cache = set()
        label_exists = False

        for n in nodes:
            labels = []

            for k in n.metadata.labels:
                labels.append(k + ": " + n.metadata.labels[k])

            logger.info(labels)

            images = []
            for i in n.status.images:
                images.extend(i.names)

            logger.info(images)

            if self.label in labels:
                if not label_exists:
                    label_exists = True
                    common_cache = set(images)
                else:
                    common_cache = common_cache.intersection(images)

        self.common_cache = common_cache
        self.label_exists = label_exists
