from typing import Dict, List

import structlog
from kubernetes.client.api import core_v1_api

from cachemachine.types import CachedDockerImage

logger = structlog.get_logger(__name__)


class CacheChecker:
    def __init__(self, labels: Dict[str, str]):
        self.api = core_v1_api.CoreV1Api()
        self.labels = labels
        self.common_cache: List[CachedDockerImage] = []

    def check(self) -> None:
        nodes = self.api.list_node().items
        logger.debug(f"Inspecting {nodes}")

        first_node = True
        common_cache = []

        for n in nodes:
            logger.debug(f"{n.metadata.name} labels: {n.metadata.labels}")

            # Do the labels we are looking for match this node?
            if self.labels.items() <= n.metadata.labels.items():
                # This is a bit tricky.  The images is a list,
                # each item containing a particular image, and containing
                # a list of all the names it is known by.
                node_images = []
                for i in n.status.images:
                    tags = set()
                    for url in i.names:
                        # Each of these "names" can either be a docker image
                        # url that has a hash or a tag in it. (although, with
                        # where the @ sign is, I'm not sure if it really
                        # counts)
                        if url == "<none>@<none>" or url == "<none>:<none>":
                            pass
                        elif "@sha256:" in url:
                            (image_url, image_hash) = url.split("@sha256:")
                        else:
                            tags.add(url.split(":")[1])

                    node_images.append(
                        CachedDockerImage(
                            image_url=image_url,
                            image_hash=image_hash,
                            tags=tags,
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
                    new_common_cache = []

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
                                common_image.tags |= node_image.tags
                                new_common_cache.append(common_image)

                    common_cache = new_common_cache

        self.common_cache = common_cache
