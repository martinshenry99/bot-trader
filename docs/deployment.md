# Meme Trader V4 Pro - Production Deployment Guide

## Overview
This guide covers the deployment process for Meme Trader V4 Pro in a production environment.

## Prerequisites
- Linux server (Ubuntu 20.04+ recommended)
- Python 3.9+
- SQLite3
- Systemd or Docker
- SSL certificate

## Environment Setup

### 1. System Requirements
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install python3.9 python3.9-venv sqlite3 supervisor nginx
```

### 2. Application Setup
```bash
# Create application directory
sudo mkdir -p /opt/meme-trader
sudo chown -R $USER:$USER /opt/meme-trader

# Clone repository
git clone https://github.com/your-repo/meme-trader.git /opt/meme-trader
cd /opt/meme-trader

# Create virtual environment
python3.9 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration

Create `.env` file:
```bash
# API Keys (Mainnet)
COVALENT_API_KEY=your_key
COVALENT_ROTATION_KEYS=key1,key2,key3
GOPLUS_API_KEY=your_key
GOPLUS_ROTATION_KEYS=key1,key2,key3
ZEROX_API_KEY=your_key
ZEROX_ROTATION_KEYS=key1,key2,key3
JUPITER_API_KEY=your_key
JUPITER_ROTATION_KEYS=key1,key2,key3
HELIUS_API_KEY=your_key
HELIUS_ROTATION_KEYS=key1,key2,key3
COINGECKO_API_KEY=your_key
COINGECKO_ROTATION_KEYS=key1,key2,key3

# Bot Configuration
TELEGRAM_BOT_TOKEN=your_bot_token
ADMIN_USER_ID=your_telegram_id
SAFE_MODE=false
LOG_LEVEL=INFO

# Database
DB_PATH=/opt/meme-trader/data/meme_trader.db

# Rate Limits (requests per minute)
COVALENT_RATE_LIMIT=60
GOPLUS_RATE_LIMIT=60
ZEROX_RATE_LIMIT=60
JUPITER_RATE_LIMIT=60
HELIUS_RATE_LIMIT=60
COINGECKO_RATE_LIMIT=60
```

### 4. Directory Structure
```bash
mkdir -p /opt/meme-trader/{logs,data,backups}
chmod 700 /opt/meme-trader/data  # Secure storage for DB
```

### 5. Logging Configuration
Create `logging.conf`:
```ini
[loggers]
keys=root,memetrader

[handlers]
keys=consoleHandler,fileHandler

[formatters]
keys=simpleFormatter

[logger_root]
level=INFO
handlers=consoleHandler

[logger_memetrader]
level=INFO
handlers=fileHandler
qualname=memetrader
propagate=0

[handler_consoleHandler]
class=StreamHandler
formatter=simpleFormatter
args=(sys.stdout,)

[handler_fileHandler]
class=handlers.RotatingFileHandler
formatter=simpleFormatter
args=('logs/meme_trader.log', 'a', 10485760, 5)

[formatter_simpleFormatter]
format=%(asctime)s - %(name)s - %(levelname)s - %(message)s
```

## Deployment Options

### Option 1: Systemd Service
Create `/etc/systemd/system/meme-trader.service`:
```ini
[Unit]
Description=Meme Trader V4 Pro
After=network.target

[Service]
Type=simple
User=memetrader
WorkingDirectory=/opt/meme-trader
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=/opt/meme-trader/.env
ExecStart=/opt/meme-trader/venv/bin/python run_bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Option 2: Docker Deployment
Create `Dockerfile`:
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "run_bot.py"]
```

Create `docker-compose.yml`:
```yaml
version: '3'
services:
  meme-trader:
    build: .
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - ./backups:/app/backups
    env_file:
      - .env
    restart: always
```

## Database Management

### Backup Configuration
Create `/opt/meme-trader/scripts/backup.sh`:
```bash
#!/bin/bash
DATE=$(date +%Y%m%d)
sqlite3 /opt/meme-trader/data/meme_trader.db ".backup '/opt/meme-trader/backups/meme_trader_$DATE.db'"
find /opt/meme-trader/backups -name "meme_trader_*.db" -mtime +7 -delete
```

Add to crontab:
```bash
0 */6 * * * /opt/meme-trader/scripts/backup.sh
```

### Restore Procedure
```bash
# Stop service
sudo systemctl stop meme-trader

# Restore from backup
sqlite3 /opt/meme-trader/data/meme_trader.db ".restore '/opt/meme-trader/backups/meme_trader_YYYYMMDD.db'"

# Start service
sudo systemctl start meme-trader
```

## Monitoring Setup

### Health Checks
Configure monitoring endpoints:
```python
# In monitor/health.py
async def health_check():
    return {
        "status": "healthy",
        "uptime": get_uptime(),
        "api_status": await check_apis(),
        "db_status": check_database(),
        "memory_usage": get_memory_usage()
    }
```

### Alert Configuration
Configure Telegram alerts in `config.py`:
```python
ALERT_LEVELS = {
    "critical": ["API_ERROR", "DB_ERROR", "WALLET_ERROR"],
    "warning": ["API_RATE_LIMIT", "HIGH_MEMORY_USAGE"],
    "info": ["TRADE_EXECUTED", "WALLET_UPDATED"]
}
```

## Security Measures

### Wallet Security
1. Store production wallet mnemonic securely offline
2. Use hardware wallet for large holdings
3. Configure withdrawal limits

### API Key Security
1. Rotate keys regularly
2. Monitor usage patterns
3. Set up alerts for unusual activity

### Access Control
1. Restrict admin commands
2. Implement IP whitelisting
3. Use SSL for all connections

## Emergency Procedures

### Emergency Shutdown
```bash
# Via bot command
/emergency_stop

# Via service
sudo systemctl stop meme-trader
```

### API Key Rotation
```bash
# Via bot command
/rotate_keys service_name

# Manual rotation
python rotate_keys.py --service covalent
```

### Wallet Rotation
```bash
# Via bot command
/rotate_wallet

# Manual rotation
python rotate_wallet.py --new-wallet
```

## Troubleshooting

### Common Issues

1. API Rate Limits
```python
# Check logs
tail -f /opt/meme-trader/logs/meme_trader.log | grep "RATE_LIMIT"

# Rotate keys
/rotate_keys service_name
```

2. Database Errors
```bash
# Check DB integrity
sqlite3 /opt/meme-trader/data/meme_trader.db "PRAGMA integrity_check;"

# Restore from backup if needed
./scripts/restore_db.sh YYYYMMDD
```

3. Memory Issues
```bash
# Check memory usage
ps aux | grep meme-trader

# Restart service
sudo systemctl restart meme-trader
```

## Production Checklist

Before going live:

1. [ ] Run production readiness check
```bash
python production_check.py
```

2. [ ] Verify all API keys
```bash
python verify_api_keys.py --mainnet
```

3. [ ] Test emergency procedures
```bash
python test_emergency.py
```

4. [ ] Confirm monitoring setup
```bash
python verify_monitoring.py
```

5. [ ] Check security settings
```bash
python security_audit.py
```
