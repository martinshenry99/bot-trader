"""
Portfolio command handler implementation
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.base_command import BaseCommand
from bot.callback_data import CallbackAction, create_callback_data
from utils.formatting import format_error_message, format_portfolio_summary
from db.models import get_db_manager
from services.wallet_analyzer import wallet_analyzer

logger = logging.getLogger(__name__)

class PortfolioCommand(BaseCommand):
    """Handler for /portfolio command and callbacks"""
    
    def __init__(self):
        super().__init__()
        self.db = get_db_manager()
        self.items_per_page = 5
        
    async def __call__(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /portfolio command"""
        try:
            # Ensure user exists
            if not await self.ensure_user_exists(update):
                return
                
            user_id = str(update.effective_user.id)
            page = 0  # Start with first page
            
            await self.show_portfolio(update, user_id, page)
            
        except Exception as e:
            logger.error(f"Error in portfolio command: {e}", exc_info=True)
            error_msg = format_error_message("Failed to load portfolio")
            if update.message:
                await update.message.reply_text(error_msg)
            elif update.callback_query:
                await update.callback_query.edit_message_text(error_msg)
                
    async def show_portfolio(self, update: Update, user_id: str, page: int):
        """Show portfolio summary with pagination"""
        try:
            # Get user's executor wallets
            wallets = await self.db.get_user_wallets(user_id)
            
            if not wallets:
                keyboard = [[
                    InlineKeyboardButton(
                        "➕ Add Wallet",
                        callback_data=create_callback_data(
                            CallbackAction.SELECT,
                            "add_wallet"
                        )
                    ),
                    InlineKeyboardButton(
                        "🔙 Back",
                        callback_data=create_callback_data(
                            CallbackAction.SELECT,
                            "main_menu"
                        )
                    )
                ]]
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                text = "❌ No wallets found. Add a wallet to start trading!"
                
                if update.message:
                    await update.message.reply_text(text, reply_markup=reply_markup)
                else:
                    await update.callback_query.edit_message_text(
                        text,
                        reply_markup=reply_markup
                    )
                return
                
            # Get balances and holdings for all wallets
            total_value = 0
            holdings: List[Dict[str, Any]] = []
            
            for wallet in wallets:
                wallet_holdings = await wallet_analyzer.get_wallet_holdings(
                    wallet.address,
                    wallet.chain
                )
                
                for token in wallet_holdings:
                    holdings.append({
                        'wallet': wallet.address,
                        'chain': wallet.chain,
                        'token': token['address'],
                        'symbol': token['symbol'],
                        'balance': token['balance'],
                        'value_usd': token['value_usd']
                    })
                    total_value += token['value_usd']
                    
            # Sort holdings by value
            holdings.sort(key=lambda x: x['value_usd'], reverse=True)
            
            # Paginate holdings
            start_idx = page * self.items_per_page
            end_idx = start_idx + self.items_per_page
            page_holdings = holdings[start_idx:end_idx]
            total_pages = (len(holdings) + self.items_per_page - 1) // self.items_per_page
            
            # Format text
            text = format_portfolio_summary(total_value, page_holdings)
            
            # Build keyboard
            keyboard = []
            
            if total_pages > 1:
                nav_buttons = []
                if page > 0:
                    nav_buttons.append(
                        InlineKeyboardButton(
                            "⬅️ Previous",
                            callback_data=create_callback_data(
                                CallbackAction.PREV_PAGE,
                                "portfolio",
                                page=page
                            )
                        )
                    )
                if page < total_pages - 1:
                    nav_buttons.append(
                        InlineKeyboardButton(
                            "Next ➡️",
                            callback_data=create_callback_data(
                                CallbackAction.NEXT_PAGE,
                                "portfolio",
                                page=page
                            )
                        )
                    )
                keyboard.append(nav_buttons)
                
            keyboard.append([
                InlineKeyboardButton(
                    "🔄 Refresh",
                    callback_data=create_callback_data(
                        CallbackAction.REFRESH,
                        "portfolio",
                        page=page
                    )
                ),
                InlineKeyboardButton(
                    "🔙 Back",
                    callback_data=create_callback_data(
                        CallbackAction.SELECT,
                        "main_menu"
                    )
                )
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if update.message:
                await update.message.reply_text(
                    text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            else:
                await update.callback_query.edit_message_text(
                    text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
