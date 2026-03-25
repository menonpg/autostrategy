"""Multi-agent debate for strategy analysis."""

from typing import Dict, Any
from autostrategy.llm import get_client


class MultiAgentDebate:
    """Bull vs Bear vs Quant debate on strategy performance."""
    
    def __init__(self, llm_config: dict):
        self.client = get_client()
        self.model = llm_config.get("model", "gpt-5-chat")
        
    def debate(
        self,
        strategy_code: str,
        metrics: Dict[str, Any],
        hypothesis: str
    ) -> Dict[str, str]:
        """
        Run multi-agent debate on strategy.
        
        Returns:
            Dict with 'bull', 'bear', 'quant' perspectives and 'evolution_hint'
        """
        metrics_summary = f"""
Sharpe Ratio: {metrics.get('sharpe', 0):.2f}
Total Return: {metrics.get('total_return', 0)*100:.1f}%
Max Drawdown: {metrics.get('max_drawdown', 0)*100:.1f}%
Trade Count: {metrics.get('trade_count', 0)}
Win Rate: {metrics.get('win_rate', 0)*100:.1f}%
"""
        
        # Bull analysis
        bull = self._get_perspective(
            "Bull Analyst",
            "You are an optimistic trading analyst. Find the STRENGTHS of this strategy. What works well? Why might it succeed?",
            strategy_code, metrics_summary, hypothesis
        )
        
        # Bear analysis
        bear = self._get_perspective(
            "Bear Analyst", 
            "You are a skeptical trading analyst. Find the WEAKNESSES of this strategy. What could fail? What risks exist?",
            strategy_code, metrics_summary, hypothesis
        )
        
        # Quant analysis
        quant = self._get_perspective(
            "Quant Analyst",
            "You are a quantitative analyst. Focus on STATISTICAL SIGNIFICANCE and robustness. Are the results reliable? What's the sample size concern?",
            strategy_code, metrics_summary, hypothesis
        )
        
        # Generate evolution hint
        evolution_hint = self._get_evolution_hint(bull, bear, quant, metrics)
        
        return {
            'bull': bull,
            'bear': bear,
            'quant': quant,
            'evolution_hint': evolution_hint
        }
    
    def _get_perspective(
        self,
        role: str,
        system_prompt: str,
        strategy_code: str,
        metrics: str,
        hypothesis: str
    ) -> str:
        """Get one agent's perspective."""
        prompt = f"""{system_prompt}

HYPOTHESIS: {hypothesis}

STRATEGY CODE:
```python
{strategy_code[:1500]}  # Truncate if too long
```

BACKTEST METRICS:
{metrics}

Provide a 2-3 sentence analysis from your perspective. Be specific and actionable."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return response.content[0].text.strip()
    
    def _get_evolution_hint(
        self,
        bull: str,
        bear: str,
        quant: str,
        metrics: Dict[str, Any]
    ) -> str:
        """Generate a hint for how to evolve the strategy."""
        prompt = f"""Based on this analysis of a trading strategy:

BULL VIEW: {bull}

BEAR VIEW: {bear}

QUANT VIEW: {quant}

METRICS: Sharpe={metrics.get('sharpe', 0):.2f}, Return={metrics.get('total_return', 0)*100:.1f}%, MaxDD={metrics.get('max_drawdown', 0)*100:.1f}%

Suggest ONE specific improvement to make this strategy better. Be concrete and actionable.
Output only the suggestion, one sentence."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return response.content[0].text.strip()
