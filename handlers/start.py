"""
Start command handler implementation
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.base_command import BaseCommand
from bot.callback_data import CallbackAction, create_callback_data
from config import Config
from utils.formatting import format_main_menu

logger = logging.getLogger(__name__)

class StartCommand(BaseCommand):
    """Handler for /start command"""
    
    async def __call__(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        try:
            # Ensure user exists and has permissions
            if not await self.ensure_user_exists(update):
                return
                
            user_id = str(update.effective_user.id)
            
            # Get user settings
            settings = await self.get_user_settings(user_id)
            
            # Create main menu keyboard
            keyboard = [
                [
                    InlineKeyboardButton(
                        "📊 Portfolio", 
                        callback_data=create_callback_data(
                            CallbackAction.SELECT,
                            "portfolio"
                        )
                    ),
                    InlineKeyboardButton(
                        "🔍 Scan Wallets",
                        callback_data=create_callback_data(
                            CallbackAction.SELECT,
                            "scan"
                        )
                    )
                ],
                [
                    InlineKeyboardButton(
                        "📈 Buy Token",
                        callback_data=create_callback_data(
                            CallbackAction.SELECT,
                            "buy"
                        )
                    ),
                    InlineKeyboardButton(
                        "📉 Sell Token",
                        callback_data=create_callback_data(
                            CallbackAction.SELECT,
                            "sell" 
                        )
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🏆 Leaderboard",
                        callback_data=create_callback_data(
                            CallbackAction.SELECT,
                            "leaderboard"
                        )
                    ),
                    InlineKeyboardButton(
                        "⚙️ Settings",
                        callback_data=create_callback_data(
                            CallbackAction.SETTINGS,
                            "main"
                        )
                    )
                ],
                [
                    InlineKeyboardButton(
                        "❓ Help",
                        callback_data=create_callback_data(
                            CallbackAction.SELECT,
                            "help"
                        )
                    ),
                    InlineKeyboardButton(
                        "🔐 Keys",
                        callback_data=create_callback_data(
                            CallbackAction.SELECT,
                            "keys"
                        )
                    )
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Format menu text based on settings
            menu_text = format_main_menu(settings)
            
            if update.message:
                await update.message.reply_text(
                    menu_text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            else:
                await update.callback_query.edit_message_text(
                    menu_text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                
        except Exception as e:
            logger.error(f"Error in start command: {e}", exc_info=True)
            error_msg = "❌ An error occurred showing the main menu. Please try again."
            if update.message:
                await update.message.reply_text(error_msg)
            elif update.callback_query:
                await update.callback_query.edit_message_text(error_msg)
