from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from app.domain.enums import (
    AlertSeverity,
    BacktestStatus,
    OrderSide,
    OrderStatus,
    SignalAction,
    TradeMode,
)


def utc_now() -> datetime:
    return datetime.now(UTC)


def serialize(value: Any) -> Any:
    if is_dataclass(value):
        return {key: serialize(item) for key, item in asdict(value).items()}
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: serialize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [serialize(item) for item in value]
    return value


@dataclass
class RiskProfile:
    risk_per_trade_pct: float = 2.0
    max_daily_loss_pct: float = 5.0
    max_open_positions: int = 5
    default_slippage_pct: float = 0.1
    fee_per_order: float = 20.0
    auto_execute_paper_signals: bool = False
    min_ai_confidence: float = 0.55
    enforce_market_hours: bool = False

    def __post_init__(self) -> None:
        if not 0 < self.risk_per_trade_pct <= 10:
            raise ValueError("risk_per_trade_pct must be between 0 and 10")
        if not 0 < self.max_daily_loss_pct <= 50:
            raise ValueError("max_daily_loss_pct must be between 0 and 50")
        if self.max_open_positions < 1:
            raise ValueError("max_open_positions must be at least 1")
        if self.default_slippage_pct < 0:
            raise ValueError("default_slippage_pct cannot be negative")
        if not 0 <= self.min_ai_confidence <= 1:
            raise ValueError("min_ai_confidence must be between 0 and 1")


@dataclass
class PaperAccountCreate:
    initial_capital: float
    user_id: str = "demo-user"
    risk_profile: RiskProfile | None = None

    def __post_init__(self) -> None:
        if self.initial_capital <= 0:
            raise ValueError("initial_capital must be positive")


@dataclass
class PaperAccount:
    user_id: str
    initial_capital: float
    available_cash: float
    risk_profile: RiskProfile
    id: UUID = field(default_factory=uuid4)
    mode: TradeMode = TradeMode.PAPER
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    status: str = "active"
    created_at: datetime = field(default_factory=utc_now)


@dataclass
class MarketQuote:
    symbol: str
    ltp: float
    instrument_key: str | None = None
    timestamp: datetime = field(default_factory=utc_now)
    bid: float | None = None
    ask: float | None = None
    volume: int = 0
    open_interest: int = 0
    source: str = "mock"


@dataclass
class Candle:
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int = 0


@dataclass
class IndicatorSnapshot:
    symbol: str
    indicators: dict[str, float]
    timeframe: str = "5m"
    timestamp: datetime = field(default_factory=utc_now)


@dataclass
class AISignalRequest:
    account_id: UUID
    symbol: str = "NIFTY26MAY24500CE"


@dataclass
class AISignal:
    account_id: UUID
    symbol: str
    action: SignalAction
    confidence: float
    rationale: str
    stop_loss: float | None = None
    take_profit: float | None = None
    entry_type: str = "MARKET"
    raw_response: dict[str, Any] = field(default_factory=dict)
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.action = SignalAction(self.action)
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if self.action in {SignalAction.BUY, SignalAction.SELL} and self.stop_loss is None:
            raise ValueError("stop_loss is required for BUY/SELL signals")


@dataclass
class PositionSizingResult:
    quantity: int
    risk_amount: float
    risk_per_unit: float
    notional: float
    reason: str = "accepted"


@dataclass
class SimulateOrderRequest:
    account_id: UUID
    symbol: str
    side: OrderSide
    market_price: float
    stop_loss: float
    signal_id: UUID | None = None
    take_profit: float | None = None
    quantity: int | None = None

    def __post_init__(self) -> None:
        self.side = OrderSide(self.side)
        if self.market_price <= 0 or self.stop_loss <= 0:
            raise ValueError("market_price and stop_loss must be positive")


@dataclass
class ExitCheckRequest:
    account_id: UUID
    prices: dict[str, float]


@dataclass
class Order:
    account_id: UUID
    symbol: str
    side: OrderSide
    quantity: int
    requested_price: float
    signal_id: UUID | None = None
    id: UUID = field(default_factory=uuid4)
    status: OrderStatus = OrderStatus.CREATED
    mode: TradeMode = TradeMode.PAPER
    created_at: datetime = field(default_factory=utc_now)
    rejection_reason: str | None = None


@dataclass
class Trade:
    order_id: UUID
    account_id: UUID
    symbol: str
    side: OrderSide
    quantity: int
    fill_price: float
    slippage_pct: float
    fees: float
    id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=utc_now)
    reason: str = "entry"


@dataclass
class Position:
    account_id: UUID
    symbol: str
    quantity: int
    avg_price: float
    last_price: float
    stop_loss: float | None = None
    take_profit: float | None = None
    opened_at: datetime = field(default_factory=utc_now)
    unrealized_pnl: float = 0.0


@dataclass
class PerformanceSummary:
    account_id: UUID
    initial_capital: float
    available_cash: float
    realized_pnl: float
    unrealized_pnl: float
    account_value: float
    total_return_pct: float
    open_positions: int
    trade_count: int
    max_drawdown_pct: float = 0.0
    win_rate_pct: float = 0.0


@dataclass
class BacktestRequest:
    user_id: str = "demo-user"
    symbol: str = "NIFTY26MAY24500CE"
    initial_capital: float = 100_000
    start_date: datetime = field(default_factory=lambda: utc_now() - timedelta(days=30))
    end_date: datetime = field(default_factory=utc_now)
    strategy_name: str = "mock-ai-rsi-vwap"


@dataclass
class BacktestResult:
    user_id: str
    symbol: str
    initial_capital: float
    start_date: datetime
    end_date: datetime
    strategy_name: str
    status: BacktestStatus = BacktestStatus.CREATED
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)
    metrics: dict[str, float] = field(default_factory=dict)
    trades: list[Trade] = field(default_factory=list)
    equity_curve: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None


@dataclass
class Alert:
    account_id: UUID | None
    message: str
    severity: AlertSeverity = AlertSeverity.INFO
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)
    resolved: bool = False


@dataclass
class LiveReadiness:
    enabled: bool
    reason: str
    checklist: dict[str, bool]


@dataclass
class User:
    email: str
    password_hash: str
    kyc_status: str = "paper_only"
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)


@dataclass
class AuthToken:
    token: str
    user: User


@dataclass
class ComplianceReport:
    account_id: UUID
    generated_at: datetime
    paper_only: bool
    total_audit_events: int
    total_signals: int
    total_orders: int
    total_trades: int
    live_readiness: dict[str, Any]
    warnings: list[str] = field(default_factory=list)


@dataclass
class DataSnapshot:
    generated_at: datetime
    payload: dict[str, Any]


@dataclass
class AuditLog:
    event_type: str
    source: str
    payload: dict[str, Any]
    user_id: str | None = None
    correlation_id: UUID = field(default_factory=uuid4)
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)
