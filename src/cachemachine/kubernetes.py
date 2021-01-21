from pathlib import Path
from typing import Dict, List

import structlog
from kubernetes.client import (
    AppsV1Api,
    V1Container,
    V1DaemonSet,
    V1DaemonSetSpec,
    V1LocalObjectReference,
    V1Node,
    V1ObjectMeta,
    V1PodSpec,
    V1PodTemplateSpec,
)
from kubernetes.client.api import core_v1_api
from kubernetes.client.exceptions import ApiException

from cachemachine.types import KubernetesDaemonsetNotFound

NAMESPACE_FILE = "/var/run/secrets/kubernetes.io/serviceaccount/namespace"

logger = structlog.get_logger(__name__)


class KubernetesClient:
    def __init__(self) -> None:
        self.namespace = Path(NAMESPACE_FILE).read_text().strip()
        self.core_api = core_v1_api.CoreV1Api()
        self.apps_api = AppsV1Api()

    def list_nodes(self) -> List[V1Node]:
        return self.core_api.list_node().items

    def daemonset_create(
        self,
        name: str,
        image_url: str,
        pull_secret_name: str,
        labels: Dict[str, str],
    ) -> None:
        # Make a container that just sits for 1200 seconds.  The time is
        # arbitrary, but long enough for us to clean it up before it
        # restarts.  Sadly with a DaemonSet, you can't set the restart
        # policy to anything but Always, so if this container exits right
        # away, it will just be restarted.
        container = V1Container(
            name="cachemachine",
            image=image_url,
            command=["/bin/sh", "-c", "sleep 1200"],
        )

        if pull_secret_name:
            pull_secret = [V1LocalObjectReference(name=pull_secret_name)]
        else:
            pull_secret = []

        template = V1PodTemplateSpec(
            metadata=V1ObjectMeta(labels={"app": name}),
            spec=V1PodSpec(
                containers=[container],
                image_pull_secrets=pull_secret,
                node_selector=labels,
            ),
        )

        spec = V1DaemonSetSpec(
            template=template,
            selector={"matchLabels": {"app": name}},
        )

        ds = V1DaemonSet(metadata=V1ObjectMeta(name=name), spec=spec)

        self.apps_api.create_namespaced_daemon_set(self.namespace, ds)

    def daemonset_delete(self, name: str) -> None:
        try:
            logger.info(f"Deleting daemonset {name}")
            status = self.apps_api.delete_namespaced_daemon_set(
                name, self.namespace
            )
            logger.debug(f"Daemonset {name} deleted: {status}")
        except ApiException:
            logger.exception("Exception deleting daemonset")
            raise

    def daemonset_finished(self, name: str) -> bool:
        try:
            logger.info(f"Checking on status for {name}")
            ds_status = self.apps_api.read_namespaced_daemon_set_status(
                name, self.namespace
            )

            image_url = ds_status.spec.template.spec.containers[0].image
            desired = ds_status.status.desired_number_scheduled
            done = ds_status.status.number_available
            logger.debug(f"{image_url}: {desired} / {done}")

            return desired == done
        except ApiException as e:
            if e.status == 404:
                raise KubernetesDaemonsetNotFound()
            logger.exception(f"Exception checking on daemonset {name}")
            raise
