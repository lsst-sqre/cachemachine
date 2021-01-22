"""Handlers for cachemachine's external root, /cachemachine/."""

__all__ = [
    "list_machines",
    "create_machine",
    "get_machine",
    "available_images",
    "stop_machine",
]

import json
from importlib import resources
from typing import List

from aiohttp import web
from jsonschema import validate

from cachemachine.cachemachine import CacheMachine
from cachemachine.handlers import routes
from cachemachine.rubinrepoman import RubinRepoMan
from cachemachine.simplerepoman import SimpleRepoMan
from cachemachine.types import (
    CacheMachineNotFoundError,
    KubernetesLabels,
    RepoMan,
)


@routes.get("/")
async def list_machines(request: web.Request) -> web.Response:
    """GET /cachemachine

    List the current names of all existing cachemachines.

    Returns a json list of the names as strings.
    """
    manager = request.config_dict["manager"]
    return web.json_response(manager.list())


@routes.post("/")
async def create_machine(request: web.Request) -> web.Response:
    """POST /cachemachine

    Create a new cachemachine with the details from the body.
    Schema for the body is validated against the post.json file.

    Returns the JSON of the newly created cachemachine.
    """
    body = await request.json()

    validate(
        instance=body,
        schema=json.loads(
            resources.read_text("cachemachine.schemas", "post.json")
        ),
    )

    name = body["name"]
    labels = KubernetesLabels(body["labels"])
    repomen: List[RepoMan] = []

    for r in body["repomen"]:
        if r["type"] == "SimpleRepoMan":
            repomen.append(SimpleRepoMan(r))
        elif r["type"] == "RubinRepoMan":
            repomen.append(RubinRepoMan(r))
        else:
            return web.HTTPBadRequest()

    cm = CacheMachine(name, labels, repomen)
    manager = request.config_dict["manager"]
    await manager.manage(cm)
    return web.json_response(cm.dump())


@routes.get("/{name}")
async def get_machine(request: web.Request) -> web.Response:
    """GET /cachemachine/{name}

    Get the details of the cachemachine of the given name.

    Returns the JSON of the requested cachemachine.
    """
    name = request.match_info["name"]
    manager = request.config_dict["manager"]

    try:
        cm = manager.get(name)
        return web.json_response(cm.dump())
    except CacheMachineNotFoundError:
        raise web.HTTPNotFound()


@routes.get("/{name}/available")
async def available_images(request: web.Request) -> web.Response:
    """GET /cachemachine/{name}/available

    Get the list of available Docker images that have been pulled
    to all the nodes the cachemachine is watching.

    Returns a JSON list of objects containing the image name and
    a friendly name to present to the user.
    """
    name = request.match_info["name"]
    manager = request.config_dict["manager"]

    try:
        cm = manager.get(name)
        return web.json_response(cm.available_images.dump())
    except CacheMachineNotFoundError:
        raise web.HTTPNotFound()


@routes.delete("/{name}")
async def stop_machine(request: web.Request) -> web.Response:
    """DELETE /cachemachine/{name}

    Stop the cachemachine with the given name.  This will stop
    the cachemachine from pulling images and stop all currently
    pulling daemonsets.
    """
    name = request.match_info["name"]
    manager = request.config_dict["manager"]
    await manager.release(name)
    return web.HTTPOk()
