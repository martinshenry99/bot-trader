# Meme Trader V4 Pro - Troubleshooting Guide

## Common Issues and Solutions

### 1. API Integration Issues

#### Rate Limit Exceeded
**Symptoms:**
- Error messages containing "429 Too Many Requests"
- API calls failing consistently
- Slow response times

**Solutions:**
1. Check current rate limit status:
```bash
python scripts/check_rate_limits.py --service service_name
```

2. Rotate API keys:
```bash
/rotate_keys service_name
```

3. Adjust rate limiting settings in `.env`:
```bash
SERVICE_RATE_LIMIT=60  # Requests per minute
```

#### API Key Invalid
**Symptoms:**
- "401 Unauthorized" errors
- API calls failing with authentication errors

**Solutions:**
1. Verify API key validity:
```bash
python scripts/verify_api_keys.py --service service_name
```

2. Update API keys:
```bash
python scripts/update_api_keys.py --service service_name
```

### 2. Database Issues

#### Database Locked
**Symptoms:**
- "database is locked" errors
- Transactions failing to complete

**Solutions:**
1. Check active connections:
```bash
python scripts/check_db_connections.py
```

2. Kill stuck connections:
```bash
python scripts/reset_db_connections.py
```

3. Verify database integrity:
```bash
sqlite3 meme_trader.db "PRAGMA integrity_check;"
```

#### Slow Queries
**Symptoms:**
- Slow response times
- High CPU usage during database operations

**Solutions:**
1. Analyze slow queries:
```bash
python scripts/analyze_db_performance.py
```

2. Optimize indexes:
```bash
python scripts/optimize_db_indexes.py
```

### 3. Wallet Issues

#### Transaction Failures
**Symptoms:**
- Failed buy/sell operations
- Gas estimation errors
- Nonce mismatch errors

**Solutions:**
1. Check wallet status:
```bash
python scripts/check_wallet_status.py
```

2. Reset nonce:
```bash
python scripts/reset_nonce.py --chain chain_name
```

3. Verify gas settings:
```bash
python scripts/verify_gas_settings.py
```

#### Wallet Connection Issues
**Symptoms:**
- "Cannot connect to wallet" errors
- RPC connection failures

**Solutions:**
1. Check RPC endpoints:
```bash
python scripts/verify_rpc_endpoints.py
```

2. Switch to backup RPC:
```bash
/switch_rpc chain_name
```

### 4. Monitoring Issues

#### Missing Alerts
**Symptoms:**
- No notifications for events
- Delayed notifications

**Solutions:**
1. Check monitoring status:
```bash
python scripts/check_monitoring.py
```

2. Verify webhook settings:
```bash
python scripts/verify_webhooks.py
```

3. Reset monitoring:
```bash
/reset_monitoring
```

#### False Alerts
**Symptoms:**
- Too many unnecessary alerts
- Incorrect trigger conditions

**Solutions:**
1. Analyze alert patterns:
```bash
python scripts/analyze_alerts.py --hours 24
```

2. Adjust alert thresholds:
```bash
python scripts/update_alert_thresholds.py
```

### 5. Memory Issues

#### High Memory Usage
**Symptoms:**
- System slowdown
- Out of memory errors

**Solutions:**
1. Check memory usage:
```bash
python scripts/check_memory.py
```

2. Clean up cache:
```bash
python scripts/cleanup_cache.py
```

3. Restart services:
```bash
sudo systemctl restart meme-trader
```

### 6. Network Issues

#### High Latency
**Symptoms:**
- Slow response times
- Timeout errors

**Solutions:**
1. Check network status:
```bash
python scripts/check_network.py
```

2. Switch endpoints:
```bash
python scripts/switch_endpoints.py --fastest
```

#### Connection Drops
**Symptoms:**
- Frequent disconnections
- WebSocket errors

**Solutions:**
1. Verify connections:
```bash
python scripts/verify_connections.py
```

2. Reset connections:
```bash
python scripts/reset_connections.py
```

## Diagnostic Tools

### System Health Check
```bash
# Full system health check
python scripts/health_check.py --full

# Quick status check
python scripts/health_check.py --quick
```

### Log Analysis
```bash
# Check error logs
python scripts/analyze_logs.py --level ERROR --hours 24

# Check specific component
python scripts/analyze_logs.py --component wallet --hours 24
```

### Performance Analysis
```bash
# Check system performance
python scripts/analyze_performance.py

# Generate performance report
python scripts/generate_performance_report.py
```

## Maintenance Procedures

### Database Maintenance
```bash
# Optimize database
python scripts/optimize_db.py

# Clean old data
python scripts/clean_old_data.py --days 30
```

### Cache Maintenance
```bash
# Clear cache
python scripts/clear_cache.py

# Optimize cache settings
python scripts/optimize_cache.py
```

### System Updates
```bash
# Update dependencies
pip install -r requirements.txt --upgrade

# Update configuration
python scripts/update_config.py
```

## Recovery Procedures

### Database Recovery
```bash
# Backup current database
python scripts/backup_db.py

# Restore from backup
python scripts/restore_db.py --backup backup_name
```

### API Recovery
```bash
# Reset API connections
python scripts/reset_apis.py

# Verify API health
python scripts/verify_apis.py
```

### Wallet Recovery
```bash
# Verify wallet integrity
python scripts/verify_wallet.py

# Restore wallet from backup
python scripts/restore_wallet.py
```

## Prevention Measures

### Regular Maintenance
1. Schedule regular health checks
```bash
# Add to crontab
0 * * * * /opt/meme-trader/scripts/health_check.py
```

2. Configure automatic backups
```bash
# Add to crontab
0 */6 * * * /opt/meme-trader/scripts/backup.sh
```

3. Set up monitoring alerts
```bash
# Configure alert thresholds
python scripts/configure_alerts.py
```

### Best Practices
1. Regular log review
2. Monitor system resources
3. Keep dependencies updated
4. Regular security audits
5. Document all incidents
