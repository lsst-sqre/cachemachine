import structlog
from kubernetes.client import (
    AppsV1Api,
    V1Container,
    V1DaemonSet,
    V1DaemonSetSpec,
    V1ObjectMeta,
    V1PodSpec,
    V1PodTemplateSpec,
)
from kubernetes.client.exceptions import ApiException

logger = structlog.get_logger(__name__)


class CacheDepositer:
    def __init__(self, name):
        self.name = name
        self.api = AppsV1Api()
        self.namespace = "cachemachine-dev"

    def deposit(self, image_url):
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

        template = V1PodTemplateSpec(
            metadata=V1ObjectMeta(labels={"app": self.name}),
            spec=V1PodSpec(containers=[container]),
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
        done = ds_status.status.updated_number_scheduled
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