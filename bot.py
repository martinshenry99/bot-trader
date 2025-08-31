import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from config import Config
from db import create_tables, get_db_session, User, Wallet, Token, Trade
from monitor import TokenMonitor, WalletMonitor
from analyzer import TokenAnalyzer
from executor import TradeExecutor

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class MemeTraderBot:
    def __init__(self):
        Config.validate()
        self.token_monitor = TokenMonitor()
        self.wallet_monitor = WalletMonitor()
        self.analyzer = TokenAnalyzer()
        self.executor = TradeExecutor()
        
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
🚀 **Welcome to Meme Trader V4 Pro!** 

Hello {user.first_name}! I'm your advanced cryptocurrency trading assistant.

**🔥 Key Features:**
• Real-time wallet & token monitoring
• AI-powered market analysis
• Automated honeypot detection
• Smart trade execution on Ethereum (Testnet)
• Multi-wallet management

**📋 Available Commands:**
/help - Show all commands
/wallet - Manage your wallets
/monitor - Start/stop monitoring
/analyze - Analyze tokens
/trade - Execute trades
/portfolio - View portfolio
/settings - Bot settings

**⚠️ Testnet Mode Active**
Currently running on Ethereum Sepolia testnet for safe testing.

Ready to start trading smarter? 📈
        """
        
        keyboard = [
            [InlineKeyboardButton("📱 Add Wallet", callback_data="add_wallet")],
            [InlineKeyboardButton("📊 Monitor Tokens", callback_data="monitor_tokens")],
            [InlineKeyboardButton("🔍 Analyze Token", callback_data="analyze_token")],
            [InlineKeyboardButton("❓ Help", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(welcome_message, reply_markup=reply_markup, parse_mode='Markdown')

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = """
🔧 **Meme Trader V4 Pro Commands**

**👛 Wallet Management:**
/wallet - Manage wallets
• Add new wallet
• View wallet balances
• Import/Export wallets

**📊 Monitoring:**
/monitor - Token/wallet monitoring
• Start monitoring tokens
• Set price alerts
• View active monitors

**🔍 Analysis:**
/analyze [token_address] - Analyze token
• Get AI-powered score
• Honeypot detection
• Market sentiment analysis

**💱 Trading:**
/trade - Execute trades
• Buy/sell tokens
• Set slippage tolerance
• View trade history

**📈 Portfolio:**
/portfolio - View portfolio
• Current holdings
• P&L analysis
• Performance metrics

**⚙️ Settings:**
/settings - Bot configuration
• Notification preferences
• Trading parameters
• Security settings

**💡 Pro Tips:**
• Use testnet for safe experimentation
• Always verify token contracts
• Set appropriate slippage (1-5%)
• Monitor gas fees before trading

Need specific help? Just ask! 🤖
        """
        await update.message.reply_text(help_text, parse_mode='Markdown')

    async def wallet_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /wallet command"""
        keyboard = [
            [InlineKeyboardButton("➕ Add Wallet", callback_data="add_wallet")],
            [InlineKeyboardButton("👀 View Wallets", callback_data="view_wallets")],
            [InlineKeyboardButton("🔄 Import Wallet", callback_data="import_wallet")],
            [InlineKeyboardButton("⚙️ Wallet Settings", callback_data="wallet_settings")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "👛 **Wallet Management**\n\nChoose an option:", 
            reply_markup=reply_markup, 
            parse_mode='Markdown'
        )

    async def monitor_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /monitor command"""
        keyboard = [
            [InlineKeyboardButton("🚀 Start Token Monitor", callback_data="start_token_monitor")],
            [InlineKeyboardButton("👛 Start Wallet Monitor", callback_data="start_wallet_monitor")],
            [InlineKeyboardButton("⏹️ Stop Monitoring", callback_data="stop_monitoring")],
            [InlineKeyboardButton("📊 View Active Monitors", callback_data="view_monitors")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "📊 **Monitoring Center**\n\nChoose monitoring option:", 
            reply_markup=reply_markup, 
            parse_mode='Markdown'
        )

    async def analyze_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /analyze command"""
        if len(context.args) == 0:
            await update.message.reply_text(
                "🔍 **Token Analysis**\n\n"
                "Please provide a token address to analyze:\n"
                "`/analyze 0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b`\n\n"
                "Or use the button below:", 
                parse_mode='Markdown'
            )
            keyboard = [[InlineKeyboardButton("🔍 Analyze Token", callback_data="analyze_token")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Choose option:", reply_markup=reply_markup)
            return
        
        token_address = context.args[0]
        await update.message.reply_text(f"🔄 Analyzing token: `{token_address}`\n\nPlease wait...", parse_mode='Markdown')
        
        try:
            analysis = await self.analyzer.analyze_token(token_address)
            
            analysis_text = f"""
🔍 **Token Analysis Results**

**Token:** {analysis.get('name', 'Unknown')} ({analysis.get('symbol', 'N/A')})
**Address:** `{token_address}`

**📊 Market Data:**
• Price: ${analysis.get('price_usd', 0):.6f}
• Market Cap: ${analysis.get('market_cap', 0):,.2f}
• Liquidity: ${analysis.get('liquidity_usd', 0):,.2f}
• 24h Volume: ${analysis.get('volume_24h', 0):,.2f}

**🤖 AI Analysis:**
• AI Score: {analysis.get('ai_score', 0):.2f}/10
• Sentiment: {analysis.get('sentiment_score', 0):.2f}
• Honeypot Risk: {'🔴 HIGH' if analysis.get('is_honeypot') else '🟢 LOW'}

**📈 Recommendation:**
{analysis.get('recommendation', 'Analysis incomplete')}
            """
            
            await update.message.reply_text(analysis_text, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Analysis error: {e}")
            await update.message.reply_text(f"❌ Analysis failed: {str(e)}")

    async def trade_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /trade command"""
        keyboard = [
            [InlineKeyboardButton("🟢 Buy Token", callback_data="buy_token")],
            [InlineKeyboardButton("🔴 Sell Token", callback_data="sell_token")],
            [InlineKeyboardButton("📊 Trade History", callback_data="trade_history")],
            [InlineKeyboardButton("⚙️ Trade Settings", callback_data="trade_settings")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "💱 **Trading Center**\n\n⚠️ **Testnet Mode Active**\nAll trades execute on Ethereum Sepolia testnet\n\nChoose trading option:", 
            reply_markup=reply_markup, 
            parse_mode='Markdown'
        )

    async def portfolio_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /portfolio command"""
        user_id = str(update.effective_user.id)
        
        try:
            portfolio = await self.get_user_portfolio(user_id)
            
            if not portfolio['wallets']:
                await update.message.reply_text(
                    "📈 **Your Portfolio**\n\n"
                    "No wallets found. Add a wallet to view your portfolio.\n\n"
                    "Use /wallet to get started!"
                )
                return
            
            portfolio_text = f"""
📈 **Your Portfolio**

**💰 Total Value:** ${portfolio['total_value_usd']:.2f}
**📊 Total Tokens:** {portfolio['total_tokens']}
**👛 Active Wallets:** {len(portfolio['wallets'])}

**🏆 Top Holdings:**
"""
            
            for holding in portfolio['top_holdings'][:5]:
                portfolio_text += f"• {holding['symbol']}: ${holding['value_usd']:.2f}\n"
            
            keyboard = [
                [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_portfolio")],
                [InlineKeyboardButton("📊 Detailed View", callback_data="detailed_portfolio")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(portfolio_text, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Portfolio error: {e}")
            await update.message.reply_text("❌ Failed to load portfolio. Please try again.")

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard button presses"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "add_wallet":
            await query.edit_message_text(
                "👛 **Add New Wallet**\n\n"
                "Please send your wallet address or private key.\n\n"
                "⚠️ **Security Note:** Private keys are encrypted and stored securely.\n\n"
                "**Format:**\n"
                "• Address: `0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b`\n"
                "• Private Key: `0x...` (for trading functionality)\n\n"
                "Send it in the next message:", 
                parse_mode='Markdown'
            )
        
        elif query.data == "analyze_token":
            await query.edit_message_text(
                "🔍 **Token Analysis**\n\n"
                "Please send the token contract address you want to analyze.\n\n"
                "**Example:**\n"
                "`0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b`\n\n"
                "Send the address in the next message:",
                parse_mode='Markdown'
            )
        
        elif query.data == "help":
            await self.help_command(update, context)
        
        else:
            await query.edit_message_text(f"🚧 Feature '{query.data}' coming soon!\n\nStay tuned for updates! 🚀")

    async def get_user_portfolio(self, user_id: str):
        """Get user portfolio summary"""
        # Placeholder implementation
        return {
            'total_value_usd': 0.0,
            'total_tokens': 0,
            'wallets': [],
            'top_holdings': []
        }

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        logger.error(f"Update {update} caused error {context.error}")

def main():
    """Start the bot"""
    print('🤖 Meme Trader V4 Pro Bot starting...')
    
    # Create database tables
    create_tables()
    
    # Create application and bot instance
    application = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()
    bot = MemeTraderBot()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", bot.start_command))
    application.add_handler(CommandHandler("help", bot.help_command))
    application.add_handler(CommandHandler("wallet", bot.wallet_command))
    application.add_handler(CommandHandler("monitor", bot.monitor_command))
    application.add_handler(CommandHandler("analyze", bot.analyze_command))
    application.add_handler(CommandHandler("trade", bot.trade_command))
    application.add_handler(CommandHandler("portfolio", bot.portfolio_command))
    
    # Add callback handler for inline keyboards
    application.add_handler(CallbackQueryHandler(bot.button_handler))
    
    # Add error handler
    application.add_error_handler(bot.error_handler)
    
    # Start the bot
    print('✅ Bot is ready and listening for messages!')
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()