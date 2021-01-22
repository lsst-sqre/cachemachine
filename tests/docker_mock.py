"""Mock Docker client."""

from typing import Dict, List


class DockerMock:
    """Mock Docker client that uses a dict for the registry entries."""

    def __init__(self, data: Dict[str, str]) -> None:
        """Create the mock, data is the registry.

        Keys of data are the tags.
        Values of data are the hash values to return."""
        self.data = data

    async def list_tags(self, authenticate: bool = True) -> List[str]:
        """Return a mock list of tags."""
        return list(self.data.keys())

    async def get_image_hash(self, tag: str, authenticate: bool = True) -> str:
        """Return the hash of a mocked image."""
        return self.data[tag]
