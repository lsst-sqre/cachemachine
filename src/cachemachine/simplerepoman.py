import structlog

logger = structlog.get_logger(__name__)


class SimpleRepoMan:
    def __init__(self, body):
        self.name = body["name"]
        self.image_url = body["image_url"]

    def desired_images(self):
        return set([self.image_url])
