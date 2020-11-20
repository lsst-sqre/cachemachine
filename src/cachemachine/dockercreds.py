import base64
import json
from typing import Optional, Tuple

import structlog

logger = structlog.get_logger(__name__)


class DockerCreds:
    @staticmethod
    def lookup(registry_url: str) -> Tuple[Optional[str], Optional[str]]:
        try:
            with open("/etc/secrets/.dockerconfigjson") as f:
                credstore = json.loads(f.read())

                if registry_url not in credstore["auths"]:
                    logger.warning(f"No credentials found for {registry_url}")
                    return (None, None)

                b64auth = credstore["auths"][registry_url]["auth"]
                basic_auth = base64.b64decode(b64auth).decode()
                (username, password) = basic_auth.split(":")
                logger.debug(f"Found {registry_url}: {username}")
                return (username, password)
        except FileNotFoundError:
            logger.warning("Credentials file not found")
            return (None, None)
