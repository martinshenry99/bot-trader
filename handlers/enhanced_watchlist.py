"""Enhanced watchlist handler with inline buttons"""
import logging
from typing import Dict, List, Optional, Tuple
from decimal import Decimal

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackContext, CallbackQueryHandler

from bot.commands import CommandHandler, command
from services.token_discovery import TokenDiscovery
from utils.formatting import format_token_discovery, format_monitoring_alert
from utils.validation import validate_address
from db.models import WatchlistEntry, Settings

logger = logging.getLogger(__name__)

class EnhancedWatchlistHandler(CommandHandler):
    """Enhanced handler for watchlist commands with inline buttons"""
    
    def __init__(
        self,
        token_discovery: TokenDiscovery,
        settings: Settings
    ):
        self.discovery = token_discovery
        self.settings = settings
        
        # Register callback handlers
        self.callback_handlers = {
            'buy': self._handle_buy_callback,
            'sell': self._handle_sell_callback,
            'analyze': self._handle_analyze_callback,
            'ignore': self._handle_ignore_callback
        }
    
    @command(
        name='watchlist',
        help='Manage token watchlist with quick actions'
    )
    async def manage_watchlist(
        self,
        action: str,
        token_address: Optional[str] = None,
        chain: str = 'ethereum'
    ) -> Tuple[str, Optional[InlineKeyboardMarkup]]:
        """Manage token watchlist with inline buttons"""
        try:
            if action == 'list':
                tokens = self.discovery.get_monitored_tokens()
                message = format_watchlist(tokens)
                
                # Add inline buttons for each token
                buttons = self._create_token_buttons(tokens)
                reply_markup = InlineKeyboardMarkup(buttons)
                
                return message, reply_markup
                
            elif action == 'add' and token_address:
                if not validate_address(token_address):
                    return "Invalid token address format", None
                    
                result = await self.discovery.add_to_watchlist(
                    token_address,
                    chain
                )
                
                message = f"Added {token_address} to watchlist\n\n{format_token_discovery([result])}"
                
                # Add quick action buttons
                buttons = self._create_action_buttons(token_address, chain)
                reply_markup = InlineKeyboardMarkup(buttons)
                
                return message, reply_markup
                
            elif action == 'remove' and token_address:
                removed = self.discovery.remove_from_watchlist(token_address)
                return (
                    f"Removed {token_address} from watchlist"
                    if removed else
                    f"Token {token_address} not found in watchlist"
                ), None
                
            else:
                return "Invalid watchlist action. Use 'list', 'add <address>', or 'remove <address>'", None
                
        except Exception as e:
            logger.error(f"Error in watchlist command: {str(e)}")
            raise
    
    def _create_token_buttons(self, tokens: List[str]) -> List[List[InlineKeyboardButton]]:
        """Create inline buttons for token list"""
        buttons = []
        
        for token in tokens:
            # Create row of buttons for each token
            token_row = [
                InlineKeyboardButton(
                    "🔍 Analyze",
                    callback_data=f"analyze_{token}"
                ),
                InlineKeyboardButton(
                    "💰 Buy",
                    callback_data=f"buy_{token}"
                ),
                InlineKeyboardButton(
                    "📉 Sell",
                    callback_data=f"sell_{token}"
                )
            ]
            buttons.append(token_row)
        
        return buttons
    
    def _create_action_buttons(
        self,
        token_address: str,
        chain: str
    ) -> List[List[InlineKeyboardButton]]:
        """Create quick action buttons for a token"""
        buttons = [
            [
                InlineKeyboardButton(
                    "💰 Buy Token",
                    callback_data=f"buy_{token_address}"
                ),
                InlineKeyboardButton(
                    "🔍 Analyze",
                    callback_data=f"analyze_{token_address}"
                )
            ],
            [
                InlineKeyboardButton(
                    "📉 Sell 25%",
                    callback_data=f"sell_{token_address}_25"
                ),
                InlineKeyboardButton(
                    "📉 Sell 50%",
                    callback_data=f"sell_{token_address}_50"
                ),
                InlineKeyboardButton(
                    "🔄 Mirror Sell",
                    callback_data=f"mirror_sell_{token_address}"
                )
            ],
            [
                InlineKeyboardButton(
                    "❌ Ignore",
                    callback_data=f"ignore_{token_address}"
                )
            ]
        ]
        
        return buttons
    
    async def _handle_buy_callback(
        self,
        update: Update,
        context: CallbackContext,
        token_address: str
    ):
        """Handle buy button callback"""
        try:
            # Get token analysis first
            analysis = await self.discovery._analyze_token(
                token_address,
                'ethereum'  # Default chain
            )
            
            # Format quick analysis
            message = (
                f"💰 Quick Buy Analysis for {analysis['name']}\n\n"
                f"Current Price: ${analysis['price_usd']:,.6f}\n"
                f"24h Volume: ${analysis['volume_24h']:,.2f}\n"
                f"Risk Score: {analysis['risk_score']:.2f}\n\n"
                "Enter amount to buy (in USD):"
            )
            
            # Store analysis in user data for /buy command
            if not context.user_data:
                context.user_data = {}
            context.user_data['pending_buy'] = {
                'token_address': token_address,
                'analysis': analysis
            }
            
            await update.callback_query.message.reply_text(message)
            
        except Exception as e:
            logger.error(f"Error handling buy callback: {str(e)}")
            await update.callback_query.message.reply_text(
                "❌ Error preparing buy analysis"
            )
    
    async def _handle_sell_callback(
        self,
        update: Update,
        context: CallbackContext,
        token_address: str,
        percentage: Optional[str] = None
    ):
        """Handle sell button callback"""
        try:
            # Get current balance
            balance = await self.discovery.get_token_balance(
                token_address,
                context.user_data['wallet_address']
            )
            
            if not balance:
                await update.callback_query.message.reply_text(
                    "❌ No balance found for this token"
                )
                return
            
            # Calculate sell amount
            sell_amount = balance
            if percentage:
                sell_amount = balance * (int(percentage) / 100)
            
            # Format confirmation message
            message = (
                f"📉 Sell Confirmation\n\n"
                f"Token: {token_address}\n"
                f"Amount: {sell_amount:,.2f} tokens\n"
                f"Percentage: {percentage if percentage else '100'}%\n\n"
                "Confirm sell? /sell confirm"
            )
            
            # Store sell data
            if not context.user_data:
                context.user_data = {}
            context.user_data['pending_sell'] = {
                'token_address': token_address,
                'amount': sell_amount,
                'percentage': percentage
            }
            
            await update.callback_query.message.reply_text(message)
            
        except Exception as e:
            logger.error(f"Error handling sell callback: {str(e)}")
            await update.callback_query.message.reply_text(
                "❌ Error preparing sell order"
            )
    
    async def _handle_analyze_callback(
        self,
        update: Update,
        context: CallbackContext,
        token_address: str
    ):
        """Handle analyze button callback"""
        try:
            # Get comprehensive analysis
            analysis = await self.discovery._analyze_token(
                token_address,
                'ethereum'  # Default chain
            )
            
            # Format detailed analysis
            message = (
                f"🔍 Token Analysis\n\n"
                f"Name: {analysis['name']} ({analysis['symbol']})\n"
                f"Price: ${analysis['price_usd']:,.6f}\n"
                f"Market Cap: ${analysis['market_cap']:,.2f}\n"
                f"24h Volume: ${analysis['volume_24h']:,.2f}\n"
                f"Liquidity: ${analysis['liquidity']:,.2f}\n"
                f"Holders: {analysis['holder_count']:,}\n"
                f"Top 10 Holdings: {analysis['holder_concentration']*100:.1f}%\n"
                f"Risk Score: {analysis['risk_score']:.2f}\n\n"
                "Risk Factors:\n"
            )
            
            for factor, score in analysis['risk_factors'].items():
                message += f"• {factor}: {score:.2f}\n"
            
            # Add security warnings
            if analysis['security_info']['is_honeypot']:
                message += "\n⚠️ WARNING: Potential honeypot detected!"
            
            await update.callback_query.message.reply_text(message)
            
        except Exception as e:
            logger.error(f"Error handling analyze callback: {str(e)}")
            await update.callback_query.message.reply_text(
                "❌ Error analyzing token"
            )
    
    async def _handle_ignore_callback(
        self,
        update: Update,
        context: CallbackContext,
        token_address: str
    ):
        """Handle ignore button callback"""
        try:
            # Remove from watchlist
            removed = self.discovery.remove_from_watchlist(token_address)
            
            message = (
                f"✅ Removed {token_address} from watchlist"
                if removed else
                f"Token {token_address} not found in watchlist"
            )
            
            await update.callback_query.message.reply_text(message)
            
        except Exception as e:
            logger.error(f"Error handling ignore callback: {str(e)}")
            await update.callback_query.message.reply_text(
                "❌ Error removing token from watchlist"
            )
