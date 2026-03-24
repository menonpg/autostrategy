"""Backtest engine for strategy evaluation."""

import pandas as pd
import numpy as np
import yfinance as yf
from typing import Dict, Any
from datetime import datetime, timedelta
import importlib.util
import tempfile
import sys


class BacktestEngine:
    """Execute backtests and compute metrics."""
    
    def __init__(self, config: dict):
        self.start_date = config.get("start_date", "2024-01-01")
        self.end_date = config.get("end_date", datetime.now().strftime("%Y-%m-%d"))
        self.universe = config.get("universe", ["SPY", "QQQ", "AAPL", "NVDA", "MSFT"])
        self.initial_capital = config.get("initial_capital", 100000)
        
        # Cache data
        self._prices = None
        self._volumes = None
        
    def _load_data(self):
        """Load historical data if not cached."""
        if self._prices is not None:
            return
            
        print(f"    Loading data for {len(self.universe)} tickers...")
        
        # Download all tickers at once (more efficient)
        try:
            df = yf.download(self.universe, start=self.start_date, end=self.end_date, progress=False)
            
            if len(df) == 0:
                print("    Warning: No data returned")
                self._prices = pd.DataFrame()
                self._volumes = pd.DataFrame()
                return
            
            # Handle MultiIndex columns (yfinance >= 0.2.40)
            if isinstance(df.columns, pd.MultiIndex):
                self._prices = df['Close']
                self._volumes = df['Volume']
            else:
                # Single ticker returns flat columns
                self._prices = df[['Close']].rename(columns={'Close': self.universe[0]})
                self._volumes = df[['Volume']].rename(columns={'Volume': self.universe[0]})
                
        except Exception as e:
            print(f"    Warning: Could not load data: {e}")
            self._prices = pd.DataFrame()
            self._volumes = pd.DataFrame()
            return
                
        print(f"    Loaded {len(self._prices)} days of data")
        
    def run(self, strategy_code: str) -> Dict[str, Any]:
        """
        Run backtest for a strategy.
        
        Args:
            strategy_code: Python code with compute_signals, entry_condition, exit_condition
            
        Returns:
            Dict with metrics: sharpe, total_return, max_drawdown, trade_count, win_rate
        """
        self._load_data()
        
        # Load strategy module dynamically
        strategy = self._load_strategy(strategy_code)
        
        # Run simulation
        portfolio_values = []
        trades = []
        capital = self.initial_capital
        position = None  # (ticker, entry_price, shares)
        
        for i in range(20, len(self._prices)):  # Start after warmup period
            date = self._prices.index[i]
            prices_slice = self._prices.iloc[:i+1]
            volumes_slice = self._volumes.iloc[:i+1]
            
            try:
                # Get signals
                signals = strategy.compute_signals(prices_slice, volumes_slice)
                
                # Current prices
                current_prices = self._prices.iloc[i]
                
                if position is None:
                    # Look for entry
                    for ticker in self.universe:
                        if ticker in signals.index and signals[ticker] != 0:
                            if strategy.entry_condition(prices_slice[[ticker]], i):
                                # Enter position
                                price = current_prices[ticker]
                                shares = (capital * 0.1) / price  # 10% position
                                position = (ticker, price, shares)
                                trades.append({
                                    'date': date,
                                    'ticker': ticker,
                                    'action': 'BUY',
                                    'price': price,
                                    'shares': shares
                                })
                                break
                else:
                    # Check for exit
                    ticker, entry_price, shares = position
                    current_price = current_prices[ticker]
                    
                    if strategy.exit_condition(prices_slice[[ticker]], i, entry_price, current_price):
                        # Exit position
                        pnl = (current_price - entry_price) * shares
                        capital += pnl
                        trades.append({
                            'date': date,
                            'ticker': ticker,
                            'action': 'SELL',
                            'price': current_price,
                            'shares': shares,
                            'pnl': pnl
                        })
                        position = None
                        
            except Exception as e:
                # Strategy error - skip this day
                pass
            
            # Track portfolio value
            if position:
                ticker, entry_price, shares = position
                current_value = capital + (self._prices.iloc[i][ticker] - entry_price) * shares
            else:
                current_value = capital
            portfolio_values.append(current_value)
        
        # Calculate metrics
        portfolio_series = pd.Series(portfolio_values)
        returns = portfolio_series.pct_change().dropna()
        
        # Sharpe ratio (annualized)
        sharpe = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() > 0 else 0
        
        # Total return
        total_return = (portfolio_series.iloc[-1] - self.initial_capital) / self.initial_capital
        
        # Max drawdown
        rolling_max = portfolio_series.expanding().max()
        drawdowns = (portfolio_series - rolling_max) / rolling_max
        max_drawdown = abs(drawdowns.min())
        
        # Trade stats
        winning_trades = len([t for t in trades if t.get('pnl', 0) > 0])
        total_trades = len([t for t in trades if 'pnl' in t])
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        return {
            'sharpe': sharpe,
            'total_return': total_return,
            'max_drawdown': max_drawdown,
            'trade_count': total_trades,
            'win_rate': win_rate,
            'final_capital': portfolio_series.iloc[-1] if len(portfolio_series) > 0 else self.initial_capital
        }
    
    def _load_strategy(self, code: str):
        """Dynamically load strategy module from code string."""
        # Write to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_path = f.name
        
        # Load module
        spec = importlib.util.spec_from_file_location("strategy", temp_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules["strategy"] = module
        spec.loader.exec_module(module)
        
        return module
