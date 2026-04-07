# ============================================================
#  SOC Platform - REST API  (FastAPI)
#  Serves data from the database to the Dashboard UI.
#  Run alongside the Manager (separate process or thread).
# ============================================================
#
#  Install deps:  pip install fastapi uvicorn
#  Run:           python api.py
#  Docs:          http://localhost:8000/docs  (auto-generated!)
# ============================================================

import os
import sys
import time

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from shared.config import API_HOST, API_PORT

try:
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import HTMLResponse
    import uvicorn
except ImportError:
    print("Install FastAPI: pip install fastapi uvicorn")
    sys.exit(1)

from database.db import (
    get_alerts, get_logs, get_all_agents,
    acknowledge_alert, get_alert_counts
)
from rule_engine.engine import RuleEngine

app    = FastAPI(title="SOC Platform API", version="1.0.0")
engine = RuleEngine()


# ─────────────────────────────────────────────
#  Health Check
# ─────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "timestamp": time.time()}


# ─────────────────────────────────────────────
#  Agents
# ─────────────────────────────────────────────
@app.get("/api/agents")
def list_agents():
    """Get all registered agents and their status."""
    return get_all_agents()


# ─────────────────────────────────────────────
#  Logs
# ─────────────────────────────────────────────
@app.get("/api/logs")
def list_logs(
    limit:    int = Query(default=100, le=1000),
    agent_id: str = Query(default=None)
):
    """Get recent log events. Filter by agent_id optionally."""
    return get_logs(limit=limit, agent_id=agent_id)


# ─────────────────────────────────────────────
#  Alerts
# ─────────────────────────────────────────────
@app.get("/api/alerts")
def list_alerts(
    limit:    int = Query(default=100, le=1000),
    severity: str = Query(default=None)
):
    """Get recent alerts. Filter by severity (LOW/MEDIUM/HIGH/CRITICAL)."""
    return get_alerts(limit=limit, severity=severity)


@app.get("/api/alerts/stats")
def alert_stats():
    """Get unacknowledged alert counts per severity (for dashboard widgets)."""
    return get_alert_counts()


@app.post("/api/alerts/{alert_id}/acknowledge")
def ack_alert(alert_id: int):
    """Mark an alert as reviewed/acknowledged by an analyst."""
    try:
        acknowledge_alert(alert_id)
        return {"success": True, "alert_id": alert_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────
#  Rule Engine Controls
# ─────────────────────────────────────────────
@app.post("/api/rules/reload")
def reload_rules():
    """Hot-reload rules.json without restarting the server."""
    engine.reload_rules()
    return {"success": True, "message": "Rules reloaded"}


# ─────────────────────────────────────────────
#  Serve Dashboard (static HTML)
# ─────────────────────────────────────────────
DASHBOARD_PATH = os.path.join(os.path.dirname(__file__), "../dashboard/templates")

@app.get("/", response_class=HTMLResponse)
def serve_dashboard():
    index = os.path.join(DASHBOARD_PATH, "index.html")
    if os.path.exists(index):
        with open(index) as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>SOC Platform - Dashboard not found</h1>")


# ─────────────────────────────────────────────
#  Entry Point
# ─────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run("api:app", host=API_HOST, port=API_PORT, reload=True)
