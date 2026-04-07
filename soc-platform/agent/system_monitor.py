# ============================================================
#  SOC Platform - System Monitor
#  Runs inside the Agent — monitors system events:
#  USB, Processes, Network, Logins, Resources, Cron, Privesc
# ============================================================

import os
import sys
import time
import hashlib
import subprocess

try:
    import psutil
except ImportError:
    print("[SystemMonitor] Install psutil: pip install psutil")
    sys.exit(1)


# ══════════════════════════════════════════════════════════════
#  1. USB MONITOR
# ══════════════════════════════════════════════════════════════
class USBMonitor:
    """Detects USB device plug/unplug via /sys/bus/usb/devices."""

    def __init__(self):
        self._known_devices = self._get_devices()
        self._known_mounts   = self._get_mounts()
        print(f"[USBMonitor] Baseline: {len(self._known_devices)} USB devices, "
              f"{len(self._known_mounts)} mounts")

    def _get_devices(self) -> dict:
        devices = {}
        base = "/sys/bus/usb/devices"
        if not os.path.exists(base):
            return devices
        for dev_id in os.listdir(base):
            dev_path = os.path.join(base, dev_id)
            info = {"id": dev_id}
            for field, fname in [("vendor", "idVendor"), ("product", "idProduct"),
                                  ("name", "product"), ("manufacturer", "manufacturer")]:
                fpath = os.path.join(dev_path, fname)
                try:
                    with open(fpath) as f:
                        info[field] = f.read().strip()
                except Exception:
                    info[field] = ""
            devices[dev_id] = info
        return devices

    def _get_mounts(self) -> set:
        mounts = set()
        try:
            for p in psutil.disk_partitions():
                if "usb" in p.opts.lower() or p.fstype in ("vfat", "ntfs", "exfat"):
                    mounts.add(p.mountpoint)
        except Exception:
            pass
        return mounts

    def check(self) -> list:
        events = []
        current = self._get_devices()

        for dev_id, info in current.items():
            if dev_id not in self._known_devices:
                vp = f"{info.get('vendor','')}:{info.get('product','')}"
                name = info.get('name', '')
                events.append(
                    f"USB_CONNECT: Device plugged in | ID={dev_id} | "
                    f"VendorProduct={vp} | Name={name}"
                )

        for dev_id, info in self._known_devices.items():
            if dev_id not in current:
                vp = f"{info.get('vendor','')}:{info.get('product','')}"
                name = info.get('name', '')
                events.append(
                    f"USB_DISCONNECT: Device removed | ID={dev_id} | "
                    f"VendorProduct={vp} | Name={name}"
                )

        self._known_devices = current
        return events


# ══════════════════════════════════════════════════════════════
#  2. PROCESS MONITOR
# ══════════════════════════════════════════════════════════════
class ProcessMonitor:
    """Detects new processes, especially root processes and known attack tools."""

    SUSPICIOUS_TOOLS = {
        "nmap", "netcat", "nc", "ncat", "hydra", "john", "hashcat",
        "aircrack", "wireshark", "tcpdump", "metasploit", "msfconsole",
        "sqlmap", "nikto", "dirb", "gobuster", "wfuzz", "burpsuite",
        "masscan", "zmap", "hping3", "ettercap", "bettercap",
        "responder", "mimikatz", "crackmapexec", "impacket",
    }

    # Terminal emulators — students opening cmd during exam
    TERMINAL_APPS = {
        "bash", "zsh", "sh", "fish", "ksh",                          # shells
        "gnome-terminal", "xterm", "konsole", "xfce4-terminal",       # GUI terminals
        "terminator", "alacritty", "kitty", "tilix", "lxterminal",
        "mate-terminal", "deepin-terminal", "foot", "wezterm",
        "xfce4-terminal", "qterminal",
    }

    def __init__(self):
        self._known_pids = {p.pid for p in psutil.process_iter(['pid'])}
        print(f"[ProcessMonitor] Baseline: {len(self._known_pids)} processes")

    def check(self) -> list:
        events = []
        try:
            current_procs = {p.pid: p for p in psutil.process_iter(
                ['pid', 'name', 'username', 'cmdline'])}
        except Exception:
            return events

        new_pids = set(current_procs.keys()) - self._known_pids

        for pid in new_pids:
            try:
                p = current_procs[pid]
                name = p.info.get('name', '') or ''
                user = p.info.get('username', '') or ''
                cmd  = ' '.join(p.info.get('cmdline', []) or [])[:80]

                # Suspicious attack tools
                if name.lower() in self.SUSPICIOUS_TOOLS:
                    events.append(
                        f"SUSPICIOUS_PROCESS: Attack tool detected | "
                        f"PID={pid} | Name={name} | User={user} | CMD={cmd}"
                    )
                # Terminal/shell opened — suspicious during exam
                elif name.lower() in self.TERMINAL_APPS:
                    events.append(
                        f"TERMINAL_OPENED: Student opened a terminal/shell | "
                        f"PID={pid} | Name={name} | User={user} | CMD={cmd}"
                    )
                # New root processes
                elif user == 'root':
                    events.append(
                        f"NEW_ROOT_PROCESS: New root process | "
                        f"PID={pid} | Name={name} | CMD={cmd}"
                    )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        self._known_pids = set(current_procs.keys())
        return events


# ══════════════════════════════════════════════════════════════
#  3. NETWORK MONITOR
# ══════════════════════════════════════════════════════════════
class NetworkMonitor:
    """Detects new TCP connections and suspicious ports."""

    SUSPICIOUS_PORTS = {4444, 1337, 6667, 31337, 9001, 8080, 4443}

    def __init__(self):
        self._known_conns     = self._get_connections()
        self._known_listeners = self._get_listeners()
        print(f"[NetworkMonitor] Baseline: {len(self._known_conns)} connections, "
              f"{len(self._known_listeners)} listeners")

    def _get_connections(self) -> set:
        conns = set()
        try:
            for c in psutil.net_connections(kind='tcp'):
                if c.status == 'ESTABLISHED' and c.raddr:
                    conns.add((c.laddr.port, c.raddr.ip, c.raddr.port))
        except Exception:
            pass
        return conns

    def _get_listeners(self) -> set:
        listeners = set()
        try:
            for c in psutil.net_connections(kind='tcp'):
                if c.status == 'LISTEN':
                    listeners.add(c.laddr.port)
        except Exception:
            pass
        return listeners

    def check(self) -> list:
        events = []
        current = self._get_connections()
        new_conns = current - self._known_conns

        for lport, rip, rport in new_conns:
            if rport in self.SUSPICIOUS_PORTS or lport in self.SUSPICIOUS_PORTS:
                events.append(
                    f"SUSPICIOUS_CONNECTION: Connection on suspicious port | "
                    f"LocalPort={lport} | RemoteIP={rip} | RemotePort={rport}"
                )
            else:
                events.append(
                    f"NEW_CONNECTION: New TCP connection | "
                    f"LocalPort={lport} | RemoteIP={rip} | RemotePort={rport}"
                )

        # New listeners
        current_listeners = self._get_listeners()
        new_listeners = current_listeners - self._known_listeners
        for port in new_listeners:
            events.append(f"NEW_LISTENER: New port listening | Port={port}")

        self._known_conns     = current
        self._known_listeners = current_listeners
        return events


# ══════════════════════════════════════════════════════════════
#  4. LOGIN MONITOR
# ══════════════════════════════════════════════════════════════
class LoginMonitor:
    """Detects user logins and logouts via psutil.users()."""

    def __init__(self):
        self._known_sessions = self._get_sessions()
        print(f"[LoginMonitor] Baseline: {len(self._known_sessions)} active sessions")

    def _get_sessions(self) -> dict:
        sessions = {}
        try:
            for u in psutil.users():
                key = (u.name, u.terminal)
                sessions[key] = {"user": u.name, "terminal": u.terminal,
                                  "host": u.host or "local", "started": u.started}
        except Exception:
            pass
        return sessions

    def check(self) -> list:
        events = []
        current = self._get_sessions()

        for key, info in current.items():
            if key not in self._known_sessions:
                events.append(
                    f"USER_LOGIN: User logged in | User={info['user']} | "
                    f"Terminal={info['terminal']} | Source=from {info['host']}"
                )

        for key, info in self._known_sessions.items():
            if key not in current:
                events.append(
                    f"USER_LOGOUT: User logged out | User={info['user']} | "
                    f"Terminal={info['terminal']}"
                )

        self._known_sessions = current
        return events


# ══════════════════════════════════════════════════════════════
#  5. RESOURCE MONITOR
# ══════════════════════════════════════════════════════════════
class ResourceMonitor:
    """Monitors CPU, RAM, and disk usage. Alerts when > 90%."""

    THRESHOLD = 90.0
    # Alert at most once per 5 minutes per mount to avoid spam
    _disk_alerted: dict = {}
    DISK_ALERT_COOLDOWN = 300  # seconds

    # Snap packages are read-only squashfs — always 100%, skip them
    SKIP_FSTYPES = {"squashfs", "tmpfs", "devtmpfs", "overlay", "ramfs"}
    SKIP_MOUNT_PREFIXES = ("/snap/", "/proc/", "/sys/", "/dev/")

    def check(self) -> list:
        events = []
        now = time.time()
        try:
            cpu = psutil.cpu_percent(interval=1)
            if cpu > self.THRESHOLD:
                events.append(f"HIGH_CPU: CPU critically high | Usage={cpu}% | "
                               f"Possible crypto miner or DoS")

            ram = psutil.virtual_memory()
            if ram.percent > self.THRESHOLD:
                events.append(f"HIGH_RAM: Memory critically low | Usage={ram.percent}% | "
                               f"Available={ram.available // (1024**2)}MB")

            for disk in psutil.disk_partitions():
                # Skip snap/squashfs/virtual filesystems — they're always 100%
                if disk.fstype in self.SKIP_FSTYPES:
                    continue
                if any(disk.mountpoint.startswith(p) for p in self.SKIP_MOUNT_PREFIXES):
                    continue
                try:
                    usage = psutil.disk_usage(disk.mountpoint)
                    if usage.percent > self.THRESHOLD:
                        # Cooldown — don't re-alert same mount within 5 minutes
                        last = self._disk_alerted.get(disk.mountpoint, 0)
                        if now - last < self.DISK_ALERT_COOLDOWN:
                            continue
                        self._disk_alerted[disk.mountpoint] = now
                        free_gb = usage.free / (1024 ** 3)
                        events.append(
                            f"HIGH_DISK: Disk nearly full | Mount={disk.mountpoint} | "
                            f"Usage={usage.percent}% | Free={free_gb:.1f}GB | "
                            f"Possible log flood or ransomware"
                        )
                except Exception:
                    pass
        except Exception:
            pass
        return events


# ══════════════════════════════════════════════════════════════
#  6. CRON MONITOR
# ══════════════════════════════════════════════════════════════
class CronMonitor:
    """Watches cron directories for new or modified jobs (persistence technique)."""

    CRON_PATHS = [
        "/etc/cron.d", "/etc/cron.daily", "/etc/cron.hourly",
        "/etc/cron.weekly", "/etc/cron.monthly",
        "/var/spool/cron/crontabs",
    ]

    def __init__(self):
        self._known_files = self._get_cron_files()
        print(f"[CronMonitor] Baseline: {len(self._known_files)} cron files")

    def _get_cron_files(self) -> set:
        files = set()
        for path in self.CRON_PATHS:
            if not os.path.exists(path):
                continue
            try:
                entries = os.listdir(path)
            except PermissionError:
                continue
            for f in entries:
                full = os.path.join(path, f)
                try:
                    mtime = os.path.getmtime(full)
                    files.add(f"{full}|{mtime}")
                except Exception:
                    pass
        return files

    def check(self) -> list:
        events = []
        current = self._get_cron_files()

        new_files = current - self._known_files
        for entry in new_files:
            path = entry.split("|")[0]
            # Check if it's a truly new file or just modified
            known_paths = {e.split("|")[0] for e in self._known_files}
            if path not in known_paths:
                events.append(f"NEW_CRON_JOB: New cron job added | File={path}")
            else:
                events.append(f"CRON_MODIFIED: Cron job modified | File={path}")

        self._known_files = current
        return events


# ══════════════════════════════════════════════════════════════
#  7. PRIVILEGE ESCALATION MONITOR
# ══════════════════════════════════════════════════════════════
class PrivilegeMonitor:
    """Watches sudoers file and SUID binaries for privilege escalation."""

    SUDOERS_PATH = "/etc/sudoers"
    SUID_SEARCH_PATHS = ["/usr/bin", "/usr/sbin", "/bin", "/sbin"]

    def __init__(self):
        self._sudoers_hash = self._hash_sudoers()
        self._known_suid   = self._get_suid_files()
        sudoers_status = "unreadable" if not self._sudoers_hash else self._sudoers_hash[:8]
        print(f"[PrivMonitor] Baseline: sudoers hash={sudoers_status}, "
              f"{len(self._known_suid)} SUID files")

    def _hash_sudoers(self) -> str:
        try:
            with open(self.SUDOERS_PATH, "rb") as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return ""

    def _get_suid_files(self) -> set:
        suid = set()
        for search_path in self.SUID_SEARCH_PATHS:
            try:
                for fname in os.listdir(search_path):
                    fpath = os.path.join(search_path, fname)
                    try:
                        if os.stat(fpath).st_mode & 0o4000:
                            suid.add(fpath)
                    except Exception:
                        pass
            except Exception:
                pass
        return suid

    def check(self) -> list:
        events = []

        # Check sudoers
        current_hash = self._hash_sudoers()
        if current_hash and self._sudoers_hash and current_hash != self._sudoers_hash:
            events.append(
                f"SUDOERS_MODIFIED: /etc/sudoers was changed | "
                f"OldHash={self._sudoers_hash} | NewHash={current_hash}"
            )
            self._sudoers_hash = current_hash

        # Check for new SUID binaries
        current_suid = self._get_suid_files()
        new_suid = current_suid - self._known_suid
        for fpath in new_suid:
            events.append(f"NEW_SUID_BINARY: New SUID binary detected | Path={fpath}")
        self._known_suid = current_suid

        return events


# ══════════════════════════════════════════════════════════════
#  SYSTEM MONITOR — aggregates all sub-monitors
# ══════════════════════════════════════════════════════════════
class SystemMonitor:
    """
    Master monitor that runs all sub-monitors and returns
    (source_tag, event_string) tuples for the agent to ship.
    """

    SOURCE_MAP = {
        "USB":      USBMonitor,
        "PROCESS":  ProcessMonitor,
        "NETWORK":  NetworkMonitor,
        "LOGIN":    LoginMonitor,
        "RESOURCE": ResourceMonitor,
        "CRON":     CronMonitor,
        "PRIVESC":  PrivilegeMonitor,
    }

    def __init__(self):
        print("[SystemMonitor] Initializing all monitors...")
        self.monitors = {}
        for source, cls in self.SOURCE_MAP.items():
            try:
                self.monitors[source] = cls()
            except Exception as e:
                print(f"[SystemMonitor] Failed to init {source}: {e}")
        print("[SystemMonitor] All monitors ready ✓")

    def collect(self) -> list:
        """Run all monitors and return list of (source, event_string)."""
        results = []
        for source, monitor in self.monitors.items():
            try:
                events = monitor.check()
                for event in events:
                    print(f"[SystemMonitor][{source}] {event[:100]}")
                    results.append((source, event))
            except Exception as e:
                print(f"[SystemMonitor][{source}] Error: {e}")
        return results


# ── Standalone test ──────────────────────────────────────────
if __name__ == "__main__":
    mon = SystemMonitor()
    print("\n[Test] Running first collect (baseline only)...")
    mon.collect()
    print("\n[Test] Sleeping 5s then collecting again...")
    time.sleep(5)
    events = mon.collect()
    print(f"\n[Test] Got {len(events)} events")
    for source, event in events:
        print(f"  [{source}] {event}")
