from typing import Any, Dict

from cachemachine.rubinimageinfo import RubinImageInfo
from cachemachine.rubinrepoman import RubinRepoMan


class SALCycleRepoMan(RubinRepoMan):
    def __init__(self, body: Dict[str, Any]):
        """Create a new SALCycleRepoMan.  It's the same as the parent except
        that the body passed to it may have an additional parameter 'cycle'

        body:
            cycle: Which XML Cycle to allow.  If specified, filter out
                   any images that don't have a matching cycle tag.
        """
        super().__init__(body)
        self.cycle = body.get("cycle", None)

    def _allow_image(self, img: RubinImageInfo) -> bool:
        """If self.cycle was defined at instance creation, only allow images
        whose cycle matches."""
        if not self.cycle:
            return True
        return img.cycle == self.cycle
