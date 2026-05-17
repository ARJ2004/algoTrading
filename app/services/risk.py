from datetime import UTC, datetime, time

from app.domain.enums import OrderSide
from app.domain.schemas import PaperAccount, PositionSizingResult, RiskProfile
from app.services.repository import InMemoryRepository, repository


class RiskValidationError(ValueError):
    pass


class RiskEngine:
    """Applies capital, stop-loss, confidence, and exposure controls before simulated fills."""

    def __init__(self, repo: InMemoryRepository = repository) -> None:
        self.repo = repo

    def validate_account_can_trade(self, account: PaperAccount) -> None:
        if account.status != "active":
            raise RiskValidationError("paper account is not active")
        if account.risk_profile.enforce_market_hours and not self.is_market_open():
            raise RiskValidationError("market is closed for this risk profile")
        positions = [key for key in self.repo.positions if key[0] == account.id]
        if len(positions) >= account.risk_profile.max_open_positions:
            raise RiskValidationError("max open positions limit reached")
        daily_loss_limit = account.initial_capital * (account.risk_profile.max_daily_loss_pct / 100)
        if account.realized_pnl <= -daily_loss_limit:
            raise RiskValidationError("max daily loss limit reached")

    def validate_signal_confidence(self, account: PaperAccount, confidence: float) -> None:
        if confidence < account.risk_profile.min_ai_confidence:
            raise RiskValidationError("AI confidence is below the configured threshold")

    def size_position(
        self,
        account: PaperAccount,
        symbol: str,
        side: OrderSide,
        entry_price: float,
        stop_loss: float,
        lot_size: int = 50,
        risk_profile: RiskProfile | None = None,
    ) -> PositionSizingResult:
        profile = risk_profile or account.risk_profile
        risk_per_unit = self._risk_per_unit(side, entry_price, stop_loss)
        if risk_per_unit <= 0:
            raise RiskValidationError("stop_loss must be below BUY entry or above SELL entry")

        risk_amount = account.initial_capital * (profile.risk_per_trade_pct / 100)
        raw_qty = int(risk_amount // risk_per_unit)
        lot_adjusted_qty = (raw_qty // lot_size) * lot_size
        if lot_adjusted_qty <= 0:
            raise RiskValidationError("capital is too small for the configured risk and lot size")

        notional = lot_adjusted_qty * entry_price
        if notional + profile.fee_per_order > account.available_cash:
            affordable_qty = int((account.available_cash - profile.fee_per_order) // entry_price)
            lot_adjusted_qty = (affordable_qty // lot_size) * lot_size
            notional = lot_adjusted_qty * entry_price

        if lot_adjusted_qty <= 0:
            raise RiskValidationError("insufficient virtual cash for this trade")

        return PositionSizingResult(
            quantity=lot_adjusted_qty,
            risk_amount=round(risk_amount, 2),
            risk_per_unit=round(risk_per_unit, 2),
            notional=round(notional, 2),
            reason=f"{profile.risk_per_trade_pct}% risk rule applied for {symbol}",
        )

    @staticmethod
    def _risk_per_unit(side: OrderSide, entry_price: float, stop_loss: float) -> float:
        if side == OrderSide.BUY:
            return entry_price - stop_loss
        return stop_loss - entry_price

    @staticmethod
    def is_market_open(now: datetime | None = None) -> bool:
        now = now or datetime.now(UTC)
        ist_minutes = 5 * 60 + 30
        ist_now = now.timestamp() + ist_minutes * 60
        ist_datetime = datetime.fromtimestamp(ist_now, UTC)
        market_open = time(9, 15)
        market_close = time(15, 30)
        return ist_datetime.weekday() < 5 and market_open <= ist_datetime.time() <= market_close
