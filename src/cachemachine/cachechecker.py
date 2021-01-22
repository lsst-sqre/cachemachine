from typing import Dict

import structlog

from cachemachine.kubernetes import KubernetesClient
from cachemachine.types import CachedDockerImage, DockerImageList

logger = structlog.get_logger(__name__)


class CacheChecker:
    def __init__(self, labels: Dict[str, str]):
        self.labels = labels
        self.common_cache = DockerImageList()
        self.kubernetes = KubernetesClient()

    def check(self) -> None:
        nodes = self.kubernetes.list_nodes()
        logger.debug(f"Inspecting {nodes}")

        first_node = True
        common_cache = DockerImageList()

        for n in nodes:
            logger.debug(f"{n.metadata.name} labels: {n.metadata.labels}")

            # Do the labels we are looking for match this node?
            if self.labels.items() <= n.metadata.labels.items():
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
