"""
Windows-Specific System Monitors
USB devices, PowerShell history, Active Window tracking
Requires: pywin32, wmi (Windows only)
"""

import sys
import os
import time
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

# Windows-only imports
if sys.platform == 'win32':
    import win32gui
    import win32process
    import win32api
    import win32con
    import psutil
    try:
        import wmi
    except ImportError:
        wmi = None

class WindowsUSBMonitor:
    """Monitor USB device connections using WMI"""
    
    def __init__(self):
        if sys.platform != 'win32':
            raise RuntimeError("WindowsUSBMonitor only works on Windows")
        if wmi is None:
            raise RuntimeError("WMI library not installed. Install with: pip install wmi")
        
        self.wmi = wmi.WMI()
        self.known_devices = set()
        self._initialize()
    
    def _initialize(self):
        """Get initial USB devices"""
        for device in self.wmi.Win32_USBHub():
            self.known_devices.add(device.DeviceID)
    
    def check_new_devices(self) -> List[Dict]:
        """Check for new USB devices"""
        events = []
        current_devices = set()
        
        try:
            for device in self.wmi.Win32_USBHub():
                device_id = device.DeviceID
                current_devices.add(device_id)
                
                if device_id not in self.known_devices:
                    # New device detected
                    events.append({
                        "timestamp": datetime.now().isoformat(),
                        "event_type": "USB_CONNECTED",
                        "device_id": device_id,
                        "description": device.Description or "Unknown USB Device",
                        "status": device.Status or "Unknown"
                    })
                    self.known_devices.add(device_id)
            
            # Check for removed devices
            removed = self.known_devices - current_devices
            for device_id in removed:
                events.append({
                    "timestamp": datetime.now().isoformat(),
                    "event_type": "USB_DISCONNECTED",
                    "device_id": device_id
                })
                self.known_devices.remove(device_id)
        
        except Exception as e:
            print(f"[WindowsUSB] Error checking devices: {e}")
        
        return events

class WindowsPowerShellMonitor:
    """Monitor PowerShell command history"""
    
    def __init__(self):
        if sys.platform != 'win32':
            raise RuntimeError("WindowsPowerShellMonitor only works on Windows")
        
        # PowerShell history file location
        appdata = os.getenv('APPDATA', '')
        self.history_file = Path(appdata) / "Microsoft" / "Windows" / "PowerShell" / "PSReadLine" / "ConsoleHost_history.txt"
        self.last_position = 0
        self.last_inode = None
        
        if self.history_file.exists():
            self.last_position = self.history_file.stat().st_size
            self.last_inode = self.history_file.stat().st_ino
    
    def collect_new_commands(self) -> List[Dict]:
        """Read new PowerShell commands from history"""
        events = []
        
        if not self.history_file.exists():
            return events
        
        try:
            stat = self.history_file.stat()
            
            # Check if file was recreated (different inode/file ID)
            if self.last_inode is not None and stat.st_ino != self.last_inode:
                self.last_position = 0
                self.last_inode = stat.st_ino
            
            # Check if file has new content
            if stat.st_size > self.last_position:
                with open(self.history_file, 'r', encoding='utf-8', errors='ignore') as f:
                    f.seek(self.last_position)
                    new_lines = f.readlines()
                    self.last_position = f.tell()
                
                for line in new_lines:
                    line = line.strip()
                    if line:
                        events.append({
                            "timestamp": datetime.now().isoformat(),
                            "event_type": "POWERSHELL_COMMAND",
                            "command": line
                        })
        
        except Exception as e:
            print(f"[PowerShell] Error reading history: {e}")
        
        return events

class WindowsActiveWindowMonitor:
    """Monitor active window (foreground application)"""
    
    def __init__(self, check_interval: int = 5):
        if sys.platform != 'win32':
            raise RuntimeError("WindowsActiveWindowMonitor only works on Windows")
        
        self.check_interval = check_interval
        self.last_window = None
        self.last_check = time.time()
    
    def get_active_window(self) -> Optional[Dict]:
        """Get currently active window information"""
        try:
            # Get foreground window handle
            hwnd = win32gui.GetForegroundWindow()
            
            if hwnd == 0:
                return None
            
            # Get window title
            window_title = win32gui.GetWindowText(hwnd)
            
            # Get process ID
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            
            # Get process name
            try:
                process = psutil.Process(pid)
                process_name = process.name()
                process_exe = process.exe()
            except:
                process_name = "Unknown"
                process_exe = "Unknown"
            
            return {
                "timestamp": datetime.now().isoformat(),
                "window_title": window_title,
                "process_name": process_name,
                "process_exe": process_exe,
                "pid": pid
            }
        
        except Exception as e:
            print(f"[ActiveWindow] Error: {e}")
            return None
    
    def check_window_change(self) -> Optional[Dict]:
        """Check if active window has changed"""
        now = time.time()
        
        # Only check at specified interval
        if now - self.last_check < self.check_interval:
            return None
        
        self.last_check = now
        current = self.get_active_window()
        
        if current is None:
            return None
        
        # Check if window changed
        current_key = (current['window_title'], current['process_name'])
        
        if self.last_window != current_key:
            self.last_window = current_key
            return {
                "timestamp": current['timestamp'],
                "event_type": "WINDOW_FOCUS_CHANGED",
                "window_title": current['window_title'],
                "process_name": current['process_name'],
                "process_exe": current['process_exe'],
                "pid": current['pid']
            }
        
        return None

class WindowsProcessMonitor:
    """Monitor process creation and termination"""
    
    def __init__(self):
        if sys.platform != 'win32':
            raise RuntimeError("WindowsProcessMonitor only works on Windows")
        
        self.known_pids = set(p.pid for p in psutil.process_iter(['pid']))
    
    def check_new_processes(self) -> List[Dict]:
        """Check for new or terminated processes"""
        events = []
        current_pids = set()
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'exe', 'username', 'create_time']):
                try:
                    pid = proc.info['pid']
                    current_pids.add(pid)
                    
                    if pid not in self.known_pids:
                        # New process
                        events.append({
                            "timestamp": datetime.now().isoformat(),
                            "event_type": "PROCESS_STARTED",
                            "pid": pid,
                            "name": proc.info['name'],
                            "exe": proc.info.get('exe', 'N/A'),
                            "username": proc.info.get('username', 'N/A'),
                            "start_time": datetime.fromtimestamp(proc.info.get('create_time', 0)).isoformat()
                        })
                        self.known_pids.add(pid)
                
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # Check for terminated processes
            terminated = self.known_pids - current_pids
            for pid in terminated:
                events.append({
                    "timestamp": datetime.now().isoformat(),
                    "event_type": "PROCESS_TERMINATED",
                    "pid": pid
                })
                self.known_pids.remove(pid)
        
        except Exception as e:
            print(f"[ProcessMonitor] Error: {e}")
        
        return events

# Format functions for SOC platform
def format_usb_event(event: Dict) -> str:
    """Format USB event for logging"""
    if event['event_type'] == 'USB_CONNECTED':
        return f"USB Device Connected: {event['description']} (ID: {event['device_id']})"
    else:
        return f"USB Device Disconnected: {event['device_id']}"

def format_powershell_event(event: Dict) -> str:
    """Format PowerShell command for logging"""
    return f"PowerShell: {event['command']}"

def format_window_event(event: Dict) -> str:
    """Format window change event"""
    return f"Window Focus: {event['window_title']} ({event['process_name']})"

def format_process_event(event: Dict) -> str:
    """Format process event"""
    if event['event_type'] == 'PROCESS_STARTED':
        return f"Process Started: {event['name']} (PID: {event['pid']}, User: {event.get('username', 'N/A')})"
    else:
        return f"Process Terminated: PID {event['pid']}"

# Test
if __name__ == "__main__":
    if sys.platform != 'win32':
        print("This module only works on Windows")
        sys.exit(1)
    
    print("[WindowsMonitors] Testing monitors...")
    
    # Test PowerShell history
    ps_monitor = WindowsPowerShellMonitor()
    cmds = ps_monitor.collect_new_commands()
    print(f"\n[PowerShell] Recent commands: {len(cmds)}")
    for cmd in cmds[-5:]:
        print(f"  {format_powershell_event(cmd)}")
    
    # Test active window
    win_monitor = WindowsActiveWindowMonitor()
    current = win_monitor.get_active_window()
    if current:
        print(f"\n[ActiveWindow] Current: {current['window_title']} ({current['process_name']})")
    
    # Test USB (if wmi available)
    if wmi:
        usb_monitor = WindowsUSBMonitor()
        print(f"\n[USB] Known devices: {len(usb_monitor.known_devices)}")
    
    print("\n[WindowsMonitors] All tests completed")
