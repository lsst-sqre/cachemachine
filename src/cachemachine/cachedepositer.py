import structlog

from cachemachine.config import Configuration
from cachemachine.kubernetes import KubernetesClient
from cachemachine.types import KubernetesDaemonsetNotFound, KubernetesLabels

logger = structlog.get_logger(__name__)


class CacheDepositer:
    def __init__(self, name: str, labels: KubernetesLabels) -> None:
        self.name = name
        self.labels = labels
        self.kubernetes = KubernetesClient()

    def deposit(self, image_url: str) -> None:
        self.kubernetes.daemonset_create(
            self.name,
            image_url,
            Configuration().docker_secret_name,
            self.labels,
        )

    def busy(self) -> bool:
        try:
            finished = self.kubernetes.daemonset_finished(self.name)
            if finished:
                self.kubernetes.daemonset_delete(self.name)
                return False
            else:
                return True
        except KubernetesDaemonsetNotFound:
            return False
