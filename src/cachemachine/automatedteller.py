import asyncio

import structlog

from cachemachine.cachechecker import CacheChecker
from cachemachine.cachedepositer import CacheDepositer

logger = structlog.get_logger(__name__)


class AutomatedTeller:
    def __init__(self, name, labels, repomen):
        self.name = name
        self.labels = labels
        self.checker = CacheChecker(self.labels)
        self.depositer = CacheDepositer(self.name, self.labels)
        self.repomen = repomen
        self.available_images = []
        self.desired_images = []
        self.images_to_cache = []

    async def do_work(self):
        while True:
            self.available_images = []
            self.desired_images = []
            self.images_to_cache = []

            self.checker.check()

            if not self.checker.nodes_exist:
                logger.warning(f"No nodes are labeled with: {self.labels}")
            else:
                for r in self.repomen:
                    for image in r.desired_images():
                        self.desired_images.append(image)

                        if image["image_url"] in self.checker.common_cache:
                            self.available_images.append(image)
                        else:
                            self.images_to_cache.append(image)

            if self.images_to_cache and not self.depositer.busy():
                self.depositer.deposit(self.images_to_cache[0]["image_url"])

            await asyncio.sleep(60)

    def talk(self):
        return {
            "name": self.name,
            "labels": self.labels,
            "nodes_exist": self.checker.nodes_exist,
            "common_cache": list(self.checker.common_cache),
            "available_images": self.available_images,
            "desired_images": self.desired_images,
            "images_to_cache": self.images_to_cache,
        }
