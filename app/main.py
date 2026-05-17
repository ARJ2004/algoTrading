import asyncio
import json
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from uuid import UUID

from app.core.config import get_settings
from app.domain.enums import OrderSide
from app.domain.schemas import (
    AISignalRequest,
    BacktestRequest,
    ExitCheckRequest,
    PaperAccountCreate,
    RiskProfile,
    SimulateOrderRequest,
    serialize,
)
from app.services.account import AccountService
from app.services.alerts import AlertService
from app.services.auth import AuthService
from app.services.backtesting import BacktestService
from app.services.live import LiveTradingReadinessService
from app.services.market import get_market_provider
from app.services.persistence import PersistenceService
from app.services.reports import ReportService
from app.services.repository import repository
from app.services.signals import SignalService
from app.services.simulator import PaperTradingSimulator

FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"
FRONTEND_INDEX = FRONTEND_DIST / "index.html"


def _json_response(handler: BaseHTTPRequestHandler, status: HTTPStatus, payload: object) -> None:
    body = json.dumps(serialize(payload)).encode("utf-8")
    handler.send_response(status.value)
    _cors_headers(handler)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _cors_headers(handler: BaseHTTPRequestHandler) -> None:
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")


def _read_json(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    if length == 0:
        return {}
    return json.loads(handler.rfile.read(length).decode("utf-8"))


def _parse_datetime(value: str | None, fallback: datetime) -> datetime:
    if not value:
        return fallback
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class TradingRequestHandler(BaseHTTPRequestHandler):
    server_version = "AlgoTradingMVP/0.2"

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT.value)
        _cors_headers(self)
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/":
                self._serve_frontend_or_status()
            elif parsed.path == "/api/health":
                _json_response(self, HTTPStatus.OK, {"status": "ok", "version": "0.2"})
            elif parsed.path == "/api/bootstrap":
                _json_response(self, HTTPStatus.OK, self._bootstrap())
            elif parsed.path.startswith("/api/paper/accounts/"):
                self._get_account(parsed.path)
            elif parsed.path == "/api/market/quote":
                params = parse_qs(parsed.query)
                symbol = params.get("symbol", ["NIFTY26MAY24500CE"])[0]
                quote = asyncio.run(get_market_provider().get_quote(symbol))
                _json_response(self, HTTPStatus.OK, quote)
            elif parsed.path == "/api/market/indicators":
                params = parse_qs(parsed.query)
                symbol = params.get("symbol", ["NIFTY26MAY24500CE"])[0]
                indicators = asyncio.run(get_market_provider().get_indicators(symbol))
                _json_response(self, HTTPStatus.OK, indicators)
            elif parsed.path == "/api/ai/signals":
                self._list_signals(parsed.query)
            elif parsed.path == "/api/paper/orders":
                _json_response(self, HTTPStatus.OK, list(repository.orders.values()))
            elif parsed.path == "/api/paper/trades":
                _json_response(self, HTTPStatus.OK, list(repository.trades.values()))
            elif parsed.path == "/api/paper/positions":
                _json_response(self, HTTPStatus.OK, list(repository.positions.values()))
            elif parsed.path.startswith("/api/paper/performance/"):
                self._performance(parsed.path)
            elif parsed.path == "/api/backtests":
                _json_response(self, HTTPStatus.OK, list(repository.backtests.values()))
            elif parsed.path.startswith("/api/backtests/"):
                self._get_backtest(parsed.path)
            elif parsed.path == "/api/alerts":
                self._list_alerts(parsed.query)
            elif parsed.path == "/api/live/readiness":
                _json_response(self, HTTPStatus.OK, LiveTradingReadinessService().status())
            elif parsed.path == "/api/audit/logs":
                _json_response(self, HTTPStatus.OK, repository.audit_logs)
            elif parsed.path.startswith("/api/reports/compliance/"):
                account_id = UUID(parsed.path.rsplit("/", 1)[-1])
                _json_response(
                    self,
                    HTTPStatus.OK,
                    ReportService().compliance_report(account_id),
                )
            elif parsed.path == "/api/persistence/export":
                _json_response(self, HTTPStatus.OK, PersistenceService().snapshot())
            elif parsed.path == "/api/me":
                token = self.headers.get("Authorization", "").replace("Bearer ", "")
                _json_response(self, HTTPStatus.OK, AuthService().me(token))
            else:
                _json_response(self, HTTPStatus.NOT_FOUND, {"detail": "not found"})
        except (ValueError, KeyError) as exc:
            _json_response(self, HTTPStatus.BAD_REQUEST, {"detail": str(exc)})
        except RuntimeError as exc:
            _json_response(self, HTTPStatus.BAD_GATEWAY, {"detail": str(exc)})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        try:
            payload = _read_json(self)
            if parsed.path == "/api/auth/register":
                token = AuthService().register(payload["email"], payload["password"])
                _json_response(self, HTTPStatus.CREATED, token)
            elif parsed.path == "/api/auth/login":
                token = AuthService().login(payload["email"], payload["password"])
                _json_response(self, HTTPStatus.OK, token)
            elif parsed.path == "/api/persistence/save":
                _json_response(self, HTTPStatus.CREATED, PersistenceService().save())
            elif parsed.path == "/api/paper/accounts":
                account = AccountService().create_paper_account(
                    PaperAccountCreate(
                        user_id=payload.get("user_id", "demo-user"),
                        initial_capital=float(payload["initial_capital"]),
                        risk_profile=self._risk_profile(payload.get("risk_profile")),
                    )
                )
                _json_response(self, HTTPStatus.CREATED, account)
            elif parsed.path == "/api/ai/signals/generate":
                request = AISignalRequest(
                    account_id=UUID(payload["account_id"]),
                    symbol=payload.get("symbol", "NIFTY26MAY24500CE"),
                )
                signal = asyncio.run(SignalService().generate(request.account_id, request.symbol))
                _json_response(self, HTTPStatus.CREATED, signal)
            elif parsed.path == "/api/paper/orders/simulate":
                order = PaperTradingSimulator().simulate_order(self._simulate_request(payload))
                _json_response(self, HTTPStatus.CREATED, order)
            elif parsed.path == "/api/paper/orders/check-exits":
                orders = PaperTradingSimulator().check_exits(
                    ExitCheckRequest(
                        account_id=UUID(payload["account_id"]),
                        prices={
                            key: float(value)
                            for key, value in payload.get("prices", {}).items()
                        },
                    )
                )
                _json_response(self, HTTPStatus.CREATED, orders)
            elif parsed.path == "/api/backtests":
                request = BacktestRequest(
                    user_id=payload.get("user_id", "demo-user"),
                    symbol=payload.get("symbol", "NIFTY26MAY24500CE"),
                    initial_capital=float(payload.get("initial_capital", 100_000)),
                    start_date=_parse_datetime(
                        payload.get("start_date"),
                        BacktestRequest().start_date,
                    ),
                    end_date=_parse_datetime(payload.get("end_date"), BacktestRequest().end_date),
                    strategy_name=payload.get("strategy_name", "mock-ai-rsi-vwap"),
                )
                result = asyncio.run(BacktestService().run(request))
                _json_response(self, HTTPStatus.CREATED, result)
            else:
                _json_response(self, HTTPStatus.NOT_FOUND, {"detail": "not found"})
        except KeyError as exc:
            _json_response(self, HTTPStatus.NOT_FOUND, {"detail": str(exc)})
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            _json_response(self, HTTPStatus.BAD_REQUEST, {"detail": str(exc)})
        except RuntimeError as exc:
            _json_response(self, HTTPStatus.BAD_GATEWAY, {"detail": str(exc)})

    def do_PATCH(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        try:
            payload = _read_json(self)
            if parsed.path.startswith("/api/paper/accounts/") and parsed.path.endswith("/risk"):
                account_id = UUID(parsed.path.split("/")[-2])
                account = AccountService().update_risk_profile(account_id, payload)
                _json_response(self, HTTPStatus.OK, account)
            else:
                _json_response(self, HTTPStatus.NOT_FOUND, {"detail": "not found"})
        except KeyError as exc:
            _json_response(self, HTTPStatus.NOT_FOUND, {"detail": str(exc)})
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            _json_response(self, HTTPStatus.BAD_REQUEST, {"detail": str(exc)})

    def _serve_frontend_or_status(self) -> None:
        if FRONTEND_INDEX.exists():
            body = FRONTEND_INDEX.read_bytes()
            self.send_response(HTTPStatus.OK.value)
            _cors_headers(self)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        _json_response(
            self,
            HTTPStatus.OK,
            {
                "message": (
                    "Backend is running. Start the React UI with "
                    "`cd frontend && npm run dev`."
                ),
                "api": "/api/health",
            },
        )

    def _get_account(self, path: str) -> None:
        account_id = UUID(path.rsplit("/", 1)[-1])
        account = repository.accounts.get(account_id)
        if not account:
            _json_response(self, HTTPStatus.NOT_FOUND, {"detail": "paper account not found"})
            return
        _json_response(self, HTTPStatus.OK, account)

    def _list_signals(self, query: str) -> None:
        params = parse_qs(query)
        account_id = UUID(params["account_id"][0]) if "account_id" in params else None
        signals = list(repository.signals.values())
        if account_id:
            signals = [signal for signal in signals if signal.account_id == account_id]
        _json_response(self, HTTPStatus.OK, signals)

    def _performance(self, path: str) -> None:
        account_id = UUID(path.rsplit("/", 1)[-1])
        if account_id not in repository.accounts:
            _json_response(self, HTTPStatus.NOT_FOUND, {"detail": "paper account not found"})
            return
        _json_response(self, HTTPStatus.OK, PaperTradingSimulator().performance(account_id))

    def _get_backtest(self, path: str) -> None:
        backtest_id = UUID(path.rsplit("/", 1)[-1])
        backtest = repository.backtests.get(backtest_id)
        if not backtest:
            _json_response(self, HTTPStatus.NOT_FOUND, {"detail": "backtest not found"})
            return
        _json_response(self, HTTPStatus.OK, backtest)

    def _list_alerts(self, query: str) -> None:
        params = parse_qs(query)
        account_id = UUID(params["account_id"][0]) if "account_id" in params else None
        include_resolved = params.get("include_resolved", ["false"])[0].lower() == "true"
        _json_response(self, HTTPStatus.OK, AlertService().list(account_id, include_resolved))

    def _bootstrap(self) -> dict:
        return {
            "users": list(repository.users.values()),
            "accounts": list(repository.accounts.values()),
            "signals": list(repository.signals.values()),
            "orders": list(repository.orders.values()),
            "trades": list(repository.trades.values()),
            "positions": list(repository.positions.values()),
            "alerts": list(repository.alerts.values()),
            "backtests": list(repository.backtests.values()),
            "live_readiness": LiveTradingReadinessService().status(),
        }

    @staticmethod
    def _risk_profile(payload: dict | None) -> RiskProfile | None:
        return RiskProfile(**payload) if payload else None

    @staticmethod
    def _simulate_request(payload: dict) -> SimulateOrderRequest:
        return SimulateOrderRequest(
            account_id=UUID(payload["account_id"]),
            signal_id=UUID(payload["signal_id"]) if payload.get("signal_id") else None,
            symbol=payload["symbol"],
            side=OrderSide(payload["side"]),
            market_price=float(payload["market_price"]),
            stop_loss=float(payload["stop_loss"]),
            take_profit=float(payload["take_profit"]) if payload.get("take_profit") else None,
            quantity=int(payload["quantity"]) if payload.get("quantity") else None,
        )


def run(host: str = "127.0.0.1", port: int = 8000) -> None:
    settings = get_settings()
    print(f"Starting {settings.app_name} on http://{host}:{port}")
    ThreadingHTTPServer((host, port), TradingRequestHandler).serve_forever()


if __name__ == "__main__":
    run()
