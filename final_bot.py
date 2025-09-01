#!/usr/bin/env python3
"""
Final Production Bot with Enhanced Main Menu System
"""

import logging
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from telegram import Update
from config import Config
from bot import MemeTraderBot
from db import create_tables

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    """Start the final enhanced bot"""
    print('🚀 MEME TRADER V4 PRO - FINAL PRODUCTION VERSION')
    print('=' * 60)
    print('✅ Enhanced Features Active:')
    print('  • Persistent Main Menu System')
    print('  • Clickable Address Formatting')  
    print('  • Portfolio with Sell Buttons')
    print('  • Confirmation Popups')
    print('  • Multi-chain Support (ETH, BSC, SOL)')
    print('  • Mirror Trading Controls')
    print('  • Advanced Risk Management')
    print('  • Real-time Portfolio Tracking')
    print('=' * 60)
    
    # Create database tables
    create_tables()
    
    # Create application and bot instance
    application = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()
    bot = MemeTraderBot()
    
    # Add all command handlers
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
    
    # Add callback handler
    application.add_handler(CallbackQueryHandler(bot.unified_callback_handler))
    
    print('\n🎯 READY FOR TESTING!')
    print('')
    print('📱 Main Menu Features:')
    print('  📊 Portfolio - View holdings with sell buttons')
    print('  🔍 Scan Wallets - Find and analyze top traders')
    print('  💰 Buy Token - Quick buy interface')  
    print('  💸 Sell Token - Portfolio-based selling')
    print('  📈 Moonshot Leaderboard - 200x+ wallets')
    print('  🚨 Panic Sell - Emergency liquidation')
    print('  ⚙️ Settings - Configure everything')
    print('  🛡️ Safe Mode - Toggle risk protection')
    print('')
    print('✨ Navigation:')
    print('  • Main Menu appears after every action')
    print('  • /start anytime to refresh menu')
    print('  • All addresses are clickable block explorer links')
    print('  • One-click actions for wallets and tokens')
    print('  • Confirmation popups for all trades')
    print('')
    print('🚀 Bot is now listening for Telegram messages!')
    print('📱 Send /start to your bot to see the enhanced interface')
    
    # Start polling
    try:
        application.run_polling(drop_pending_updates=True)
    except KeyboardInterrupt:
        print('\n⏹️ Bot stopped by user')
    except Exception as e:
        print(f'\n❌ Bot error: {e}')

if __name__ == '__main__':
    main()