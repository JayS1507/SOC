# ============================================================
#  SOC Platform - Log Collection Agent
#  Run this on every machine in your SOC lab.
#  It collects logs and ships them to the Central Manager.
# ============================================================

import socket
import time
import os
import sys
import hashlib
import threading

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from shared.config import (
    MANAGER_HOST, MANAGER_PORT, AGENT_SEND_INTERVAL,
    AGENT_ID, AGENT_HOSTNAME, LOG_SOURCES, FIM_WATCH_PATHS,
    MANAGER_BUFFER_SIZE
)
from shared.models import LogEvent
from system_monitor import SystemMonitor
from student_monitor import StudentActivityMonitor


# ─────────────────────────────────────────────
#  1. LOG READER  — reads new lines from log files
# ─────────────────────────────────────────────
class LogReader:
    """
    Tails log files (like `tail -f`).
    Tracks file position so it only reads NEW lines each interval.

    skip_existing=True (default): jumps to end of file on first open,
    so old historical logs don't flood the manager on startup.
    Set to False only if you want to ingest all historical logs.
    """
    def __init__(self, log_paths: list, skip_existing: bool = True):
        self.log_paths    = log_paths
        self.skip_existing = skip_existing
        self._file_pos    = {}

        if skip_existing:
            # Seek to end of each file so we only pick up NEW lines
            for path in self.log_paths:
                if os.path.exists(path):
                    try:
                        self._file_pos[path] = os.path.getsize(path)
                        print(f"[Agent] Skipping existing logs in {path} (starting from end)")
                    except Exception:
                        self._file_pos[path] = 0

    def read_new_lines(self) -> list[tuple[str, str]]:
        """Returns list of (source_path, log_line) for all new log lines."""
        results = []
        for path in self.log_paths:
            if not os.path.exists(path):
                continue
            try:
                with open(path, "r", errors="ignore") as f:
                    # Seek to last known position
                    f.seek(self._file_pos.get(path, 0))
                    new_lines = f.readlines()
                    self._file_pos[path] = f.tell()

                for line in new_lines:
                    line = line.strip()
                    if line:
                        results.append((path, line))
            except PermissionError:
                print(f"[Agent] Permission denied: {path}")
        return results


# ─────────────────────────────────────────────
#  2. FILE INTEGRITY MONITOR — detects file changes
# ─────────────────────────────────────────────
class FileIntegrityMonitor:
    """
    Hashes watched files and reports when they change.
    Catches unauthorized modifications to critical files.
    """
    def __init__(self, watch_paths: list):
        self.watch_paths  = watch_paths
        self._known_hashes = {}
        self._baseline()

    def _hash_file(self, path: str) -> str | None:
        """Returns MD5 hash of a file, or None if unreadable."""
        try:
            with open(path, "rb") as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return None

    def _baseline(self):
        """Record initial hashes of all watched files."""
        for path in self.watch_paths:
            h = self._hash_file(path)
            if h:
                self._known_hashes[path] = h
                print(f"[FIM] Baseline: {path} → {h}")

    def check_changes(self) -> list[str]:
        """Returns list of FIM alert strings for any changed files."""
        alerts = []
        for path in self.watch_paths:
            current = self._hash_file(path)
            if current is None:
                continue
            if path not in self._known_hashes:
                self._known_hashes[path] = current
            elif current != self._known_hashes[path]:
                msg = f"FIM ALERT: {path} was MODIFIED (old={self._known_hashes[path]} new={current})"
                alerts.append(msg)
                self._known_hashes[path] = current  # Update baseline
        return alerts


# ─────────────────────────────────────────────
#  3. AGENT — main class that ships data to manager
# ─────────────────────────────────────────────
class Agent:
    def __init__(self):
        self.log_reader      = LogReader(LOG_SOURCES)
        self.fim             = FileIntegrityMonitor(FIM_WATCH_PATHS)
        self.system_monitor  = SystemMonitor()
        self.student_monitor = StudentActivityMonitor()   # ← Lab/exam monitor
        self.sock            = None

    # --- Connection ---
    def connect(self):
        """Establish TCP connection to the Central Manager."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((MANAGER_HOST, MANAGER_PORT))
        print(f"[Agent] Connected to Manager at {MANAGER_HOST}:{MANAGER_PORT}")

    def reconnect(self):
        """Retry connection if dropped."""
        while True:
            try:
                print("[Agent] Reconnecting...")
                self.connect()
                return
            except Exception as e:
                print(f"[Agent] Reconnect failed: {e}. Retrying in 5s...")
                time.sleep(5)

    # --- Sending ---
    def send_event(self, source: str, raw_log: str):
        """Wrap a log line in a LogEvent and send to manager."""
        event = LogEvent(
            agent_id=AGENT_ID,
            hostname=AGENT_HOSTNAME,
            source=source,
            raw_log=raw_log
        )
        payload = event.to_json() + "\n"   # Newline = message delimiter
        try:
            self.sock.sendall(payload.encode("utf-8"))
        except Exception as e:
            print(f"[Agent] Send failed: {e}")
            self.reconnect()

    # --- Main Loop ---
    def run(self):
        """Main agent loop: collect → send → sleep → repeat."""
        print(f"[Agent] Starting | ID={AGENT_ID} | Host={AGENT_HOSTNAME}")
        self.connect()

        while True:
            # 1. Read new log lines from log files
            new_logs = self.log_reader.read_new_lines()
            for source, line in new_logs:
                self.send_event(source, line)

            # 2. Check file integrity
            fim_alerts = self.fim.check_changes()
            for alert_msg in fim_alerts:
                self.send_event("FIM", alert_msg)

            # 3. Full system monitoring (USB, processes, network, logins, etc.)
            sys_events = self.system_monitor.collect()
            for source, event_msg in sys_events:
                self.send_event(source, event_msg)

            # 4. Student activity monitoring (browser, windows, lab USB)
            student_events = self.student_monitor.collect()
            for source, event_msg in student_events:
                self.send_event(source, event_msg)

            total = len(new_logs) + len(fim_alerts) + len(sys_events) + len(student_events)
            if total > 0:
                print(f"[Agent] Sent {len(new_logs)} logs | {len(fim_alerts)} FIM | "
                      f"{len(sys_events)} system | {len(student_events)} student events")

            time.sleep(AGENT_SEND_INTERVAL)


# ─────────────────────────────────────────────
#  Entry Point
# ─────────────────────────────────────────────
if __name__ == "__main__":
    agent = Agent()
    agent.run()
