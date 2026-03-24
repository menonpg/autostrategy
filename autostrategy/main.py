"""AutoStrategy CLI entry point."""

import argparse
import yaml
from pathlib import Path

from .loop import AutoStrategyLoop


def main():
    parser = argparse.ArgumentParser(
        description="AutoStrategy - AI-driven trading strategy evolution"
    )
    parser.add_argument(
        "command",
        choices=["run"],
        help="Command to execute"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Path to config file"
    )
    parser.add_argument(
        "--hypothesis",
        type=str,
        default=None,
        help="Initial hypothesis (overrides config)"
    )
    parser.add_argument(
        "--hours",
        type=float,
        default=None,
        help="Time budget in hours (overrides config)"
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=None,
        help="Max iterations (overrides config)"
    )
    
    args = parser.parse_args()
    
    # Load config
    config_path = Path(args.config)
    if config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f)
    else:
        config = get_default_config()
    
    if args.command == "run":
        run_evolution(config, args)


def run_evolution(config: dict, args):
    """Run the evolution loop."""
    # Override config with CLI args
    hypothesis = args.hypothesis or config.get("hypothesis", {}).get("initial", "Momentum strategies work in trending markets")
    hours = args.hours or config.get("evolution", {}).get("time_budget_hours", 8)
    iterations = args.iterations or config.get("evolution", {}).get("max_iterations", 50)
    threshold = config.get("evolution", {}).get("keep_threshold", 1.5)
    
    # Create and run loop
    loop = AutoStrategyLoop(config)
    leaderboard = loop.run(
        initial_hypothesis=hypothesis,
        max_iterations=iterations,
        time_budget_hours=hours,
        keep_threshold=threshold
    )
    
    print(f"\n✓ Run complete. {len(leaderboard)} strategies saved.")


def get_default_config() -> dict:
    """Return default configuration."""
    return {
        "hypothesis": {
            "initial": "Momentum strategies work when volume is above average"
        },
        "backtest": {
            "start_date": "2024-01-01",
            "end_date": "2026-03-01",
            "universe": ["SPY", "QQQ", "AAPL", "NVDA", "MSFT", "GOOGL", "AMZN", "META", "TSLA"],
            "initial_capital": 100000
        },
        "constraints": {
            "max_drawdown": 0.25,
            "min_trades": 30
        },
        "evolution": {
            "max_iterations": 50,
            "time_budget_hours": 8,
            "keep_threshold": 1.5
        },
        "llm": {
            "provider": "anthropic",
            "model": "claude-sonnet-4-20250514"
        }
    }


if __name__ == "__main__":
    main()
