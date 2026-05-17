from datetime import timedelta

from app.domain.enums import BacktestStatus, OrderSide
from app.domain.schemas import (
    BacktestRequest,
    BacktestResult,
    ExitCheckRequest,
    PaperAccountCreate,
    SimulateOrderRequest,
)
from app.services.account import AccountService
from app.services.indicators import IndicatorEngine
from app.services.market import MockMarketDataProvider
from app.services.repository import InMemoryRepository, repository
from app.services.simulator import PaperTradingSimulator


class BacktestService:
    """Runs deterministic historical replays through the same paper simulator used live."""

    def __init__(self, repo: InMemoryRepository = repository) -> None:
        self.repo = repo

    async def run(self, request: BacktestRequest) -> BacktestResult:
        result = BacktestResult(
            user_id=request.user_id,
            symbol=request.symbol,
            initial_capital=request.initial_capital,
            start_date=request.start_date,
            end_date=request.end_date,
            strategy_name=request.strategy_name,
            status=BacktestStatus.RUNNING,
        )
        self.repo.backtests[result.id] = result
        try:
            temp_repo = InMemoryRepository()
            account = AccountService(temp_repo).create_paper_account(
                PaperAccountCreate(user_id=request.user_id, initial_capital=request.initial_capital)
            )
            simulator = PaperTradingSimulator(temp_repo)
            market = MockMarketDataProvider()
            candles = await market.get_candles(request.symbol, limit=120)
            # Spread synthetic candles across requested window for UI/reporting consistency.
            total_seconds = max((request.end_date - request.start_date).total_seconds(), 1)
            step_seconds = total_seconds / max(len(candles), 1)
            for index, candle in enumerate(candles):
                candle.timestamp = request.start_date + timedelta(seconds=step_seconds * index)

            for index in range(20, len(candles)):
                candle = candles[index]
                window = candles[: index + 1]
                indicators = IndicatorEngine().snapshot(request.symbol, window)
                has_position = (account.id, request.symbol) in temp_repo.positions
                if not has_position and self._should_enter(indicators.indicators):
                    simulator.simulate_order(
                        SimulateOrderRequest(
                            account_id=account.id,
                            symbol=request.symbol,
                            side=OrderSide.BUY,
                            market_price=candle.close,
                            stop_loss=round(candle.close * 0.9, 2),
                            take_profit=round(candle.close * 1.16, 2),
                        )
                    )
                simulator.check_exits(
                    ExitCheckRequest(
                        account_id=account.id,
                        prices={request.symbol: candle.close},
                    )
                )

            summary = simulator.performance(account.id)
            result.status = BacktestStatus.COMPLETED
            result.metrics = {
                "total_return_pct": summary.total_return_pct,
                "account_value": summary.account_value,
                "realized_pnl": summary.realized_pnl,
                "unrealized_pnl": summary.unrealized_pnl,
                "max_drawdown_pct": summary.max_drawdown_pct,
                "win_rate_pct": summary.win_rate_pct,
                "trade_count": float(summary.trade_count),
            }
            result.trades = list(temp_repo.trades.values())
            result.equity_curve = temp_repo.account_equity[account.id]
        except Exception as exc:  # noqa: BLE001 - capture failure in backtest result for API consumers.
            result.status = BacktestStatus.FAILED
            result.error = str(exc)
        return result

    @staticmethod
    def _should_enter(indicators: dict[str, float]) -> bool:
        return indicators.get("rsi_14", 50) < 70 and indicators.get("pcr", 1) >= 1
