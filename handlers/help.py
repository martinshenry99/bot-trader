"""
Help command handler implementation
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.base_command import BaseCommand
from bot.callback_data import CallbackAction, create_callback_data

logger = logging.getLogger(__name__)

class HelpCommand(BaseCommand):
    """Handler for /help command"""
    
    async def __call__(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        try:
            # Ensure user exists
            if not await self.ensure_user_exists(update):
                return
                
            help_text = (
                "📖 **MEME TRADER V4 PRO - HELP**\n\n"
                "**Basic Commands:**\n"
                "/start or /menu - Show main menu\n"
                "/portfolio - View your holdings\n"
                "/scan - Scan whale wallets\n"
                "/buy - Buy a token\n"
                "/sell - Sell a token\n"
                "/keys - Manage API keys\n"
                "/settings - Bot configuration\n"
                "/help - Show this help\n\n"
                
                "**Security Features:**\n"
                "• Safe Mode (prevents risky trades)\n"
                "• API Key Rotation\n"
                "• Transaction Simulation\n"
                "• Token Security Checks\n\n"
                
                "**Trading Features:**\n"
                "• Multi-Chain Support (ETH, BSC, SOL)\n"
                "• Auto Stop Loss & Take Profit\n"
                "• Gas Fee Optimization\n"
                "• Whale Wallet Tracking\n\n"
                
                "**Usage Tips:**\n"
                "1. Add API keys via /keys command\n"
                "2. Configure settings for your risk level\n"
                "3. Use scan feature to find opportunities\n"
                "4. Always verify token security before trading\n\n"
                
                "Need more help? Contact support."
            )
            
            # Create keyboard
            keyboard = [[
                InlineKeyboardButton(
                    "🔙 Back to Menu",
                    callback_data=create_callback_data(
                        CallbackAction.SELECT,
                        "main_menu"
                    )
                )
            ]]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if update.message:
                await update.message.reply_text(
                    help_text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            else:
                await update.callback_query.edit_message_text(
                    help_text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                
        except Exception as e:
            logger.error(f"Error in help command: {e}", exc_info=True)
            error_msg = "❌ Failed to show help menu"
            if update.message:
                await update.message.reply_text(error_msg)
            elif update.callback_query:
                await update.callback_query.edit_message_text(error_msg)
