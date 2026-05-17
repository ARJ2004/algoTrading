# AI-Driven NIFTY Options Paper Trading Platform

This repository implements the PRD2 application as an expanded paper-trading product slice with a Python backend and a React + Vite frontend. Live trading remains deliberately disabled behind readiness gates until broker order execution, KYC/consent, kill-switches, and regulatory checks are complete.

## Completed capability map

- Paper account creation with configurable capital allocation.
- Risk-based position sizing with default 2% per-trade risk, max daily loss, max open-position, minimum AI confidence, slippage, and fee controls.
- Simulated order execution with fills, slippage, brokerage-style fees, positions, realized/unrealized P&L, equity snapshots, and performance metrics.
- Stop-loss/take-profit monitoring through `/api/paper/orders/check-exits`.
- AI signal orchestration with market snapshots, audit correlation IDs, mock AI, and Ollama-compatible provider support.
- Market-data layer with mock provider, indicator engine, and an Upstox quote adapter boundary.
- Backtesting workflow that replays deterministic candles through the same paper-trading simulator.
- Alerts, audit logs, compliance reports, exportable JSON snapshots, live-trading readiness checklist, and safety guardrails that keep live order placement disabled.
- React + Vite dashboard for capital allocation, signal generation, paper simulation, exit checks, backtesting, alerts, positions, and live readiness.

## Stack

### Backend

- Python 3.11+
- Python standard-library HTTP server (`ThreadingHTTPServer`) for this dependency-light environment
- Dataclasses for domain models
- In-memory repository abstraction, ready to replace with PostgreSQL/Redis adapters
- Ollama-compatible AI adapter
- Upstox market-data adapter boundary
- Pytest and Ruff for tests/linting

### Frontend

- React
- Vite
- Vanilla CSS modules/stylesheet
- Browser Fetch API
- `lucide-react` icons

## Quick start

Backend:

```bash
python -m pytest
python -m app.main
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Open:

- React dashboard: <http://127.0.0.1:5173/>
- Backend health check: <http://127.0.0.1:8000/api/health>

If you run `npm run build`, the backend can serve the built frontend from `frontend/dist` at <http://127.0.0.1:8000/>.

## Configuration

```text
APP_NAME=AI NIFTY Options Paper Trading
ENVIRONMENT=local
DEFAULT_RISK_PER_TRADE_PCT=2
DEFAULT_SLIPPAGE_PCT=0.1
DEFAULT_FEE_PER_ORDER=20
MAX_OPEN_POSITIONS=5
MIN_AI_CONFIDENCE=0.55
MARKET_DATA_MAX_AGE_SECONDS=60
UPSTOX_CLIENT_ID=
UPSTOX_CLIENT_SECRET=
UPSTOX_REDIRECT_URI=
UPSTOX_ACCESS_TOKEN=
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1
OLLAMA_API_KEY=
AI_PROVIDER=mock
MARKET_PROVIDER=mock
```

Set `AI_PROVIDER=ollama` to use Ollama. The optional `OLLAMA_API_KEY` supports hosted/proxied Ollama-compatible deployments. Set `MARKET_PROVIDER=upstox` and provide `UPSTOX_ACCESS_TOKEN` to use the Upstox quote adapter.

## Key API endpoints

- `POST /api/paper/accounts`
- `PATCH /api/paper/accounts/{account_id}/risk`
- `POST /api/ai/signals/generate`
- `POST /api/paper/orders/simulate`
- `POST /api/paper/orders/check-exits`
- `GET /api/paper/performance/{account_id}`
- `GET /api/market/quote?symbol=...`
- `GET /api/market/indicators?symbol=...`
- `POST /api/backtests`
- `GET /api/live/readiness`
- `GET /api/audit/logs`
- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/reports/compliance/{account_id}`
- `GET /api/persistence/export`
- `POST /api/persistence/save`

## Safety model

The AI never executes orders directly. Signals are stored and audited, then each simulated trade must pass risk validation. Live trading is not implemented as an executable broker order path; `/api/live/readiness` reports the checklist that must pass before future enablement.

## Remaining production hardening

This code now covers the application phases as an end-to-end MVP, but production deployment should still add durable PostgreSQL/Redis storage, real auth/KYC, complete Upstox MCP/WebSocket/historical data integration, richer options-chain analytics, full OpenAPI validation, observability, deployment manifests, and formal regulatory review.
