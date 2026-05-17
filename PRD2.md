# AI-Driven Options Trading Platform (NIFTY 50): Product Requirements Update

## Executive Summary  
This platform enables users to engage in algorithmic trading of NIFTY 50 options with AI assistance.  A user first specifies an **investment budget** (e.g. ₹100,000), and the system automatically sizes and executes trades within that capital.  Two modes are offered: **Paper Trading** (simulated) and **Live Trading** (actual orders via broker).  In Paper mode (MVP focus), the AI will suggest trades using the allocated capital, simulate their execution (with realistic slippage and fees) and display hypothetical profit/loss.  In future releases, **Live mode** will actually place orders through the user’s broker API.  Importantly, the AI itself is not trained in-house; instead the platform will call an external AI service (via a provided API key) with market data and account context.  The AI model returns trade signals and rationales.  For example, the system might send a JSON payload of recent prices and indicators to an LLM or specialised model, which responds with “BUY/SELL” signals and explanation.  (Upstox’s Model Context Protocol shows how GPT-like AI can link to trading data【62†L72-L80】.)  

The user starts in **Paper Trading mode**: they enter their capital and enable the AI to “mock trade” historical or live data.  Each simulated trade will be sized by a risk-management rule (e.g. not risking more than ~2% of capital per trade【69†L300-L308】), and filled at the current price plus a small slippage.  This lets the user see the potential outcome without real risk.  Real mode (for later) would simply re-use the same AI signals to place actual orders via the broker.  Initially, the focus is on robustly implementing and backtesting the Paper mode with full business logic, including position sizing, slippage modelling, and trade simulation.  

## Product Vision  
The platform’s vision is to bring advanced, **AI-driven options trading** to retail users in a compliant, user-friendly way.  By inputting a capital amount and receiving data-backed signals, traders can test sophisticated strategies without manual effort.  The product democratises algo trading: even non-technical users can deploy capital, view real-time analytics, and let the AI suggest trades, all within the same interface.  The ultimate goal is to improve retail performance (for example, overcoming the historical 90% loss rate in F&O【2†L95-L103】) while ensuring full transparency.  Explainable AI is central: every AI-generated trade will be accompanied by an explanation (e.g. referencing RSI or volatility), so users trust the system’s decisions.  

## Target Users and Personas  
- **Retail Options Trader:** A self-directed investor (25–45) trading NIFTY options. Has some market knowledge but limited experience with algo tools. Seeks automated signals to enhance returns. Values an intuitive UI and clear explanations of trades.  
- **Quant Enthusiast:** A user familiar with backtesting and technical indicators. Wants to test and refine strategies using paper trading. Will input custom stop-loss or sizing parameters. Appreciates detailed performance metrics (Sharpe, drawdown).  
- **Performance-Seeker:** A trader focusing on portfolio growth. Uses Paper mode to learn and validate strategies. Later may switch to Live mode for actual profit. Expects rigorous risk controls (e.g. “no more than 2% risk per trade”【69†L300-L308】).  
- **Tech-Savvy Novice:** Has capital to invest but limited trading experience. Relies heavily on AI-generated signals. Needs assurance (clear audit log, simulation results) to build confidence.  

## Core Features  

- **Capital Allocation & Position Sizing:** The user enters the total amount they want to deploy (in ₹). The system then automatically determines position sizes. For example, it may cap risk at ~1–2% of capital per trade【69†L300-L308】. This ensures trade sizes scale with available funds and risk tolerance. If the user has ₹100,000 capital, risking 2% means at most ₹2,000 risk per trade. Stop-loss levels (set by volatility or ATR) and margin requirements are used to compute quantity.  

- **Trading Modes (Paper vs Live):**  
  - *Paper Trading (Simulation):* AI-generated trades are executed on a virtual portfolio. The engine applies realistic assumptions – e.g. fills at market price plus small slippage (see below) and deducts brokerage fees – to compute a hypothetical P&L. Users see how the AI strategy would have performed. All trades are clearly marked as “simulated.”  No real money is used.  
  - *Live Trading (Future):* In a later phase, the platform will place real orders through the connected broker API. The same trade-sizing and signals would be used, but with actual execution. Live mode requires additional compliance (e.g. dual confirmation) and will only be enabled once Paper mode is validated.  

- **Live Market Data Ingestion:** Streaming NIFTY index and options data from a broker or data provider (via WebSockets). Upstox’s sandbox, for instance, simulates live quotes for developers【56†L77-L85】. In Paper mode we can use either historical data or live feed in replay.  

- **Real-time Analytics & Indicators:** The platform computes and presents key metrics on-the-fly. This includes technical indicators (e.g. moving averages, RSI, MACD, Bollinger Bands) and options-specific metrics (implied volatility, Greeks). These are shown on charts and fed to the AI. We will incorporate well-known signals used in Indian options trading: for example, implied volatility (IV), put-call ratio, open interest, max-pain levels, as well as RSI and VWAP【71†L178-L186】. The AI model can use these indicators in its analysis. For instance, high IV or a bullish PCR might influence a “buy call” decision.  

- **AI Trade Signal Generation (Cloud-based):** Using an external AI model (e.g. GPT-like service via provided API key), the system sends market context and receives trade suggestions. The integration works as follows: the backend packages recent price history, computed indicators, and user capital into a structured request. The cloud model (with the user’s key) returns a response like `{action:"BUY", symbol:"NIFTY27APR23000CE", qty:10, confidence:0.85, rationale:"RSI was oversold and IV is low"}`. Upstox’s MCP documentation shows one approach to feed account-specific data into an AI assistant【62†L72-L80】. Here, we’ll define a JSON contract: input fields (e.g. timestamped price candles, SMA values, available margin) and output fields (signal, instrument, size, explanation). The backend will parse the response to enact trades or update simulations.  

- **Order Execution:** In Paper mode, orders from the AI signals are executed on the virtual account by the simulation engine. In Live mode, these signals invoke actual broker orders (e.g. Upstox “placeOrder” API). All orders include required tags (e.g. unique Algo ID). The system supports market and limit orders.  

- **Portfolio & Risk Management:** The user’s portfolio (paper or real) is tracked continuously. We display positions, notional and percent P&L, Greeks, and margin usage. Risk rules (e.g. stop-loss at certain loss threshold) can be set. If a paper-trade position hits a stop, the platform simulates the exit. The allocation logic from above ensures diversification (e.g. not exceeding a max number of concurrent positions, or margin usage).  

- **Backtesting & Paper-Trade Simulation Engine:** A core component is a backtester/simulator. In backtesting, historical price data is used to replay trades: the strategy (AI or defined rules) is run on past data, and trades are logged. In live Paper mode, current streaming data is fed in real-time. In both cases, the engine applies realistic execution assumptions: **slippage** (small price difference) and commissions. For example, if the AI signals a market buy at price P, the simulator might fill it at P*(1+ε), where ε is a small slippage (perhaps 0.1–0.5%).  (Slippage – the difference between expected and executed price – is a known trading cost【66†L99-L107】.) Each trade’s P&L is calculated after slippage and fees, and the virtual account is updated. This produces metrics like cumulative profit, drawdown, and Sharpe.  

- **Alerts & Notifications:** Users can set alerts (e.g. “Notify if cash falls below 80% of initial capital”, or “trade executed”). The system will also notify on key events (AI had no signal, simulation completed, etc.).  

- **Dashboards:** Interactive UI with charts of the simulated portfolio equity curve, positions grid, indicator overlays, etc. All simulated trades are listed with time/price and P&L. The dashboard clearly indicates “Paper Trading Mode” to avoid confusion.  

- **Audit Logs & Explainability:** The platform logs every action: each AI prediction, simulated trade (timestamp, price, qty), and user action. This creates a full audit trail for transparency. Additionally, each AI-generated signal includes an explanation (e.g. “Signal triggered because RSI crossed below 30” or “IV dropped to support level”), enabling users and auditors to understand the rationale. This aligns with best practices for algorithmic trading transparency.  

## User Flows and UI Components  

- **Initial Setup:** The user signs up and completes KYC (PAN/Aadhaar). They then navigate to a “Capital Allocation” screen where they input the amount they wish to deploy (e.g. ₹100,000) for a given session or strategy.  

- **Mode Selection:** The dashboard offers a toggle: *Paper Mode* or *Live Mode*. Initially, only *Paper Mode* will be enabled. Selecting Paper Mode will route trades through the simulation engine; selecting Live (once available) will route them to the broker.  

- **Dashboard:** After entering capital, the main dashboard shows the virtual cash (initial capital), current holdings (if any), and real-time NIFTY index. Widgets display available margin (simulated), used margin, and account value. A chart of simulated equity over time will update as trades are simulated.  

- **Market View and Analytics:** The UI includes a live NIFTY chart with applied indicators (e.g. MA lines, RSI panel). Users can hover or click to see indicator values at any time. A watchlist displays relevant option symbols and their real-time quotes (fetched from the data API).  

- **AI Signal Panel:** A section lists the latest AI-generated signals (“Potential Trades”). Each entry shows trade details, size, and the AI’s confidence or rationale. Users can click “Run Simulation” to execute the suggested trades in the paper account. They can also adjust parameters (e.g. smaller size) if desired.  

- **Trade Execution Flow (Paper Mode):** When the AI indicates a trade (or on user command), the system simulates the order. The user sees a confirmation: “Buy 10 lots at ₹X each – simulated”. The simulator immediately calculates slippage and executes the trade, updating the virtual portfolio. The trade appears in the “Orders & Trades” table along with simulated fill price.  

- **Backtesting Workflow:** Separately, the user can go to a Backtesting page, select historical dates, and run the AI strategy on past data. Upon completion, the system shows the backtest results: a P&L chart, key statistics (profit %, Sharpe, max drawdown), and list of trades.  

- **Settings/Config:** Users can adjust position sizing rules (e.g. percent risk), view their provided AI API key, and connect/disconnect the broker account for future live mode.  

Wireframes would include a main trading dashboard with clear mode indicators, forms for capital input, and panels for charts, signals, and simulated trades. All in-app messaging will clarify that Paper Mode is simulated (e.g. watermark or header “Simulated Portfolio”).

## Data Model (Database Schema)  

We extend the schema to support simulation:  

| **Table**        | **Key Fields (PK)**        | **Notes**                                                      |
|------------------|----------------------------|---------------------------------------------------------------|
| users            | **user_id**                | Customer info (incl. KYC status, PAN)                         |
| demo_accounts    | **demo_id**                | Links user_id, allocated_capital (₹), mode (paper/live)        |
| orders           | **order_id**               | user_id (FK), symbol, side, quantity, price, status, executed_at |
| trades           | **trade_id**               | order_id (FK), fill_price, fill_qty, timestamp, slippage_pct   |
| positions        | **position_id**            | user_id (FK), symbol, quantity, avg_price, current_value      |
| signals          | **signal_id**              | user_id (FK), symbol, side, recommended_qty, timestamp, rationale |
| alerts           | **alert_id**               | user_id (FK), message, condition, triggered_at, resolved       |
| backtests        | **backtest_id**            | user_id, strategy_id, start_date, end_date, result_metrics (JSON) |
| logs             | **log_id**                 | user_id (nullable), level, source, message, timestamp         |

The new **demo_accounts** table stores the user’s chosen capital and current paper mode status. **trades** records include a slippage percentage column to model the difference between requested and fill price.  

## API Contracts  

We add endpoints and data contracts for the new features:  

- **POST /simulation/start** – Start a new simulation with `{ user_id, capital_amount, mode:"paper" }`. Returns a simulation ID and initial portfolio state.  
- **POST /simulation/run** – Run an AI-driven simulation step. Takes `{ simulation_id, market_data: [ {timestamp, price, volume, indicators...} ], user_metrics: {...} }`. The system packages this into the AI request.  
- **POST /ai/signal** – (Internal) Sends a request to the external AI service with payload `{ key: AI_API_KEY, market_history: [...], indicators: {...}, allocated_capital: X }`. Expected response `{ decision: "BUY"|"SELL"|"NONE", symbol, qty, explanation }`.  
- **POST /orders/paper** – Execute a simulated order in the paper account. Body: `{ simulation_id, symbol, side, qty, limit_price? }`. Returns a fill confirmation including `{ fill_price, slippage_pct, executed_qty }`.  
- **GET /simulation/status** – Retrieves current portfolio P&L and positions for a simulation.  
- **Webhooks/Callbacks:** If the AI service supports webhooks, the platform may receive asynchronous responses. Otherwise, polling is used.  

The AI integration specifically expects the user’s AI API key to be securely stored and included in calls.  The JSON payload to the AI will include recent price series and computed indicators (RSI, ATR, IV, etc.).  The response must include both the trade signal and a textual rationale for explainability.  

All APIs require authentication and rate limits.  In paper mode, we simulate orders locally (no broker call). In live mode (future), the `POST /orders` endpoint would call the broker’s trade API.  

## Technical Architecture  

```mermaid
graph LR
    Frontend[React+Vite UI] -->|REST/WSS| Backend[Node.js/Express]
    Backend -->|Reads/Writes| Database[(PostgreSQL)]
    Backend -->|Streams| MarketAPI[Market Data API (WebSocket/REST)]
    Backend -->|Broker Sandbox| BrokerAPI[Broker API (Upstox Sandbox)]
    Backend -->|AI Requests| AIService[External AI Model (Cloud)]
    Backend -->|Logs| Logger[(Logging/Monitoring System)]
```

- **Frontend:** Handles UI/UX, collects user input (capital, mode), shows charts and tables. Communicates via WebSocket for live data and REST for commands.  
- **Backend:** Orchestrates trading logic. Key modules include:  
  - *Simulation Engine:* Maintains paper account, applies trades, calculates P&L with slippage.  
  - *AI Adapter:* Calls the cloud AI API (with the user’s key) and parses its response into trade instructions.  
  - *Trade Executor:* Sends orders to the Broker API (sandbox or live) or to the simulation engine.  
  - *Risk Manager:* Enforces capital and size rules (e.g. 2% risk limit).  
- **Database:** Stores user info, simulation state (capital remaining, positions), logs of trades and signals.  
- **MarketAPI / BrokerAPI:** We will use sandbox/testing feeds. For instance, Upstox provides a sandbox for quotes and orders【56†L77-L85】. In simulation we may also replay historical data.  
- **AIService:** An external LLM or predictive model. The backend securely transmits market snapshots; receives actionable signals in response. The Upstox MCP integration guides how to share market context with GPT-like models【62†L72-L80】.  

All components run in a cloud environment. The backend and simulation engine will be stateless (caching current sim state in the DB). The AIService is external (e.g. OpenAI, Claude, or a custom LLM). The architecture ensures that user API keys (for broker or AI) are never logged or exposed, and that simulated trading never interacts with the live market in Paper mode.

## Deployment and Scaling Plan  
- **Sandbox Environment:** Initially deploy using broker sandbox APIs (e.g. Upstox sandbox) to eliminate financial risk. No real money is moved during MVP.  
- **Containerized Services:** Use Docker and Kubernetes to run services. Auto-scale simulation and backend nodes based on load (number of concurrent users/simulations).  
- **Database:** Use a managed Postgres with multi-AZ for high availability. Use read replicas if simulation queries become heavy.  
- **Logging/Monitoring:** Collect metrics (number of simulated trades, API latency, error rates). Use Prometheus/Grafana. Provide alerts for unusual situations (e.g. simulation balances going negative).  
- **CI/CD:** Fully automate testing. Include automated backtest runs and simulation tests to ensure accuracy of profit calculations and AI responses.  

## Latency and Throughput Targets  
- **Simulation Speed:** The system should process AI signals and simulate trade execution quickly. Target sub-second response for each AI call (depending on external AI latency).  
- **Data Updates:** Market data should be ingested at least once per second in Paper mode; trade simulation should occur in near real-time.  
- **Concurrency:** The platform should support tens of simultaneous simulations (each user with their own paper portfolio) without degradation.  

## Data Sources and Providers  

| Provider             | Data / API             | Features                        | Cost / Notes                                                                 |
|----------------------|------------------------|---------------------------------|------------------------------------------------------------------------------|
| **Upstox (Sandbox)** | NIFTY & options feed   | Free REST/WebSocket, sandbox    | Upstox offers a sandbox to simulate quotes and orders【56†L77-L85】. All APIs (market data, historical, order) can be tested without risk. |
| **Zerodha (Kite)**   | NIFTY & options feed   | REST/WebSocket (paid), demo UI  | No official paper-API: only a dummy Kite web demo exists【58†L95-L100】. Kite Connect API requires a real account (₹500/m for live feed)【19†L107-L114】. |
| **Angel One**        | NIFTY & options feed   | SmartAPI (free, WebSockets)     | Angel’s API provides real-time and historical data (free for account holders)【21†L115-L123】. No known sandbox. |
| **5paisa**           | NIFTY & options feed   | XTS API (free for clients)      | Offers streaming API; presumed free. No official sandbox documentation found. |
| **TrueData**         | Global market feeds    | Low-latency ticks, Greeks       | Paid service; robust data.                                                      |

Upstox sandbox is the most straightforward for initial development (no cost). Zerodha’s lack of an API demo means we cannot auto-simulate on its platform. In Paper mode, we may choose to use historical ticks or Upstox sandbox data.  

## Costs  
- **API/Data:** We will primarily use Upstox sandbox (free). Other feeds (Angel, 5paisa) are also free for user accounts.  
- **Brokerage (simulated):** Upstox’s live brokerage is ₹20 per order, but in simulation we’ll apply a comparable flat fee or percentage per trade.  
- **AI Service:** The user’s AI API key (e.g. OpenAI) may incur costs per call. This cost is external to our platform. We should log usage for cost monitoring.  
- **Infrastructure:** Cloud services (compute, DB) – moderate cost at MVP scale.  

## Regulatory Compliance (SEBI/Exchange)  
- **Algo Trading Regulations:** All actual trade orders (future Live mode) will be placed via a registered broker, following SEBI’s retail algo framework. Each API order will include a unique Algo ID, and brokers’ audit logs will record time/price【46†L201-L209】. While Paper mode is simulated, we will still obtain user KYC (PAN mandatory【14†L80-L88】) to keep usage legitimate and ready for any transition to Live mode.  
- **Disclosure:** Paper trading results are for simulation only. We will clearly label outputs as “simulated performance”, and include disclaimers that actual trading may differ. This transparency aligns with responsible AI guidelines.  
- **KYC/AML:** As with any trading platform, user identity (PAN/Aadhaar) is verified up front. Since no real money is used in Paper mode, financial regulations like PMLA are not triggered, but storing KYC data complies with privacy rules.  
- **Trade Limits:** To avoid regulatory thresholds, the system will not auto-place more than 10 orders/second by design (SEBI requires exchange approval above that limit【46†L179-L187】).  
- **Risk Controls:** Automated trade sizing (e.g. max 2% risk per trade【69†L300-L308】) serves both risk management and regulatory expectations that clients not over-leverage.  
- **Data Licensing:** Market data used in Paper mode (e.g. live quotes) comes via authorized APIs. For any third-party data shown, we ensure licensing compliance (e.g. using Upstox’s licensed feed).  

## Security and Authentication  
- **API Keys:** Users provide an AI API key which the backend securely stores and uses for calls. It is never logged in plain text.  
- **2FA:** Enforce two-factor authentication for user login and sensitive actions.  
- **Encryption:** All communications (browser, AI calls, broker calls) use HTTPS/TLS.  
- **Segmentation:** Paper-mode and Live-mode environments are logically separated to prevent any cross-over of simulated and real funds.  
- **Explainability:** Each AI decision is logged with input snapshot and output. This allows audits of “why” a trade was suggested.  

## AI Integration and Inputs  
We do not train our own ML model. Instead, we use a cloud AI (LLM) as follows:  
- **Inputs to AI:** A structured JSON including recent price series (e.g. last 100 bars of NIFTY futures and options), calculated indicators (SMA, RSI, ATR, implied volatility, put-call ratio, etc.【71†L178-L186】), and the user’s capital allocation. Optionally news sentiment or fundamental prompts can be included.  
- **Calling the AI:** The backend sends this payload to the AI endpoint using the user’s provided API key. For example, it might call OpenAI’s ChatGPT or Claude via their REST API. The payload may be prefixed with a system prompt like “You are a trading assistant” to guide the model.  
- **Output from AI:** A JSON with fields such as `action` (BUY/SELL/NONE), `symbol`, `quantity`, `confidence`, and `rationale`. E.g. `{"action":"BUY","symbol":"NIFTY28APR23000CE","qty":5,"confidence":0.76,"explanation":"RSI is oversold and IV is rising"}`.  
- **Integration Contract:** This request/response schema is part of our spec. We must handle cases like “no trade recommended”. We also set a timeout so the frontend gets a prompt answer (e.g. default to no trade if AI is slow).  

This design leverages the concept of Upstox’s MCP, where a model is context-aware of trading data【62†L72-L80】, but here we implement it as a direct API call from backend to the AI provider.

## Backtesting & Simulation Engine  

- **Historical Backtests:** Users can run historical tests by selecting a date range. The engine fetches historical NIFTY data and replays the AI signals over that period. Trades are simulated with the same slippage and sizing rules as in live Paper mode.  
- **Slippage Modelling:** We incorporate slippage in each simulated trade. Slippage is the deviation between expected and executed price【66†L99-L107】. For simplicity, we might assume a constant slippage of e.g. 0.1–0.5%, or derive it from historical bid-ask spreads. This cost (positive or negative) is applied to the fill price in the simulation.  
- **Commissions and Fees:** We deduct a flat commission per trade (or % of notional) to mimic broker fees. This ensures the simulated P&L is realistic.  
- **Stop-Loss and Exit:** Trades may include stop-loss or take-profit orders. In simulation, if price hits those levels, the engine exits the position and records the result.  
- **Metrics:** After simulation/backtest, the engine computes performance metrics: total return, max drawdown, Sharpe ratio, win/loss rate, etc. Users can review trade-by-trade logs.  

## Monitoring, Explainability, and Compliance (Paper Trading)  

- **Performance Monitoring:** We track simulation health (e.g. cumulative P&L vs. time) and system metrics (AI call latency, error rates). If the simulation logic fails (e.g. resulting in negative capital unexpectedly), alerts are raised.  
- **Explainability:** Every AI suggestion is accompanied by the `rationale` text. We log inputs (price & indicator snapshots) so that a compliance audit could reconstruct any decision. This mitigates “black box” concerns. In reports, we highlight which indicators were most influential for a signal.  
- **Audit Logs:** As with live trading, we keep a complete audit trail of actions in Paper mode. This includes user inputs, AI outputs, simulated order details, and portfolio changes. Though SEBI does not regulate virtual trades, these logs ensure transparency and build trust.  
- **User Disclaimers:** The UI and user agreement will clearly state that Paper mode results are hypothetical. This protects both the user and the company from misunderstandings.  

## MVP Scope and Roadmap  

- **MVP (Q3 2026):** Implement user capital entry, basic position sizing (e.g. fixed 2% risk rule【69†L300-L308】), data ingestion for NIFTY index, an initial set of indicators (SMA, RSI, IV, PCR【71†L178-L186】), and a stub AI integration (mock responses). Build the paper-trade simulator to execute these mock trades with slippage. UI includes mode toggle and results display.  
- **Phase 2 (Q4 2026):** Integrate real AI API (with user-provided key). Populate input data (e.g. candles + indicators) for each AI call. Use Upstox sandbox for data if needed【56†L77-L85】. Add real-time paper trading: as data streams in, the AI periodically gives signals and simulation engine trades. Add backtesting UI.  
- **Phase 3 (Q1 2027):** Refine risk rules (user-configurable risk %), add more technical indicators (MACD, Bollinger, OI, Greeks). Validate simulation results against historical “ground truth” for accuracy.  
- **Phase 4 (Q2-Q3 2027):** Develop Live Trading mode. This requires final broker API integration and additional compliance checks. By Q3 2027, roll out Live mode as a beta for power users, while continuing Paper mode support.  

**Feature Prioritisation:**  
Features are ranked high (H), medium (M), or low (L) priority in MVP:  

| Feature                            | Priority |
|------------------------------------|----------|
| Capital input & position sizing    | H        |
| Paper trading simulation engine    | H        |
| AI signal integration (stub)       | H        |
| Real-time NIFTY data ingestion     | H        |
| Backtesting (historical simulation)| M        |
| Additional indicators (MACD, etc.) | M        |
| Explanatory UI (rationale text)    | M        |
| Alerts and notifications           | L        |
| Live trading mode (broker orders)  | L        |

## Key Performance Indicators (KPIs)  

- **Simulation Accuracy:** Consistency of simulated P&L (Paper mode) with actual market moves. Tracked by comparing sample simulated runs to actual data.  
- **User Engagement:** Number of users running simulations (paper trades) per month. Retention of users after 30/90 days.  
- **Signal Utilisation:** Percentage of AI-generated signals that are executed in simulations.  
- **System Reliability:** Uptime (target ≥99.9%), average response time for AI calls (<1s), error rate (<1%).  
- **AI Performance:** For internal evaluation, track simulated strategy Sharpe ratio, max drawdown, and win rate. These indicate model effectiveness (though not user metrics).  
- **Regulatory:** Zero instances of compliance breaches (all KYC complete, logs intact).  

## Assumptions  

- **Trading Capital Entry:** Users can allocate a fixed capital (in INR). They will not add or withdraw funds dynamically in Paper mode.  
- **Risk Rule:** We assume a default “2% per trade” risk rule【69†L300-L308】 unless user configures otherwise.  
- **Market Hours:** Using NSE derivatives hours (09:15–15:30 IST)【51†L1113-L1116】. Simulation will only process trades within these hours.  
- **Slippage:** We assume a nominal slippage (e.g. 0.1% of price) on all simulated market orders. This accounts for bid-ask spread and latency (see slippage definition【66†L99-L107】).  
- **Broker Integration:** For MVP, we assume Upstox sandbox APIs for data and (future) live orders. Other brokers could be added later.  
- **AI Model:** The provided AI API is assumed to understand the trading context. No model training is done on our side. The AI key is valid and has sufficient quota.  
- **Indicators:** We will compute at least RSI, SMA/EMA, and implied volatility (IV). Options-specific signals like PCR and open interest may be fetched from data APIs or calculated.  
- **Regulations:** Paper trading is considered risk-free usage. Users have their own risk tolerance and accept simulation results as hypothetical.  

**Sources:** We have incorporated brokerage and regulatory info (e.g. Upstox sandbox【56†L77-L85】, Zerodha paper trading【58†L95-L100】), trading best practices (position sizing【69†L300-L308】), and strategy development guidelines (slippage modeling【66†L99-L107】, option indicators【71†L178-L186】). SEBI guidelines (audit trail, order limits) from prior research remain in force. The AI integration follows the recommended approach of using external LLMs (e.g. via Upstox MCP【62†L72-L80】) rather than in-app training. 

