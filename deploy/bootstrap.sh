#!/usr/bin/env bash
# ==============================================================================
# FRIDAY Universe - Production Server Bootstrap (Ubuntu 24.04 ARM64)
# ==============================================================================
set -euo pipefail

echo "=========================================================="
echo "   🚀 FRIDAY UNIVERSE - PRODUCTION SERVER BOOTSTRAP       "
echo "=========================================================="

export DEBIAN_FRONTEND=noninteractive

# 1. Update OS packages & essential tools
echo "[1/6] Updating system packages and installing tools..."
sudo apt-get update -y && sudo apt-get upgrade -y
sudo apt-get install -y \
    curl git ufw jq htop ca-certificates gnupg lsb-release \
    fail2ban software-properties-common unzip

# 2. Configure 8 GB High-Performance Swap (with swappiness=10 tuning)
echo "[2/6] Configuring 8 GB Swap and Linux kernel memory tuning..."
if [ ! -f /swapfile ]; then
    sudo fallocate -l 8G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    echo "  -> 8 GB Swap allocated successfully."
else
    echo "  -> Swapfile already exists."
fi

# Kernel memory & network optimizations
sudo tee /etc/sysctl.d/99-friday.conf > /dev/null << 'EOF'
# Do not touch swap unless RAM is >= 90% full (zero slowdown during normal ops)
vm.swappiness = 10
# Cache filesystem inodes for fast reading
vm.vfs_cache_pressure = 50
# Network connection limits for FastAPI/Uvicorn high throughput
net.core.somaxconn = 1024
fs.file-max = 2097152
EOF
sudo sysctl --system > /dev/null

# 3. Install Docker Engine & Docker Compose Plugin
echo "[3/6] Installing official Docker CE & Compose..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker ubuntu
    rm get-docker.sh

    # Docker log rotation so 150 GB disk never fills up with container logs
    sudo tee /etc/docker/daemon.json > /dev/null << 'EOF'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
EOF
    sudo systemctl restart docker
    echo "  -> Docker Engine installed and configured."
else
    echo "  -> Docker already installed."
fi

# 4. Install Caddy (Production Reverse Proxy with Auto-HTTPS)
echo "[4/6] Installing Caddy Web Server (Auto-SSL)..."
if ! command -v caddy &> /dev/null; then
    sudo apt-get install -y debian-keyring debian-archive-keyring apt-transport-https
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg --yes
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
    sudo apt-get update -y
    sudo apt-get install -y caddy
    echo "  -> Caddy installed."
else
    echo "  -> Caddy already installed."
fi

# 5. Configure Security Hardening (UFW Firewall & Fail2ban)
echo "[5/6] Hardening server firewall and SSH protection..."
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp    comment 'SSH'
sudo ufw allow 80/tcp    comment 'HTTP'
sudo ufw allow 443/tcp   comment 'HTTPS'
sudo ufw allow 10000/tcp comment 'FRIDAY Gateway'
sudo ufw --force enable

# Oracle Linux/Ubuntu specific iptables unblock (before default REJECT rule)
sudo iptables -I INPUT 5 -p tcp -m state --state NEW -m multiport --dports 80,443,10000 -j ACCEPT 2>/dev/null || true
if command -v netfilter-persistent &> /dev/null; then
    sudo netfilter-persistent save
fi

sudo systemctl enable fail2ban
sudo systemctl restart fail2ban

# 6. Prepare Directory Hierarchy
echo "[6/6] Setting up project directory structure..."
sudo mkdir -p /opt/friday_universe/{logs,data,backups,config}
sudo chown -R ubuntu:ubuntu /opt/friday_universe

echo "=========================================================="
echo "   ✅ SERVER BOOTSTRAP COMPLETE! READY FOR DEPLOYMENT     "
echo "=========================================================="
