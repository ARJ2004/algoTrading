import React, { useEffect, useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { Activity, Bot, FlaskConical, ShieldCheck, Wallet } from 'lucide-react'
import './styles.css'

const api = async (path, options = {}) => {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options
  })
  const payload = await response.json()
  if (!response.ok) throw new Error(payload.detail || 'Request failed')
  return payload
}

function Metric({ label, value }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function JsonPanel({ title, value }) {
  return (
    <section className="card span-2">
      <h2>{title}</h2>
      <pre>{JSON.stringify(value, null, 2)}</pre>
    </section>
  )
}

function App() {
  const [capital, setCapital] = useState(100000)
  const [symbol, setSymbol] = useState('NIFTY26MAY24500CE')
  const [account, setAccount] = useState(null)
  const [signal, setSignal] = useState(null)
  const [performance, setPerformance] = useState(null)
  const [bootstrap, setBootstrap] = useState(null)
  const [backtest, setBacktest] = useState(null)
  const [compliance, setCompliance] = useState(null)
  const [snapshot, setSnapshot] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const latestPositions = useMemo(() => bootstrap?.positions || [], [bootstrap])
  const latestAlerts = useMemo(() => bootstrap?.alerts || [], [bootstrap])

  const refresh = async () => {
    const data = await api('/api/bootstrap')
    setBootstrap(data)
    if (account) {
      setPerformance(await api(`/api/paper/performance/${account.id}`))
    }
  }

  useEffect(() => {
    refresh().catch((err) => setError(err.message))
  }, [])

  const run = async (operation) => {
    setBusy(true)
    setError('')
    try {
      await operation()
      await refresh()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const createAccount = () => run(async () => {
    const created = await api('/api/paper/accounts', {
      method: 'POST',
      body: JSON.stringify({
        user_id: 'demo-user',
        initial_capital: Number(capital),
        risk_profile: {
          risk_per_trade_pct: 2,
          max_daily_loss_pct: 5,
          max_open_positions: 5,
          default_slippage_pct: 0.1,
          fee_per_order: 20,
          auto_execute_paper_signals: false,
          min_ai_confidence: 0.55
        }
      })
    })
    setAccount(created)
    setPerformance(await api(`/api/paper/performance/${created.id}`))
  })

  const generateSignal = () => run(async () => {
    if (!account) throw new Error('Create a paper account first')
    const generated = await api('/api/ai/signals/generate', {
      method: 'POST',
      body: JSON.stringify({ account_id: account.id, symbol })
    })
    setSignal(generated)
  })

  const simulateSignal = () => run(async () => {
    if (!account || !signal) throw new Error('Create an account and generate a signal first')
    await api('/api/paper/orders/simulate', {
      method: 'POST',
      body: JSON.stringify({
        account_id: account.id,
        signal_id: signal.id,
        symbol: signal.symbol,
        side: signal.action,
        market_price: 125.5,
        stop_loss: signal.stop_loss,
        take_profit: signal.take_profit
      })
    })
    setPerformance(await api(`/api/paper/performance/${account.id}`))
  })

  const checkExits = () => run(async () => {
    if (!account) throw new Error('Create a paper account first')
    await api('/api/paper/orders/check-exits', {
      method: 'POST',
      body: JSON.stringify({ account_id: account.id, prices: { [symbol]: 151 } })
    })
    setPerformance(await api(`/api/paper/performance/${account.id}`))
  })

  const runCompliance = () => run(async () => {
    if (!account) throw new Error('Create a paper account first')
    setCompliance(await api(`/api/reports/compliance/${account.id}`))
  })

  const exportSnapshot = () => run(async () => {
    setSnapshot(await api('/api/persistence/export'))
  })

  const runBacktest = () => run(async () => {
    const result = await api('/api/backtests', {
      method: 'POST',
      body: JSON.stringify({ user_id: 'demo-user', symbol, initial_capital: Number(capital) })
    })
    setBacktest(result)
  })

  return (
    <main>
      <header className="hero">
        <div>
          <span className="badge">Paper Trading MVP</span>
          <h1>AI-Driven NIFTY Options Trading Platform</h1>
          <p>React + Vite frontend for capital allocation, AI signals, simulated execution, backtesting, risk controls, and live-readiness gates.</p>
        </div>
        <ShieldCheck size={54} />
      </header>

      {error && <div className="error">{error}</div>}

      <section className="grid">
        <div className="card">
          <Wallet />
          <h2>Capital Allocation</h2>
          <label>Capital (₹)</label>
          <input type="number" value={capital} onChange={(event) => setCapital(event.target.value)} />
          <label>Option Symbol</label>
          <input value={symbol} onChange={(event) => setSymbol(event.target.value)} />
          <button disabled={busy} onClick={createAccount}>Create Paper Account</button>
        </div>

        <div className="card">
          <Bot />
          <h2>AI Signal</h2>
          <p>Uses mock AI by default or Ollama when <code>AI_PROVIDER=ollama</code>.</p>
          <button disabled={busy || !account} onClick={generateSignal}>Generate AI Signal</button>
          <button disabled={busy || !signal} onClick={simulateSignal}>Simulate Signal</button>
        </div>

        <div className="card">
          <Activity />
          <h2>Risk & Exits</h2>
          <p>Trigger stop-loss/take-profit checks with latest market prices.</p>
          <button disabled={busy || !account} onClick={checkExits}>Check Exits @ ₹151</button>
          <button disabled={busy} onClick={refresh}>Refresh</button>
        </div>

        <div className="card">
          <FlaskConical />
          <h2>Backtesting</h2>
          <p>Replays synthetic candles through the same paper simulator.</p>
          <button disabled={busy} onClick={runBacktest}>Run Backtest</button>
        </div>

        <div className="card">
          <ShieldCheck />
          <h2>Compliance & Export</h2>
          <p>Generate paper-mode compliance reports and export auditable snapshots.</p>
          <button disabled={busy || !account} onClick={runCompliance}>Compliance Report</button>
          <button disabled={busy} onClick={exportSnapshot}>Export Snapshot</button>
        </div>
      </section>

      <section className="metrics">
        <Metric label="Available Cash" value={performance ? `₹${performance.available_cash}` : '—'} />
        <Metric label="Account Value" value={performance ? `₹${performance.account_value}` : '—'} />
        <Metric label="Return" value={performance ? `${performance.total_return_pct}%` : '—'} />
        <Metric label="Trades" value={performance?.trade_count ?? '—'} />
        <Metric label="Open Positions" value={performance?.open_positions ?? '—'} />
      </section>

      <section className="grid">
        <JsonPanel title="Account" value={account || {}} />
        <JsonPanel title="Latest Signal" value={signal || {}} />
        <JsonPanel title="Positions" value={latestPositions} />
        <JsonPanel title="Alerts" value={latestAlerts} />
        <JsonPanel title="Backtest" value={backtest || {}} />
        <JsonPanel title="Live Readiness" value={bootstrap?.live_readiness || {}} />
        <JsonPanel title="Compliance Report" value={compliance || {}} />
        <JsonPanel title="Export Snapshot" value={snapshot || {}} />
      </section>
    </main>
  )
}

createRoot(document.getElementById('root')).render(<App />)
