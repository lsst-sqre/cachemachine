"""Tests for the cachemachine.SimpleRepoMan class.

Pretty much just a container, but shows the interface.
"""

from __future__ import annotations

from typing import List

from cachemachine.simplerepoman import SimpleRepoMan
from cachemachine.types import CachedDockerImage


def test_simplerepoman() -> None:
    """Test SimpleRepoMan, a simple way to pull an image."""

    body = {
        "images": [
            {
                "image_url": "lsstsqre/sciplat-lab:recommended",
                "name": "Recommended",
            },
        ]
    }

    common_cache: List[CachedDockerImage] = []

    r = SimpleRepoMan(body)
    di = r.desired_images(common_cache)
    assert len(di) == 1
    assert di[0].image_url == "lsstsqre/sciplat-lab:recommended"
    assert di[0].name == "Recommended"
