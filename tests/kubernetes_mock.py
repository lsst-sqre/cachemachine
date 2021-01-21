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

        # if image_url not in self.data:
        #    raise Exception("Asking for URL that isn't in registry")

        self.daemonsets[name] = {
            "finished": False,
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

        assert image_url.startswith("lsstsqre/sciplat-lab")
        names = [image_url]
        self.nodes[0].status.images.append(V1ContainerImage(names=names))
        return True
