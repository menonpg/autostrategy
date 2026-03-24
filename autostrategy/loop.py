"""Core autonomous evolution loop."""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from .generator.coder import StrategyCoder
from .backtest.engine import BacktestEngine
from .analyze.debate import MultiAgentDebate
from .evolution.lessons import LessonsTracker


class AutoStrategyLoop:
    """
    The core autonomous loop:
    HYPOTHESIS → GENERATE → BACKTEST → ANALYZE → DECIDE → REPEAT
    """
    
    def __init__(
        self,
        config: dict,
        artifacts_dir: Optional[Path] = None
    ):
        self.config = config
        self.artifacts_dir = artifacts_dir or Path(f"artifacts/run-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize components
        self.coder = StrategyCoder(config.get("llm", {}))
        self.backtester = BacktestEngine(config.get("backtest", {}))
        self.analyzer = MultiAgentDebate(config.get("llm", {}))
        self.lessons = LessonsTracker(self.artifacts_dir / "lessons.jsonl")
        
        # State
        self.leaderboard = []
        self.all_strategies = []  # Track ALL strategies, not just winners
        self.iteration = 0
        self.start_time = None
        
    def run(
        self,
        initial_hypothesis: str,
        max_iterations: int = 50,
        time_budget_hours: float = 8,
        keep_threshold: float = 1.5
    ):
        """Run the autonomous evolution loop."""
        self.start_time = time.time()
        time_budget_secs = time_budget_hours * 3600
        
        hypothesis = initial_hypothesis
        current_strategy = None
        
        print(f"[{self._elapsed()}] Starting AutoStrategy run")
        print(f"[{self._elapsed()}] Time budget: {time_budget_hours} hours")
        print(f"[{self._elapsed()}] Keep threshold: Sharpe > {keep_threshold}")
        
        while self.iteration < max_iterations:
            # Check time budget
            if time.time() - self.start_time > time_budget_secs:
                print(f"[{self._elapsed()}] Time budget exhausted")
                break
                
            self.iteration += 1
            print(f"\n[{self._elapsed()}] === ITERATION {self.iteration} ===")
            
            # 1. Generate strategy from hypothesis
            print(f"[{self._elapsed()}] Hypothesis: {hypothesis[:60]}...")
            strategy_code, strategy_name = self.coder.generate(
                hypothesis=hypothesis,
                previous_strategy=current_strategy,
                lessons=self.lessons.get_recent(5)
            )
            print(f"[{self._elapsed()}] Generated: {strategy_name}")
            
            # Save strategy
            strategy_path = self.artifacts_dir / "strategies" / f"{strategy_name}.py"
            strategy_path.parent.mkdir(exist_ok=True)
            strategy_path.write_text(strategy_code)
            
            # 2. Backtest
            print(f"[{self._elapsed()}] Backtesting...")
            try:
                metrics = self.backtester.run(strategy_code)
            except Exception as e:
                print(f"[{self._elapsed()}] Backtest failed: {e}")
                self.lessons.add(f"Strategy {strategy_name} failed: {e}")
                hypothesis = self.coder.generate_new_hypothesis(self.lessons.get_recent(10))
                current_strategy = None
                continue
                
            print(f"[{self._elapsed()}] Results: Sharpe={metrics['sharpe']:.2f}, Return={metrics['total_return']*100:.1f}%, MaxDD={metrics['max_drawdown']*100:.1f}%")
            
            # 3. Multi-agent analysis
            print(f"[{self._elapsed()}] Analyzing...")
            analysis = self.analyzer.debate(
                strategy_code=strategy_code,
                metrics=metrics,
                hypothesis=hypothesis
            )
            print(f"[{self._elapsed()}] Bull: {analysis['bull'][:80]}...")
            print(f"[{self._elapsed()}] Bear: {analysis['bear'][:80]}...")
            
            # 4. Decide: KEEP, EVOLVE, or DISCARD
            decision = self._decide(metrics, analysis, keep_threshold)
            print(f"[{self._elapsed()}] Decision: {decision}")
            
            # Save ALL strategies with metrics (not just winners)
            self.all_strategies.append({
                "name": strategy_name,
                "sharpe": metrics["sharpe"],
                "total_return": metrics["total_return"],
                "max_drawdown": metrics["max_drawdown"],
                "trades": metrics["trade_count"],
                "win_rate": metrics.get("win_rate", 0),
                "iteration": self.iteration,
                "decision": decision,
                "hypothesis": hypothesis[:200]
            })
            
            if decision == "KEEP":
                # Add to leaderboard
                self.leaderboard.append({
                    "name": strategy_name,
                    "sharpe": metrics["sharpe"],
                    "total_return": metrics["total_return"],
                    "max_drawdown": metrics["max_drawdown"],
                    "trades": metrics["trade_count"],
                    "iteration": self.iteration
                })
                self.leaderboard.sort(key=lambda x: x["sharpe"], reverse=True)
                print(f"[{self._elapsed()}] ✓ Added to leaderboard (rank #{len(self.leaderboard)})")
                
                # Generate new hypothesis for next iteration
                hypothesis = self.coder.generate_new_hypothesis(self.lessons.get_recent(10))
                current_strategy = None
                
            elif decision == "EVOLVE":
                # Evolve the current strategy
                evolution_hint = analysis.get("evolution_hint", "Improve entry/exit timing")
                hypothesis = f"{hypothesis}. Evolution: {evolution_hint}"
                current_strategy = strategy_code
                self.lessons.add(f"Evolving {strategy_name}: {evolution_hint}")
                
            else:  # DISCARD
                self.lessons.add(f"Discarded {strategy_name}: {analysis.get('discard_reason', 'Poor performance')}")
                hypothesis = self.coder.generate_new_hypothesis(self.lessons.get_recent(10))
                current_strategy = None
        
        # Final output
        self._save_results()
        self._print_leaderboard()
        
        return self.leaderboard
    
    def _decide(self, metrics: dict, analysis: dict, keep_threshold: float) -> str:
        """Decide whether to KEEP, EVOLVE, or DISCARD."""
        sharpe = metrics.get("sharpe", 0)
        max_dd = metrics.get("max_drawdown", 1)
        trades = metrics.get("trade_count", 0)
        
        # Hard constraints
        if max_dd > self.config.get("constraints", {}).get("max_drawdown", 0.25):
            return "DISCARD"
        if trades < self.config.get("constraints", {}).get("min_trades", 30):
            return "DISCARD"
        
        # Keep if above threshold
        if sharpe >= keep_threshold:
            return "KEEP"
        
        # Evolve if promising (above 0.5)
        if sharpe >= 0.5:
            return "EVOLVE"
        
        return "DISCARD"
    
    def _elapsed(self) -> str:
        """Return elapsed time as MM:SS."""
        if not self.start_time:
            return "00:00"
        elapsed = int(time.time() - self.start_time)
        return f"{elapsed // 60:02d}:{elapsed % 60:02d}"
    
    def _save_results(self):
        """Save leaderboard, all strategies, and lessons."""
        # Save winners (leaderboard)
        leaderboard_path = self.artifacts_dir / "leaderboard.json"
        leaderboard_path.write_text(json.dumps(self.leaderboard, indent=2))
        
        # Save ALL strategies with metrics
        all_strategies_path = self.artifacts_dir / "all_strategies.json"
        all_strategies_path.write_text(json.dumps(self.all_strategies, indent=2))
        
        print(f"\n[{self._elapsed()}] Results saved to {self.artifacts_dir}")
    
    def _print_leaderboard(self):
        """Print final leaderboard."""
        print(f"\n[{self._elapsed()}] === FINAL LEADERBOARD ===")
        if not self.leaderboard:
            print("No strategies met the threshold.")
            return
            
        for i, s in enumerate(self.leaderboard[:10], 1):
            print(f"  {i}. {s['name']:25} Sharpe={s['sharpe']:.2f}  Return={s['total_return']*100:.1f}%  MaxDD={s['max_drawdown']*100:.1f}%")
