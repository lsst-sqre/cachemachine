from typing import Any, Dict, List

from kubernetes.client import (
    V1ContainerImage,
    V1Node,
    V1NodeStatus,
    V1ObjectMeta,
)

from cachemachine.types import KubernetesDaemonsetNotFound


class KubernetesMock:
    def __init__(self, data: Dict[str, str]) -> None:
        self.data = data
        self.daemonsets: Dict[str, Any] = {}

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
        return self.nodes

    def daemonset_create(
        self,
        name: str,
        image_url: str,
        pull_secret_name: str,
        labels: Dict[str, str],
    ) -> None:
        if name in self.daemonsets:
            raise Exception("Daemonset already exists")

        assert image_url.startswith("lsstsqre/sciplat-lab")
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
        del self.daemonsets[name]

    def daemonset_finished(self, name: str) -> bool:
        if name not in self.daemonsets:
            raise KubernetesDaemonsetNotFound()

        if not self.daemonsets[name]["finished"]:
            # It'll be done next time.
            self.daemonsets[name]["finished"] = True
            return False

        image_url = self.daemonsets[name]["image_url"]
        image_hash = self.daemonsets[name]["image_hash"]
        repository = self.daemonsets[name]["repository"]
        hash_url = f"{repository}@{image_hash}"

        for i in self.nodes[0].status.images:
            if image_url in i.names:
                return True

        self.nodes[0].status.images.append(
            V1ContainerImage(names=[image_url, hash_url])
        )
        return True
