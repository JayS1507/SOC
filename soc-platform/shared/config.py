# ============================================================
#  SOC Platform - Shared Configuration
# ============================================================

# --- Manager Server ---
MANAGER_HOST = "127.0.0.1"       # Change to manager's IP in real deployment
MANAGER_PORT = 9000               # Port agents connect to
MANAGER_BUFFER_SIZE = 4096        # Bytes per recv() call

# --- API Server ---
API_HOST = "0.0.0.0"
API_PORT = 8000

# --- Database ---
DB_PATH = "soc_platform.db"       # SQLite file path (swap for Postgres URI later)

# --- Agent ---
AGENT_SEND_INTERVAL = 1           # Seconds between log batches
AGENT_ID = "agent-001"            # Unique ID per machine (change per install)
AGENT_HOSTNAME = "lab-machine-1"  # Human-readable name

# --- Severity Levels ---
SEVERITY = {
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
    "CRITICAL": 4
}

# --- Log Sources (Agent collects these) ---
LOG_SOURCES = [
    "/var/log/syslog",
    "/var/log/auth.log",
]

# --- File Integrity Monitoring ---
FIM_WATCH_PATHS = [
    "/etc/passwd",
    "/etc/shadow",
    "/etc/hosts",
]
