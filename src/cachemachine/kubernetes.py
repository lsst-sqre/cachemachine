"""Kubernetes client abstraction for cachemachine."""

from pathlib import Path
from typing import Dict, List

import structlog
from kubernetes.client import (
    AppsV1Api,
    V1Capabilities,
    V1Container,
    V1DaemonSet,
    V1DaemonSetSpec,
    V1LocalObjectReference,
    V1Node,
    V1ObjectMeta,
    V1PodSecurityContext,
    V1PodSpec,
    V1PodTemplateSpec,
    V1SecurityContext,
)
from kubernetes.client.api import core_v1_api
from kubernetes.client.exceptions import ApiException

from cachemachine.types import KubernetesDaemonsetNotFound

NAMESPACE_FILE = "/var/run/secrets/kubernetes.io/serviceaccount/namespace"

logger = structlog.get_logger(__name__)


class KubernetesClient:
    """A client for cachemachine's usage of Kubernetes.

    This provides a level of abstraction away from the python-kubernetes
    objects and models.  By hiding these obscure objects here it makes
    the code easier to mock and test.
    """

    def __init__(self) -> None:
        """Create a new client for the cluster we are running in."""
        self.namespace = Path(NAMESPACE_FILE).read_text().strip()
        self.core_api = core_v1_api.CoreV1Api()
        self.apps_api = AppsV1Api()

    def list_nodes(self) -> List[V1Node]:
        """List all the nodes in the Kubernetes cluster.

        This contains a complex object hierarchy which contains
        information about the node, including its Docker image
        cache.
        """
        return self.core_api.list_node().items

    def daemonset_create(
        self,
        name: str,
        image_url: str,
        pull_secret_name: str,
        labels: Dict[str, str],
    ) -> None:
        """Create a new Kubernetes daemonset.

        Parameters
        ----------
        name: Name of the daemonset.  This filters down to the pods
          created and the name to use to find this in kubectl.
        image_url: URL of the docker image to pull for this daemonset.
        pull_secret_name: Name of the Kubernetes secret to use while pulling
          this image.  This allows for Kubernetes to authenticate while
          pulling.
        labels: Kubernetes label restriction for which nodes the daemonset's
          pods should run on.
        """
        # Make a container that just sits for 1200 seconds.  The time is
        # arbitrary, but long enough for us to clean it up before it
        # restarts.  Sadly with a DaemonSet, you can't set the restart
        # policy to anything but Always, so if this container exits right
        # away, it will just be restarted.
        container = V1Container(
            name="cachemachine",
            image=image_url,
            command=["/bin/sh", "-c", "sleep 1200"],
            security_context=V1SecurityContext(
                allow_privilege_escalation=False,
                capabilities=V1Capabilities(drop=["ALL"]),
                read_only_root_filesystem=True,
            ),
        )

        if pull_secret_name:
            pull_secret = [V1LocalObjectReference(name=pull_secret_name)]
        else:
            pull_secret = []

        # The pod cachemachine label is used to apply a NetworkPolicy.
        template = V1PodTemplateSpec(
            metadata=V1ObjectMeta(
                labels={"app": name, "cachemachine": "pull"}
            ),
            spec=V1PodSpec(
                automount_service_account_token=False,
                containers=[container],
                image_pull_secrets=pull_secret,
                node_selector=labels,
                security_context=V1PodSecurityContext(
                    run_as_non_root=True,
                    run_as_group=1000,
                    run_as_user=1000,
                ),
            ),
        )

        spec = V1DaemonSetSpec(
            template=template,
            selector={"matchLabels": {"app": name}},
        )

        ds = V1DaemonSet(metadata=V1ObjectMeta(name=name), spec=spec)

        self.apps_api.create_namespaced_daemon_set(self.namespace, ds)

    def daemonset_delete(self, name: str) -> None:
        """Delete the daemonset of the given name."""
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
        """Check if the daemonset of the given name is finished pulling.

        Parameters
        ----------
        name: Name of the daemonset to check on.

        Returns
        -------
        True: if the daemonset has pulled the images on all nodes,
          and is running.
        False: if the daemonset is still pulling on at least one node.
        """
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
