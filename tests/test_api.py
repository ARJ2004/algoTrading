import json
import threading
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

from app.main import TradingRequestHandler
from app.services.repository import repository


def setup_function() -> None:
    repository.reset()


def request(server: ThreadingHTTPServer, method: str, path: str, payload: dict | None = None):
    conn = HTTPConnection(server.server_address[0], server.server_address[1], timeout=5)
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    conn.request(method, path, body=body, headers=headers)
    response = conn.getresponse()
    data = json.loads(response.read().decode("utf-8"))
    conn.close()
    return response.status, data


def start_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), TradingRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def stop_server(server: ThreadingHTTPServer, thread: threading.Thread) -> None:
    server.shutdown()
    thread.join(timeout=5)


def test_health_endpoint() -> None:
    server, thread = start_server()
    try:
        status, data = request(server, "GET", "/api/health")
        assert status == 200
        assert data == {"status": "ok", "version": "0.2"}
    finally:
        stop_server(server, thread)


def test_account_signal_and_simulated_order_flow() -> None:
    server, thread = start_server()
    try:
        status, account = request(
            server,
            "POST",
            "/api/paper/accounts",
            {"user_id": "demo", "initial_capital": 100000},
        )
        assert status == 201

        status, signal = request(
            server,
            "POST",
            "/api/ai/signals/generate",
            {"account_id": account["id"], "symbol": "NIFTY26MAY24500CE"},
        )
        assert status == 201
        assert signal["action"] == "BUY"
        assert signal["rationale"]

        status, order = request(
            server,
            "POST",
            "/api/paper/orders/simulate",
            {
                "account_id": account["id"],
                "signal_id": signal["id"],
                "symbol": signal["symbol"],
                "side": signal["action"],
                "market_price": 125.5,
                "stop_loss": signal["stop_loss"],
                "take_profit": signal["take_profit"],
            },
        )
        assert status == 201
        assert order["status"] == "FILLED"

        status, performance = request(server, "GET", f"/api/paper/performance/{account['id']}")
        assert status == 200
        assert performance["trade_count"] == 1
    finally:
        stop_server(server, thread)


def test_backtest_alerts_and_live_readiness_endpoints() -> None:
    server, thread = start_server()
    try:
        status, backtest = request(
            server,
            "POST",
            "/api/backtests",
            {"user_id": "demo", "symbol": "NIFTY26MAY24500CE", "initial_capital": 100000},
        )
        assert status == 201
        assert backtest["status"] == "COMPLETED"
        assert "total_return_pct" in backtest["metrics"]

        status, readiness = request(server, "GET", "/api/live/readiness")
        assert status == 200
        assert readiness["enabled"] is False
        assert readiness["checklist"]["broker_order_adapter_implemented"] is False

        status, bootstrap = request(server, "GET", "/api/bootstrap")
        assert status == 200
        assert len(bootstrap["backtests"]) == 1
    finally:
        stop_server(server, thread)


def test_auth_compliance_report_and_snapshot_export() -> None:
    server, thread = start_server()
    try:
        status, registered = request(
            server,
            "POST",
            "/api/auth/register",
            {"email": "demo@example.com", "password": "password123"},
        )
        assert status == 201
        assert registered["user"]["email"] == "demo@example.com"
        assert registered["token"]

        status, account = request(
            server,
            "POST",
            "/api/paper/accounts",
            {"user_id": "demo", "initial_capital": 100000},
        )
        assert status == 201

        status, report = request(server, "GET", f"/api/reports/compliance/{account['id']}")
        assert status == 200
        assert report["paper_only"] is True
        assert report["live_readiness"]["enabled"] is False

        status, snapshot = request(server, "GET", "/api/persistence/export")
        assert status == 200
        assert "accounts" in snapshot["payload"]
        assert "audit_logs" in snapshot["payload"]
    finally:
        stop_server(server, thread)
