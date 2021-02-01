"""Mock Kubernetes client."""
from typing import Any, Dict, List

from kubernetes.client import (
    V1ContainerImage,
    V1Node,
    V1NodeStatus,
    V1ObjectMeta,
)

from cachemachine.types import KubernetesDaemonsetNotFound


class KubernetesMock:
    """Mock Kubernetes client that pretends to be a cluster."""

    def __init__(self, data: Dict[str, str]) -> None:
        """Create a mock kubernetes cluster.

        data is the mock registry data to ensure images exist
        and to choose tags."""
        self.data = data
        self.daemonsets: Dict[str, Any] = {}

        # Create two nodes in our pretend cluster.  One we will
        # pull to, and one we won't.  This uses the python kubernetes
        # objects to look like what the client returns.
        n1 = V1Node(
            metadata=V1ObjectMeta(name="n1", labels={"k1": "v1"}),
            status=V1NodeStatus(
                images=[V1ContainerImage(names=["<none>@<none>"])]
            ),
        )
        n2 = V1Node(
            metadata=V1ObjectMeta(name="n2", labels={"k2": "v2"}),
            status=V1NodeStatus(
                images=[V1ContainerImage(names=["<none>@<none>"])]
            ),
        )

        self.nodes = [n1, n2]

    def list_nodes(self) -> List[V1Node]:
        """Return the current status of all nodes."""
        return self.nodes

    def daemonset_create(
        self,
        name: str,
        image_url: str,
        pull_secret_name: str,
        labels: Dict[str, str],
    ) -> None:
        """Mock out creating a daemonset.

        This keeps track of the parameters in a dict called daemonsets.
        Once the status is checked on twice, the images will be considered
        pulled by the nodes.

        Parameters
        ----------
        name: name of the daemonset in kubernetes.  Must be unique.
        image_url: docker image for the containers of the daemonset.
        pull_secret_name: unused.  Used by kubernetes to auth to docker.
        labels: Labels to restrict where the daemonsets spawn.
        """
        if name in self.daemonsets:
            raise Exception("Daemonset already exists")

        assert image_url.startswith(
            "registry.hub.docker.com/lsstsqre/sciplat-lab"
        )
        (repository, tag) = image_url.split(":", 2)
        if tag not in self.data:
            raise Exception("Asking for a tag that isn't in the registry")

        self.daemonsets[name] = {
            "finished": False,
            "tag": tag,
            "repository": repository,
            "image_hash": self.data[tag],
            "image_url": image_url,
            "labels": labels,
        }

    def daemonset_delete(self, name: str) -> None:
        """Delete a mock daemonset with the given name."""
        del self.daemonsets[name]

    def daemonset_finished(self, name: str) -> bool:
        """Check the status of a daemonset with the given name.

        On the first check, we set a flag.
        On the second check, we insert the image into the caches
        where the node labels match what was provided to create
        the daemonset.

        Returns
        -------
        True: if the daemonset is finished pulling and running.
        False: the daemonset is still starting and pulling images.
        """
        if name not in self.daemonsets:
            raise KubernetesDaemonsetNotFound()

        if not self.daemonsets[name]["finished"]:
            # It'll be done next time.
            self.daemonsets[name]["finished"] = True
            return False

        image_url = self.daemonsets[name]["image_url"]
        image_hash = self.daemonsets[name]["image_hash"]
        repository = self.daemonsets[name]["repository"]
        labels = self.daemonsets[name]["labels"]
        hash_url = f"{repository}@{image_hash}"

        for n in self.nodes:
            if labels.matches(n.metadata.labels):
                already_pulled = False
                for i in n.status.images:
                    if image_url in i.names:
                        already_pulled = True

                if not already_pulled:
                    n.status.images.append(
                        V1ContainerImage(names=[image_url, hash_url])
                    )

        return True
