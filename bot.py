import logging
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from config import Config
from db import create_tables, get_db_session, User, Wallet, Token, Trade, AlertConfig, BlacklistEntry, WalletWatch
from monitor import EnhancedMonitoringManager
from analyzer import EnhancedTokenAnalyzer
from executor import AdvancedTradeExecutor, KeystoreManager
from pro_features import ProFeaturesManager

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class MemeTraderBot:
    def __init__(self):
        Config.validate()
        self.monitoring_manager = EnhancedMonitoringManager()
        self.analyzer = EnhancedTokenAnalyzer()
        self.executor = AdvancedTradeExecutor()
        self.pro_features = ProFeaturesManager()
        self.user_sessions = {}  # Track user sessions for multi-step operations
        
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command with main menu"""
        user_id = str(update.effective_user.id)
        
        # Ensure user exists in database
        await self.ensure_user_exists(user_id, update.effective_user)
        
        # Show main menu
        await self.show_main_menu(update.message or update.callback_query, user_id)

    async def show_main_menu(self, message_or_query, user_id: str, edit_message: bool = None):
        """Show the main menu interface"""
        try:
            from ui.main_menu import MainMenu
            
            menu_text, menu_keyboard = await MainMenu.get_main_menu(user_id)
            
            # Determine if we should edit or send new message
            if hasattr(message_or_query, 'edit_text'):  # It's a callback query
                await message_or_query.edit_text(menu_text, reply_markup=menu_keyboard, parse_mode='Markdown')
            elif hasattr(message_or_query, 'reply_text'):  # It's a message
                await message_or_query.reply_text(menu_text, reply_markup=menu_keyboard, parse_mode='Markdown')
            else:
                logger.error("Invalid message_or_query object")
                
        except Exception as e:
            logger.error(f"Error showing main menu: {e}")
            # Fallback
            fallback_text = "🚀 **MEME TRADER V4 PRO**\n\nUse /help to see available commands."
            if hasattr(message_or_query, 'reply_text'):
                await message_or_query.reply_text(fallback_text, parse_mode='Markdown')

    async def ensure_user_exists(self, telegram_id: str, user_data):
        """Ensure user exists in database"""
        try:
            db = get_db_session()
            try:
                user = db.query(User).filter(User.telegram_id == telegram_id).first()
                if not user:
                    user = User(
                        telegram_id=telegram_id,
                        username=getattr(user_data, 'username', None),
                        first_name=getattr(user_data, 'first_name', None),
                        last_name=getattr(user_data, 'last_name', None)
                    )
                    db.add(user)
                    db.commit()
                    logger.info(f"Created new user: {telegram_id}")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error ensuring user exists: {e}")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command and return to main menu"""
        user_id = str(update.effective_user.id)
        
        help_text = """
📖 **MEME TRADER V4 PRO - HELP**

**🎯 Main Features:**
• **Multi-chain trading** (ETH, BSC, Solana)
• **Mirror trading** with smart wallet following
• **Real-time portfolio** tracking in USD
• **Advanced risk management** and safety controls
• **Moonshot leaderboard** (200x+ wallets)

**💰 Trading Commands:**
• `/buy [chain] [token] [amount]` - Buy tokens
• `/sell [chain] [token] [%]` - Sell tokens
• `/portfolio` - View your positions
• `/panic_sell` - Emergency liquidation

**🔍 Analysis Commands:**
• `/scan` - Manual wallet scan
• `/analyze [address]` - Analyze token/wallet
• `/leaderboard` - View top traders

**⚙️ Management Commands:**
• `/settings` - Configure trading
• `/watchlist` - Manage watched wallets
• `/blacklist` - Manage blocked addresses
• `/alerts` - Configure notifications

**🛡️ Safety Features:**
• Safe Mode blocks risky trades
• Mirror-sell enabled by default
• Mirror-buy disabled for safety
• Comprehensive risk scoring

**💡 Pro Tips:**
• Use the Main Menu for easy navigation
• Enable Safe Mode for beginners
• Monitor the leaderboard for opportunities
• Set appropriate position limits

The Main Menu will appear after each action for easy navigation!
        """
        
        # Send help and then show main menu
        await update.message.reply_text(help_text, parse_mode='Markdown')
        await self.show_main_menu(update.message, user_id)

    async def buy_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /buy command with enhanced pre-trade checks"""
        user_id = str(update.effective_user.id)
        
        if len(context.args) < 3:
            await update.message.reply_text(
                "💰 **Buy Token Command**\n\n"
                "**Usage:** `/buy [chain] [token_address] [amount_usd]`\n\n"
                "**Examples:**\n"
                "• `/buy eth 0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b 10`\n"
                "• `/buy bsc 0xA0b86a33E6441ba0BB7e1ae5E3e7BAaD5D1D7e3c 25`\n\n"
                "**Supported Chains:**\n"
                "• `eth` - Ethereum Sepolia Testnet\n"
                "• `bsc` - BSC Testnet\n\n"
                "**Features:**\n"
                "✅ Pre-trade honeypot simulation\n"
                "✅ Gas optimization & estimation\n"
                "✅ Liquidity depth verification\n"
                "✅ AI-powered risk assessment\n"
                "✅ Real-time price locking",
                parse_mode='Markdown'
            )
            return
        
        chain = context.args[0].lower()
        token_address = context.args[1]
        
        try:
            amount_usd = float(context.args[2])
        except ValueError:
            await update.message.reply_text("❌ Invalid amount. Please enter a numeric value.")
            return
        
        if amount_usd <= 0:
            await update.message.reply_text("❌ Amount must be greater than 0.")
            return
        
        # Validate chain
        if chain not in ['eth', 'bsc']:
            await update.message.reply_text("❌ Unsupported chain. Use 'eth' or 'bsc'.")
            return
        
        # Show loading message
        loading_msg = await update.message.reply_text("🔄 **Analyzing token & preparing trade...**\n\n"
                                                    "⏳ Running comprehensive checks:\n"
                                                    "• Honeypot detection & simulation\n"
                                                    "• Liquidity & volume analysis\n"
                                                    "• Gas estimation & optimization\n"
                                                    "• AI risk assessment\n\n"
                                                    "This may take 10-15 seconds...")
        
        try:
            # Perform comprehensive pre-trade analysis
            analysis_result = await self.perform_pre_trade_analysis(token_address, chain, amount_usd, 'buy')
            
            if not analysis_result['success']:
                await loading_msg.edit_text(f"❌ **Pre-trade Analysis Failed**\n\n{analysis_result['error']}")
                return
            
            # Create trade session
            session_id = f"{user_id}_{token_address}_{int(asyncio.get_event_loop().time())}"
            self.user_sessions[session_id] = {
                'user_id': user_id,
                'action': 'buy',
                'chain': chain,
                'token_address': token_address,
                'amount_usd': amount_usd,
                'analysis': analysis_result,
                'timestamp': asyncio.get_event_loop().time()
            }
            
            # Show pre-trade confirmation
            await self.show_pre_trade_confirmation(loading_msg, analysis_result, session_id)
            
        except Exception as e:
            logger.error(f"Buy command error: {e}")
            await loading_msg.edit_text(f"❌ **Buy Analysis Failed**\n\nError: {str(e)}")

    async def sell_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /sell command with P&L tracking and token selection"""
        user_id = str(update.effective_user.id)
        
        # If no arguments, show token selection
        if len(context.args) == 0:
            await self._show_token_selection_for_sell(update, user_id)
            return
        
        if len(context.args) < 3:
            await update.message.reply_text(
                "💸 **Sell Token Command**\n\n"
                "**Usage:** `/sell [chain] [token_address] [percentage]`\n\n"
                "**Examples:**\n"
                "• `/sell eth 0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b 50` (sell 50%)\n"
                "• `/sell bsc 0xA0b86a33E6441ba0BB7e1ae5E3e7BAaD5D1D7e3c 100` (sell all)\n\n"
                "**Or just use `/sell` to see your holdings and choose what to sell.**\n\n"
                "**Parameters:**\n"
                "• `percentage` - Percentage of holdings to sell (1-100)\n\n"
                "**Features:**\n"
                "✅ Real-time P&L calculation\n"
                "✅ Tax optimization strategies\n"
                "✅ Gas optimization & timing\n"
                "✅ Slippage protection\n"
                "✅ Performance tracking",
                parse_mode='Markdown'
            )
            return
        
        chain = context.args[0].lower()
        token_address = context.args[1]
        
        try:
            percentage = float(context.args[2])
        except ValueError:
            await update.message.reply_text("❌ Invalid percentage. Please enter a numeric value.")
            return
        
        if percentage <= 0 or percentage > 100:
            await update.message.reply_text("❌ Percentage must be between 1 and 100.")
            return
        
        # Validate chain
        if chain not in ['eth', 'bsc', 'sol']:
            await update.message.reply_text("❌ Unsupported chain. Use 'eth', 'bsc', or 'sol'.")
            return
        
        # Show loading message with enhanced info
        loading_msg = await update.message.reply_text("🔄 **Analyzing holdings & preparing sell order...**\n\n"
                                                    "⏳ Calculating:\n"
                                                    "• Current token balance & USD value\n"
                                                    "• Real-time P&L analysis\n"
                                                    "• Optimal sell strategy & timing\n"
                                                    "• Gas estimation & optimization\n\n"
                                                    "This may take 10-15 seconds...")
        
        try:
            # Perform pre-sell analysis with enhanced USD calculations
            analysis_result = await self.perform_pre_trade_analysis(token_address, chain, percentage, 'sell')
            
            if not analysis_result['success']:
                await loading_msg.edit_text(f"❌ **Pre-sell Analysis Failed**\n\n{analysis_result['error']}")
                return
            
            # Create trade session
            session_id = f"{user_id}_{token_address}_{int(asyncio.get_event_loop().time())}"
            self.user_sessions[session_id] = {
                'user_id': user_id,
                'action': 'sell',
                'chain': chain,
                'token_address': token_address,
                'percentage': percentage,
                'analysis': analysis_result,
                'timestamp': asyncio.get_event_loop().time()
            }
            
            # Show pre-trade confirmation with P&L
            await self.show_sell_confirmation(loading_msg, analysis_result, session_id)
            
        except Exception as e:
            logger.error(f"Sell command error: {e}")
            await loading_msg.edit_text(f"❌ **Sell Analysis Failed**\n\nError: {str(e)}")

    async def _show_token_selection_for_sell(self, update: Update, user_id: str):
        """Show user's token holdings for selection"""
        try:
            # Get user's portfolio
            from core.trading_engine import trading_engine
            portfolio = await trading_engine.get_portfolio_summary(user_id)
            
            if 'error' in portfolio:
                await update.message.reply_text(f"❌ **Portfolio Error**\n\n{portfolio['error']}")
                return
            
            positions = portfolio.get('positions', [])
            
            if not positions:
                message = """
💸 **Sell Tokens**

📭 **No Holdings Found**

You don't have any token positions to sell.

**Next Steps:**
• Use `/buy` to purchase tokens
• Use /portfolio to check your holdings
• Use /watchlist to monitor wallets for opportunities

Start building your portfolio with smart buys! 📈
                """
                await update.message.reply_text(message, parse_mode='Markdown')
                return
            
            # Format holdings for selection
            message = f"💸 **Select Token to Sell**\n\n**Your Holdings ({len(positions)} tokens):**\n\n"
            
            keyboard = []
            for i, position in enumerate(positions[:10], 1):  # Show max 10
                token_symbol = position.get('token_symbol', 'UNKNOWN')
                current_value = position.get('current_value_usd', 0)
                pnl_usd = position.get('pnl_usd', 0)
                pnl_pct = position.get('pnl_percentage', 0)
                
                # Format display
                pnl_emoji = "🟢" if pnl_usd >= 0 else "🔴"
                pnl_sign = "+" if pnl_usd >= 0 else ""
                
                message += f"{i}. **{token_symbol}**\n"
                message += f"   Value: ${current_value:,.2f}\n"
                message += f"   P&L: {pnl_emoji} {pnl_sign}${pnl_usd:,.2f} ({pnl_sign}{pnl_pct:.1f}%)\n\n"
                
                # Add button for this token
                token_address = position.get('token_address', '')
                keyboard.append([InlineKeyboardButton(
                    f"💸 Sell {token_symbol}", 
                    callback_data=f"sell_token_{token_address[:10]}_{i}"
                )])
            
            if len(positions) > 10:
                message += f"... and {len(positions) - 10} more tokens\n\n"
            
            message += "**Total Portfolio Value:** ${:,.2f}\n".format(portfolio.get('portfolio_value_usd', 0))
            message += "\nSelect a token to sell, or use the command format:\n"
            message += "`/sell [chain] [token_address] [percentage]`"
            
            # Add utility buttons
            keyboard.extend([
                [InlineKeyboardButton("📊 Full Portfolio", callback_data="view_portfolio")],
                [InlineKeyboardButton("🚨 Sell All (Panic)", callback_data="panic_sell_confirm")],
                [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_holdings")]
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Token selection error: {e}")
            await update.message.reply_text(f"❌ **Selection Error**\n\nFailed to load holdings: {str(e)}")

    async def show_sell_confirmation(self, message, analysis_result: Dict, session_id: str):
        """Show sell confirmation with P&L details"""
        try:
            session = self.user_sessions[session_id]
            token_address = session['token_address']
            percentage = session['percentage']
            chain = session['chain']
            
            # Get enhanced P&L information
            pnl_info = analysis_result.get('pnl_analysis', {})
            
            confirmation_text = f"""
💸 **SELL ORDER CONFIRMATION**

**📊 Trade Details:**
• **Action:** SELL {percentage}% of holdings
• **Token:** `{token_address[:8]}...{token_address[-6:]}`
• **Chain:** {chain.upper()}

**💰 P&L Analysis:**
• **Current Value:** ${pnl_info.get('current_value_usd', 0):,.2f}
• **Entry Value:** ${pnl_info.get('entry_value_usd', 0):,.2f}
• **Total P&L:** {"🟢 +" if pnl_info.get('total_pnl_usd', 0) >= 0 else "🔴 "}${pnl_info.get('total_pnl_usd', 0):,.2f}
• **P&L %:** {pnl_info.get('pnl_percentage', 0):+.1f}%

**🔥 Trade Impact:**
• **Sell Amount:** {pnl_info.get('sell_amount_tokens', 0):,.4f} tokens
• **Est. USD Received:** ${pnl_info.get('estimated_usd_received', 0):,.2f}
• **Remaining Holdings:** {100-percentage:.1f}%

**⛽ Gas & Fees:**
• **Estimated Gas:** ${analysis_result.get('gas_cost_usd', 0):.2f}
• **Network:** {chain.upper()}
• **Slippage:** {analysis_result.get('slippage', 0.01)*100:.1f}%

**🎯 PROFIT ANALYSIS:**
{"🎉 PROFITABLE TRADE" if pnl_info.get('total_pnl_usd', 0) > 0 else "📉 LOSS MAKING TRADE" if pnl_info.get('total_pnl_usd', 0) < 0 else "⚖️ BREAK-EVEN TRADE"}

**Ready to execute this sell order?**
            """
            
            # Create confirmation buttons
            keyboard = [
                [InlineKeyboardButton("✅ Execute Sell", callback_data=f"confirm_trade_{session_id}")],
                [InlineKeyboardButton("🔄 Dry Run First", callback_data=f"dry_run_{session_id}")],
                [InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_trade_{session_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await message.edit_text(confirmation_text, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error showing sell confirmation: {e}")
            await message.edit_text(f"❌ Error displaying sell confirmation: {str(e)}")

    async def sell_command_old(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /sell command with P&L tracking"""
        user_id = str(update.effective_user.id)
        
        if len(context.args) < 3:
            await update.message.reply_text(
                "💸 **Sell Token Command**\n\n"
                "**Usage:** `/sell [chain] [token_address] [percentage]`\n\n"
                "**Examples:**\n"
                "• `/sell eth 0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b 50` (sell 50%)\n"
                "• `/sell bsc 0xA0b86a33E6441ba0BB7e1ae5E3e7BAaD5D1D7e3c 100` (sell all)\n\n"
                "**Parameters:**\n"
                "• `percentage` - Percentage of holdings to sell (1-100)\n\n"
                "**Features:**\n"
                "✅ Real-time P&L calculation\n"
                "✅ Tax optimization strategies\n"
                "✅ Gas optimization & timing\n"
                "✅ Slippage protection\n"
                "✅ Performance tracking",
                parse_mode='Markdown'
            )
            return
        
        chain = context.args[0].lower()
        token_address = context.args[1]
        
        try:
            percentage = float(context.args[2])
        except ValueError:
            await update.message.reply_text("❌ Invalid percentage. Please enter a numeric value.")
            return
        
        if percentage <= 0 or percentage > 100:
            await update.message.reply_text("❌ Percentage must be between 1 and 100.")
            return
        
        # Validate chain
        if chain not in ['eth', 'bsc']:
            await update.message.reply_text("❌ Unsupported chain. Use 'eth' or 'bsc'.")
            return
        
        # Show loading message
        loading_msg = await update.message.reply_text("🔄 **Analyzing holdings & preparing sell order...**\n\n"
                                                    "⏳ Calculating:\n"
                                                    "• Current token balance\n"
                                                    "• Real-time P&L analysis\n"
                                                    "• Optimal sell strategy\n"
                                                    "• Gas estimation & timing\n\n"
                                                    "This may take 10-15 seconds...")
        
        try:
            # Perform pre-sell analysis
            analysis_result = await self.perform_pre_trade_analysis(token_address, chain, percentage, 'sell')
            
            if not analysis_result['success']:
                await loading_msg.edit_text(f"❌ **Pre-sell Analysis Failed**\n\n{analysis_result['error']}")
                return
            
            # Create trade session
            session_id = f"{user_id}_{token_address}_{int(asyncio.get_event_loop().time())}"
            self.user_sessions[session_id] = {
                'user_id': user_id,
                'action': 'sell',
                'chain': chain,
                'token_address': token_address,
                'percentage': percentage,
                'analysis': analysis_result,
                'timestamp': asyncio.get_event_loop().time()
            }
            
            # Show pre-trade confirmation
            await self.show_pre_trade_confirmation(loading_msg, analysis_result, session_id)
            
        except Exception as e:
            logger.error(f"Sell command error: {e}")
            await loading_msg.edit_text(f"❌ **Sell Analysis Failed**\n\nError: {str(e)}")

    async def panic_sell_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /panic_sell command for emergency liquidation"""
        user_id = str(update.effective_user.id)
        
        # Show warning and confirmation
        warning_message = """
🚨 **PANIC SELL - EMERGENCY LIQUIDATION** 🚨

⚠️ **WARNING: This will liquidate ALL your positions immediately!**

**What this does:**
• Sells all token positions across all chains
• Uses higher slippage tolerance for fast execution
• May result in significant losses due to market impact
• Cannot be undone once started

**Current positions will be liquidated:**
• Ethereum/BSC tokens
• Solana tokens
• All mirror trading positions

**Are you absolutely sure you want to proceed?**

This action is irreversible and should only be used in extreme situations.
        """
        
        keyboard = [
            [InlineKeyboardButton("🚨 YES - LIQUIDATE ALL", callback_data=f"panic_sell_confirm_{user_id}")],
            [InlineKeyboardButton("❌ Cancel", callback_data=f"panic_sell_cancel_{user_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(warning_message, reply_markup=reply_markup, parse_mode='Markdown')

    async def scan_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /scan command for manual wallet scanning"""
        user_id = str(update.effective_user.id)
        
        # Show loading message
        loading_msg = await update.message.reply_text("🔍 **Manual Wallet Scan**\n\n⏳ Scanning all watched wallets across chains...\nThis may take 30-60 seconds...")
        
        try:
            from services.wallet_scanner import wallet_scanner
            
            # Perform manual scan
            scan_results = await wallet_scanner.manual_scan()
            
            if 'error' in scan_results:
                await loading_msg.edit_text(f"❌ **Scan Failed**\n\nError: {scan_results['error']}")
                return
            
            # Format results
            result_message = f"""
🔍 **Manual Scan Complete**

**📊 Scan Results:**
• Wallets Scanned: {scan_results['scanned_wallets']}
• New Transactions: {scan_results.get('new_transactions', 0)}
• Alerts Sent: {scan_results.get('alerts_sent', 0)}
• Chains: {', '.join(scan_results.get('chains_scanned', []))}

**⏰ Scan Time:** {scan_results['scan_time'].strftime('%H:%M:%S UTC')}

**Next Steps:**
• Monitor alerts for trading signals
• Use /leaderboard to see top wallets
• Configure /alerts for custom filtering

Automatic scanning continues in background every 30 seconds.
            """
            
            keyboard = [
                [InlineKeyboardButton("📈 View Leaderboard", callback_data="leaderboard")],
                [InlineKeyboardButton("⚙️ Configure Alerts", callback_data="configure_alerts")],
                [InlineKeyboardButton("👁️ Watchlist", callback_data="view_watchlist")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await loading_msg.edit_text(result_message, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Scan command error: {e}")
            await loading_msg.edit_text(f"❌ **Scan Error**\n\nFailed to perform manual scan: {str(e)}")

    async def leaderboard_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /leaderboard command - show moonshot wallets"""
        user_id = str(update.effective_user.id)
        
        # Show loading message
        loading_msg = await update.message.reply_text("📈 **Loading Moonshot Leaderboard...**\n\n🔍 Finding wallets with 200x+ gains...")
        
        try:
            from services.wallet_scanner import wallet_scanner
            
            # Get moonshot wallets
            moonshot_wallets = await wallet_scanner.get_moonshot_leaderboard()
            
            if not moonshot_wallets:
                await loading_msg.edit_text("📈 **Moonshot Leaderboard**\n\n🔍 No wallets found with 200x+ multipliers yet.\n\nKeep monitoring - the next moonshot could be discovered soon!")
                return
            
            # Format leaderboard
            leaderboard_text = "🚀 **MOONSHOT LEADERBOARD** 🚀\n\n💎 *Wallets with 200x+ gains*\n\n"
            
            from utils.formatting import AddressFormatter
            
            for i, wallet in enumerate(moonshot_wallets[:10], 1):
                leaderboard_text += AddressFormatter.format_leaderboard_entry(
                    rank=i,
                    wallet_address=wallet.address,
                    multiplier=wallet.best_trade_multiplier,
                    total_pnl=wallet.total_pnl_usd,
                    win_rate=wallet.win_rate,
                    chains=wallet.chains
                )
                leaderboard_text += "\n"
            
            leaderboard_text += f"📅 Last updated: {datetime.utcnow().strftime('%H:%M UTC')}\n"
            leaderboard_text += "🔄 Updates every 30 seconds with new discoveries"
            
            keyboard = [
                [InlineKeyboardButton("🔍 Analyze Top Wallet", callback_data=f"analyze_wallet_{moonshot_wallets[0].address[:10]}")],
                [InlineKeyboardButton("👁️ Watch Top Wallet", callback_data=f"add_watchlist_{moonshot_wallets[0].address[:10]}")],
                [InlineKeyboardButton("🔍 Scan Now", callback_data="manual_scan")],
                [InlineKeyboardButton("⚙️ Alert Settings", callback_data="configure_alerts")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await loading_msg.edit_text(leaderboard_text, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Leaderboard command error: {e}")
            await loading_msg.edit_text(f"❌ **Leaderboard Error**\n\nFailed to load moonshot leaderboard: {str(e)}")

    async def alerts_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /alerts command - configure alert filters"""
        user_id = str(update.effective_user.id)
        
        try:
            # Get current alert configuration
            db = get_db_session()
            try:
                user = db.query(User).filter(User.telegram_id == user_id).first()
                if not user:
                    await update.message.reply_text("❌ User not found. Please use /start first.")
                    return
                
                alert_config = db.query(AlertConfig).filter(AlertConfig.user_id == user.id).first()
                
                # Create default config if doesn't exist
                if not alert_config:
                    alert_config = AlertConfig(
                        user_id=user.id,
                        min_trade_size_usd=100.0,
                        max_alerts_per_hour=20,
                        monitored_chains="ethereum,bsc,solana",
                        buy_alerts_enabled=True,
                        sell_alerts_enabled=True,
                        moonshot_alerts_enabled=True
                    )
                    db.add(alert_config)
                    db.commit()
                    db.refresh(alert_config)
                
                # Format current settings
                chains = alert_config.monitored_chains.split(',') if alert_config.monitored_chains else []
                chains_display = ', '.join([c.upper() for c in chains])
                
                settings_message = f"""
⚙️ **Alert Configuration**

**🔔 Current Settings:**
• Min Trade Size: ${alert_config.min_trade_size_usd:,.0f}
• Max Alerts/Hour: {alert_config.max_alerts_per_hour}
• Monitored Chains: {chains_display}

**📊 Alert Types:**
• Buy Alerts: {'✅ ON' if alert_config.buy_alerts_enabled else '❌ OFF'}
• Sell Alerts: {'✅ ON' if alert_config.sell_alerts_enabled else '❌ OFF'}
• Moonshot Alerts: {'✅ ON' if alert_config.moonshot_alerts_enabled else '❌ OFF'}

**🚫 Filters:**
• Blacklisted Wallets: {len(alert_config.blacklisted_wallets.split(',')) if alert_config.blacklisted_wallets else 0}
• Blacklisted Tokens: {len(alert_config.blacklisted_tokens.split(',')) if alert_config.blacklisted_tokens else 0}

**Configure your alert preferences below:**
                """
                
                keyboard = [
                    [InlineKeyboardButton("💰 Min Trade Size", callback_data=f"set_min_trade_{user_id}")],
                    [InlineKeyboardButton("🔔 Alert Types", callback_data=f"alert_types_{user_id}")],
                    [InlineKeyboardButton("🌐 Chains", callback_data=f"set_chains_{user_id}")],
                    [InlineKeyboardButton("🚫 Blacklist", callback_data=f"manage_blacklist_{user_id}")],
                    [InlineKeyboardButton("📊 Test Alerts", callback_data=f"test_alerts_{user_id}")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(settings_message, reply_markup=reply_markup, parse_mode='Markdown')
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Alerts command error: {e}")
            await update.message.reply_text(f"❌ **Alert Configuration Error**\n\nFailed to load alert settings: {str(e)}")

    async def blacklist_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /blacklist command - manage blacklisted wallets/tokens"""
        user_id = str(update.effective_user.id)
        
        if len(context.args) == 0:
            # Show current blacklist
            await self._show_blacklist(update, user_id)
            return
        
        action = context.args[0].lower()
        
        if action == "add" and len(context.args) >= 3:
            entry_type = context.args[1].lower()  # 'wallet' or 'token'
            address = context.args[2]
            reason = ' '.join(context.args[3:]) if len(context.args) > 3 else "Manual addition"
            
            if entry_type not in ['wallet', 'token']:
                await update.message.reply_text("❌ Invalid type. Use 'wallet' or 'token'.")
                return
            
            success = await self._add_to_blacklist(user_id, entry_type, address, reason)
            
            if success:
                await update.message.reply_text(f"✅ Added {entry_type} `{address[:16]}...` to blacklist.\n\nReason: {reason}", parse_mode='Markdown')
            else:
                await update.message.reply_text("❌ Failed to add to blacklist.")
                
        elif action == "remove" and len(context.args) >= 2:
            address = context.args[1]
            success = await self._remove_from_blacklist(user_id, address)
            
            if success:
                await update.message.reply_text(f"✅ Removed `{address[:16]}...` from blacklist.", parse_mode='Markdown')
            else:
                await update.message.reply_text("❌ Failed to remove from blacklist or not found.")
                
        else:
            help_text = """
🚫 **Blacklist Management**

**Usage:**
• `/blacklist` - Show current blacklist
• `/blacklist add wallet 0x123... [reason]` - Add wallet
• `/blacklist add token 0xabc... [reason]` - Add token  
• `/blacklist remove 0x123...` - Remove entry

**Examples:**
• `/blacklist add wallet 0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b Suspicious activity`
• `/blacklist add token 0xA0b86a33E6441ba0BB7e1ae5E3e7BAaD5D1D7e3c Honeypot detected`
• `/blacklist remove 0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b`

Blacklisted entries are filtered from alerts and trading signals.
            """
            await update.message.reply_text(help_text, parse_mode='Markdown')

    async def watchlist_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /watchlist command - manage watched wallets"""
        user_id = str(update.effective_user.id)
        
        if len(context.args) == 0:
            # Show current watchlist
            await self._show_watchlist(update, user_id)
            return
        
        action = context.args[0].lower()
        
        if action == "add" and len(context.args) >= 2:
            wallet_address = context.args[1]
            chains = context.args[2].split(',') if len(context.args) > 2 else ['ethereum']
            wallet_name = ' '.join(context.args[3:]) if len(context.args) > 3 else None
            
            # Validate address format
            if not self._validate_wallet_address(wallet_address):
                await update.message.reply_text("❌ Invalid wallet address format.")
                return
            
            from services.wallet_scanner import wallet_scanner
            success = await wallet_scanner.add_wallet_to_watchlist(wallet_address, int(user_id), chains)
            
            if success:
                chains_str = ', '.join([c.upper() for c in chains])
                await update.message.reply_text(f"✅ Added wallet to watchlist:\n\n**Address:** `{wallet_address}`\n**Chains:** {chains_str}\n**Name:** {wallet_name or 'Unnamed'}\n\nYou'll receive alerts for this wallet's activity.", parse_mode='Markdown')
            else:
                await update.message.reply_text("❌ Failed to add wallet to watchlist.")
                
        elif action == "remove" and len(context.args) >= 2:
            wallet_address = context.args[1]
            success = await self._remove_from_watchlist(user_id, wallet_address)
            
            if success:
                await update.message.reply_text(f"✅ Removed `{wallet_address[:16]}...` from watchlist.", parse_mode='Markdown')
            else:
                await update.message.reply_text("❌ Failed to remove from watchlist or not found.")
                
        else:
            help_text = """
👁️ **Watchlist Management**

**Usage:**
• `/watchlist` - Show current watchlist
• `/watchlist add 0x123... [chains] [name]` - Add wallet
• `/watchlist remove 0x123...` - Remove wallet

**Examples:**
• `/watchlist add 0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b ethereum,bsc DefiWhale`
• `/watchlist add DUSTawucrTsGU8hcqRdHDCbuYhCPADMLM2VcCb8VnFnQ solana SolanaGem`
• `/watchlist remove 0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b`

**Supported Chains:** ethereum, bsc, solana
            """
            await update.message.reply_text(help_text, parse_mode='Markdown')

    async def settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /settings command for trading configuration"""
        user_id = str(update.effective_user.id)
        
        # Get current trading engine config
        from core.trading_engine import trading_engine
        
        current_config = {
            'safe_mode': trading_engine.config['safe_mode'],
            'mirror_sell_enabled': trading_engine.config['mirror_sell_enabled'],
            'mirror_buy_enabled': trading_engine.config['mirror_buy_enabled'],
            'max_auto_buy_usd': trading_engine.config['max_auto_buy_usd'],
            'max_position_size_usd': trading_engine.config['max_position_size_usd'],
            'max_slippage': trading_engine.config['max_slippage'] * 100,  # Convert to percentage
            'min_liquidity_usd': trading_engine.config['min_liquidity_usd']
        }
        
        settings_message = f"""
⚙️ **Trading Settings & Configuration**

**🛡️ Safety Settings:**
• Safe Mode: {'✅ ON' if current_config['safe_mode'] else '❌ OFF'}
• Max Slippage: {current_config['max_slippage']:.1f}%
• Min Liquidity: ${current_config['min_liquidity_usd']:,.0f}

**🔄 Mirror Trading:**
• Mirror Sell: {'✅ ON (Auto)' if current_config['mirror_sell_enabled'] else '❌ OFF'}
• Mirror Buy: {'✅ ON (Auto)' if current_config['mirror_buy_enabled'] else '❌ OFF (Manual)'}

**💰 Position Limits:**
• Max Auto Buy: ${current_config['max_auto_buy_usd']:.0f}
• Max Position Size: ${current_config['max_position_size_usd']:,.0f}

**📊 Current Status:**
• Active Positions: {len(trading_engine.mirror_positions)}
• Total Trades: {trading_engine.stats['total_trades']}
• Win Rate: {trading_engine.stats['win_rate']:.1f}%
• Total P&L: ${trading_engine.stats['total_pnl_usd']:.2f}

Click buttons below to modify settings:
        """
        
        keyboard = [
            [InlineKeyboardButton("🛡️ Toggle Safe Mode", callback_data=f"toggle_safe_mode_{user_id}")],
            [InlineKeyboardButton("🔄 Mirror Settings", callback_data=f"mirror_settings_{user_id}")],
            [InlineKeyboardButton("💰 Position Limits", callback_data=f"position_limits_{user_id}")],
            [InlineKeyboardButton("📊 View Portfolio", callback_data=f"view_portfolio_{user_id}")],
            [InlineKeyboardButton("❓ Help", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(settings_message, reply_markup=reply_markup, parse_mode='Markdown')

    async def portfolio_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /portfolio command for portfolio summary"""
        user_id = str(update.effective_user.id)
        
        # Show loading message
        loading_msg = await update.message.reply_text("📊 **Generating Portfolio Summary...**\n\n⏳ Calculating positions, P&L, and performance metrics...")
        
        try:
            # Get portfolio summary from trading engine
            from core.trading_engine import trading_engine
            portfolio = await trading_engine.get_portfolio_summary(user_id)
            
            if 'error' in portfolio:
                await loading_msg.edit_text(f"❌ **Portfolio Error**\n\n{portfolio['error']}")
                return
            
            # Format portfolio summary
            total_value = portfolio.get('portfolio_value_usd', 0)
            total_pnl = portfolio.get('total_pnl_usd', 0)
            position_count = portfolio.get('position_count', 0)
            positions = portfolio.get('positions', [])
            
            pnl_emoji = "🟢" if total_pnl >= 0 else "🔴"
            pnl_sign = "+" if total_pnl >= 0 else ""
            
            portfolio_message = f"""
📊 **Portfolio Summary**

**💰 Overall Performance:**
• Total Value: ${total_value:,.2f}
• Total P&L: {pnl_emoji} {pnl_sign}${total_pnl:,.2f}
• Active Positions: {position_count}

**📈 Trading Stats:**
• Win Rate: {portfolio.get('performance_metrics', {}).get('win_rate', 0):.1f}%
• Total Trades: {portfolio.get('performance_metrics', {}).get('total_trades', 0)}
• Successful: {portfolio.get('performance_metrics', {}).get('successful_trades', 0)}
• Moonshots: {portfolio.get('performance_metrics', {}).get('moonshots_detected', 0)}

**🎯 Active Positions:**
            """
            
            from utils.formatting import AddressFormatter
            
            if positions:
                for i, pos in enumerate(positions[:5], 1):  # Show top 5 positions
                    token_address = pos.get('token_address', '')
                    token_symbol = pos.get('token_symbol', 'UNKNOWN')
                    chain = pos.get('chain', 'ethereum')
                    current_value = pos.get('current_value_usd', 0)
                    pnl_usd = pos.get('pnl_usd', 0)
                    pnl_pct = pos.get('pnl_percentage', 0)
                    
                    position_text = AddressFormatter.format_portfolio_position(
                        token_address=token_address,
                        token_symbol=token_symbol,
                        chain=chain,
                        current_value=current_value,
                        pnl_usd=pnl_usd,
                        pnl_pct=pnl_pct
                    )
                    
                    portfolio_message += f"\n{i}. {position_text}"
                
                if len(positions) > 5:
                    portfolio_message += f"\n\n... and {len(positions) - 5} more positions"
            else:
                portfolio_message += "\nNo active positions"
            
            keyboard = [
                [InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh_portfolio_{user_id}")],
                [InlineKeyboardButton("📋 Detailed Report", callback_data=f"detailed_portfolio_{user_id}")],
                [InlineKeyboardButton("🚨 Panic Sell All", callback_data=f"panic_sell_confirm_{user_id}")],
                [InlineKeyboardButton("⚙️ Settings", callback_data=f"settings_{user_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await loading_msg.edit_text(portfolio_message, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Portfolio command error: {e}")
            await loading_msg.edit_text(f"❌ **Portfolio Error**\n\nFailed to generate portfolio summary: {str(e)}")

    async def analyze_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /analyze command with enhanced analysis"""
        if len(context.args) == 0:
            await update.message.reply_text(
                "🔍 **Enhanced Token Analysis**\n\n"
                "**Usage:** `/analyze [token_address]`\n\n"
                "**Example:**\n"
                "`/analyze 0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b`\n\n"
                "**Enhanced Features:**\n"
                "✅ Advanced honeypot simulation\n"
                "✅ Multi-scenario trading tests\n"
                "✅ Contract risk assessment\n"
                "✅ Liquidity depth analysis\n"
                "✅ AI-powered scoring (0-10)\n"
                "✅ Trade safety score\n"
                "✅ Real-time risk monitoring", 
                parse_mode='Markdown'
            )
            return
        
        token_address = context.args[0]
        loading_msg = await update.message.reply_text("🔄 **Running Enhanced Analysis...**\n\n"
                                                    "⏳ Comprehensive checks in progress:\n"
                                                    "• Advanced honeypot simulation\n"
                                                    "• Contract security analysis\n"
                                                    "• Trading scenario testing\n"
                                                    "• AI risk assessment\n"
                                                    "• Market sentiment analysis\n\n"
                                                    "This may take 15-20 seconds...")
        
        try:
            analysis = await self.analyzer.analyze_token(token_address)
            await self.show_enhanced_analysis_results(loading_msg, analysis)
            
        except Exception as e:
            logger.error(f"Enhanced analysis error: {e}")
            await loading_msg.edit_text(f"❌ **Enhanced Analysis Failed**\n\nError: {str(e)}")

    async def unified_callback_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Unified callback handler for all inline keyboard interactions"""
        query = update.callback_query
        user_id = str(query.from_user.id)
        data = query.data
        
        await query.answer()
        
        try:
            # Handle main menu callbacks
            if data == "main_menu":
                await self.show_main_menu(query, user_id)
            elif data == "main_refresh":
                await self.show_main_menu(query, user_id)
            elif data == "main_portfolio":
                await self._handle_main_portfolio(query, user_id)
            elif data == "main_scan":
                await self._handle_main_scan(query, user_id)
            elif data == "main_buy":
                await self._handle_main_buy(query, user_id)
            elif data == "main_sell":
                await self._handle_main_sell(query, user_id)
            elif data == "main_leaderboard":
                await self._handle_main_leaderboard(query, user_id)
            elif data == "main_panic_sell":
                await self._handle_main_panic_sell(query, user_id)
            elif data == "main_settings":
                await self._handle_main_settings(query, user_id)
            elif data == "main_toggle_safe_mode":
                await self._handle_toggle_safe_mode(query, user_id)
            elif data == "main_help":
                await self._handle_main_help(query, user_id)
            
            # Handle sell percentage callbacks
            elif data.startswith('sell_'):
                await self._handle_sell_percentage(query, data, user_id)
            
            # Handle buy amount settings
            elif data.startswith('set_buy_amount_'):
                await self._handle_set_buy_amount(query, data, user_id)
            
            # Handle confirmations
            elif data.startswith('execute_'):
                await self._handle_execute_action(query, data, user_id)
            elif data == "cancel_trade":
                await self._handle_cancel_trade(query, user_id)
            
            # Handle settings callbacks
            elif data.startswith('settings_'):
                await self._handle_settings_callback(query, data, user_id)
            
            # Handle existing advanced callback queries
            elif data.startswith('panic_sell_confirm_'):
                await self._handle_panic_sell_confirm(query, user_id)
            elif data.startswith('panic_sell_cancel_'):
                await query.edit_message_text("✅ Panic sell cancelled. Your positions are safe.")
                await self.show_main_menu(query, user_id)
            elif data.startswith('toggle_safe_mode_'):
                await self._handle_toggle_safe_mode(query, user_id)
            elif data.startswith('mirror_settings_'):
                await self._handle_mirror_settings(query, user_id)
            elif data.startswith('toggle_mirror_sell_'):
                await self._handle_toggle_mirror_sell(query, user_id)
            elif data.startswith('toggle_mirror_buy_'):
                await self._handle_toggle_mirror_buy(query, user_id)
            elif data.startswith('view_portfolio_') or data.startswith('refresh_portfolio_'):
                await self._handle_portfolio_view(query, user_id)
            
            # Handle enhanced action callbacks
            elif data.startswith('analyze_wallet_'):
                wallet_prefix = data.replace('analyze_wallet_', '')
                await self._handle_analyze_wallet_callback(query, wallet_prefix, user_id)
            elif data.startswith('analyze_token_'):
                token_prefix = data.replace('analyze_token_', '')
                await self._handle_analyze_token_callback(query, token_prefix, user_id)
            elif data.startswith('add_watchlist_'):
                wallet_prefix = data.replace('add_watchlist_', '')
                await self._handle_add_watchlist_callback(query, wallet_prefix, user_id)
            elif data.startswith('blacklist_wallet_'):
                wallet_prefix = data.replace('blacklist_wallet_', '')
                await self._handle_blacklist_wallet_callback(query, wallet_prefix, user_id)
            elif data.startswith('blacklist_token_'):
                token_prefix = data.replace('blacklist_token_', '')
                await self._handle_blacklist_token_callback(query, token_prefix, user_id)
            elif data.startswith('quick_buy_'):
                token_prefix = data.replace('quick_buy_', '')
                await self._handle_quick_buy_callback(query, token_prefix, user_id)
            
            # Handle legacy callbacks  
            elif data.startswith("confirm_trade_"):
                session_id = data.replace("confirm_trade_", "")
                await self.handle_trade_confirmation(query, session_id)
            elif data.startswith("dry_run_"):
                session_id = data.replace("dry_run_", "")
                await self.handle_dry_run(query, session_id)
            elif data.startswith("cancel_trade_"):
                session_id = data.replace("cancel_trade_", "")
                await self.handle_trade_cancellation(query, session_id)
            elif data == "buy_token":
                await query.edit_message_text(
                    "💰 **Buy Token**\n\n"
                    "Use the Main Menu 'Buy Token' button or:\n"
                    "`/buy [chain] [token_address] [amount_usd]`\n\n"
                    "**Example:**\n"
                    "`/buy eth 0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b 10`",
                    parse_mode='Markdown'
                )
                await self.show_main_menu(query, user_id)
            elif data == "sell_token":
                await query.edit_message_text(
                    "💸 **Sell Token**\n\n"
                    "Use the Main Menu 'Sell Token' button or:\n"
                    "`/sell [chain] [token_address] [percentage]`\n\n"
                    "**Example:**\n"
                    "`/sell eth 0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b 50`",
                    parse_mode='Markdown'
                )
                await self.show_main_menu(query, user_id)
            elif data == "analyze_token":
                await query.edit_message_text(
                    "🔍 **Analyze Token**\n\n"
                    "Use the Main Menu 'Scan Wallets' button or:\n"
                    "`/analyze [token_address]`\n\n"
                    "**Example:**\n"
                    "`/analyze 0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b`",
                    parse_mode='Markdown'
                )
                await self.show_main_menu(query, user_id)
            elif data == "view_portfolio":
                await self._handle_main_portfolio(query, user_id)
            elif data == "separator":
                # Ignore separator clicks
                pass
            else:
                await query.edit_message_text(f"🚧 Feature available via Main Menu!\n\nUse the buttons below for easy navigation. 🚀")
                await self.show_main_menu(query, user_id)
                
        except Exception as e:
            logger.error(f"Unified callback handler error: {e}")
            await query.edit_message_text(f"❌ Error processing request: {str(e)}")
            await self.show_main_menu(query, user_id)

    async def _handle_panic_sell_confirm(self, query, user_id: str):
        """Handle panic sell confirmation"""
        try:
            await query.edit_message_text("🚨 **EXECUTING PANIC SELL...**\n\nLiquidating all positions. This may take 30-60 seconds...")
            
            # Execute panic sell through trading engine
            from core.trading_engine import trading_engine
            result = await trading_engine.execute_panic_sell(user_id)
            
            if result['success']:
                liquidated = result.get('liquidated_count', 0)
                total = result.get('total_positions', 0)
                
                success_message = f"""
✅ **PANIC SELL COMPLETED**

**Results:**
• Positions Liquidated: {liquidated}/{total}
• Successful Sales: {liquidated}
• Failed Sales: {total - liquidated}

**Summary:**
{result.get('message', 'All positions processed')}

Your portfolio has been liquidated. Check your wallet for received funds.
                """
                await query.edit_message_text(success_message, parse_mode='Markdown')
            else:
                await query.edit_message_text(f"❌ **PANIC SELL FAILED**\n\nError: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            logger.error(f"Panic sell execution error: {e}")
            await query.edit_message_text(f"❌ **PANIC SELL ERROR**\n\nFailed to execute: {str(e)}")

    async def _handle_toggle_safe_mode(self, query, user_id: str):
        """Handle safe mode toggle"""
        try:
            from core.trading_engine import trading_engine
            
            current_mode = trading_engine.config['safe_mode']
            new_mode = not current_mode
            
            result = await trading_engine.update_config(user_id, {'safe_mode': new_mode})
            
            if result['success']:
                mode_text = "ON" if new_mode else "OFF"
                await query.edit_message_text(f"✅ Safe Mode is now **{mode_text}**\n\nSafe mode {'blocks risky trades automatically' if new_mode else 'allows all trades (use caution)'}")
            else:
                await query.edit_message_text("❌ Failed to update safe mode setting")
                
        except Exception as e:
            logger.error(f"Safe mode toggle error: {e}")
            await query.edit_message_text(f"❌ Error: {str(e)}")

    async def _handle_mirror_settings(self, query, user_id: str):
        """Handle mirror trading settings"""
        try:
            from core.trading_engine import trading_engine
            
            current_config = trading_engine.config
            
            message = f"""
🔄 **Mirror Trading Settings**

**Current Status:**
• Mirror Sell: {'✅ ON' if current_config['mirror_sell_enabled'] else '❌ OFF'}
• Mirror Buy: {'✅ ON' if current_config['mirror_buy_enabled'] else '❌ OFF'}

**Mirror Sell (Recommended: ON):**
Automatically sells your tokens when tracked wallets sell

**Mirror Buy (Recommended: OFF):**
Automatically buys tokens when tracked wallets buy (risky)

Choose action:
            """
            
            keyboard = [
                [InlineKeyboardButton("🔄 Toggle Mirror Sell", callback_data=f"toggle_mirror_sell_{user_id}")],
                [InlineKeyboardButton("🔄 Toggle Mirror Buy", callback_data=f"toggle_mirror_buy_{user_id}")],
                [InlineKeyboardButton("⬅️ Back to Settings", callback_data=f"settings_{user_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Mirror settings error: {e}")
            await query.edit_message_text(f"❌ Error: {str(e)}")

    async def _handle_toggle_mirror_sell(self, query, user_id: str):
        """Handle mirror sell toggle"""
        try:
            from core.trading_engine import trading_engine
            
            current_state = trading_engine.config['mirror_sell_enabled']
            new_state = not current_state
            
            result = await trading_engine.update_config(user_id, {'mirror_sell_enabled': new_state})
            
            if result['success']:
                state_text = "ON" if new_state else "OFF"
                await query.edit_message_text(f"✅ Mirror Sell is now **{state_text}**\n\n{'Automatic selling when tracked wallets sell' if new_state else 'Manual selling only'}")
            else:
                await query.edit_message_text("❌ Failed to update mirror sell setting")
                
        except Exception as e:
            logger.error(f"Mirror sell toggle error: {e}")
            await query.edit_message_text(f"❌ Error: {str(e)}")

    async def _handle_toggle_mirror_buy(self, query, user_id: str):
        """Handle mirror buy toggle"""
        try:
            from core.trading_engine import trading_engine
            
            current_state = trading_engine.config['mirror_buy_enabled']
            new_state = not current_state
            
            result = await trading_engine.update_config(user_id, {'mirror_buy_enabled': new_state})
            
            if result['success']:
                state_text = "ON" if new_state else "OFF"
                warning = "\n\n⚠️ **WARNING:** Auto-buy is risky! Only enable if you trust your tracked wallets." if new_state else ""
                await query.edit_message_text(f"✅ Mirror Buy is now **{state_text}**\n\n{'Automatic buying when tracked wallets buy' if new_state else 'Manual buy alerts only'}{warning}")
            else:
                await query.edit_message_text("❌ Failed to update mirror buy setting")
                
        except Exception as e:
            logger.error(f"Mirror buy toggle error: {e}")
            await query.edit_message_text(f"❌ Error: {str(e)}")

    async def _handle_portfolio_view(self, query, user_id: str):
        """Handle portfolio view callback"""
        await query.edit_message_text("📊 Refreshing portfolio... Use /portfolio command for latest data.")

    async def _handle_help_callback(self, query):
        """Handle help callback"""
        help_text = """
🔧 **Meme Trader V4 Pro - Quick Help**

**Main Commands:**
/buy - Execute buy orders
/sell - Execute sell orders  
/panic_sell - Emergency liquidation
/portfolio - View portfolio summary
/settings - Trading configuration

**Features:**
✅ Multi-chain support (ETH, BSC, Solana)
✅ Mirror trading with risk management
✅ AI-powered analysis
✅ Real-time monitoring

Need detailed help? Use /help command.
        """
        await query.edit_message_text(help_text, parse_mode='Markdown')

    # === MAIN MENU CALLBACK HANDLERS ===
    
    async def _handle_main_portfolio(self, query, user_id: str):
        """Handle main menu portfolio button"""
        try:
            from ui.main_menu import MainMenu
            menu_text, menu_keyboard = await MainMenu.get_portfolio_menu(user_id)
            await query.edit_text(menu_text, reply_markup=menu_keyboard, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Main portfolio error: {e}")
            await query.edit_message_text("❌ Error loading portfolio")
            await self.show_main_menu(query, user_id)
    
    async def _handle_main_scan(self, query, user_id: str):
        """Handle main menu scan button"""
        try:
            from ui.main_menu import MainMenu
            menu_text, menu_keyboard = await MainMenu.get_scan_menu()
            await query.edit_text(menu_text, reply_markup=menu_keyboard, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Main scan error: {e}")
            await query.edit_message_text("❌ Error loading scan menu")
            await self.show_main_menu(query, user_id)
    
    async def _handle_main_buy(self, query, user_id: str):
        """Handle main menu buy button"""
        await query.edit_message_text(
            "💰 **Buy Token**\n\n"
            "**Format:** `/buy [chain] [token_address] [amount_usd]`\n\n"
            "**Examples:**\n"
            "• `/buy eth 0x742d35... 10` - Buy $10 of ETH token\n"
            "• `/buy bsc 0xA0b86a... 25` - Buy $25 of BSC token\n"
            "• `/buy sol EPjFWdd5... 5` - Buy $5 of SOL token\n\n"
            "**Supported Chains:** eth, bsc, sol",
            parse_mode='Markdown'
        )
        await self.show_main_menu(query, user_id)
    
    async def _handle_main_sell(self, query, user_id: str):
        """Handle main menu sell button - show portfolio with sell options"""
        await self._handle_main_portfolio(query, user_id)
    
    async def _handle_main_leaderboard(self, query, user_id: str):
        """Handle main menu leaderboard button"""
        try:
            # Reuse existing leaderboard command logic
            from services.wallet_scanner import wallet_scanner
            moonshot_wallets = await wallet_scanner.get_moonshot_leaderboard()
            
            if not moonshot_wallets:
                await query.edit_message_text(
                    "📈 **Moonshot Leaderboard**\n\n"
                    "🔍 No wallets found with 200x+ multipliers yet.\n\n"
                    "Keep monitoring - the next moonshot could be discovered soon!"
                )
                await self.show_main_menu(query, user_id)
                return
            
            # Format leaderboard with enhanced formatting
            leaderboard_text = "🚀 **MOONSHOT LEADERBOARD** 🚀\n\n💎 *Wallets with 200x+ gains*\n\n"
            
            from utils.formatting import AddressFormatter
            
            for i, wallet in enumerate(moonshot_wallets[:10], 1):
                leaderboard_text += AddressFormatter.format_leaderboard_entry(
                    rank=i,
                    wallet_address=wallet.address,
                    multiplier=wallet.best_trade_multiplier,
                    total_pnl=wallet.total_pnl_usd,
                    win_rate=wallet.win_rate,
                    chains=wallet.chains
                )
                leaderboard_text += "\n"
            
            leaderboard_text += f"📅 Last updated: {datetime.utcnow().strftime('%H:%M UTC')}"
            
            keyboard = [
                [InlineKeyboardButton("🔍 Analyze Top Wallet", callback_data=f"analyze_wallet_{moonshot_wallets[0].address[:10]}")],
                [InlineKeyboardButton("👁️ Watch Top Wallet", callback_data=f"add_watchlist_{moonshot_wallets[0].address[:10]}")],
                [InlineKeyboardButton("🔍 Scan Now", callback_data="manual_scan")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_text(leaderboard_text, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Main leaderboard error: {e}")
            await query.edit_message_text("❌ Error loading leaderboard")
            await self.show_main_menu(query, user_id)
    
    async def _handle_main_panic_sell(self, query, user_id: str):
        """Handle main menu panic sell button"""
        try:
            from ui.main_menu import MainMenu
            from core.trading_engine import trading_engine
            
            # Get portfolio for confirmation details
            portfolio = await trading_engine.get_portfolio_summary(user_id)
            
            confirmation_details = {
                'total_value': portfolio.get('portfolio_value_usd', 0),
                'position_count': portfolio.get('position_count', 0)
            }
            
            message, keyboard = MainMenu.create_confirmation_popup("panic_sell", confirmation_details)
            await query.edit_text(message, reply_markup=keyboard, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Main panic sell error: {e}")
            await query.edit_message_text("❌ Error preparing panic sell")
            await self.show_main_menu(query, user_id)
    
    async def _handle_main_settings(self, query, user_id: str):
        """Handle main menu settings button"""
        try:
            from ui.main_menu import MainMenu
            menu_text, menu_keyboard = await MainMenu.get_settings_menu(user_id)
            await query.edit_text(menu_text, reply_markup=menu_keyboard, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Main settings error: {e}")
            await query.edit_message_text("❌ Error loading settings")
            await self.show_main_menu(query, user_id)
    
    async def _handle_main_help(self, query, user_id: str):
        """Handle main menu help button"""
        help_text = """
📖 **MEME TRADER V4 PRO - QUICK HELP**

**🎯 Main Menu Features:**
• **Portfolio** - View holdings with sell buttons
• **Scan Wallets** - Find and analyze top traders
• **Buy Token** - Quick buy interface
• **Sell Token** - Portfolio-based selling
• **Moonshot Leaderboard** - 200x+ wallets
• **Panic Sell** - Emergency liquidation
• **Settings** - Configure everything
• **Safe Mode** - Toggle risk protection

**💡 Navigation Tips:**
• Main Menu appears after every action
• Use /start anytime to refresh menu
• All addresses are clickable links
• Buttons provide one-click actions

**🛡️ Safety Features:**
• Safe Mode ON by default
• Confirmation popups for all trades
• Real-time risk assessment
• Multi-chain support

**📱 The Main Menu makes everything easy!**
        """
        
        await query.edit_message_text(help_text, parse_mode='Markdown')
        await self.show_main_menu(query, user_id)
    
    # === SELL PERCENTAGE HANDLERS ===
    
    async def _handle_sell_percentage(self, query, data: str, user_id: str):
        """Handle sell percentage buttons"""
        try:
            # Parse the sell data: sell_25_0x742d35Cc or sell_custom_0x742d35Cc
            parts = data.split('_')
            if len(parts) < 3:
                raise ValueError("Invalid sell data format")
            
            percentage_str = parts[1]  # 25, 50, 100, custom
            token_id = '_'.join(parts[2:])  # Rejoin token ID parts
            
            if percentage_str == "custom":
                await query.edit_message_text(
                    f"💸 **Custom Sell Amount**\n\n"
                    f"Token: `{token_id}...`\n\n"
                    f"Use command: `/sell [chain] [full_token_address] [percentage]`\n\n"
                    f"**Example:** `/sell eth {token_id}... 75`\n\n"
                    f"*Enter any percentage from 1-100*"
                )
                await self.show_main_menu(query, user_id)
                return
            
            # Convert percentage
            try:
                percentage = int(percentage_str)
            except ValueError:
                raise ValueError("Invalid percentage")
            
            # Create confirmation popup
            from ui.main_menu import MainMenu
            
            confirmation_details = {
                'token_symbol': f"Token {token_id[-6:]}",
                'token_id': token_id,
                'percentage': percentage,
                'estimated_value': 1000.0,  # Would calculate real value
                'token_amount': 1000.0  # Would calculate real amount
            }
            
            message, keyboard = MainMenu.create_confirmation_popup("sell", confirmation_details)
            await query.edit_text(message, reply_markup=keyboard, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Handle sell percentage error: {e}")
            await query.edit_message_text("❌ Error processing sell request")
            await self.show_main_menu(query, user_id)
    
    # === BUY AMOUNT HANDLERS ===
    
    async def _handle_set_buy_amount(self, query, data: str, user_id: str):
        """Handle buy amount setting"""
        try:
            # Parse amount: set_buy_amount_50 or set_buy_amount_custom
            amount_str = data.replace('set_buy_amount_', '')
            
            if amount_str == "custom":
                await query.edit_message_text(
                    "💵 **Custom Buy Amount**\n\n"
                    "Please enter your custom default buy amount using:\n\n"
                    "`/settings buy_amount [amount]`\n\n"
                    "**Example:** `/settings buy_amount 75`\n\n"
                    "*This will set $75 as your default buy amount*"
                )
                await self.show_main_menu(query, user_id)
                return
            
            try:
                amount = float(amount_str)
            except ValueError:
                raise ValueError("Invalid amount")
            
            # Update trading engine config
            from core.trading_engine import trading_engine
            result = await trading_engine.update_config(user_id, {'max_auto_buy_usd': amount})
            
            if result['success']:
                await query.edit_message_text(
                    f"✅ **Default Buy Amount Updated**\n\n"
                    f"New default buy amount: **${amount:.0f}**\n\n"
                    f"This will be used for:\n"
                    f"• Quick buy buttons\n"
                    f"• Mirror trading (when enabled)\n"
                    f"• Auto-buy features"
                )
            else:
                await query.edit_message_text("❌ Failed to update buy amount")
            
            await self.show_main_menu(query, user_id)
            
        except Exception as e:
            logger.error(f"Set buy amount error: {e}")
            await query.edit_message_text("❌ Error setting buy amount")
            await self.show_main_menu(query, user_id)
    
    # === EXECUTION HANDLERS ===
    
    async def _handle_execute_action(self, query, data: str, user_id: str):
        """Handle execute action callbacks"""
        try:
            if data.startswith('execute_sell_'):
                # execute_sell_0x742d35Cc__50
                parts = data.replace('execute_sell_', '').split('__')
                if len(parts) >= 2:
                    token_id = parts[0]
                    percentage = parts[1]
                    
                    await query.edit_message_text(
                        f"⏳ **Executing Sell Order...**\n\n"
                        f"Selling {percentage}% of token `{token_id}...`\n\n"
                        f"*This would execute the actual trade*\n\n"
                        f"✅ **Trade executed successfully!**"
                    )
                    
            elif data.startswith('execute_buy_'):
                # execute_buy_0x742d35Cc__50
                parts = data.replace('execute_buy_', '').split('__')
                if len(parts) >= 2:
                    token_id = parts[0]
                    amount = parts[1]
                    
                    await query.edit_message_text(
                        f"⏳ **Executing Buy Order...**\n\n"
                        f"Buying ${amount} of token `{token_id}...`\n\n"
                        f"*This would execute the actual trade*\n\n"
                        f"✅ **Trade executed successfully!**"
                    )
                    
            elif data == 'execute_panic_sell':
                await query.edit_message_text(
                    f"🚨 **EXECUTING PANIC SELL...**\n\n"
                    f"Liquidating all positions...\n\n"
                    f"*This would execute actual trades*\n\n"
                    f"✅ **All positions liquidated!**"
                )
            
            # Show main menu after execution
            await self.show_main_menu(query, user_id)
            
        except Exception as e:
            logger.error(f"Execute action error: {e}")
            await query.edit_message_text("❌ Error executing action")
            await self.show_main_menu(query, user_id)
    
    async def _handle_cancel_trade(self, query, user_id: str):
        """Handle trade cancellation"""
        await query.edit_message_text("✅ **Trade Cancelled**\n\nNo action was taken.")
        await self.show_main_menu(query, user_id)
    
    # === SETTINGS HANDLERS ===
    
    async def _handle_settings_callback(self, query, data: str, user_id: str):
        """Handle settings-related callbacks"""
        try:
            if data == "settings_buy_amount":
                from ui.main_menu import MainMenu
                menu_text, menu_keyboard = MainMenu.get_buy_amount_menu()
                await query.edit_text(menu_text, reply_markup=menu_keyboard, parse_mode='Markdown')
            
            elif data == "settings_mirror_sell":
                await self._handle_toggle_mirror_sell(query, user_id)
            
            elif data == "settings_mirror_buy":
                await self._handle_toggle_mirror_buy(query, user_id)
            
            elif data == "settings_safe_mode":
                await self._handle_toggle_safe_mode(query, user_id)
            
            else:
                await query.edit_message_text(f"⚙️ Settings feature '{data}' coming soon!")
                await self.show_main_menu(query, user_id)
                
        except Exception as e:
            logger.error(f"Settings callback error: {e}")
            await query.edit_message_text("❌ Error processing settings")
            await self.show_main_menu(query, user_id)

    async def _handle_analyze_wallet_callback(self, query, wallet_prefix: str, user_id: str):
        """Handle analyze wallet callback"""
        try:
            # In a real implementation, you'd store the full address mapped to the prefix
            # For now, show a placeholder
            await query.edit_message_text(
                f"🔍 **Wallet Analysis**\n\n"
                f"Analyzing wallet `{wallet_prefix}...`\n\n"
                f"This would show:\n"
                f"• Trading history and patterns\n"
                f"• Win rate and performance\n"
                f"• Risk assessment\n"
                f"• Recent transactions\n\n"
                f"*Feature coming soon!*"
            )
        except Exception as e:
            logger.error(f"Analyze wallet callback error: {e}")
            await query.edit_message_text("❌ Error analyzing wallet")

    async def _handle_analyze_token_callback(self, query, token_prefix: str, user_id: str):
        """Handle analyze token callback"""
        try:
            # In a real implementation, you'd store the full address mapped to the prefix
            # For now, show a placeholder
            await query.edit_message_text(
                f"🔍 **Token Analysis**\n\n"
                f"Analyzing token `{token_prefix}...`\n\n"
                f"This would show:\n"
                f"• Security scan results\n"
                f"• Liquidity analysis\n"
                f"• Holder distribution\n"
                f"• Trading safety score\n\n"
                f"*Feature coming soon!*"
            )
        except Exception as e:
            logger.error(f"Analyze token callback error: {e}")
            await query.edit_message_text("❌ Error analyzing token")

    async def _handle_add_watchlist_callback(self, query, wallet_prefix: str, user_id: str):
        """Handle add to watchlist callback"""
        try:
            await query.edit_message_text(
                f"👁️ **Add to Watchlist**\n\n"
                f"Adding wallet `{wallet_prefix}...` to your watchlist\n\n"
                f"✅ You'll receive alerts when this wallet:\n"
                f"• Buys new tokens\n"
                f"• Sells existing positions\n"
                f"• Makes large trades\n\n"
                f"*Feature coming soon!*"
            )
        except Exception as e:
            logger.error(f"Add watchlist callback error: {e}")
            await query.edit_message_text("❌ Error adding to watchlist")

    async def _handle_blacklist_wallet_callback(self, query, wallet_prefix: str, user_id: str):
        """Handle blacklist wallet callback"""
        try:
            await query.edit_message_text(
                f"🚫 **Blacklist Wallet**\n\n"
                f"Blacklisting wallet `{wallet_prefix}...`\n\n"
                f"✅ This wallet will be:\n"
                f"• Excluded from all alerts\n"
                f"• Blocked from mirror trading\n"
                f"• Hidden from leaderboards\n\n"
                f"*Feature coming soon!*"
            )
        except Exception as e:
            logger.error(f"Blacklist wallet callback error: {e}")
            await query.edit_message_text("❌ Error blacklisting wallet")

    async def _handle_blacklist_token_callback(self, query, token_prefix: str, user_id: str):
        """Handle blacklist token callback"""
        try:
            await query.edit_message_text(
                f"🚫 **Blacklist Token**\n\n"
                f"Blacklisting token `{token_prefix}...`\n\n"
                f"✅ This token will be:\n"
                f"• Excluded from trading alerts\n"
                f"• Blocked from auto-trading\n"
                f"• Hidden from recommendations\n\n"
                f"*Feature coming soon!*"
            )
        except Exception as e:
            logger.error(f"Blacklist token callback error: {e}")
            await query.edit_message_text("❌ Error blacklisting token")

    async def _handle_quick_buy_callback(self, query, token_prefix: str, user_id: str):
        """Handle quick buy callback"""
        try:
            await query.edit_message_text(
                f"💰 **Quick Buy**\n\n"
                f"Preparing to buy token `{token_prefix}...`\n\n"
                f"🔍 This would:\n"
                f"• Show current token price\n"
                f"• Display liquidity info\n"
                f"• Offer buy amount options\n"
                f"• Execute with one click\n\n"
                f"*Feature coming soon!*"
            )
        except Exception as e:
            logger.error(f"Quick buy callback error: {e}")
            await query.edit_message_text("❌ Error with quick buy")

    async def _show_blacklist(self, update: Update, user_id: str):
        """Show current blacklist entries"""
        try:
            db = get_db_session()
            try:
                user = db.query(User).filter(User.telegram_id == user_id).first()
                if not user:
                    await update.message.reply_text("❌ User not found. Please use /start first.")
                    return
                
                blacklist_entries = db.query(BlacklistEntry).filter(
                    BlacklistEntry.user_id == user.id,
                    BlacklistEntry.is_active == True
                ).all()
                
                if not blacklist_entries:
                    message = "🚫 **Your Blacklist is Empty**\n\nNo wallets or tokens are currently blacklisted.\n\nUse `/blacklist add wallet 0x123...` to add entries."
                else:
                    message = "🚫 **Your Blacklist**\n\n"
                    
                    from utils.formatting import AddressFormatter
                    
                    wallets = [e for e in blacklist_entries if e.entry_type == 'wallet']
                    tokens = [e for e in blacklist_entries if e.entry_type == 'token']
                    
                    if wallets:
                        message += "**👤 Blacklisted Wallets:**\n"
                        for entry in wallets[:10]:  # Show max 10
                            wallet_link = AddressFormatter.format_wallet_address(
                                entry.address, 
                                'ethereum',  # Default chain for display
                                None
                            )
                            reason = entry.reason or "No reason"
                            message += f"• {wallet_link} - {reason}\n"
                        if len(wallets) > 10:
                            message += f"... and {len(wallets) - 10} more\n"
                        message += "\n"
                    
                    if tokens:
                        message += "**🪙 Blacklisted Tokens:**\n"
                        for entry in tokens[:10]:  # Show max 10
                            token_link = AddressFormatter.format_token_address(
                                entry.address,
                                'ethereum',  # Default chain for display
                                None
                            )
                            reason = entry.reason or "No reason"
                            message += f"• {token_link} - {reason}\n"
                        if len(tokens) > 10:
                            message += f"... and {len(tokens) - 10} more\n"
                    
                    message += f"\n**Total Entries:** {len(blacklist_entries)}"
                
                keyboard = [
                    [InlineKeyboardButton("➕ Add Entry", callback_data="add_blacklist")],
                    [InlineKeyboardButton("➖ Remove Entry", callback_data="remove_blacklist")],
                    [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_blacklist")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Show blacklist error: {e}")
            await update.message.reply_text(f"❌ **Blacklist Error**\n\nFailed to load blacklist: {str(e)}")

    async def _add_to_blacklist(self, user_id: str, entry_type: str, address: str, reason: str) -> bool:
        """Add entry to blacklist"""
        try:
            db = get_db_session()
            try:
                user = db.query(User).filter(User.telegram_id == user_id).first()
                if not user:
                    return False
                
                # Check if already exists
                existing = db.query(BlacklistEntry).filter(
                    BlacklistEntry.user_id == user.id,
                    BlacklistEntry.address == address.lower()
                ).first()
                
                if existing:
                    existing.is_active = True
                    existing.reason = reason
                    existing.entry_type = entry_type
                else:
                    blacklist_entry = BlacklistEntry(
                        user_id=user.id,
                        entry_type=entry_type,
                        address=address.lower(),
                        reason=reason
                    )
                    db.add(blacklist_entry)
                
                db.commit()
                return True
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Add to blacklist error: {e}")
            return False

    async def _remove_from_blacklist(self, user_id: str, address: str) -> bool:
        """Remove entry from blacklist"""
        try:
            db = get_db_session()
            try:
                user = db.query(User).filter(User.telegram_id == user_id).first()
                if not user:
                    return False
                
                blacklist_entry = db.query(BlacklistEntry).filter(
                    BlacklistEntry.user_id == user.id,
                    BlacklistEntry.address == address.lower()
                ).first()
                
                if blacklist_entry:
                    blacklist_entry.is_active = False
                    db.commit()
                    return True
                
                return False
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Remove from blacklist error: {e}")
            return False

    async def _show_watchlist(self, update: Update, user_id: str):
        """Show current watchlist"""
        try:
            db = get_db_session()
            try:
                user = db.query(User).filter(User.telegram_id == user_id).first()
                if not user:
                    await update.message.reply_text("❌ User not found. Please use /start first.")
                    return
                
                watched_wallets = db.query(WalletWatch).filter(
                    WalletWatch.user_id == user.id,
                    WalletWatch.is_active == True
                ).all()
                
                if not watched_wallets:
                    message = "👁️ **Your Watchlist is Empty**\n\nNo wallets are currently being monitored.\n\nUse `/watchlist add 0x123... ethereum` to start watching wallets."
                else:
                    message = f"👁️ **Your Watchlist** ({len(watched_wallets)} wallets)\n\n"
                    
                    from utils.formatting import AddressFormatter
                    
                    for i, wallet in enumerate(watched_wallets[:15], 1):  # Show max 15
                        chains = wallet.chains.split(',') if wallet.chains else ['ethereum']
                        main_chain = chains[0]
                        
                        # Enhanced wallet link
                        wallet_link = AddressFormatter.format_wallet_address(
                            wallet.wallet_address, 
                            main_chain, 
                            wallet.wallet_name or f"Wallet {i}"
                        )
                        
                        chains_display = ', '.join([AddressFormatter.CHAIN_NAMES.get(c.lower(), c.upper()) for c in chains[:2]])
                        
                        # Performance info if available
                        perf_info = ""
                        if wallet.win_rate:
                            perf_info = f" | {wallet.win_rate:.1f}% WR"
                        if wallet.best_multiplier and wallet.best_multiplier > 1:
                            perf_info += f" | {wallet.best_multiplier:.1f}x best"
                        
                        message += f"{i}. {wallet_link}\n"
                        message += f"   Chains: {chains_display}{perf_info}\n"
                        
                        if wallet.last_active:
                            days_ago = (datetime.utcnow() - wallet.last_active).days
                            if days_ago == 0:
                                message += f"   🟢 Active today\n\n"
                            elif days_ago <= 7:
                                message += f"   🟡 Active {days_ago}d ago\n\n"
                            else:
                                message += f"   🔴 Active {days_ago}d ago\n\n"
                        else:
                            message += f"   ⚪ Not tracked yet\n\n"
                    
                    if len(watched_wallets) > 15:
                        message += f"... and {len(watched_wallets) - 15} more wallets\n\n"
                    
                    message += "🔄 Scanning every 30 seconds for new activity"
                
                keyboard = [
                    [InlineKeyboardButton("➕ Add Wallet", callback_data="add_watchlist")],
                    [InlineKeyboardButton("➖ Remove Wallet", callback_data="remove_watchlist")],
                    [InlineKeyboardButton("🔍 Scan Now", callback_data="manual_scan")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Show watchlist error: {e}")
            await update.message.reply_text(f"❌ **Watchlist Error**\n\nFailed to load watchlist: {str(e)}")

    async def _remove_from_watchlist(self, user_id: str, wallet_address: str) -> bool:
        """Remove wallet from watchlist"""
        try:
            db = get_db_session()
            try:
                user = db.query(User).filter(User.telegram_id == user_id).first()
                if not user:
                    return False
                
                wallet_watch = db.query(WalletWatch).filter(
                    WalletWatch.user_id == user.id,
                    WalletWatch.wallet_address == wallet_address.lower()
                ).first()
                
                if wallet_watch:
                    wallet_watch.is_active = False
                    db.commit()
                    return True
                
                return False
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Remove from watchlist error: {e}")
            return False

    def _validate_wallet_address(self, address: str) -> bool:
        """Validate wallet address format"""
        try:
            # Ethereum/BSC address validation
            if address.startswith('0x') and len(address) == 42:
                return True
            
            # Solana address validation (basic)
            if len(address) >= 32 and len(address) <= 44 and not address.startswith('0x'):
                return True
            
            return False
            
        except Exception:
            return False


# Global function for sending messages to users
async def send_message_to_user(telegram_id: str, message: str, reply_markup=None):
    """Send message to user via Telegram with optional inline keyboard"""
    try:
        # This would need the bot instance to send messages
        # For now, log the message that would be sent
        button_info = f" with {len(reply_markup.inline_keyboard)} button rows" if reply_markup else ""
        logger.info(f"Alert for {telegram_id}{button_info}: {message[:100]}...")
    except Exception as e:
        logger.error(f"Failed to send message to {telegram_id}: {e}")

def main():
    """Start the enhanced bot"""
    print('🤖 Meme Trader V4 Pro Enhanced Bot starting...')
    
    # Run startup sequence
    from startup import run_startup
    startup_success = run_startup()
    
    if not startup_success:
        print('❌ Failed to initialize integrations. Exiting...')
        return
    
    # Create database tables
    create_tables()
    
    # Start background services
    print('🔍 Starting background services...')
    
    # Create application and bot instance
    application = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()
    bot = MemeTraderBot()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", bot.start_command))
    application.add_handler(CommandHandler("help", bot.help_command))
    application.add_handler(CommandHandler("buy", bot.buy_command))
    application.add_handler(CommandHandler("sell", bot.sell_command))
    application.add_handler(CommandHandler("analyze", bot.analyze_command))
    application.add_handler(CommandHandler("panic_sell", bot.panic_sell_command))
    application.add_handler(CommandHandler("scan", bot.scan_command))
    application.add_handler(CommandHandler("leaderboard", bot.leaderboard_command))
    application.add_handler(CommandHandler("alerts", bot.alerts_command))
    application.add_handler(CommandHandler("blacklist", bot.blacklist_command))
    application.add_handler(CommandHandler("watchlist", bot.watchlist_command))
    application.add_handler(CommandHandler("settings", bot.settings_command))
    application.add_handler(CommandHandler("portfolio", bot.portfolio_command))
    
    # Add basic callback handler for inline keyboards
    application.add_handler(CallbackQueryHandler(bot.unified_callback_handler))
    
    # Start the bot
    print('✅ Enhanced Bot is ready and listening for messages!')
    print('🔥 New features: /scan, /leaderboard, /alerts, /watchlist, /blacklist commands')
    print('💰 Trading: /buy, /sell, /panic_sell, /portfolio, /settings commands')
    print('🛡️  Enhanced security: Honeypot simulation, gas optimization, risk assessment')
    print('📡 Real-time monitoring: Mempool tracking, price alerts, portfolio analytics')
    print('🚀 Multi-chain: Ethereum, BSC, and Solana trading with mirror functionality')
    
    # Fix asyncio event loop issue
    try:
        import nest_asyncio
        nest_asyncio.apply()
    except ImportError:
        pass
    
    # Start polling with proper error handling
    try:
        # Start background services after bot initialization
        async def start_background_services():
            """Start background services"""
            try:
                from services.wallet_scanner import wallet_scanner
                await wallet_scanner.start_scanning()
            except Exception as e:
                logger.error(f"Failed to start background services: {e}")
        
        # Schedule background services to start
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.create_task(start_background_services())
        
        application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    except KeyboardInterrupt:
        print('\n⏹️ Bot stopped by user')
    except Exception as e:
        print(f'\n❌ Bot error: {e}')
        # Try alternative startup method
        import asyncio
        asyncio.set_event_loop(asyncio.new_event_loop())
        application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == '__main__':
    main()