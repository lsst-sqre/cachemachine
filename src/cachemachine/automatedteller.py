import asyncio
from typing import Any, Dict, List, Sequence

import structlog

from cachemachine.cachechecker import CacheChecker
from cachemachine.cachedepositer import CacheDepositer
from cachemachine.types import RepoMan

logger = structlog.get_logger(__name__)


class AutomatedTeller:
    def __init__(
        self,
        name: str,
        labels: Dict[str, str],
        repomen: Sequence[RepoMan],
    ):
        self.available_images: List[Dict[str, str]]
        self.desired_images: List[Dict[str, str]]
        self.images_to_cache: List[Dict[str, str]]

        self.name = name
        self.labels = labels
        self.repomen = repomen

        self.recommended_image_urls = [
            url
            for r in self.repomen
            # Use a walrus and store what is returned by recommended_image_url
            # so that we can compare against that to help the typing.
            # Otherwise mypy has trouble figuring out that None isn't valid
            # in this list.
            if (url := r.recommended_image_url()) is not None
        ]

        self.checker = CacheChecker(self.labels, self.recommended_image_urls)
        self.depositer = CacheDepositer(self.name, self.labels)

    # Note, doesn't actually return, intended to run forever.
    async def do_work(self) -> None:
        while True:
            self.available_images = []
            self.desired_images = []
            self.images_to_cache = []

            self.checker.check()

            if not self.checker.nodes_exist:
                logger.warning(f"No nodes are labeled with: {self.labels}")
            else:
                for r in self.repomen:
                    recommended_image_url = r.recommended_image_url()
                    if recommended_image_url:
                        recommended_names = self.checker.recommended_names[
                            recommended_image_url
                        ]
                    else:
                        recommended_names = set()

                    for image in r.desired_images(recommended_names):
                        self.desired_images.append(image)

                        if image["image_url"] in self.checker.common_cache:
                            self.available_images.append(image)
                        else:
                            self.images_to_cache.append(image)

            if self.images_to_cache and not self.depositer.busy():
                self.depositer.deposit(self.images_to_cache[0]["image_url"])

            await asyncio.sleep(60)

    def talk(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "labels": self.labels,
            "nodes_exist": self.checker.nodes_exist,
            "common_cache": list(self.checker.common_cache),
            "available_images": self.available_images,
            "desired_images": self.desired_images,
            "images_to_cache": self.images_to_cache,
        }
