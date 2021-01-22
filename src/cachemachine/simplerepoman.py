"""Simple Repository Manager."""
from typing import Any, Dict, List

import structlog

from cachemachine.types import CachedDockerImage, DockerImageList, RepoMan

logger = structlog.get_logger(__name__)


class SimpleRepoMan(RepoMan):
    """Use a simple static list of images to cache."""

    def __init__(self, body: Dict[str, Any]):
        """Create a new SimpleRepoMan.

        Parameters
        ----------
        body: JSON body for the SimpleRepoMan.  Defined also in post.json
          Contains a JSON list of images that have an image_url and image_name
          field.
        """
        self._images = DockerImageList()
        self._images.load(body["images"])

    async def desired_images(
        self, common_cache: List[CachedDockerImage]
    ) -> DockerImageList:
        """Return the static list of desired images.

        Parameters
        ----------
        common_cache: unused.  The current cache of images on all nodes.

        Returns
        -------
        List of images to cache, which come directly from the JSON post body.
        """
        return self._images
