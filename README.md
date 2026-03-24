# AutoStrategy

**Autoresearch for trading strategies.** AI writes, tests, and evolves trading strategies overnight.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

```
$ autostrategy run --hours 8

[00:00] Starting autonomous strategy evolution...
[00:05] Hypothesis: "Momentum + volume surge"
[00:15] Backtest: Sharpe=0.82 → EVOLVE
[00:45] Evolved: Sharpe=1.67 → KEEP ✓
...
[08:00] === LEADERBOARD ===
        1. momentum_vol_v3     Sharpe=1.67  Return=38%
        2. rsi_reversion_v2    Sharpe=1.54  Return=29%
        
Strategies saved. You slept. Your portfolio got smarter.
```

## What Is This?

AutoStrategy applies the [Autoresearch](https://github.com/karpathy/autoresearch) pattern to trading:

1. **AI writes** trading strategy code (not just tune parameters)
2. **Backtests** against historical data
3. **Multi-agent debate** analyzes why it worked/failed
4. **Evolves** the actual logic based on learnings
5. **Repeats** until time budget exhausted

Like Karpathy's chess engine that evolved from 2250 to 2718 ELO — but for trading.

## Quick Start

```bash
pip install -e .
export ANTHROPIC_API_KEY="sk-ant-..."

# Run overnight
autostrategy run --hours 8 --hypothesis "Momentum works in trending markets"
```

## The Loop

```
HYPOTHESIS → GENERATE → BACKTEST → ANALYZE → DECIDE
     ↑                                          │
     └──────────── EVOLVE ←─────────────────────┘
```

## Disclaimer

⚠️ **Not financial advice.** Past performance ≠ future results. Paper trade first.

## License

MIT

**Built by [The Menon Lab](https://themenonlab.com)**
