"""Manager for all the tellers and their cache deposits."""

__all__ = [
    "AutomatedTellerManager",
]

from dataclasses import dataclass, field
from typing import Dict, List

from aiohttp import web
from aiojobs import Scheduler, create_scheduler
from aiojobs._job import Job

from cachemachine.automatedteller import AutomatedTeller


@dataclass
class AutomatedTellerManager:
    _tellers: Dict[str, AutomatedTeller] = field(default_factory=dict)
    _jobs: Dict[str, Job] = field(default_factory=dict)
    _scheduler: Scheduler = None

    async def init(self, app: web.Application) -> None:
        self._scheduler = await create_scheduler()

    async def cleanup(self, app: web.Application) -> None:
        await self._scheduler.close()

    def get_teller(self, name: str) -> AutomatedTeller:
        return self._tellers[name]

    def list_tellers(self) -> List[str]:
        return list(self._tellers.keys())

    async def manage_teller(self, teller: AutomatedTeller) -> None:
        await self.release_teller(teller.name)
        self._tellers[teller.name] = teller
        await self._scheduler.spawn(teller.do_work())

    async def release_teller(self, name: str) -> None:
        if name in self._jobs:
            j = self._jobs[name]
            j.close(timeout=0)
            del self._jobs[name]

        if name in self._tellers:
            del self._tellers[name]
