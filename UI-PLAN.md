# AutoStrategy UI Plan

## Option A: Simple Web Dashboard (FastAPI + HTMX)
**Effort:** 1-2 hours
**Deploy:** Railway

```
┌──────────────────────────────────────────────────────┐
│  🧬 AutoStrategy                          [Run] [Stop]│
├──────────────────────────────────────────────────────┤
│ Hypothesis: [_________________________________] [Go] │
├──────────────────────────────────────────────────────┤
│ 📊 LIVE RUN                                          │
│ ┌──────────────────────────────────────────────────┐ │
│ │ [00:15] Iteration 3 of 50                        │ │
│ │ [00:15] Testing: momentum_rsi_divergence         │ │
│ │ [00:18] Sharpe: 1.23 → EVOLVE                    │ │
│ │ [00:20] Iteration 4...                           │ │
│ └──────────────────────────────────────────────────┘ │
├──────────────────────────────────────────────────────┤
│ 🏆 LEADERBOARD                                       │
│ ┌────┬─────────────────────────┬───────┬───────────┐ │
│ │ #  │ Strategy                │ Sharpe│ Return    │ │
│ ├────┼─────────────────────────┼───────┼───────────┤ │
│ │ 1  │ momentum_vol_v3         │ 1.67  │ +38%      │ │
│ │ 2  │ rsi_reversion_v2        │ 1.54  │ +29%      │ │
│ │ 3  │ breakout_atr_v1         │ 1.51  │ +24%      │ │
│ └────┴─────────────────────────┴───────┴───────────┘ │
├──────────────────────────────────────────────────────┤
│ 📜 Click strategy to view code & backtest chart      │
└──────────────────────────────────────────────────────┘
```

### Tech Stack
- **Backend:** FastAPI + SSE (server-sent events for live updates)
- **Frontend:** HTMX + TailwindCSS (no React bloat)
- **Charts:** Lightweight-charts (TradingView style)
- **Deploy:** Railway (auto from GitHub push)

### Endpoints
```
GET  /                    # Dashboard
POST /run                 # Start new run
GET  /run/{id}/stream     # SSE live updates
GET  /leaderboard         # Top strategies
GET  /strategy/{name}     # View code + chart
POST /strategy/{name}/deploy  # Export to live trading
```

## Option B: Streamlit (Fastest MVP)
**Effort:** 30 min
**Limitation:** Less polished, polling instead of streaming

## Option C: Full React Dashboard
**Effort:** 4-6 hours
**For:** If we want charts, drag-drop strategy comparison, etc.

---

## Recommended: Option A
- Professional look
- Real-time streaming
- Deploys to Railway easily
- Can add Telegram notifications when strategies hit threshold

## Next Steps
1. Add `/api` routes to autostrategy
2. Build simple HTMX frontend
3. Deploy to Railway
4. URL: autostrategy.thinkcreate.ai
