import asyncio

import structlog

from cachemachine.cachechecker import CacheChecker
from cachemachine.cachedepositer import CacheDepositer

logger = structlog.get_logger(__name__)


class AutomatedTeller:
    def __init__(self, name, label, repomen):
        self.name = name
        self.label = label
        self.checker = CacheChecker(self.label)
        self.depositer = CacheDepositer()
        self.repomen = repomen
        self.desired_cache = set()
        self.images_to_cache = []

    async def do_work(self):
        while True:
            desired_cache = set()
            for r in self.repomen:
                desired_cache = desired_cache.union(r.desired_images())

            self.desired_cache = desired_cache

            self.checker.check()

            if self.checker.label_exists:
                self.images_to_cache = list(
                    self.desired_cache - self.checker.common_cache
                )
            else:
                self.images_to_cache = []

            if self.images_to_cache:
                self.depositer.deposit(self.images_to_cache[0])

            await asyncio.sleep(60)

    def talk(self):
        return {
            "name": self.name,
            "label": self.label,
            "label_exists": self.checker.label_exists,
            "common_cache": list(self.checker.common_cache),
            "desired_cache": list(self.desired_cache),
            "images_to_cache": self.images_to_cache,
        }
