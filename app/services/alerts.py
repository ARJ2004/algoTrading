from uuid import UUID

from app.domain.enums import AlertSeverity
from app.domain.schemas import Alert
from app.services.repository import InMemoryRepository, repository


class AlertService:
    def __init__(self, repo: InMemoryRepository = repository) -> None:
        self.repo = repo

    def create(
        self,
        message: str,
        account_id: UUID | None = None,
        severity: AlertSeverity = AlertSeverity.INFO,
    ) -> Alert:
        alert = Alert(account_id=account_id, message=message, severity=severity)
        self.repo.alerts[alert.id] = alert
        return alert

    def list(self, account_id: UUID | None = None, include_resolved: bool = False) -> list[Alert]:
        alerts = list(self.repo.alerts.values())
        if account_id:
            alerts = [alert for alert in alerts if alert.account_id == account_id]
        if not include_resolved:
            alerts = [alert for alert in alerts if not alert.resolved]
        return alerts
