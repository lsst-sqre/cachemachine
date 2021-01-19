from typing import Dict, List


class DockerMock:
    def __init__(self, data: Dict[str, str]) -> None:
        self.data = data

    async def list_tags(self, authenticate: bool = True) -> List[str]:
        return list(self.data.keys())

    async def get_image_hash(self, tag: str, authenticate: bool = True) -> str:
        return self.data[tag]
