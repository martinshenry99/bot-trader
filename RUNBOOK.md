# RUNBOOK: Meme Trader V4 Pro

## Common Failures & Recovery

### API Keys Exhausted
- If all keys for a service are exhausted, bot uses cache and sends admin alert
- Rotate keys via .env and restart bot

### Keystore Missing
- Run `/mnemonic generate` (admin only)
- Check server console for one-time seed
- Import with `scripts/import_mnemonic.py`

### DB Reset
- Run `python scripts/setup_db.py` to reinitialize
- All tables will be recreated

### Telegram Bot Not Responding
- Ensure only one bot instance is running
- Restart bot

### Health Checks
- Use `/health` to check DB, keys, Telegram connectivity

## Debugging
- Check `bot.log` for errors
- Use DRY_RUN_MODE=true for safe testing
