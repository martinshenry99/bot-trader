#!/usr/bin/env python3
"""
Quick Start Bot - Bypasses lengthy startup for immediate testing
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
    """Quick start the enhanced bot"""
    print('🚀 Meme Trader V4 Pro - Quick Start Mode')
    print('⚡ Bypassing lengthy API health checks for immediate testing...')
    
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
    
    print('✅ Meme Trader V4 Pro - READY FOR TESTING!')
    print('')
    print('🎯 Available Commands:')
    print('   /start          - Welcome & overview')
    print('   /help           - Complete documentation')
    print('   /scan           - Manual wallet scan')
    print('   /leaderboard    - Moonshot wallets (200x+)')
    print('   /alerts         - Configure alert settings')
    print('   /blacklist      - Manage blocked wallets/tokens')
    print('   /watchlist      - Monitor specific wallets')
    print('   /buy            - Multi-chain token buying')
    print('   /sell           - Smart token selling')
    print('   /portfolio      - Real-time portfolio')
    print('   /settings       - Trading configuration')
    print('   /panic_sell     - Emergency liquidation')
    print('   /analyze        - Token security analysis')
    print('')
    print('🔥 Enhanced Features Ready:')
    print('   ✅ Multi-chain: ETH, BSC, Solana')
    print('   ✅ Mirror trading (sell ON, buy OFF)')
    print('   ✅ Real-time wallet scanning')
    print('   ✅ USD portfolio tracking')
    print('   ✅ Advanced risk management')
    print('   ✅ Token selection interface')
    print('   ✅ Moonshot leaderboard')
    print('')
    print('📱 Bot is now listening for Telegram messages!')
    
    # Start polling
    try:
        application.run_polling(drop_pending_updates=True)
    except KeyboardInterrupt:
        print('\n⏹️ Bot stopped by user')
    except Exception as e:
        print(f'\n❌ Bot error: {e}')

if __name__ == '__main__':
    main()