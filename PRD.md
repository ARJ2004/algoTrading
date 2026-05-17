# Paper-Trading Feature (AI-Driven): Summary  

## Executive Summary  
The Paper-Trading module lets users simulate AI-driven trades on virtual capital. The user specifies a **capital amount** and toggles **Paper** or **Live** mode. In Paper mode, the AI analyses market trends and places trades on a virtual portfolio, showing hypothetical P&L. Trades are sized by risk rules (default ~1–2% of capital per trade【69†L300-L308】) with checks on margin and max concurrent positions. A slippage model and commission are applied to fills. AI signals are obtained via a cloud API (user’s key); the request JSON includes recent price/indicator data and capital, and the response JSON includes action, symbol, quantity, confidence and rationale. We define minimal APIs (e.g. `POST /simulation/start`, `POST /ai/signal`, `POST /orders/paper`, `GET /simulation/status`) and data schema extensions (e.g. a `demo_accounts` table with simulation ID, capital, slippage_pct). Compliance measures include KYC (PAN) checks, audit logs, clear “simulated” labelling, and enforcing SEBI limits (e.g. <10 orders/sec【46†L179-L187】). The MVP goal is end-to-end Paper mode using a broker sandbox (e.g. Upstox) or historical data, with explainable AI output.  

## User Flow and Behaviour  
- **Capital Input:** Upon setup, the user enters an investment budget (e.g. ₹100,000). This sets the notional pool for the simulation.  
- **Mode Toggle:** The user can toggle between *Paper* (simulation) and *Live* modes. Initially only Paper mode is active. The UI clearly indicates “Simulation Mode” when paper-trading.  
- **Simulation Execution:** When the AI suggests a trade, the system executes it on the virtual portfolio. The user can also step through backtests on historical data. All actions (orders, fills, P&L) update in real time on the dashboard.  

## Position Sizing and Risk Rules  
- **Default Rule:** By default the platform limits risk to ~**2% of capital per trade**【69†L300-L308】. For example, with ₹100,000 capital, at most ₹2,000 is at risk on any single trade (accounting for stops).  
- **Stop-Loss Calculations:** Trade size is determined by where a stop-loss would be placed; quantity = (Risk Amount) / (Entry Price – Stop Price). Users may set maximum position sizes or margin limits.  
- **Concurrent Positions:** To manage risk, there is a cap on concurrent open positions (configurable, e.g. max 3-5) and a check that margin usage remains below the allocated capital.  
- **SEBI Order Limit:** The simulator will not place orders at a rate exceeding 10 orders per second to avoid regulatory issues【46†L179-L187】.  

## Simulation and Fill Rules  
- **Market Hours:** Trades are only executed within NSE F&O hours (09:15–15:30 IST)【51†L1113-L1116】.  
- **Slippage:** Each simulated order fill includes slippage. We assume a small slippage (e.g. **0.1%–0.2%** of price) to model market impact. (Slippage is the difference between the expected price and actual fill【66†L99-L107】.)  
- **Commission:** A flat commission per trade (or percentage) is subtracted from each simulated P&L to reflect broker fees.  
- **Fill Logic:** Market orders are filled immediately at the current price ± slippage. Limit orders fill if the market touches the limit price. Partial fills are not modelled (all-or-none fills).  
- **Portfolio Update:** After each simulated trade, the virtual portfolio (cash, positions) is updated. The system tracks running P&L, peak drawdown, and equity curve for performance metrics.  

## AI Integration & API Contract  
- **AI Request:** The backend calls the external AI service (e.g. Ollama/Grok) with a JSON payload, including fields like:  
  - `prices`: recent time-series (timestamped close/high/low/volume for relevant instruments).  
  - `indicators`: precomputed values (RSI, SMA, ATR, implied volatility, put-call ratio, etc.).  
  - `capital`: user’s available capital (for sizing).  
  - `positions`: current positions (if any).  
- **AI Response:** The AI returns a JSON, e.g.: `{"action":"BUY","symbol":"NIFTY25MAY18000PE","qty":10,"rationale":"RSI oversold, PCR bullish"}`. Key fields are **action** (BUY/SELL/NONE), **symbol**, **quantity**, **confidence** (optional), and **explanation** text.  
- **Timeout/Retry:** The AI call should timeout after a few seconds (e.g. 5s) to keep the UI responsive. On timeout or error, the platform treats it as “no trade”. We may retry once.  
- **API Endpoints:** Minimal endpoints include:  
  - `POST /simulation/start` – begins a paper-trade session with given capital.  
  - `POST /ai/signal` – (internal) relays a JSON payload to the AI model.  
  - `POST /orders/paper` – executes a simulated order (input: `{symbol,side,qty,limit?}`). Returns `{fill_price,slippage_pct}`.  
  - `GET /simulation/status` – returns current virtual portfolio and P&L.  

- **Security:** The user’s AI API key is stored securely (encrypted) and included in the request headers to the AI service. Backend logs do not record the raw key. All communications are over HTTPS.  

## Data Model Additions  
- **demo_accounts:** New table linking `user_id` to `simulation_id`, `capital_allocated`, and mode (paper/live).  
- **slippage_pct:** In the `trades` table, add a `slippage_pct` field to record each simulated fill’s slippage (for audit).  
- **positions_tracked:** Existing positions table must be updated by the simulator after each trade.  
- **Unique Simulation ID:** Each paper session gets an ID used in APIs and logs.  

## Compliance and Governance  
- **KYC/Registration:** Paper mode still requires basic user KYC (PAN, email) to prevent abuse. The platform will label all outputs as *simulated* and include a disclaimer.  
- **Audit Logs:** Every AI signal and simulated order is logged (with timestamp, inputs, outputs) to enable traceability. This aligns with SEBI’s “audit trail” requirement for algorithmic trades【46†L201-L209】, even though no real funds are used.  
- **Regulatory Limits:** The system enforces SEBI’s algorithmic trading limits by design (e.g. no more than 10 order/sec【46†L179-L187】). Risk checks (max loss per day) are monitored in simulation.  
- **Data Privacy:** Market data is obtained via authorised APIs. User credentials and API keys are stored securely. No sensitive financial data is published.  

## MVP Scope & Acceptance  
- **Working Criteria:** End-to-end paper mode must function: user allocates capital, AI calls return signals, simulated trades execute, and a final P&L is shown. Trade logs include explanation from the AI (for audit).  
- **Data Source:** Initially use Upstox’s sandbox API for live data and order simulation【56†L77-L85】; alternately use historical replay. Successful simulation with either is acceptable.  
- **Acceptance Tests:** Demonstrate a sample session: user sets capital, the AI suggests a trade, the system executes it virtually (showing fill price with slippage), and updates the simulated portfolio. The AI’s JSON response must include a non-empty `rationale`.  
- **Performance:** Simulation run should complete within a few seconds after each AI signal. The service should handle at least 5 concurrent paper-trade sessions without errors.  

## Broker Data Providers (Sandbox/API)  

| Provider            | Data Access          | Pros                                   | Cons                                              |
|---------------------|----------------------|----------------------------------------|---------------------------------------------------|
| **Upstox Sandbox**  | Streaming + REST     | Free broker APIs, supports sandbox【56†L77-L85】 (simulate orders & market data) | Requires Upstox account; mostly NSE only.          |
| **Zerodha Kite Demo** | Dummy Web UI only   | Official NIFTY data (live) in demo site | No real API for paper trading【58†L95-L100】; only manual UI. |
| **TrueData**        | WebSocket/REST API   | Authorised NSE/BSE feed, real-time & historical【73†L238-L247】 | Paid service; integration effort for REST/WebSocket. |

_Pros/cons_: Upstox sandbox is ideal for end-to-end testing【56†L77-L85】. Zerodha offers a demo GUI but no API【58†L95-L100】. TrueData provides robust data (especially historical tick data)【73†L238-L247】 but at a subscription cost.  

## Architecture (Mermaid Diagram)  

```mermaid
graph LR
    UI[Frontend (React/Vite)] --> Backend[Backend (Node.js/Express)]
    Backend --> DB[(PostgreSQL DB)]
    Backend --> AI[AI Model Service (Cloud)]
    Backend --> MarketAPI[Market Data API]
    Backend --> SimEngine[Simulation Engine]
```

## Data Flow (Mermaid Diagram)  

```mermaid
graph TD
    MarketData[Market Data Feed] -->|quotes + indicators| Backend
    Backend -->|request (JSON)| AIService[AI Model]
    AIService -->|signal (JSON)| Backend
    Backend -->|simulate order| SimulationEngine
    SimulationEngine -->|update portfolio| Database[(PostgreSQL DB)]
```

**Assumptions:** Default slippage 0.1–0.2% per fill; commission = ₹20/order; max 5 open positions; market hours 09:15–15:30. These can be tuned later. 

