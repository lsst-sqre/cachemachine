"""Client for accessing Docker v2 registry using aiohttp."""

import base64
import json
from typing import List

import structlog
from aiohttp import BasicAuth, ClientResponse, ClientSession

from cachemachine.types import DockerRegistryError

logger = structlog.get_logger(__name__)


class DockerClient:
    """Simple client for querying Docker registry."""

    def __init__(self, registry_host: str, repository: str) -> None:
        """Create a new Docker Client.

        Parameters
        ----------
        registry_host: host to contact for registry.
        repository: name of the docker repository to query,
          ex: lsstsqre/sciplat-lab
        """
        self.url = registry_host
        self.repository = repository
        self.session = ClientSession()
        self.headers = {
            "Accept": "application/vnd.docker.distribution.manifest.v2+json"
        }
        self._lookup_credentials()

    async def list_tags(self, authenticate: bool = True) -> List[str]:
        """List all the tags.

        Lists all the tags for the repository this client is used with.

        Parameters
        ----------
        authenticate: should we try and authenticate?  Used internally
          for retrying after successful authentication.
        """
        url = f"https://{self.url}/v2/{self.repository}/tags/list"
        async with self.session.get(url, headers=self.headers) as r:
            logger.debug(f"List tags response: {r}")
            if r.status == 200:
                body = await r.json()
                logger.debug(body)
                return body["tags"]
            elif r.status == 401 and authenticate:
                await self._authenticate(r)
                return await self.list_tags(authenticate=False)
            else:
                raise DockerRegistryError(f"Unknown error listing tags {r}")

    async def get_image_hash(self, tag: str, authenticate: bool = True) -> str:
        """Get the hash of a tag.

        Get the associated image hash of a Docker tag.

        Parameters
        ----------
        tag: the tag to inspect
        authenticate: should we try and authenticate?  Used internally
          for retrying after successful authentication.

        Returns the hash as a string, such as "sha256:abcdef"
        """
        url = f"https://{self.url}/v2/{self.repository}/manifests/{tag}"
        async with self.session.head(url, headers=self.headers) as r:
            logger.debug(f"Get image hash response: {r}")
            if r.status == 200:
                return r.headers["Docker-Content-Digest"]
            elif r.status == 401 and authenticate:
                await self._authenticate(r)
                return await self.get_image_hash(tag, authenticate=False)
            else:
                raise DockerRegistryError(f"Unknown error retrieving hash {r}")

    async def _authenticate(self, response: ClientResponse) -> None:
        """Internal method to authenticate after getting an auth challenge.

        Doesn't return anything but will set additional headers for future
        requests.

        Parameters
        ----------
        response: response that contains an auth challenge.
        """
        logger.debug(type(response))
        logger.debug(f"Authenticating {response}")

        challenge = response.headers.get(
            "WWW-Authenticate", response.headers.get("Www-Authenticate")
        )

        if not challenge:
            raise DockerRegistryError("No authentication challenge")

        (challenge_type, params) = challenge.split(" ", 1)
        challenge_type = challenge_type.lower()

        if challenge_type == "basic":
            # Basic auth is used by the Nexus Docker Registry.
            if not self.username or not self.password:
                msg = f"No password for basic auth for {self.url}"
                raise DockerRegistryError(msg)

            self.headers["Authorization"] = BasicAuth(
                self.username, password=self.password
            ).encode()
            logger.debug(f"Auth header is {self.headers}")
            logger.info("Authenticated with basic auth")
        elif challenge_type == "bearer":
            # Bearer is used by Docker's official registry.
            parts = {}
            for p in params.split(","):
                logger.debug(p)
                (k, v) = p.split("=")
                parts[k] = v.replace('"', "")

            url = parts["realm"]
            auth = None

            if self.username and self.password:
                auth = BasicAuth(self.username, password=self.password)

            async with self.session.get(url, auth=auth, params=parts) as r:
                if r.status == 200:
                    body = await r.json()
                    token = body["token"]
                    self.headers["Authorization"] = f"Bearer {token}"
                    logger.info("Authenticated with bearer token")
                else:
                    raise DockerRegistryError(f"Error getting token {r}")
        else:
            raise DockerRegistryError(
                f"Unknown authentication challenge {challenge}"
            )

    def _lookup_credentials(self) -> None:
        """Find credentials for the current client.

        Using the repository host, look for an entry in the dockerconfig
        that contains a username and password for authenticating.
        """
        self.username = None
        self.password = None

        try:
            logger.debug("Parsing /etc/secrets/.dockerconfigjson")
            with open("/etc/secrets/.dockerconfigjson") as f:
                credstore = json.loads(f.read())
                logger.debug(f"Found data: {credstore}")

                if self.url in credstore["auths"]:
                    b64auth = credstore["auths"][self.url]["auth"]
                    basic_auth = base64.b64decode(b64auth).decode()
                    (self.username, self.password) = basic_auth.split(":", 1)
                    logger.debug(f"Found {self.url}: {self.username}")
        except FileNotFoundError:
            pass
