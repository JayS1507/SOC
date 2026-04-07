# ============================================================
#  SOC Platform - Alert & Rule Engine
#  Receives LogEvents, matches them against rules.json,
#  and generates Alert objects when rules are triggered.
# ============================================================

import re
import json
import os
import sys
import time

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from shared.models import LogEvent, Alert

RULES_FILE = os.path.join(os.path.dirname(__file__), "rules.json")


# ─────────────────────────────────────────────
#  Rule Loader
# ─────────────────────────────────────────────
class RuleLoader:
    """
    Loads and hot-reloads rules from rules.json.
    Add new rules to rules.json without restarting the server.
    """
    def __init__(self, rules_file: str = RULES_FILE):
        self.rules_file = rules_file
        self.rules      = []
        self.load()

    def load(self):
        """Load/reload rules from disk."""
        try:
            with open(self.rules_file, "r") as f:
                raw = json.load(f)
            # Pre-compile regex patterns for performance
            self.rules = []
            for r in raw:
                self.rules.append({
                    **r,
                    "_compiled": re.compile(r["pattern"], re.IGNORECASE)
                })
            print(f"[RuleEngine] Loaded {len(self.rules)} rules from {self.rules_file}")
        except Exception as e:
            print(f"[RuleEngine] Failed to load rules: {e}")

    def reload(self):
        """Hot-reload rules without restarting. Call this via API."""
        print("[RuleEngine] Reloading rules...")
        self.load()


# ─────────────────────────────────────────────
#  Rule Engine
# ─────────────────────────────────────────────
class RuleEngine:
    """
    Core matching engine.
    Pass a LogEvent in → get back a list of Alerts (empty if no match).

    Deduplication: the same rule will not fire for the same agent more than
    once every DEDUP_WINDOW seconds. This prevents log-replay storms.
    """
    DEDUP_WINDOW = 300   # 5 minutes — prevents spam from repeated events

    def __init__(self):
        self.loader    = RuleLoader()
        self._last_hit = {}   # { (rule_id, agent_id, log_hash) : timestamp }

    def _is_duplicate(self, rule_id: str, agent_id: str, raw_log: str) -> bool:
        """Return True if this exact (rule, agent, log) fired recently."""
        # For disk/resource alerts — deduplicate by rule+agent only (ignore mount path)
        if "HIGH_DISK" in raw_log or "HIGH_CPU" in raw_log or "HIGH_RAM" in raw_log:
            key = (rule_id, agent_id, "RESOURCE")
        else:
            log_hash = hash(raw_log[:120])
            key = (rule_id, agent_id, log_hash)
        now  = time.time()
        last = self._last_hit.get(key, 0)
        if now - last < self.DEDUP_WINDOW:
            return True
        self._last_hit[key] = now
        return False

    def evaluate(self, event: LogEvent) -> list[Alert]:
        """
        Check a single LogEvent against all loaded rules.
        Returns list of Alert objects (can match multiple rules).
        """
        alerts = []

        for rule in self.loader.rules:
            if rule["source_filter"] and event.source != rule["source_filter"]:
                continue

            if rule["_compiled"].search(event.raw_log):
                # Deduplicate: skip if same rule fired for same agent recently
                if self._is_duplicate(rule["id"], event.agent_id, event.raw_log):
                    continue

                alert = Alert(
                    rule_id     = rule["id"],
                    rule_name   = rule["name"],
                    severity    = rule["severity"],
                    agent_id    = event.agent_id,
                    hostname    = event.hostname,
                    matched_log = event.raw_log,
                    timestamp   = event.timestamp
                )
                alerts.append(alert)
                print(f"[RuleEngine] {alert}")

        return alerts

    def reload_rules(self):
        self.loader.reload()


# ─────────────────────────────────────────────
#  Quick Test
# ─────────────────────────────────────────────
if __name__ == "__main__":
    engine = RuleEngine()

    # Simulate some log events
    test_logs = [
        LogEvent("agent-001", "lab-pc-1", "/var/log/auth.log",
                 "Jan 10 10:23:01 sshd[1234]: Failed password for root from 192.168.1.100"),
        LogEvent("agent-001", "lab-pc-1", "/var/log/syslog",
                 "Jan 10 10:24:00 kernel: Normal kernel message"),
        LogEvent("agent-001", "lab-pc-1", "FIM",
                 "FIM ALERT: /etc/passwd was MODIFIED (old=abc123 new=def456)"),
    ]

    for event in test_logs:
        alerts = engine.evaluate(event)
        if not alerts:
            print(f"[RuleEngine] No match: {event.raw_log[:60]}")
