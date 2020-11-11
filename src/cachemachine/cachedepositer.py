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

logger = structlog.get_logger(__name__)


class CacheDepositer:
    def __init__(self):
        self.api = AppsV1Api()

    def deposit(self, name):
        container = V1Container(
            name="cachemachine", image=name, command=["/bin/true"]
        )

        template = V1PodTemplateSpec(
            metadata=V1ObjectMeta(labels={"app": "cachemachine"}),
            spec=V1PodSpec(containers=[container]),
        )

        spec = V1DaemonSetSpec(
            template=template,
            selector={"matchLabels": {"app": "cachemachine"}},
        )

        ds = V1DaemonSet(metadata=V1ObjectMeta(name="cachedeposit"), spec=spec)

        self.api.create_namespaced_daemon_set("cachemachine-dev", ds)
