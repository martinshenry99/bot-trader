"""
Bot event handlers registration module
"""

import logging
from typing import List, Tuple
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from bot.callbacks import register_handlers
from bot.commands import get_bot_commands

logger = logging.getLogger(__name__)

def register_bot_handlers(app: Application) -> bool:
    """
    Register all bot command and callback handlers
    Returns True if successful, False if any errors occurred
    """
    try:
        logger.debug("Starting handler registration")
        commands = get_bot_commands()
        
        # Debug message handler to log all incoming messages
        async def debug_message_handler(update, context):
            logger.debug("=== Received Update ===")
            logger.debug(f"Raw update: {update}")
            if update.message:
                logger.debug(f"Message text: {update.message.text}")
                logger.debug(f"From user: {update.effective_user.id}")
                logger.debug(f"Chat ID: {update.effective_chat.id}")
            elif update.callback_query:
                logger.debug(f"Callback query: {update.callback_query.data}")
                logger.debug(f"From user: {update.effective_user.id}")
            else:
                logger.debug("No message or callback query found in update")
            logger.debug("=====================")
            return None  # Don't stop the handler chain
            
        # Basic command handlers first
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
            
        # Add debug handler last to catch all unhandled messages
        app.add_handler(MessageHandler(filters.ALL, debug_message_handler))
        logger.debug("Added debug message handler")
            
        logger.info(f"Successfully registered {len(command_list)} commands")
        return True
        
    except Exception as e:
        logger.error(f"Handler registration failed: {e}")
        return False
