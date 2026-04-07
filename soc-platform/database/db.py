# ============================================================
#  SOC Platform - Database Layer
#  SQLite for now (easy to swap to PostgreSQL later).
#  Stores: logs, alerts, registered agents.
# ============================================================

import sqlite3
import os
import sys
import time

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from shared.config import DB_PATH
from shared.models import LogEvent, Alert


def get_connection():
    """
    Get a SQLite connection.
    - timeout=10: wait up to 10s if DB is locked (instead of failing instantly)
    - WAL mode: allows concurrent readers + 1 writer (fixes Manager vs API conflict)
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")    # KEY FIX: enables concurrent access
    conn.execute("PRAGMA synchronous=NORMAL")  # Faster writes, still safe
    return conn


# ─────────────────────────────────────────────
#  Schema Setup
# ─────────────────────────────────────────────
def init_db():
    """Create tables if they don't exist. Safe to call on every startup."""
    conn = get_connection()
    cur  = conn.cursor()

    # --- Agents table ---
    cur.execute("""
        CREATE TABLE IF NOT EXISTS agents (
            agent_id    TEXT PRIMARY KEY,
            hostname    TEXT NOT NULL,
            last_seen   REAL NOT NULL,
            status      TEXT DEFAULT 'active'
        )
    """)

    # --- Logs table ---
    cur.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id    TEXT NOT NULL,
            hostname    TEXT NOT NULL,
            source      TEXT NOT NULL,
            raw_log     TEXT NOT NULL,
            timestamp   REAL NOT NULL
        )
    """)

    # --- Alerts table ---
    cur.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_id     TEXT NOT NULL,
            rule_name   TEXT NOT NULL,
            severity    TEXT NOT NULL,
            agent_id    TEXT NOT NULL,
            hostname    TEXT NOT NULL,
            matched_log TEXT NOT NULL,
            timestamp   REAL NOT NULL,
            acknowledged INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()
    print(f"[DB] Database initialized at {DB_PATH}")


# ─────────────────────────────────────────────
#  Agent Operations
# ─────────────────────────────────────────────
def upsert_agent(agent_id: str, hostname: str):
    """Register a new agent or update its last_seen timestamp."""
    conn = get_connection()
    conn.execute("""
        INSERT INTO agents (agent_id, hostname, last_seen)
        VALUES (?, ?, ?)
        ON CONFLICT(agent_id) DO UPDATE SET
            hostname  = excluded.hostname,
            last_seen = excluded.last_seen,
            status    = 'active'
    """, (agent_id, hostname, time.time()))
    conn.commit()
    conn.close()


def get_all_agents() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM agents ORDER BY last_seen DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────
#  Log Operations
# ─────────────────────────────────────────────
def insert_log(event: LogEvent):
    """Save a LogEvent to the database."""
    conn = get_connection()
    conn.execute("""
        INSERT INTO logs (agent_id, hostname, source, raw_log, timestamp)
        VALUES (?, ?, ?, ?, ?)
    """, (event.agent_id, event.hostname, event.source, event.raw_log, event.timestamp))
    conn.commit()
    conn.close()


def get_logs(limit: int = 100, agent_id: str = None) -> list[dict]:
    """Fetch recent logs, optionally filtered by agent."""
    conn = get_connection()
    if agent_id:
        rows = conn.execute(
            "SELECT * FROM logs WHERE agent_id=? ORDER BY timestamp DESC LIMIT ?",
            (agent_id, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM logs ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────
#  Alert Operations
# ─────────────────────────────────────────────
def insert_alert(alert: Alert):
    """Save an Alert to the database."""
    conn = get_connection()
    conn.execute("""
        INSERT INTO alerts
            (rule_id, rule_name, severity, agent_id, hostname, matched_log, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        alert.rule_id, alert.rule_name, alert.severity,
        alert.agent_id, alert.hostname, alert.matched_log, alert.timestamp
    ))
    conn.commit()
    conn.close()


def get_alerts(limit: int = 100, severity: str = None) -> list[dict]:
    """Fetch recent alerts, optionally filtered by severity."""
    conn = get_connection()
    if severity:
        rows = conn.execute(
            "SELECT * FROM alerts WHERE severity=? ORDER BY timestamp DESC LIMIT ?",
            (severity, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM alerts ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def acknowledge_alert(alert_id: int):
    """Mark an alert as acknowledged (reviewed by analyst)."""
    conn = get_connection()
    conn.execute("UPDATE alerts SET acknowledged=1 WHERE id=?", (alert_id,))
    conn.commit()
    conn.close()


def get_alert_counts() -> dict:
    """Get alert counts grouped by severity (for dashboard stats)."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT severity, COUNT(*) as count
        FROM alerts
        WHERE acknowledged = 0
        GROUP BY severity
    """).fetchall()
    conn.close()
    return {r["severity"]: r["count"] for r in rows}
