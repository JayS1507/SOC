# ============================================================
#  SOC Platform - Central Manager / Server
#  Listens for incoming Agent connections.
#  For each log received → runs Rule Engine → saves to DB.
# ============================================================

import socket
import threading
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from shared.config import MANAGER_HOST, MANAGER_PORT, MANAGER_BUFFER_SIZE
from shared.models  import LogEvent
from rule_engine.engine import RuleEngine
from database.db import init_db, insert_log, insert_alert, upsert_agent


# ─────────────────────────────────────────────
#  Client Handler — one thread per Agent
# ─────────────────────────────────────────────
class AgentHandler(threading.Thread):
    """
    Spawned for each connected Agent.
    Reads newline-delimited JSON log events and processes them.
    """
    def __init__(self, conn: socket.socket, addr: tuple, engine: RuleEngine):
        super().__init__(daemon=True)
        self.conn   = conn
        self.addr   = addr
        self.engine = engine

    def run(self):
        print(f"[Manager] Agent connected from {self.addr}")
        buffer = ""

        try:
            while True:
                data = self.conn.recv(MANAGER_BUFFER_SIZE)
                if not data:
                    break  # Agent disconnected

                buffer += data.decode("utf-8", errors="ignore")

                # Messages are newline-delimited — process complete ones
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if line:
                        self._process(line)

        except ConnectionResetError:
            pass
        except Exception as e:
            print(f"[Manager] Error from {self.addr}: {e}")
        finally:
            self.conn.close()
            print(f"[Manager] Agent disconnected: {self.addr}")

    def _process(self, raw: str):
        """Deserialize a JSON log event → rule check → save to DB."""
        try:
            import json
            data = json.loads(raw)

            # ── Heartbeat message — just update agent last_seen, no alert ──
            if data.get("type") == "heartbeat":
                upsert_agent(data["agent_id"], data["hostname"])
                return

            # ── Normal log event ──
            event = LogEvent.from_json(raw)
            upsert_agent(event.agent_id, event.hostname)
            insert_log(event)
            alerts = self.engine.evaluate(event)
            for alert in alerts:
                insert_alert(alert)

        except Exception as e:
            print(f"[Manager] Failed to process event: {e} | raw={raw[:80]}")


# ─────────────────────────────────────────────
#  Manager Server
# ─────────────────────────────────────────────
class Manager:
    def __init__(self):
        self.engine = RuleEngine()

    def start(self):
        """Start the TCP server and listen for agent connections."""
        init_db()   # Ensure DB tables exist

        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((MANAGER_HOST, MANAGER_PORT))
        server.listen(50)   # Up to 50 queued connections

        print(f"[Manager] Listening on {MANAGER_HOST}:{MANAGER_PORT}")
        print(f"[Manager] Waiting for agents...")

        while True:
            try:
                conn, addr = server.accept()
                handler = AgentHandler(conn, addr, self.engine)
                handler.start()
            except KeyboardInterrupt:
                print("\n[Manager] Shutting down...")
                break
            except Exception as e:
                print(f"[Manager] Accept error: {e}")

        server.close()


# ─────────────────────────────────────────────
#  Entry Point
# ─────────────────────────────────────────────
if __name__ == "__main__":
    mgr = Manager()
    mgr.start()
