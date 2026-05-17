from uuid import UUID

from app.domain.schemas import ComplianceReport, DataSnapshot, serialize, utc_now
from app.services.live import LiveTradingReadinessService
from app.services.repository import InMemoryRepository, repository


class ReportService:
    def __init__(self, repo: InMemoryRepository = repository) -> None:
        self.repo = repo

    def compliance_report(self, account_id: UUID) -> ComplianceReport:
        account = self.repo.accounts.get(account_id)
        if not account:
            raise KeyError("paper account not found")
        warnings: list[str] = []
        if account.mode != "paper":
            warnings.append("Account is not marked as paper mode")
        if not self.repo.audit_logs:
            warnings.append("No audit logs are present")
        readiness = LiveTradingReadinessService().status()
        total_audit_events = len(
            [log for log in self.repo.audit_logs if log.user_id == account.user_id]
        )
        total_signals = len(
            [signal for signal in self.repo.signals.values() if signal.account_id == account_id]
        )
        total_orders = len(
            [order for order in self.repo.orders.values() if order.account_id == account_id]
        )
        total_trades = len(
            [trade for trade in self.repo.trades.values() if trade.account_id == account_id]
        )
        return ComplianceReport(
            account_id=account_id,
            generated_at=utc_now(),
            paper_only=True,
            total_audit_events=total_audit_events,
            total_signals=total_signals,
            total_orders=total_orders,
            total_trades=total_trades,
            live_readiness=serialize(readiness),
            warnings=warnings,
        )

    def export_snapshot(self) -> DataSnapshot:
        return DataSnapshot(
            generated_at=utc_now(),
            payload={
                "users": list(self.repo.users.values()),
                "accounts": list(self.repo.accounts.values()),
                "signals": list(self.repo.signals.values()),
                "orders": list(self.repo.orders.values()),
                "trades": list(self.repo.trades.values()),
                "positions": list(self.repo.positions.values()),
                "alerts": list(self.repo.alerts.values()),
                "backtests": list(self.repo.backtests.values()),
                "audit_logs": self.repo.audit_logs,
            },
        )
