from uuid import UUID

from app.domain.enums import AlertSeverity, OrderSide, OrderStatus, SignalAction
from app.domain.schemas import (
    ExitCheckRequest,
    Order,
    PerformanceSummary,
    Position,
    SimulateOrderRequest,
    Trade,
    utc_now,
)
from app.services.alerts import AlertService
from app.services.audit import AuditService
from app.services.repository import InMemoryRepository, repository
from app.services.risk import RiskEngine, RiskValidationError


class PaperTradingSimulator:
    def __init__(
        self,
        repo: InMemoryRepository = repository,
        risk_engine: RiskEngine | None = None,
        audit: AuditService | None = None,
        alerts: AlertService | None = None,
    ) -> None:
        self.repo = repo
        self.risk_engine = risk_engine or RiskEngine(repo)
        self.audit = audit or AuditService(repo)
        self.alerts = alerts or AlertService(repo)

    def simulate_order(
        self,
        request: SimulateOrderRequest,
        correlation_id: UUID | None = None,
    ) -> Order:
        account = self.repo.accounts.get(request.account_id)
        if not account:
            raise KeyError("paper account not found")

        if request.signal_id:
            signal = self.repo.signals.get(request.signal_id)
            if not signal:
                raise KeyError("signal not found")
            if signal.action == SignalAction.HOLD:
                return self._reject(request, "HOLD signals cannot be executed")
            try:
                self.risk_engine.validate_signal_confidence(account, signal.confidence)
            except RiskValidationError as exc:
                return self._reject(request, str(exc))

        if request.side == OrderSide.SELL:
            existing = self.repo.positions.get((request.account_id, request.symbol))
            if not existing:
                return self._reject(request, "cannot sell without an open paper position")

        try:
            if request.side == OrderSide.BUY:
                self.risk_engine.validate_account_can_trade(account)
            sizing = self.risk_engine.size_position(
                account=account,
                symbol=request.symbol,
                side=request.side,
                entry_price=request.market_price,
                stop_loss=request.stop_loss,
            )
        except RiskValidationError as exc:
            return self._reject(request, str(exc))

        quantity = request.quantity or sizing.quantity
        order = Order(
            account_id=request.account_id,
            signal_id=request.signal_id,
            symbol=request.symbol,
            side=request.side,
            quantity=quantity,
            requested_price=request.market_price,
            status=OrderStatus.FILLED,
        )
        fill_price = self._apply_slippage(
            side=request.side,
            price=request.market_price,
            slippage_pct=account.risk_profile.default_slippage_pct,
        )
        trade = Trade(
            order_id=order.id,
            account_id=account.id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            fill_price=fill_price,
            slippage_pct=account.risk_profile.default_slippage_pct,
            fees=account.risk_profile.fee_per_order,
        )

        self.repo.orders[order.id] = order
        self.repo.trades[trade.id] = trade
        self.repo.account_trade_index[account.id].append(trade.id)
        self._update_account_and_position(order, trade, request.stop_loss, request.take_profit)
        self._record_equity(account.id)
        self.audit.record(
            event_type="paper_order_filled",
            source="paper_simulator",
            user_id=account.user_id,
            correlation_id=correlation_id,
            payload={"order": order, "trade": trade, "sizing": sizing},
        )
        self._create_risk_alerts(account.id)
        return order

    def check_exits(self, request: ExitCheckRequest) -> list[Order]:
        account = self.repo.accounts.get(request.account_id)
        if not account:
            raise KeyError("paper account not found")
        exit_orders: list[Order] = []
        for (account_id, symbol), position in list(self.repo.positions.items()):
            if account_id != request.account_id or symbol not in request.prices:
                continue
            price = request.prices[symbol]
            position.last_price = price
            position.unrealized_pnl = round((price - position.avg_price) * position.quantity, 2)
            hit_stop = position.stop_loss is not None and price <= position.stop_loss
            hit_target = position.take_profit is not None and price >= position.take_profit
            if hit_stop or hit_target:
                reason = "stop_loss" if hit_stop else "take_profit"
                exit_orders.append(self._exit_position(position, price, reason))
        self._record_equity(request.account_id)
        return exit_orders

    def performance(self, account_id: UUID) -> PerformanceSummary:
        account = self.repo.accounts[account_id]
        positions = [
            position
            for key, position in self.repo.positions.items()
            if key[0] == account_id
        ]
        account.unrealized_pnl = round(sum(position.unrealized_pnl for position in positions), 2)
        account_value = round(
            account.available_cash + sum(p.quantity * p.last_price for p in positions),
            2,
        )
        total_return_pct = round(
            ((account_value - account.initial_capital) / account.initial_capital) * 100,
            2,
        )
        return PerformanceSummary(
            account_id=account.id,
            initial_capital=account.initial_capital,
            available_cash=round(account.available_cash, 2),
            realized_pnl=round(account.realized_pnl, 2),
            unrealized_pnl=account.unrealized_pnl,
            account_value=account_value,
            total_return_pct=total_return_pct,
            open_positions=len(positions),
            trade_count=len(self.repo.account_trade_index[account.id]),
            max_drawdown_pct=self._max_drawdown(account.id),
            win_rate_pct=self._win_rate(account.id),
        )

    def _reject(self, request: SimulateOrderRequest, reason: str) -> Order:
        order = Order(
            account_id=request.account_id,
            signal_id=request.signal_id,
            symbol=request.symbol,
            side=request.side,
            quantity=0,
            requested_price=request.market_price,
            status=OrderStatus.REJECTED,
            rejection_reason=reason,
        )
        self.repo.orders[order.id] = order
        self.alerts.create(reason, request.account_id, AlertSeverity.WARNING)
        return order

    @staticmethod
    def _apply_slippage(side: OrderSide, price: float, slippage_pct: float) -> float:
        multiplier = 1 + slippage_pct / 100 if side == OrderSide.BUY else 1 - slippage_pct / 100
        return round(price * multiplier, 2)

    def _update_account_and_position(
        self,
        order: Order,
        trade: Trade,
        stop_loss: float | None,
        take_profit: float | None,
    ) -> None:
        account = self.repo.accounts[order.account_id]
        key = (order.account_id, order.symbol)
        existing = self.repo.positions.get(key)

        if order.side == OrderSide.BUY:
            cost = trade.quantity * trade.fill_price + trade.fees
            account.available_cash = round(account.available_cash - cost, 2)
            if existing:
                total_qty = existing.quantity + trade.quantity
                existing.avg_price = round(
                    ((existing.avg_price * existing.quantity) + (trade.fill_price * trade.quantity))
                    / total_qty,
                    2,
                )
                existing.quantity = total_qty
                existing.last_price = trade.fill_price
                existing.stop_loss = stop_loss
                existing.take_profit = take_profit
            else:
                self.repo.positions[key] = Position(
                    account_id=order.account_id,
                    symbol=order.symbol,
                    quantity=trade.quantity,
                    avg_price=trade.fill_price,
                    last_price=trade.fill_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                )
        else:
            if not existing or existing.quantity < trade.quantity:
                order.status = OrderStatus.REJECTED
                order.rejection_reason = "cannot sell more than the open paper position"
                return
            self._apply_sell(account.id, existing, trade)

    def _exit_position(self, position: Position, price: float, reason: str) -> Order:
        order = Order(
            account_id=position.account_id,
            symbol=position.symbol,
            side=OrderSide.SELL,
            quantity=position.quantity,
            requested_price=price,
            status=OrderStatus.FILLED,
        )
        account = self.repo.accounts[position.account_id]
        fill_price = self._apply_slippage(
            OrderSide.SELL,
            price,
            account.risk_profile.default_slippage_pct,
        )
        trade = Trade(
            order_id=order.id,
            account_id=position.account_id,
            symbol=position.symbol,
            side=OrderSide.SELL,
            quantity=position.quantity,
            fill_price=fill_price,
            slippage_pct=account.risk_profile.default_slippage_pct,
            fees=account.risk_profile.fee_per_order,
            reason=reason,
        )
        self.repo.orders[order.id] = order
        self.repo.trades[trade.id] = trade
        self.repo.account_trade_index[position.account_id].append(trade.id)
        self._apply_sell(position.account_id, position, trade)
        self.audit.record(
            event_type=f"paper_position_exited_{reason}",
            source="paper_simulator",
            user_id=account.user_id,
            payload={"order": order, "trade": trade},
        )
        return order

    def _apply_sell(self, account_id: UUID, position: Position, trade: Trade) -> None:
        account = self.repo.accounts[account_id]
        proceeds = trade.quantity * trade.fill_price - trade.fees
        realized = (trade.fill_price - position.avg_price) * trade.quantity - trade.fees
        account.available_cash = round(account.available_cash + proceeds, 2)
        account.realized_pnl = round(account.realized_pnl + realized, 2)
        position.quantity -= trade.quantity
        position.last_price = trade.fill_price
        if position.quantity == 0:
            del self.repo.positions[(account_id, position.symbol)]

    def _record_equity(self, account_id: UUID) -> None:
        summary = self.performance(account_id)
        self.repo.account_equity[account_id].append(
            {"timestamp": utc_now(), "account_value": summary.account_value}
        )

    def _create_risk_alerts(self, account_id: UUID) -> None:
        summary = self.performance(account_id)
        account = self.repo.accounts[account_id]
        if summary.available_cash < account.initial_capital * 0.2:
            self.alerts.create(
                "Virtual cash below 20% of initial capital",
                account_id,
                AlertSeverity.WARNING,
            )
        if summary.total_return_pct <= -account.risk_profile.max_daily_loss_pct:
            self.alerts.create(
                "Max daily loss threshold reached",
                account_id,
                AlertSeverity.CRITICAL,
            )

    def _max_drawdown(self, account_id: UUID) -> float:
        curve = self.repo.account_equity[account_id]
        peak = 0.0
        max_drawdown = 0.0
        for point in curve:
            value = float(point["account_value"])
            peak = max(peak, value)
            if peak:
                max_drawdown = min(max_drawdown, (value - peak) / peak * 100)
        return round(abs(max_drawdown), 2)

    def _win_rate(self, account_id: UUID) -> float:
        trade_ids = self.repo.account_trade_index[account_id]
        exit_trades = [
            self.repo.trades[trade_id]
            for trade_id in trade_ids
            if self.repo.trades[trade_id].side == OrderSide.SELL
        ]
        if not exit_trades:
            return 0.0
        wins = 0
        for trade in exit_trades:
            # Realized P&L is aggregated on the account; classify by reason/fill conservatively.
            wins += 1 if trade.reason == "take_profit" else 0
        return round((wins / len(exit_trades)) * 100, 2)
