# SOC Platform - Windows Installation Script
# Run as Administrator

Write-Host "====================================" -ForegroundColor Cyan
Write-Host "  SOC Platform - Windows Installer  " -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan
Write-Host ""

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "[ERROR] This script must be run as Administrator!" -ForegroundColor Red
    Write-Host "Right-click PowerShell and select 'Run as Administrator'" -ForegroundColor Yellow
    pause
    exit 1
}

Write-Host "[OK] Running as Administrator" -ForegroundColor Green

# Check Python installation
Write-Host "`nChecking Python installation..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "[OK] Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Python not found!" -ForegroundColor Red
    Write-Host "Please install Python 3.8+ from https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "Make sure to check 'Add Python to PATH' during installation" -ForegroundColor Yellow
    pause
    exit 1
}

# Get installation type
Write-Host "`n====================================" -ForegroundColor Cyan
Write-Host "Select Installation Type:" -ForegroundColor Cyan
Write-Host "1. Manager Server (central server)" -ForegroundColor White
Write-Host "2. Agent (install on lab machines)" -ForegroundColor White
Write-Host "====================================" -ForegroundColor Cyan
$installType = Read-Host "Enter choice (1 or 2)"

# Get current directory
$installDir = Get-Location

# Install Python dependencies
Write-Host "`nInstalling Python dependencies..." -ForegroundColor Yellow
try {
    python -m pip install --upgrade pip
    pip install -r "$installDir\requirements.txt"
    Write-Host "[OK] Dependencies installed" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Failed to install dependencies: $_" -ForegroundColor Red
    pause
    exit 1
}

# Create .env file if it doesn't exist
if (-not (Test-Path "$installDir\.env")) {
    Write-Host "`nCreating .env configuration file..." -ForegroundColor Yellow
    Copy-Item "$installDir\.env.example" "$installDir\.env"
    Write-Host "[OK] Created .env file" -ForegroundColor Green
    Write-Host "[INFO] Please edit .env file to configure your deployment" -ForegroundColor Yellow
}

# Generate TLS certificates
Write-Host "`nGenerating TLS certificates..." -ForegroundColor Yellow
$certsDir = "$installDir\certs"
if (-not (Test-Path $certsDir)) {
    New-Item -ItemType Directory -Path $certsDir | Out-Null
}

python -c @"
from shared.security import CertificateManager
from pathlib import Path
cert_dir = Path('$certsDir')
try:
    CertificateManager.generate_self_signed_cert(cert_dir)
    print('[OK] TLS certificates generated')
except Exception as e:
    print(f'[ERROR] Certificate generation failed: {e}')
"@

if ($installType -eq "1") {
    # Manager Server Installation
    Write-Host "`n====================================" -ForegroundColor Cyan
    Write-Host "  Manager Server Installation       " -ForegroundColor Cyan
    Write-Host "====================================" -ForegroundColor Cyan
    
    # Configure Windows Firewall
    Write-Host "`nConfiguring Windows Firewall..." -ForegroundColor Yellow
    try {
        # Allow port 9000 for agent connections
        New-NetFirewallRule -DisplayName "SOC Manager - Agent Port" -Direction Inbound -Protocol TCP -LocalPort 9000 -Action Allow -ErrorAction SilentlyContinue
        
        # Allow port 8000 for web dashboard
        New-NetFirewallRule -DisplayName "SOC Manager - Dashboard Port" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow -ErrorAction SilentlyContinue
        
        Write-Host "[OK] Firewall rules created" -ForegroundColor Green
    } catch {
        Write-Host "[WARNING] Could not create firewall rules: $_" -ForegroundColor Yellow
        Write-Host "You may need to manually allow ports 9000 and 8000" -ForegroundColor Yellow
    }
    
    # Create start script
    Write-Host "`nCreating startup scripts..." -ForegroundColor Yellow
    
    $managerScript = @"
@echo off
echo Starting SOC Manager...
cd /d "$installDir"
python manager/manager.py
pause
"@
    Set-Content -Path "$installDir\start_manager.bat" -Value $managerScript
    
    $dashboardScript = @"
@echo off
echo Starting SOC Dashboard...
cd /d "$installDir"
python dashboard/api.py
pause
"@
    Set-Content -Path "$installDir\start_dashboard.bat" -Value $dashboardScript
    
    Write-Host "[OK] Created start_manager.bat and start_dashboard.bat" -ForegroundColor Green
    
    Write-Host "`n====================================" -ForegroundColor Green
    Write-Host "  Manager Installation Complete!    " -ForegroundColor Green
    Write-Host "====================================" -ForegroundColor Green
    Write-Host "`nNext Steps:" -ForegroundColor Yellow
    Write-Host "1. Edit .env file and set AUTH_SECRET_KEY, API_KEY, etc." -ForegroundColor White
    Write-Host "2. Run start_manager.bat to start the manager server" -ForegroundColor White
    Write-Host "3. Run start_dashboard.bat to start the web dashboard" -ForegroundColor White
    Write-Host "4. Access dashboard at http://localhost:8000" -ForegroundColor White
    
} elseif ($installType -eq "2") {
    # Agent Installation
    Write-Host "`n====================================" -ForegroundColor Cyan
    Write-Host "  Agent Installation                " -ForegroundColor Cyan
    Write-Host "====================================" -ForegroundColor Cyan
    
    # Get manager server IP
    $managerIP = Read-Host "`nEnter Manager Server IP address"
    $agentID = Read-Host "Enter unique Agent ID (e.g., agent-lab-pc-01)"
    
    # Update .env file
    Write-Host "`nConfiguring agent..." -ForegroundColor Yellow
    $envContent = Get-Content "$installDir\.env"
    $envContent = $envContent -replace "MANAGER_HOST=.*", "MANAGER_HOST=$managerIP"
    $envContent = $envContent -replace "AGENT_ID=.*", "AGENT_ID=$agentID"
    Set-Content -Path "$installDir\.env" -Value $envContent
    
    # Configure Windows Firewall for outbound
    Write-Host "Configuring Windows Firewall..." -ForegroundColor Yellow
    try {
        New-NetFirewallRule -DisplayName "SOC Agent - Outbound" -Direction Outbound -Protocol TCP -RemotePort 9000 -Action Allow -ErrorAction SilentlyContinue
        Write-Host "[OK] Firewall rule created" -ForegroundColor Green
    } catch {
        Write-Host "[WARNING] Could not create firewall rule: $_" -ForegroundColor Yellow
    }
    
    # Create Windows Service (optional)
    Write-Host "`nDo you want to install the agent as a Windows Service?" -ForegroundColor Yellow
    Write-Host "(Service will auto-start on boot)" -ForegroundColor Yellow
    $createService = Read-Host "Install as service? (y/n)"
    
    if ($createService -eq "y") {
        # Create service wrapper script
        $serviceScript = @"
import win32serviceutil
import win32service
import win32event
import servicemanager
import socket
import sys
import os
import time

# Add SOC platform to path
sys.path.insert(0, r'$installDir')

class SOCAgentService(win32serviceutil.ServiceFramework):
    _svc_name_ = 'SOCAgent'
    _svc_display_name_ = 'SOC Monitoring Agent'
    _svc_description_ = 'Student activity monitoring agent for SOC platform'
    
    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        socket.setdefaulttimeout(60)
        self.is_running = True
    
    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)
        self.is_running = False
    
    def SvcDoRun(self):
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                            servicemanager.PYS_SERVICE_STARTED,
                            (self._svc_name_, ''))
        self.main()
    
    def main(self):
        os.chdir(r'$installDir')
        from agent import agent
        # Agent main loop runs here
        # This will be imported and executed

if __name__ == '__main__':
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(SOCAgentService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(SOCAgentService)
"@
        Set-Content -Path "$installDir\agent\service.py" -Value $serviceScript
        
        # Install service
        Write-Host "Installing Windows Service..." -ForegroundColor Yellow
        try {
            python "$installDir\agent\service.py" install
            Write-Host "[OK] Service installed" -ForegroundColor Green
            Write-Host "Use 'net start SOCAgent' to start the service" -ForegroundColor Yellow
        } catch {
            Write-Host "[ERROR] Service installation failed: $_" -ForegroundColor Red
            Write-Host "You can still run the agent manually" -ForegroundColor Yellow
        }
    }
    
    # Create manual start script
    $agentScript = @"
@echo off
echo Starting SOC Agent...
cd /d "$installDir"
python agent/agent.py
pause
"@
    Set-Content -Path "$installDir\start_agent.bat" -Value $agentScript
    
    Write-Host "`n====================================" -ForegroundColor Green
    Write-Host "  Agent Installation Complete!      " -ForegroundColor Green
    Write-Host "====================================" -ForegroundColor Green
    Write-Host "`nNext Steps:" -ForegroundColor Yellow
    if ($createService -eq "y") {
        Write-Host "1. Start service: net start SOCAgent" -ForegroundColor White
        Write-Host "2. Or run manually: start_agent.bat" -ForegroundColor White
    } else {
        Write-Host "1. Run start_agent.bat to start the agent" -ForegroundColor White
    }
    Write-Host "`nAgent will connect to: $managerIP:9000" -ForegroundColor Cyan
}

Write-Host "`n====================================" -ForegroundColor Cyan
Write-Host "  Installation Complete!            " -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan

pause
