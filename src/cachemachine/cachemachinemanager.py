"""Manager for all the cachemachines."""

__all__ = [
    "CacheMachineManager",
]

from typing import Dict, List

from aiohttp import web
from aiojobs import create_scheduler
from aiojobs._job import Job

from cachemachine.cachemachine import CacheMachine
from cachemachine.types import CacheMachineNotFoundError


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

    async def manage(self, cm: CacheMachine) -> None:
        """Begin managing this cachemachine."""
        await self.release(cm.name)
        self._machines[cm.name] = cm
        await self._scheduler.spawn(cm.do_work())

    async def release(self, name: str) -> None:
        """Stop managing the cachemachine of this name."""
        if name in self._jobs:
            j = self._jobs[name]
            j.close(timeout=0)
            del self._jobs[name]

        if name in self._machines:
            del self._machines[name]
