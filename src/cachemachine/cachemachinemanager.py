"""Manager for all the cachemachines."""

__all__ = [
    "CacheMachineManager",
]

import json
from pathlib import Path
from typing import Any, Dict, List

import structlog
from aiohttp import web
from aiojobs import create_scheduler
from aiojobs._job import Job

from cachemachine.cachemachine import CacheMachine
from cachemachine.rubinrepogar import RubinRepoGar
from cachemachine.rubinrepoman import RubinRepoMan
from cachemachine.simplerepoman import SimpleRepoMan
from cachemachine.types import (
    CacheMachineNotFoundError,
    KubernetesLabels,
    RepoMan,
    RepoManTypeNotFoundError,
)

logger = structlog.get_logger(__name__)


class CacheMachineManager:
    """Manager of CacheMachines.

    Manages the existence and running of individual cachemachines."""

    async def init(self, app: web.Application) -> None:
        """Create CacheMachineManager.

        Called from the aiohttp server startup hook only.

        Parameters
        ----------
        app: unused.  Associated application instance.
        """
        self._scheduler = await create_scheduler()
        self._jobs: Dict[str, Job] = {}
        self._machines: Dict[str, CacheMachine] = {}

        try:
            for p in Path("/etc/cachemachine").iterdir():
                if p.is_file():
                    logger.info(f"Automatically creating from file: {p}")
                    await self.create(json.loads(p.read_text()))
        except FileNotFoundError:
            logger.info("No automatic cachemachines found.")

    async def cleanup(self, app: web.Application) -> None:
        """Cleanup CacheMachineManager.

        Called from the aiohttp server cleanup hook only.

        Note: By closing the scheduler, that will clean up all the
        jobs running inside of it.

        Parameters
        ----------
        app: unused.  Associated application instance."""
        await self._scheduler.close()

    def get(self, name: str) -> CacheMachine:
        """Retrieve cachemachine of the given name."""
        try:
            return self._machines[name]
        except KeyError:
            raise CacheMachineNotFoundError()

    def list(self) -> List[str]:
        """List all names of all the cachemachines."""
        return list(self._machines.keys())

    async def create(self, body: Dict[str, Any]) -> CacheMachine:
        """Begin managing this cachemachine."""
        name = body["name"]
        labels = KubernetesLabels(body["labels"])
        repomen: List[RepoMan] = []

        for r in body["repomen"]:
            if r["type"] == "SimpleRepoMan":
                repomen.append(SimpleRepoMan(r))
            elif r["type"] == "RubinRepoMan":
                repomen.append(RubinRepoMan(r))
            elif r["type"] == "RubinRepoGar":
                repomen.append(RubinRepoGar(r))
            else:
                raise RepoManTypeNotFoundError(r["type"])

        # Delete anything previously named the same thing.
        await self.release(name)

        # Start the new one.
        cm = CacheMachine(name, labels, repomen)
        self._machines[name] = cm
        await self._scheduler.spawn(cm.do_work())
        return cm

    async def release(self, name: str) -> None:
        """Stop managing the cachemachine of this name."""
        if name in self._jobs:
            j = self._jobs[name]
            j.close(timeout=0)
            del self._jobs[name]

        if name in self._machines:
            del self._machines[name]
