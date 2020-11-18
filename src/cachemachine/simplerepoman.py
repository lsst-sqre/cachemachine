import structlog

logger = structlog.get_logger(__name__)


class SimpleRepoMan:
    def __init__(self, body):
        self.images = body["images"]

    def desired_images(self):
        return self.images
