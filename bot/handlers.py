"""
Bot event handlers registration module
"""

import logging
from typing import List, Tuple
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from bot.callbacks import register_handlers
from bot.commands import get_bot_commands

logger = logging.getLogger(__name__)

def register_bot_handlers(app: Application) -> bool:
    """
    Register all bot command and callback handlers
    Returns True if successful, False if any errors occurred
    """
    try:
        commands = get_bot_commands()
        
        # Basic command handlers
        command_list: List[Tuple[str, callable]] = [
            ("start", commands.start),
            ("help", commands.help_command),
            ("scan", commands.scan_command),
            ("analyze", commands.analyze_command),
            ("watchlist", commands.watchlist_command),
            ("buy", commands.buy_command),
            ("sell", commands.sell_command),
            ("balance", commands.balance_command),
            ("mnemonic", commands.mnemonic_command),
            ("settings", commands.settings_command),
            ("portfolio", commands.portfolio_command)
        ]
        
        # Register each command handler
        for cmd_name, handler in command_list:
            try:
                logger.info(f"Registering command handler: /{cmd_name}")
                app.add_handler(CommandHandler(cmd_name, handler))
            except Exception as e:
                logger.error(f"Failed to register /{cmd_name} command: {e}")
                return False
                
        # Register callback query handlers
        try:
            logger.info("Registering callback handlers...")
            register_handlers(app)
        except Exception as e:
            logger.error(f"Failed to register callback handlers: {e}")
            return False
            
        logger.info(f"Successfully registered {len(command_list)} commands")
        return True
        
    except Exception as e:
        logger.error(f"Handler registration failed: {e}")
        return False
