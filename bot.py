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
        """Handle /start command"""
        user = update.effective_user
        chat_id = update.effective_chat.id
        
        # Save user to database
        db = get_db_session()
        try:
            existing_user = db.query(User).filter(User.telegram_id == str(user.id)).first()
            if not existing_user:
                new_user = User(
                    telegram_id=str(user.id),
                    username=user.username,
                    first_name=user.first_name,
                    last_name=user.last_name
                )
                db.add(new_user)
                db.commit()
                logger.info(f"New user registered: {user.username} ({user.id})")
        finally:
            db.close()
        
        welcome_message = f"""
🚀 **Welcome to Meme Trader V4 Pro Enhanced!** 

Hello {user.first_name}! Your advanced cryptocurrency trading assistant is ready.

**🔥 Enhanced Features:**
• Real-time mempool monitoring & early alerts
• Advanced honeypot detection with simulation
• AI-powered market analysis & trade execution
• Multi-chain support (ETH/BSC testnet)
• Smart trade execution with gas optimization
• Enhanced portfolio tracking & risk management

**📋 Available Commands:**
/help - Show all commands
/buy - Execute buy orders with pre-trade analysis
/sell - Execute sell orders with profit/loss tracking
/analyze - Advanced token analysis with honeypot detection
/scan - Manual wallet scanning across chains
/leaderboard - View moonshot wallet leaderboard
/watchlist - Manage watched wallets
/alerts - Configure alert settings
/blacklist - Manage blacklisted wallets/tokens
/portfolio - Advanced portfolio analytics
/settings - Trading & risk management settings

**⚠️ Enhanced Testnet Mode**
Running on Ethereum Sepolia & BSC testnet with full mempool monitoring.

**🔒 Security Features:**
• Secure keystore management
• Pre-trade honeypot simulation
• Gas optimization & slippage protection
• Real-time risk assessment

Ready to trade smarter and safer? 📈🔒
        """
        
        keyboard = [
            [InlineKeyboardButton("💰 Buy Token", callback_data="buy_token")],
            [InlineKeyboardButton("💸 Sell Token", callback_data="sell_token")],
            [InlineKeyboardButton("🔍 Analyze Token", callback_data="analyze_token")],
            [InlineKeyboardButton("👛 Manage Wallets", callback_data="manage_wallets")],
            [InlineKeyboardButton("📊 Portfolio", callback_data="view_portfolio")],
            [InlineKeyboardButton("❓ Help", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(welcome_message, reply_markup=reply_markup, parse_mode='Markdown')

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = """
🔧 **Meme Trader V4 Pro Enhanced Commands**

**💰 Trading Commands:**
/buy [chain] [token_address] [amount_usd] - Execute buy order
• Example: `/buy eth 0x742d35... 10`
• Supports: eth (Sepolia), bsc (BSC Testnet)
• Pre-trade honeypot check & gas estimation

/sell [chain] [token_address] [percentage] - Execute sell order  
• Example: `/sell eth 0x742d35... 50`
• Percentage of holdings to sell (1-100)
• Profit/loss calculation & tax optimization

**🔍 Analysis & Monitoring:**
/analyze [token_address] - Advanced token analysis
• Comprehensive honeypot detection
• AI-powered risk assessment
• Real-time liquidity & volume analysis
• Trading safety score (0-10)

/scan - Manual wallet scan across all chains
• Scan all watched wallets for new transactions
• Get real-time trading signals and alerts
• Monitor moonshot opportunities

/leaderboard - View moonshot wallet leaderboard
• Top wallets with 200x+ gains
• Performance metrics and win rates
• Copy trading opportunities

**👁️ Wallet & Alert Management:**
/watchlist - Manage watched wallets
• Add/remove wallets to monitor
• Multi-chain wallet tracking
• Real-time activity alerts

/alerts - Configure alert settings
• Set minimum trade size filters
• Enable/disable alert types
• Chain-specific monitoring

/blacklist - Manage blacklisted wallets/tokens
• Block suspicious wallets from alerts
• Filter out honeypot tokens
• Custom filtering rules

**📈 Portfolio & Analytics:**
/portfolio - Advanced portfolio analytics
• Real-time P&L tracking
• Performance metrics & charts
• Risk assessment & diversification
• AI-powered optimization suggestions

**⚙️ Settings & Configuration:**
/settings - Trading & risk management
• Gas settings & slippage tolerance
• Risk limits & position sizing
• Alert preferences & thresholds
• Security & backup settings

**🔥 Pro Features:**
• Multi-wallet automated strategies
• AI-guided trade execution
• Advanced market sentiment analysis
• Mempool monitoring & early alerts
• Moonshot wallet discovery

**💡 Command Examples:**
• Buy: `/buy eth 0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b 5`
• Sell: `/sell eth 0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b 25`
• Analyze: `/analyze 0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b`
• Watch wallet: `/watchlist add 0x742d35... ethereum,bsc WhaleWallet`
• Configure alerts: `/alerts`

**🚨 Safety First:**
All trades include pre-execution checks:
✅ Honeypot detection & simulation
✅ Liquidity depth verification
✅ Gas optimization & estimation
✅ Slippage protection
✅ Risk assessment scoring

Need specific help? Just ask! 🤖
        """
        await update.message.reply_text(help_text, parse_mode='Markdown')

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
            
            for i, wallet in enumerate(moonshot_wallets[:10], 1):
                # Medal emojis for top 3
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                
                # Format multiplier
                multiplier_str = f"{wallet.best_trade_multiplier:.0f}x" if wallet.best_trade_multiplier >= 10 else f"{wallet.best_trade_multiplier:.1f}x"
                
                # Format PnL
                pnl_str = f"${wallet.total_pnl_usd/1000000:.1f}M" if wallet.total_pnl_usd >= 1000000 else f"${wallet.total_pnl_usd/1000:.0f}K"
                
                # Wallet display
                wallet_display = f"{wallet.address[:6]}...{wallet.address[-4:]}"
                
                leaderboard_text += f"{medal} **{wallet_display}**\n"
                leaderboard_text += f"   💰 Best: {multiplier_str} | Total: {pnl_str}\n"
                leaderboard_text += f"   📊 Win Rate: {wallet.win_rate:.1f}% | Trades: {wallet.total_trades}\n"
                leaderboard_text += f"   🔗 Chains: {', '.join(wallet.chains[:2])}\n\n"
            
            leaderboard_text += f"📅 Last updated: {datetime.utcnow().strftime('%H:%M UTC')}\n"
            leaderboard_text += "🔄 Updates every 30 seconds with new discoveries"
            
            keyboard = [
                [InlineKeyboardButton("👁️ Watch Top Wallet", callback_data=f"watch_wallet_{moonshot_wallets[0].address}")],
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
            
            if positions:
                for i, pos in enumerate(positions[:5]):  # Show top 5 positions
                    token_symbol = pos.get('token_symbol', 'UNKNOWN')
                    pnl_pct = pos.get('pnl_percentage', 0)
                    pnl_usd = pos.get('pnl_usd', 0)
                    current_value = pos.get('current_value_usd', 0)
                    
                    pnl_emoji = "🟢" if pnl_usd >= 0 else "🔴"
                    pnl_sign = "+" if pnl_usd >= 0 else ""
                    
                    portfolio_message += f"\n{i+1}. **{token_symbol}**"
                    portfolio_message += f"\n   Value: ${current_value:,.2f}"
                    portfolio_message += f"\n   P&L: {pnl_emoji} {pnl_sign}${pnl_usd:,.2f} ({pnl_sign}{pnl_pct:.1f}%)"
                
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
                    
                    wallets = [e for e in blacklist_entries if e.entry_type == 'wallet']
                    tokens = [e for e in blacklist_entries if e.entry_type == 'token']
                    
                    if wallets:
                        message += "**👤 Blacklisted Wallets:**\n"
                        for entry in wallets[:10]:  # Show max 10
                            address_display = f"{entry.address[:8]}...{entry.address[-6:]}"
                            reason = entry.reason or "No reason"
                            message += f"• `{address_display}` - {reason}\n"
                        if len(wallets) > 10:
                            message += f"... and {len(wallets) - 10} more\n"
                        message += "\n"
                    
                    if tokens:
                        message += "**🪙 Blacklisted Tokens:**\n"
                        for entry in tokens[:10]:  # Show max 10
                            address_display = f"{entry.address[:8]}...{entry.address[-6:]}"
                            reason = entry.reason or "No reason"
                            message += f"• `{address_display}` - {reason}\n"
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
                    
                    for i, wallet in enumerate(watched_wallets[:15], 1):  # Show max 15
                        address_display = f"{wallet.wallet_address[:8]}...{wallet.wallet_address[-6:]}"
                        chains = wallet.chains.split(',') if wallet.chains else ['ethereum']
                        chains_display = ', '.join([c.upper() for c in chains[:2]])
                        
                        name = wallet.wallet_name or "Unnamed"
                        
                        # Performance info if available
                        perf_info = ""
                        if wallet.win_rate:
                            perf_info = f" | {wallet.win_rate:.1f}% WR"
                        if wallet.best_multiplier and wallet.best_multiplier > 1:
                            perf_info += f" | {wallet.best_multiplier:.1f}x best"
                        
                        message += f"{i}. **{name}**\n"
                        message += f"   `{address_display}` | {chains_display}{perf_info}\n"
                        
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
async def send_message_to_user(telegram_id: str, message: str):
    """Send message to user via Telegram"""
    try:
        # This would need the bot instance to send messages
        # For now, log the message that would be sent
        logger.info(f"Alert for {telegram_id}: {message[:100]}...")
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