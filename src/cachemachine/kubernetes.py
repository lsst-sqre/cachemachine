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
    V1OwnerReference,
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
            image_pull_policy="Always",
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

        # Copy annotations of this cachemachine pod (running this code),
        # down to sub items it will create.
        ds_annotations = self._read_current_pod_info("annotations")

        # The labels on the daemonset and its pods should be a combination
        # of the labels running on the cachemachine pod (running this code),
        # and a bit of extra sauce.
        ds_labels = self._read_current_pod_info("labels")

        # The pod cachemachine label is used to apply a NetworkPolicy.
        ds_labels["cachemachine"] = "pull"

        # This ties the pods to a particular cachemachine puller, so we could
        # run and track multiple at the same time.  This matches the selector
        # on the daemonset.
        ds_labels["app"] = name

        template = V1PodTemplateSpec(
            metadata=V1ObjectMeta(
                annotations=ds_annotations,
                labels=ds_labels,
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

        ds = V1DaemonSet(
            metadata=V1ObjectMeta(
                annotations=ds_annotations,
                name=name,
                labels=ds_labels,
                owner_references=[
                    V1OwnerReference(
                        api_version="v1",
                        kind="Pod",
                        name=self._read_pod_info("name"),
                        uid=self._read_pod_info("uid"),
                    ),
                ],
            ),
            spec=V1DaemonSetSpec(
                template=template,
                selector={"matchLabels": {"app": name}},
            ),
        )

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

    def _read_pod_info(self, filename: str) -> str:
        """Read the file containing some information about our current pod.

        This data is provided as files mounted into the container by
        kubernetes.

        Parameters
        ----------
        filename: filename to read in /etc/podinfo.  The list is
          available in the helm chart.

        Returns
        -------
        Contents of that file."""
        return Path("/etc/podinfo/", filename).read_text()

    def _read_current_pod_info(self, info_type: str) -> Dict[str, str]:
        """Load kubernetes downward API information about our pod.

        This data is provided as files mounted into the container
        by kubernetes.

        Parameters
        ----------
        info_type: Either labels or annotations

        Returns
        -------
        A dict containing the information in a way that kubernetes
        can create it as a set of labels or annotations.
        """
        info = {}
        # Format is k="v"
        # Who knows why it quotes the value.
        # Quotes aren't allowed in labels or annotations.
        for line in self._read_pod_info(info_type).splitlines():
            (k, v) = line.replace('"', "").split("=", 1)
            info[k] = v

        return info
