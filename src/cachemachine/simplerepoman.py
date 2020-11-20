import structlog

logger = structlog.get_logger(__name__)


class SimpleRepoMan:
    def __init__(self, body):
        self.images = body["images"]
        self.recommended_image_url = None

    def desired_images(self, recommended_names):
        return self.images
