from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class HealthProvider(ABC):
    @abstractmethod
    def connection_status(self, tenant_id: str, member_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def activity_summary(self, tenant_id: str, member_id: str, days: int) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def data_quality(self, tenant_id: str, member_id: str, days: int) -> dict[str, Any]:
        raise NotImplementedError
