"""Externally-accessible endpoint handlers that serve relative to
/cachemachine/.
"""

__all__ = [
    "list_machines",
    "create_machine",
    "get_machine",
    "available_images",
    "stop_machine",
]

from cachemachine.handlers.external.cache import (
    available_images,
    create_machine,
    get_machine,
    list_machines,
    stop_machine,
)
