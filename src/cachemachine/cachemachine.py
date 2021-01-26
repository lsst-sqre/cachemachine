import asyncio
from typing import Any, Dict, Sequence

import structlog

from cachemachine.config import Configuration
from cachemachine.kubernetes import KubernetesClient
from cachemachine.types import (
    CachedDockerImage,
    DockerImageList,
    KubernetesDaemonsetNotFound,
    KubernetesLabels,
    RepoMan,
)

logger = structlog.get_logger(__name__)


async def _wait() -> None:
    await asyncio.sleep(60)


class CacheMachine:
    def __init__(
        self,
        name: str,
        labels: KubernetesLabels,
        repomen: Sequence[RepoMan],
    ):
        self.available_images = DockerImageList()
        self.common_cache = DockerImageList()
        self.desired_images = DockerImageList()
        self.images_to_cache = DockerImageList()

        self.name = name
        self.labels = labels
        self.repomen = repomen

        self.kubernetes = KubernetesClient()

    # Note, doesn't actually return, intended to run forever.
    async def do_work(self) -> None:
        while True:
            try:
                available_images = DockerImageList()
                desired_images = DockerImageList()
                images_to_cache = DockerImageList()

                self.inspect_node_caches()

                for r in self.repomen:
                    for image in await r.desired_images(self.common_cache):
                        desired_images.append(image)

                        available = False
                        for i in self.common_cache:
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

    def inspect_node_caches(self) -> None:
        nodes = self.kubernetes.list_nodes()
        logger.debug(f"Inspecting {nodes}")

        first_node = True
        common_cache = DockerImageList()

        for n in nodes:
            logger.debug(f"{n.metadata.name} labels: {n.metadata.labels}")

            # Do the labels we are looking for match this node?
            if self.labels.matches(n.metadata.labels):
                # This is a bit tricky.  The images is a list,
                # each item containing a particular image, and containing
                # a list of all the names it is known by.
                node_images = DockerImageList()
                for i in n.status.images:
                    tags = []
                    repository = None
                    image_hash = None

                    for url in i.names:
                        # Each of these "names" can either be a docker image
                        # url that has a hash or a tag in it. (although, with
                        # where the @ sign is, I'm not sure if it really
                        # counts)
                        if url == "<none>@<none>" or url == "<none>:<none>":
                            pass
                        elif "@sha256:" in url:
                            (repository, image_hash) = url.split("@")
                        else:
                            new_tag = url.split(":")[1]
                            if new_tag not in tags:
                                tags.append(new_tag)

                    if repository and image_hash:
                        for t in tags:
                            other_tags = list(tags)
                            other_tags.remove(t)

                            node_images.append(
                                CachedDockerImage(
                                    image_url=f"{repository}:{t}",
                                    image_hash=image_hash,
                                    tags=other_tags,
                                )
                            )

                logger.debug(f"{n.metadata.name} images: {node_images}")

                if first_node:
                    # This is the first node we're looking at
                    common_cache = node_images
                    first_node = False
                else:
                    # Calculate what images are available on this node and all
                    # the previously inspected nodes.
                    new_common_cache = DockerImageList()

                    for common_image in common_cache:
                        for node_image in node_images:
                            if (
                                common_image.image_hash
                                == node_image.image_hash
                                and common_image.image_url
                                == node_image.image_url
                            ):
                                # If we find something that is the same hash,
                                # take the union of these tags.  It could be
                                # any of the tags found.
                                for t in node_image.tags:
                                    if t not in common_image.tags:
                                        common_image.tags.append(t)

                                new_common_cache.append(common_image)

                    common_cache = new_common_cache

        self.common_cache = common_cache

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

    def dump(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "labels": self.labels,
            "common_cache": self.common_cache.dump(),
            "available_images": self.available_images.dump(),
            "desired_images": self.desired_images.dump(),
            "images_to_cache": self.images_to_cache.dump(),
        }
