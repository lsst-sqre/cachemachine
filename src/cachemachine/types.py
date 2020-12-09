from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Set


class RepoMan(ABC):
    @abstractmethod
    def desired_images(
        self, recommended_names: Set[str]
    ) -> List[Dict[str, str]]:
        pass

    @abstractmethod
    def recommended_image_url(self) -> Optional[str]:
        pass
