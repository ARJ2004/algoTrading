from collections import defaultdict
from uuid import UUID

from app.domain.schemas import (
    AISignal,
    Alert,
    AuditLog,
    BacktestResult,
    Order,
    PaperAccount,
    Position,
    Trade,
    User,
)


class InMemoryRepository:
    """Simple repository for the MVP; replace with PostgreSQL adapters in production."""

    def __init__(self) -> None:
        self.users: dict[UUID, User] = {}
        self.sessions: dict[str, UUID] = {}
        self.accounts: dict[UUID, PaperAccount] = {}
        self.signals: dict[UUID, AISignal] = {}
        self.orders: dict[UUID, Order] = {}
        self.trades: dict[UUID, Trade] = {}
        self.positions: dict[tuple[UUID, str], Position] = {}
        self.audit_logs: list[AuditLog] = []
        self.alerts: dict[UUID, Alert] = {}
        self.backtests: dict[UUID, BacktestResult] = {}
        self.account_trade_index: dict[UUID, list[UUID]] = defaultdict(list)
        self.account_equity: dict[UUID, list[dict]] = defaultdict(list)

    def reset(self) -> None:
        self.__init__()


repository = InMemoryRepository()
