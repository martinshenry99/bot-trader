# Meme Trader V4 Pro

## Overview
Production-ready Telegram bot for trading, monitoring, and due diligence across ETH/BSC/SOL. Features:
- Discovery (/scan) with Insider Detection
- Real-time Monitoring & Alerts (/watchlist)
- Deep Due-Diligence (/analyze)
- Safe Execution (/buy, /sell, /panic_sell)
- Portfolio & Reporting (/portfolio, daily report)
- Secure Keystore / mnemonic flows (/mnemonic)
- Robust API key rotation, caching, logging, tests and CI

## Install & Setup
1. Clone repo and checkout `feature/integrated-v4pro`
2. Copy `.env.example` to `.env` and fill in your secrets
3. Run `python scripts/setup_db.py` to initialize DB
4. Start bot: `python run_bot.py`

## Key Rotation
- Supports both CSV and individual key env formats
- Keys are rotated and marked cooldown on 429
- See `/settings` for usage stats

## Admin Operations
- Only ADMIN_TELEGRAM_ID can generate/export/delete mnemonics
- All sensitive actions require confirmation

## Diagnostic Mode
- Run with DRY_RUN_MODE=true for safe testing

## See RUNBOOK.md for troubleshooting and common failures
