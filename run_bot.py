#!/usr/bin/env python3
"""
Simple startup script for Meme Trader V4 Pro
"""

import asyncio
import platform
import logging
import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log')
    ]
)

logger = logging.getLogger(__name__)

def main():
    """Main startup function"""
    try:
        # Ensure a compatible event loop on Windows
        if platform.system() == "Windows":
            try:
                asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            except Exception:
                pass
        logger.info("Starting Meme Trader V4 Pro...")
        
        # Import and validate config (allow running with warnings for missing optional APIs)
        from config import Config
        try:
            # Prefer soft validation: only require Telegram token
            if not Config.TELEGRAM_BOT_TOKEN:
                raise ValueError("Missing TELEGRAM_BOT_TOKEN")
            # Warn if Covalent rotation keys missing (features limited)
            if not (os.getenv('COVALENT_KEYS') or os.getenv('COVALENT_API_KEY')):
                logger.warning("Covalent keys not configured – discovery/analysis features will be limited")
            logger.info("Configuration validated (with possible warnings)")
        except ValueError as e:
            logger.error(f"Configuration error: {e}")
            logger.error("Please check your .env file and ensure all required variables are set")
            logger.error("See env_template.txt for required variables")
            return False
        
        # Initialize database
        logger.info("Initializing database...")
        from db import create_tables
        create_tables()
        logger.info("Database initialized")
        
        # Initialize integrations
        logger.info("Initializing API integrations...")
        from startup import initialize_integrations
        # Initialize integrations (async wrapper)
        try:
            asyncio.run(initialize_integrations())
        except RuntimeError:
            pass
        
        # Start the bot
        logger.info("Starting Telegram bot...")
        from bot.commands import get_bot_commands
        commands = get_bot_commands()
        
        # Import telegram components
        from telegram.ext import Application, CommandHandler, CallbackQueryHandler
        
        # Create application
        application = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()
        
        # Wire basic commands available now
        application.add_handler(CommandHandler("scan", commands.scan_command))
        application.add_handler(CommandHandler("watchlist", commands.watchlist_command))
        application.add_handler(CommandHandler("analyze", commands.analyze_command))
        
        # Minimal /start and /help placeholders to avoid missing handlers
        async def _start(update, context):
            await update.message.reply_text("Meme Trader V4 Pro online. Try /scan or /watchlist.")
        async def _help(update, context):
            help_text = (
                "Commands:\n"
                "\n"
                "- /start — Initialize the bot and show a quick intro\n"
                "- /help — Show this help menu\n"
                "\n"
                "Discovery & Analysis:\n"
                "- /scan — Discover high-performing trader wallets across chains\n"
                "- /analyze <address> [chain] — Deep-dive wallet/token analysis\n"
                "\n"
                "Watchlist & Monitoring:\n"
                "- /watchlist — Manage your watchlist (add/remove/list/rename)\n"
                "\n"
                "Trading & Portfolio:\n"
                "- /portfolio — Show current tracked positions and PnL\n"
                "- /panic_sell — Market-sell tracked tokens immediately (safety checks apply)\n"
                "\n"
                "Wallet & Security:\n"
                "- /balance — Show balances for your configured wallets\n"
                "- /address — Show your current executor wallet addresses\n"
                "- /mnemonic — Keystore management options (import/export/create)\n"
                "\n"
                "Settings:\n"
                "- /settings — View and change preferences (slippage, scoring thresholds, alerts)\n"
            )
            await update.message.reply_text(help_text)
        application.add_handler(CommandHandler("start", _start))
        application.add_handler(CommandHandler("help", _help))
        
        # Callback handler placeholder (buttons handled within commands callbacks elsewhere if added)
        async def _noop_callback(update, context):
            await update.callback_query.answer()
        application.add_handler(CallbackQueryHandler(_noop_callback))
        
        logger.info("Bot handlers configured")
        logger.info("Starting bot...")
        logger.info("Send /start to your bot to begin!")
        
        # Ensure a current event loop exists (Python 3.13 get_event_loop strictness)
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # Start the bot using PTB's built-in runner
        application.run_polling()
        
    except ImportError as e:
        logger.error(f"Import error: {e}")
        logger.error("Please ensure all dependencies are installed: pip install -r requirements.txt")
        return False
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        return False

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1) 