"""AutoStrategy Web API with real-time streaming."""

import asyncio
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

# Store for active runs and results
runs: dict = {}
leaderboard: list = []

BASE_DIR = Path(__file__).parent.parent
ARTIFACTS_DIR = BASE_DIR / "artifacts"


class RunConfig(BaseModel):
    hypothesis: str
    iterations: int = 20
    hours: float = 2.0
    keep_threshold: float = 1.5


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load existing leaderboard on startup."""
    global leaderboard
    leaderboard = load_all_strategies()
    yield


app = FastAPI(title="AutoStrategy", lifespan=lifespan)

# Mount static files and templates
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


def load_all_strategies() -> list:
    """Load all strategies from artifacts directories."""
    strategies = []
    if not ARTIFACTS_DIR.exists():
        return strategies
    
    for run_dir in ARTIFACTS_DIR.iterdir():
        if not run_dir.is_dir():
            continue
        leaderboard_file = run_dir / "leaderboard.json"
        if leaderboard_file.exists():
            try:
                data = json.loads(leaderboard_file.read_text())
                for s in data:
                    s['run_id'] = run_dir.name
                    s['code_path'] = str(run_dir / "strategies" / f"{s['name']}.py")
                strategies.extend(data)
            except:
                pass
    
    # Sort by Sharpe ratio
    strategies.sort(key=lambda x: x.get('sharpe', 0), reverse=True)
    return strategies[:20]  # Top 20


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard."""
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html", 
        context={
            "leaderboard": leaderboard[:10],
            "active_runs": {k: v for k, v in runs.items() if v.get('status') == 'running'}
        }
    )


@app.post("/run")
async def start_run(config: RunConfig, background_tasks: BackgroundTasks):
    """Start a new AutoStrategy run."""
    run_id = f"run-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    runs[run_id] = {
        "id": run_id,
        "status": "running",
        "config": config.model_dump(),
        "started_at": datetime.now().isoformat(),
        "logs": [],
        "iteration": 0,
        "strategies": []
    }
    
    # Start the run in background
    background_tasks.add_task(execute_run, run_id, config)
    
    return {"run_id": run_id, "status": "started"}


async def execute_run(run_id: str, config: RunConfig):
    """Execute the AutoStrategy loop in a thread pool to avoid blocking."""
    import sys
    import concurrent.futures
    sys.path.insert(0, str(BASE_DIR))
    
    run = runs[run_id]
    
    def run_sync():
        """Synchronous wrapper to run in thread pool."""
        from autostrategy.loop import AutoStrategyLoop
        
        def log_callback(message: str):
            run["logs"].append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "message": message
            })
        
        try:
            # Build config
            loop_config = {
                "hypothesis": {"initial": config.hypothesis},
                "backtest": {
                    "start_date": "2024-01-01",
                    "end_date": "2026-03-01",
                    "universe": ["SPY", "QQQ", "AAPL", "NVDA", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "AMD"],
                    "initial_capital": 100000
                },
                "constraints": {"max_drawdown": 0.25, "min_trades": 30},
                "evolution": {
                    "max_iterations": config.iterations,
                    "time_budget_hours": config.hours,
                    "keep_threshold": config.keep_threshold
                },
                "llm": {"provider": "anthropic", "model": "claude-sonnet-4-20250514"}
            }
            
            # Create artifacts dir for this run
            artifacts_dir = ARTIFACTS_DIR / run_id
            
            strategy_loop = AutoStrategyLoop(loop_config, artifacts_dir=artifacts_dir)
            
            # Monkey-patch print to capture output
            original_print = print
            def captured_print(*args, **kwargs):
                message = " ".join(str(a) for a in args)
                log_callback(message)
                original_print(*args, **kwargs)
            
            import builtins
            builtins.print = captured_print
            
            try:
                result = strategy_loop.run(
                    initial_hypothesis=config.hypothesis,
                    max_iterations=config.iterations,
                    time_budget_hours=config.hours,
                    keep_threshold=config.keep_threshold
                )
                
                run["strategies"] = result
                run["status"] = "completed"
                
            finally:
                builtins.print = original_print
                
        except Exception as e:
            run["status"] = "failed"
            run["error"] = str(e)
            run["logs"].append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "message": f"ERROR: {e}"
            })
    
    # Run the sync function in a thread pool
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, run_sync)
    
    # Update global leaderboard after completion
    global leaderboard
    leaderboard = load_all_strategies()


@app.get("/run/{run_id}")
async def get_run(run_id: str):
    """Get run status and details."""
    if run_id not in runs:
        return {"error": "Run not found"}
    return runs[run_id]


@app.get("/run/{run_id}/stream")
async def stream_run(run_id: str):
    """SSE stream for live run updates."""
    async def event_generator():
        last_log_count = 0
        
        while True:
            if run_id not in runs:
                yield f"data: {json.dumps({'error': 'Run not found'})}\n\n"
                break
            
            run = runs[run_id]
            
            # Send new logs
            current_logs = run.get("logs", [])
            if len(current_logs) > last_log_count:
                for log in current_logs[last_log_count:]:
                    yield f"data: {json.dumps({'type': 'log', 'data': log})}\n\n"
                last_log_count = len(current_logs)
            
            # Send status update
            yield f"data: {json.dumps({'type': 'status', 'status': run['status']})}\n\n"
            
            if run["status"] in ["completed", "failed"]:
                # Send final results
                yield f"data: {json.dumps({'type': 'complete', 'strategies': run.get('strategies', [])})}\n\n"
                break
            
            await asyncio.sleep(1)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )


@app.get("/leaderboard")
async def get_leaderboard():
    """Get top strategies."""
    return {"strategies": leaderboard}


@app.get("/strategy/{run_id}/{name}")
async def get_strategy(run_id: str, name: str):
    """Get strategy code and details."""
    code_path = ARTIFACTS_DIR / run_id / "strategies" / f"{name}.py"
    
    if not code_path.exists():
        return {"error": "Strategy not found"}
    
    code = code_path.read_text()
    
    # Find in leaderboard for metrics
    metrics = next((s for s in leaderboard if s.get('name') == name), {})
    
    return {
        "name": name,
        "code": code,
        "metrics": metrics
    }


@app.get("/strategy/{run_id}/{name}/html", response_class=HTMLResponse)
async def get_strategy_html(request: Request, run_id: str, name: str):
    """Get strategy detail page."""
    code_path = ARTIFACTS_DIR / run_id / "strategies" / f"{name}.py"
    
    if not code_path.exists():
        return HTMLResponse("<p>Strategy not found</p>")
    
    code = code_path.read_text()
    metrics = next((s for s in leaderboard if s.get('name') == name), {})
    
    return templates.TemplateResponse(
        request=request,
        name="strategy_detail.html",
        context={
            "name": name,
            "code": code,
            "metrics": metrics,
            "run_id": run_id
        }
    )


# ============ SCANNER ENDPOINTS ============

from .scanner import (
    deploy_strategy, undeploy_strategy, load_deployed_strategies,
    run_scanner, run_scanner_with_alerts
)


@app.post("/strategy/{run_id}/{name}/deploy")
async def deploy_strategy_endpoint(run_id: str, name: str):
    """Deploy a strategy for daily signal scanning."""
    code_path = ARTIFACTS_DIR / run_id / "strategies" / f"{name}.py"
    
    if not code_path.exists():
        return {"error": "Strategy not found"}
    
    success = deploy_strategy(run_id, name)
    
    if success:
        return {"status": "deployed", "message": f"Strategy {name} deployed for daily alerts"}
    else:
        return {"status": "already_deployed", "message": f"Strategy {name} was already deployed"}


@app.delete("/strategy/{run_id}/{name}/deploy")
async def undeploy_strategy_endpoint(run_id: str, name: str):
    """Remove a strategy from daily scanning."""
    success = undeploy_strategy(run_id, name)
    
    if success:
        return {"status": "undeployed", "message": f"Strategy {name} removed from alerts"}
    else:
        return {"status": "not_found", "message": f"Strategy {name} was not deployed"}


@app.get("/deployed")
async def get_deployed_strategies():
    """List all deployed strategies."""
    return {"strategies": load_deployed_strategies()}


@app.post("/scan")
async def run_scan():
    """Run all deployed strategies and return signals (no alerts)."""
    results = run_scanner()
    return {"results": results}


@app.post("/scan/alerts")
async def run_scan_with_alerts():
    """Run all deployed strategies and send Telegram alerts."""
    results = await run_scanner_with_alerts()
    return results


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
