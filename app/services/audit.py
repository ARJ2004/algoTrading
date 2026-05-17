from typing import Any
from uuid import UUID, uuid4

from app.domain.schemas import AuditLog
from app.services.repository import InMemoryRepository, repository


class AuditService:
    def __init__(self, repo: InMemoryRepository = repository) -> None:
        self.repo = repo

    def record(
        self,
        event_type: str,
        source: str,
        payload: dict[str, Any],
        user_id: str | None = None,
        correlation_id: UUID | None = None,
    ) -> AuditLog:
        log = AuditLog(
            user_id=user_id,
            correlation_id=correlation_id or uuid4(),
            event_type=event_type,
            source=source,
            payload=payload,
        )
        self.repo.audit_logs.append(log)
        return log
