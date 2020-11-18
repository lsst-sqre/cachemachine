"""Handlers for the app's external root, ``/<app-name>/``."""

__all__ = ["get_tellers", "create_teller", "ask_teller", "stop_teller"]

from aiohttp import web

from cachemachine.automatedteller import AutomatedTeller
from cachemachine.handlers import routes
from cachemachine.rubinrepoman import RubinRepoMan
from cachemachine.simplerepoman import SimpleRepoMan


@routes.get("/")
async def get_tellers(request: web.Request) -> web.Response:
    manager = request.config_dict["automatedtellermanager"]
    return web.json_response(manager.list_tellers())


@routes.post("/")
async def create_teller(request: web.Request) -> web.Response:
    body = await request.json()
    name = body["name"]
    labels = body["labels"]
    repomen = []

    for r in body["repomen"]:
        if r["type"] == "SimpleRepoMan":
            repomen.append(SimpleRepoMan(r))
        elif r["type"] == "RubinRepoMan":
            repomen.append(RubinRepoMan(r))
        else:
            return web.HTTPBadRequest()

    teller = AutomatedTeller(name, labels, repomen)
    manager = request.config_dict["automatedtellermanager"]
    await manager.manage_teller(teller)
    return web.json_response(teller.talk())


@routes.get("/{name}")
async def ask_teller(request: web.Request) -> web.Response:
    name = request.match_info["name"]
    manager = request.config_dict["automatedtellermanager"]

    try:
        teller = manager.get_teller(name)
        return web.json_response(teller.talk())
    except KeyError:
        raise web.HTTPNotFound()


@routes.get("/{name}/available")
async def available_images(request: web.Request) -> web.Response:
    name = request.match_info["name"]
    manager = request.config_dict["automatedtellermanager"]

    try:
        teller = manager.get_teller(name)
        return web.json_response(teller.available_images)
    except KeyError:
        raise web.HTTPNotFound()


@routes.delete("/{name}")
async def stop_teller(request: web.Request) -> web.Response:
    name = request.match_info["name"]
    manager = request.config_dict["automatedtellermanager"]
    await manager.release_teller(name)
    return web.HTTPOk()
