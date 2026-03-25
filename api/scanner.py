"""Daily signal scanner - runs deployed strategies and sends alerts."""

import os
import json
import importlib.util
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional
import httpx
import pandas as pd
import yfinance as yf

# Deployed strategies file - use /data if available (Railway persistent volume), else artifacts/
_DATA_DIR = Path("/data") if Path("/data").exists() else Path(__file__).parent.parent / "artifacts"
DEPLOYED_FILE = _DATA_DIR / "deployed.json"
ARTIFACTS_DIR = Path(__file__).parent.parent / "artifacts"

# Telegram config (set via env vars)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def load_deployed_strategies() -> list:
    """Load list of deployed strategy paths."""
    if not DEPLOYED_FILE.exists():
        return []
    try:
        return json.loads(DEPLOYED_FILE.read_text())
    except:
        return []


def save_deployed_strategies(strategies: list):
    """Save deployed strategies list."""
    DEPLOYED_FILE.parent.mkdir(parents=True, exist_ok=True)
    DEPLOYED_FILE.write_text(json.dumps(strategies, indent=2))


def deploy_strategy(run_id: str, name: str) -> bool:
    """Mark a strategy as deployed for daily scanning."""
    strategies = load_deployed_strategies()
    
    entry = {
        "run_id": run_id,
        "name": name,
        "deployed_at": datetime.now().isoformat(),
        "code_path": str(ARTIFACTS_DIR / run_id / "strategies" / f"{name}.py")
    }
    
    # Check if already deployed
    if any(s["name"] == name and s["run_id"] == run_id for s in strategies):
        return False
    
    strategies.append(entry)
    save_deployed_strategies(strategies)
    return True


def undeploy_strategy(run_id: str, name: str) -> bool:
    """Remove a strategy from deployment."""
    strategies = load_deployed_strategies()
    original_len = len(strategies)
    strategies = [s for s in strategies if not (s["name"] == name and s["run_id"] == run_id)]
    
    if len(strategies) < original_len:
        save_deployed_strategies(strategies)
        return True
    return False


def load_strategy_module(code_path: str):
    """Dynamically load a strategy module from file."""
    spec = importlib.util.spec_from_file_location("strategy", code_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["strategy"] = module
    spec.loader.exec_module(module)
    return module


def get_market_data(tickers: list, days: int = 30) -> tuple:
    """Fetch recent market data."""
    try:
        df = yf.download(tickers, period=f"{days}d", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            prices = df['Close']
            volumes = df['Volume']
        else:
            prices = df[['Close']].rename(columns={'Close': tickers[0]})
            volumes = df[['Volume']].rename(columns={'Volume': tickers[0]})
        return prices, volumes
    except Exception as e:
        print(f"Error fetching data: {e}")
        return pd.DataFrame(), pd.DataFrame()


def scan_strategy(strategy_info: dict, prices: pd.DataFrame, volumes: pd.DataFrame) -> dict:
    """Run a single strategy and return signals."""
    try:
        module = load_strategy_module(strategy_info["code_path"])
        signals = module.compute_signals(prices, volumes)
        
        # Get non-zero signals
        buy_signals = signals[signals == 1].index.tolist()
        sell_signals = signals[signals == -1].index.tolist()
        
        return {
            "name": strategy_info["name"],
            "run_id": strategy_info["run_id"],
            "buy": buy_signals,
            "sell": sell_signals,
            "error": None
        }
    except Exception as e:
        return {
            "name": strategy_info["name"],
            "run_id": strategy_info["run_id"],
            "buy": [],
            "sell": [],
            "error": str(e)
        }


def run_scanner(tickers: Optional[list] = None) -> list:
    """Run all deployed strategies and return signals."""
    if tickers is None:
        tickers = ["SPY", "QQQ", "AAPL", "NVDA", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "AMD"]
    
    strategies = load_deployed_strategies()
    if not strategies:
        return []
    
    # Fetch data once for all strategies
    prices, volumes = get_market_data(tickers)
    if prices.empty:
        return [{"error": "Failed to fetch market data"}]
    
    results = []
    for strategy_info in strategies:
        result = scan_strategy(strategy_info, prices, volumes)
        results.append(result)
    
    return results


async def send_telegram_alert(message: str):
    """Send alert via Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print(f"Telegram not configured. Message: {message}")
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "Markdown"
            })
            return response.status_code == 200
        except Exception as e:
            print(f"Telegram error: {e}")
            return False


async def run_scanner_with_alerts(tickers: Optional[list] = None) -> dict:
    """Run scanner and send Telegram alerts for any signals."""
    results = run_scanner(tickers)
    
    # Build alert message
    alerts = []
    for result in results:
        if result.get("error"):
            continue
        
        if result["buy"]:
            alerts.append(f"🟢 *BUY* ({result['name']}): {', '.join(result['buy'])}")
        
        if result["sell"]:
            alerts.append(f"🔴 *SELL* ({result['name']}): {', '.join(result['sell'])}")
    
    # Send alert if we have signals
    if alerts:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        message = f"🚨 *AutoStrategy Signals* ({now})\n\n" + "\n".join(alerts)
        await send_telegram_alert(message)
    
    return {
        "scanned_at": datetime.now().isoformat(),
        "strategies_checked": len(results),
        "signals": results,
        "alerts_sent": len(alerts) > 0
    }
