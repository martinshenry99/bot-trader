
"""
Mirror Trading Command Handlers
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from services.mirror_trading import mirror_trading_service
from db import get_db_session, WalletWatch

logger = logging.getLogger(__name__)


async def handle_mirror_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start mirror trading with watched wallets"""
    try:
        # Get watched wallets from database
        db = next(get_db_session())
        watched_wallets = db.query(WalletWatch).filter(
            WalletWatch.user_id == str(update.effective_user.id),
            WalletWatch.is_active == True
        ).all()
        
        if not watched_wallets:
            await update.message.reply_text(
                "❌ **No Watched Wallets**\n\n"
                "You need to add wallets to your watchlist first.\n"
                "Use /watchlist to add wallets.",
                parse_mode='Markdown'
            )
            return
        
        wallet_addresses = [w.wallet_address for w in watched_wallets]
        await mirror_trading_service.start_mirror_trading(wallet_addresses)
        
        await update.message.reply_text(
            f"🪞 **Mirror Trading Started**\n\n"
            f"Monitoring {len(wallet_addresses)} wallets for trading signals.\n\n"
            f"⚙️ **Current Settings:**\n"
            f"• Auto-sell: {'ON' if mirror_trading_service.settings.auto_sell_enabled else 'OFF'}\n"
            f"• Safe mode: {'ON' if mirror_trading_service.settings.safe_mode_enabled else 'OFF'}\n"
            f"• Max position: ${mirror_trading_service.settings.max_position_size_usd:,.0f}\n\n"
            f"Use /auto_sell to toggle auto-sell mode.",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Mirror start failed: {e}")
        await update.message.reply_text("❌ Failed to start mirror trading")
    finally:
        db.close()


async def handle_mirror_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop mirror trading"""
    try:
        await mirror_trading_service.stop_mirror_trading()
        
        await update.message.reply_text(
            "🛑 **Mirror Trading Stopped**\n\n"
            "All mirror trading monitoring has been disabled.\n"
            "Use /mirror_start to resume monitoring.",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Mirror stop failed: {e}")
        await update.message.reply_text("❌ Failed to stop mirror trading")


async def handle_auto_sell_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle auto-sell functionality"""
    try:
        args = context.args
        
        if args:
            setting = args[0].lower()
            if setting in ['on', 'true', '1']:
                mirror_trading_service.settings.auto_sell_enabled = True
                status = "ENABLED"
                emoji = "🟢"
            elif setting in ['off', 'false', '0']:
                mirror_trading_service.settings.auto_sell_enabled = False
                status = "DISABLED"
                emoji = "🔴"
            else:
                await update.message.reply_text(
                    "❌ Invalid option. Use: /auto_sell on or /auto_sell off"
                )
                return
        else:
            # Toggle current state
            mirror_trading_service.settings.auto_sell_enabled = not mirror_trading_service.settings.auto_sell_enabled
            status = "ENABLED" if mirror_trading_service.settings.auto_sell_enabled else "DISABLED"
            emoji = "🟢" if mirror_trading_service.settings.auto_sell_enabled else "🔴"
        
        await update.message.reply_text(
            f"{emoji} **Auto-Sell {status}**\n\n"
            f"When watched wallets sell tokens, your positions will be "
            f"{'automatically sold' if mirror_trading_service.settings.auto_sell_enabled else 'require manual confirmation'}.\n\n"
            f"⚠️ **Warning:** Auto-sell executes immediately without confirmation.",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Auto-sell toggle failed: {e}")
        await update.message.reply_text("❌ Failed to toggle auto-sell")
