#!/bin/bash

# SOC Platform - Ubuntu Installation Script
# Run with: sudo bash install_ubuntu.sh

echo "===================================="
echo "  SOC Platform - Ubuntu Installer  "
echo "===================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "[ERROR] This script must be run as root (use sudo)"
    exit 1
fi

echo "[OK] Running as root"

# Check Python installation
echo ""
echo "Checking Python installation..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo "[OK] Python found: $PYTHON_VERSION"
else
    echo "[ERROR] Python3 not found!"
    echo "Installing Python3..."
    apt-get update
    apt-get install -y python3 python3-pip python3-venv
fi

# Get installation directory
INSTALL_DIR=$(pwd)

# Get installation type
echo ""
echo "===================================="
echo "Select Installation Type:"
echo "1. Manager Server (central server)"
echo "2. Agent (install on lab machines)"
echo "===================================="
read -p "Enter choice (1 or 2): " INSTALL_TYPE

# Create virtual environment (optional but recommended)
echo ""
read -p "Create Python virtual environment? (recommended) (y/n): " CREATE_VENV

if [ "$CREATE_VENV" = "y" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    echo "[OK] Virtual environment created and activated"
fi

# Install dependencies
echo ""
echo "Installing Python dependencies..."
python3 -m pip install --upgrade pip
pip install -r requirements.txt

if [ $? -eq 0 ]; then
    echo "[OK] Dependencies installed"
else
    echo "[ERROR] Failed to install dependencies"
    exit 1
fi

# Create .env file
if [ ! -f ".env" ]; then
    echo ""
    echo "Creating .env configuration file..."
    cp .env.example .env
    echo "[OK] Created .env file"
    echo "[INFO] Please edit .env file to configure your deployment"
fi

# Generate TLS certificates
echo ""
echo "Generating TLS certificates..."
mkdir -p certs

python3 -c "
from shared.security import CertificateManager
from pathlib import Path
cert_dir = Path('$INSTALL_DIR/certs')
try:
    CertificateManager.generate_self_signed_cert(cert_dir)
    print('[OK] TLS certificates generated')
except Exception as e:
    print(f'[ERROR] Certificate generation failed: {e}')
"

if [ "$INSTALL_TYPE" = "1" ]; then
    # Manager Server Installation
    echo ""
    echo "===================================="
    echo "  Manager Server Installation      "
    echo "===================================="
    
    # Configure UFW firewall
    echo ""
    echo "Configuring UFW firewall..."
    ufw allow 9000/tcp comment 'SOC Manager - Agent Port'
    ufw allow 8000/tcp comment 'SOC Manager - Dashboard Port'
    echo "[OK] Firewall rules added"
    
    # Create systemd service files
    echo ""
    echo "Creating systemd services..."
    
    # Manager service
    cat > /etc/systemd/system/soc-manager.service <<EOF
[Unit]
Description=SOC Manager Server
After=network.target

[Service]
Type=simple
User=$SUDO_USER
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/bin/python3 $INSTALL_DIR/manager/manager.py
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
EOF

    # Dashboard service
    cat > /etc/systemd/system/soc-dashboard.service <<EOF
[Unit]
Description=SOC Dashboard API
After=network.target soc-manager.service

[Service]
Type=simple
User=$SUDO_USER
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/bin/python3 $INSTALL_DIR/dashboard/api.py
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
EOF

    # Reload systemd
    systemctl daemon-reload
    
    echo "[OK] Systemd services created"
    echo ""
    echo "===================================="
    echo "  Manager Installation Complete!   "
    echo "===================================="
    echo ""
    echo "Next Steps:"
    echo "1. Edit .env file and set AUTH_SECRET_KEY, API_KEY, etc."
    echo "2. Start services:"
    echo "   sudo systemctl start soc-manager"
    echo "   sudo systemctl start soc-dashboard"
    echo "3. Enable auto-start on boot:"
    echo "   sudo systemctl enable soc-manager"
    echo "   sudo systemctl enable soc-dashboard"
    echo "4. Check status:"
    echo "   sudo systemctl status soc-manager"
    echo "   sudo systemctl status soc-dashboard"
    echo "5. Access dashboard at http://localhost:8000"
    
elif [ "$INSTALL_TYPE" = "2" ]; then
    # Agent Installation
    echo ""
    echo "===================================="
    echo "  Agent Installation                "
    echo "===================================="
    
    # Get manager server IP
    echo ""
    read -p "Enter Manager Server IP address: " MANAGER_IP
    read -p "Enter unique Agent ID (e.g., agent-lab-pc-01): " AGENT_ID
    
    # Update .env file
    echo ""
    echo "Configuring agent..."
    sed -i "s/MANAGER_HOST=.*/MANAGER_HOST=$MANAGER_IP/" .env
    sed -i "s/AGENT_ID=.*/AGENT_ID=$AGENT_ID/" .env
    
    # Configure UFW firewall for outbound
    echo "Configuring UFW firewall..."
    ufw allow out 9000/tcp comment 'SOC Agent - Outbound'
    echo "[OK] Firewall rule added"
    
    # Create systemd service
    echo ""
    echo "Creating systemd service..."
    
    cat > /etc/systemd/system/soc-agent.service <<EOF
[Unit]
Description=SOC Monitoring Agent
After=network.target

[Service]
Type=simple
User=$SUDO_USER
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/bin/python3 $INSTALL_DIR/agent/agent.py
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
EOF

    # Reload systemd
    systemctl daemon-reload
    
    echo "[OK] Systemd service created"
    echo ""
    echo "===================================="
    echo "  Agent Installation Complete!     "
    echo "===================================="
    echo ""
    echo "Next Steps:"
    echo "1. Start service: sudo systemctl start soc-agent"
    echo "2. Enable auto-start: sudo systemctl enable soc-agent"
    echo "3. Check status: sudo systemctl status soc-agent"
    echo "4. View logs: sudo journalctl -u soc-agent -f"
    echo ""
    echo "Agent will connect to: $MANAGER_IP:9000"
fi

echo ""
echo "===================================="
echo "  Installation Complete!           "
echo "===================================="
