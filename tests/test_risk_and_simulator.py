from app.domain.enums import OrderSide, OrderStatus
from app.domain.schemas import PaperAccountCreate, SimulateOrderRequest
from app.services.account import AccountService
from app.services.repository import repository
from app.services.risk import RiskEngine
from app.services.simulator import PaperTradingSimulator


def setup_function() -> None:
    repository.reset()


def test_risk_engine_sizes_position_by_two_percent_rule() -> None:
    account = AccountService().create_paper_account(
        PaperAccountCreate(user_id="u1", initial_capital=100_000)
    )

    sizing = RiskEngine().size_position(
        account=account,
        symbol="NIFTY26MAY24500CE",
        side=OrderSide.BUY,
        entry_price=125.0,
        stop_loss=110.0,
    )

    assert sizing.risk_amount == 2000
    assert sizing.risk_per_unit == 15
    assert sizing.quantity == 100
    assert sizing.notional == 12_500


def test_paper_simulator_applies_slippage_fees_and_updates_position() -> None:
    account = AccountService().create_paper_account(
        PaperAccountCreate(user_id="u1", initial_capital=100_000)
    )

    order = PaperTradingSimulator().simulate_order(
        SimulateOrderRequest(
            account_id=account.id,
            symbol="NIFTY26MAY24500CE",
            side=OrderSide.BUY,
            market_price=125.0,
            stop_loss=110.0,
            take_profit=150.0,
        )
    )

    assert order.status == OrderStatus.FILLED
    assert order.quantity == 100
    trade = next(iter(repository.trades.values()))
    assert trade.fill_price == 125.12
    assert repository.accounts[account.id].available_cash == 87_468.0
    assert repository.positions[(account.id, "NIFTY26MAY24500CE")].quantity == 100


def test_paper_simulator_rejects_invalid_stop_loss() -> None:
    account = AccountService().create_paper_account(
        PaperAccountCreate(user_id="u1", initial_capital=100_000)
    )

    order = PaperTradingSimulator().simulate_order(
        SimulateOrderRequest(
            account_id=account.id,
            symbol="NIFTY26MAY24500CE",
            side=OrderSide.BUY,
            market_price=125.0,
            stop_loss=130.0,
        )
    )

    assert order.status == OrderStatus.REJECTED
    assert order.rejection_reason == "stop_loss must be below BUY entry or above SELL entry"
