import base64
import json

import structlog

from cachemachine.types import DockerCredentials

logger = structlog.get_logger(__name__)


def lookup_docker_credentials(registry_url: str) -> DockerCredentials:
    try:
        with open("/etc/secrets/.dockerconfigjson") as f:
            credstore = json.loads(f.read())

            if registry_url not in credstore["auths"]:
                logger.warning(f"No credentials found for {registry_url}")
                return DockerCredentials()

            b64auth = credstore["auths"][registry_url]["auth"]
            basic_auth = base64.b64decode(b64auth).decode()
            (username, password) = basic_auth.split(":")
            logger.debug(f"Found {registry_url}: {username}")
            return DockerCredentials(username=username, password=password)
    except FileNotFoundError:
        logger.warning("Credentials file not found")
        return DockerCredentials()
