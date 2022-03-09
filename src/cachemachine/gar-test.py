import asyncio
from typing import List

from cachemachine.rubinrepogar import RubinRepoGar
from cachemachine.types import CachedDockerImage


async def main():

    body = {
        "project_id": "rubin-shared-services-71ec",
        "location": "us-central1",
        "gar_repository": "sciplat",
        "registry_url": "",
        "num_releases": 1,
        "num_weeklies": 1,
        "num_dailies": 1,
        "cycle": None,
        # "alias_tags": [
        #    "recommended",
        #    "latest",
        #    "latest_daily",
        #    "latest_weekly"
        # ],
        "recommended_tag": "recommended",
    }

    common_cache: List[CachedDockerImage] = []
    # common_cache = DockerImageList()

    r = RubinRepoGar(body)
    desired_images = await r.desired_images(common_cache)
    di = desired_images.desired_images

    print(di[0].image_url)
    # print(di[1].name)
    print(di[1].image_url)
    # print(f'name 1 is {di[1].name}')
    print(di[2].image_url)
    print(di[3].image_url)


asyncio.run(main())
