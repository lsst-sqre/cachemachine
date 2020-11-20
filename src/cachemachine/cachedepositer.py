from typing import Dict

import structlog
from kubernetes.client import (
    AppsV1Api,
    V1Container,
    V1DaemonSet,
    V1DaemonSetSpec,
    V1LocalObjectReference,
    V1ObjectMeta,
    V1PodSpec,
    V1PodTemplateSpec,
)
from kubernetes.client.exceptions import ApiException

from cachemachine.config import Configuration

logger = structlog.get_logger(__name__)


class CacheDepositer:
    def __init__(self, name: str, labels: Dict[str, str]):
        self.name = name
        self.labels = labels
        self.api = AppsV1Api()
        self.namespace = self._get_namespace()

    def deposit(self, image_url: str) -> None:
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

        pull_secret_name = Configuration().docker_secret_name
        if pull_secret_name:
            pull_secret = [V1LocalObjectReference(name=pull_secret_name)]
        else:
            pull_secret = []

        template = V1PodTemplateSpec(
            metadata=V1ObjectMeta(labels={"app": self.name}),
            spec=V1PodSpec(
                containers=[container],
                image_pull_secrets=pull_secret,
                node_selector=self.labels,
            ),
        )

        spec = V1DaemonSetSpec(
            template=template,
            selector={"matchLabels": {"app": self.name}},
        )

        ds = V1DaemonSet(metadata=V1ObjectMeta(name=self.name), spec=spec)

        self.api.create_namespaced_daemon_set(self.namespace, ds)

    def busy(self) -> bool:
        try:
            logger.info(f"Checking on status for {self.name}")
            ds_status = self.api.read_namespaced_daemon_set_status(
                self.name, self.namespace
            )
        except ApiException as e:
            if e.status == 404:
                logger.info("Daemonset not found")
                return False
            logger.exception(
                f"Exception checking on status of daemonset {self.name}"
            )
            raise

        image_url = ds_status.spec.template.spec.containers[0].image
        desired = ds_status.status.desired_number_scheduled
        done = ds_status.status.number_available
        logger.info(f"{image_url}: {desired} / {done}")

        if desired != done:
            return True

        self._cleanup()
        return False

    def _cleanup(self) -> None:
        try:
            logger.info(f"Deleting daemonset {self.name}")
            status = self.api.delete_namespaced_daemon_set(
                self.name, self.namespace
            )
            logger.debug(f"Daemonset {self.name} deleted: {status}")
        except ApiException:
            logger.exception("Exception deleting daemonset")
            raise

    def _get_namespace(self) -> str:
        ns_file = "/var/run/secrets/kubernetes.io/serviceaccount/namespace"

        with open(ns_file) as f:
            return f.read().strip()
