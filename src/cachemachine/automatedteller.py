import asyncio
from typing import Any, Dict, Sequence

import structlog

from cachemachine.cachechecker import CacheChecker
from cachemachine.config import Configuration
from cachemachine.kubernetes import KubernetesClient
from cachemachine.types import (
    DockerImageList,
    KubernetesDaemonsetNotFound,
    KubernetesLabels,
    RepoMan,
)

logger = structlog.get_logger(__name__)


async def _wait() -> None:
    await asyncio.sleep(60)


class AutomatedTeller:
    def __init__(
        self,
        name: str,
        labels: KubernetesLabels,
        repomen: Sequence[RepoMan],
    ):
        self.available_images = DockerImageList()
        self.desired_images = DockerImageList()
        self.images_to_cache = DockerImageList()

        self.name = name
        self.labels = labels
        self.repomen = repomen

        self.kubernetes = KubernetesClient()
        self.checker = CacheChecker(self.labels)

    # Note, doesn't actually return, intended to run forever.
    async def do_work(self) -> None:
        while True:
            try:
                available_images = DockerImageList()
                desired_images = DockerImageList()
                images_to_cache = DockerImageList()

                self.checker.check()

                for r in self.repomen:
                    for image in await r.desired_images(
                        self.checker.common_cache
                    ):
                        desired_images.append(image)

                        available = False
                        for i in self.checker.common_cache:
                            if i.image_url == image.image_url and (
                                image.image_hash is None
                                or i.image_hash == image.image_hash
                            ):
                                available_images.append(image)
                                available = True

                        if not available:
                            images_to_cache.append(image)

                if images_to_cache and not self.caching():
                    self.start_caching(images_to_cache[0].image_url)

                self.available_images = available_images
                self.desired_images = desired_images
                self.images_to_cache = images_to_cache
            except Exception:
                logger.exception("Exception caching images")

            await _wait()

    def start_caching(self, image_url: str) -> None:
        self.kubernetes.daemonset_create(
            self.name,
            image_url,
            Configuration().docker_secret_name,
            self.labels,
        )

    def caching(self) -> bool:
        try:
            finished = self.kubernetes.daemonset_finished(self.name)
            if finished:
                self.kubernetes.daemonset_delete(self.name)
                return False
            else:
                return True
        except KubernetesDaemonsetNotFound:
            return False

    def talk(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "labels": self.labels,
            "common_cache": self.checker.common_cache.dump(),
            "available_images": self.available_images.dump(),
            "desired_images": self.desired_images.dump(),
            "images_to_cache": self.images_to_cache.dump(),
        }
