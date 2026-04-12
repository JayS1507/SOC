# Deployment Guide - Live Machine (168.144.73.18)

## Quick Deployment Steps

### 1. Push Code to Live Machine

```bash
# From your local machine
git add .
git commit -m "Add macOS support to student monitor + manager connection config"
git push origin main

# OR manually SSH and pull:
ssh root@168.144.73.18
cd /path/to/SOC-main/soc-platform
git pull origin main
```

### 2. Install/Update Dependencies

```bash
cd /Users/anshul/Documents/SOC-main/soc-platform
pip install -r requirements.txt
```

### 3. Verify Configuration

```bash
# Check manager host is set correctly
cat shared/config.py | grep MANAGER_HOST

# Check agent identity
cat shared/config.py | grep AGENT_ID
cat shared/config.py | grep AGENT_HOSTNAME
```

### 4. Run Tests on Live Machine

```bash
# Test all monitors
python test_student_monitor.py

# Test with activity
python test_with_events.py

# Verify connectivity
python -m agent.agent  # Should connect to manager
```

### 5. Start Agent as Service

```bash
# Option 1: Background process
nohup python -m agent.agent > agent.log 2>&1 &

# Option 2: Systemd service (recommended for production)
# Create /etc/systemd/system/soc-agent.service:
[Unit]
Description=SOC Platform Agent
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/Users/anshul/Documents/SOC-main/soc-platform
ExecStart=/usr/bin/python -m agent.agent
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target

# Then:
systemctl daemon-reload
systemctl start soc-agent
systemctl enable soc-agent
systemctl status soc-agent
```

### 6. Monitor Live Agent

```bash
# Check agent logs
tail -f agent.log

# Check if agent is connected
ps aux | grep agent.agent

# Check if sending data to manager
# Monitor on manager machine:
tail -f /var/log/soc-manager.log
```

---

## What Changed in Code

### Configuration (shared/config.py)
- `MANAGER_HOST = "168.144.73.18"` (was "0.0.0.0")
- `AGENT_ID = "anshul"`
- `AGENT_HOSTNAME = "anshul"`

### Agent (agent/agent.py)
- Fixed to use `MANAGER_HOST` from config instead of hardcoded "127.0.0.1"

### Student Monitor (agent/student_monitor.py)
- Added macOS browser paths
- Added AppleScript-based window detection for macOS
- Added Windows API window detection
- Maintained full backward compatibility

---

## Rollback Plan

If issues occur on live machine:

```bash
# Stop agent
pkill -f "python.*agent.agent"

# Revert to previous version
git revert HEAD
git push origin main

# Restart
python -m agent.agent
```

---

## Testing Checklist for Live Machine

- [ ] Agent starts without errors
- [ ] Connects to manager at 168.144.73.18:9000
- [ ] Browser history detected
- [ ] Window monitoring working
- [ ] Shell hooks installed
- [ ] Logs flowing to manager
- [ ] No high CPU/memory usage
- [ ] Agent restarts after network interruption

---

## Support

**Test Files Location:**
- [LOCAL_TEST_REPORT.md](LOCAL_TEST_REPORT.md)
- [test_student_monitor.py](test_student_monitor.py)
- [test_with_events.py](test_with_events.py)

**Run these on live machine to verify:**
```bash
python test_student_monitor.py
python test_with_events.py
```

---

Ready to deploy! 🚀
