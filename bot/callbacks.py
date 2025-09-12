def get_env_mnemonic():
    """Get wallet mnemonic from environment or config"""
    mnemonic = os.getenv('WALLET_MNEMONIC') or os.getenv('MNEMONIC')
    return mnemonic

async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle settings management callbacks"""
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    session = get_session()
    try:
        await query.answer()
        # settings:<action>:<key>:<value>
        parts = data.split(":")
        if len(parts) < 2:
            await query.edit_message_text("Invalid settings request.")
            return
        action = parts[1]
        key = parts[2] if len(parts) > 2 else None
        value = parts[3] if len(parts) > 3 else None
        
        if action == "list":
            rows = session.query(Settings).filter_by(user_id=user_id).all()
            if not rows:
                await query.edit_message_text("No settings found.")
                return
            msg = "\n".join([f"{r.key}: {r.value}" for r in rows])
            await query.edit_message_text(f"Your settings:\n{msg}")
        elif action == "get" and key:
            row = session.query(Settings).filter_by(user_id=user_id, key=key).first()
            await query.edit_message_text(f"Setting '{key}': {row.value if row else 'Not set'}")
        elif action == "set" and key and value:
            row = session.query(Settings).filter_by(user_id=user_id, key=key).first()
            if row:
                row.value = value
            else:
                row = Settings(user_id=user_id, key=key, value=value)
                session.add(row)
            session.commit()
            await query.edit_message_text(f"Set '{key}' to '{value}'")
        elif action == "delete" and key:
            row = session.query(Settings).filter_by(user_id=user_id, key=key).first()
            if row:
                session.delete(row)
                session.commit()
                await query.edit_message_text(f"Deleted setting '{key}'")
            else:
                await query.edit_message_text(f"Setting '{key}' not found.")
        else:
            await query.edit_message_text("Invalid settings action or missing key/value.")
    
        # Show menu button after action
        keyboard = [
            [InlineKeyboardButton("🔄 Back to Settings", callback_data="settings:list")]
        ]
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
        
    except Exception as e:
        logger.error(f"Settings callback error: {e}")
        await query.edit_message_text("❌ Settings action failed. Please try again.")
import os
from config import Config
def get_env_mnemonic():
    # Prefer WALLET_MNEMONIC, fallback to MNEMONIC
    return os.getenv('WALLET_MNEMONIC') or os.getenv('MNEMONIC') or getattr(Config, 'MNEMONIC', None)

async def mnemonic_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle mnemonic management callbacks"""
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    try:
        await query.answer()
        
        # Get current mnemonic state
        mnemonic = get_env_mnemonic()
        
        # Parse action from data (mnemonic:<action>)
        parts = data.split(":")
        if len(parts) < 2:
            await query.edit_message_text("❌ Invalid mnemonic action")
            return
            
        action = parts[1]
        keyboard = None
        
        if action == "status":
            if mnemonic:
                masked = f"{mnemonic[:8]}...{mnemonic[-8:]}"
                msg = (
                    f"🔐 Wallet Status\n\n"
                    f"✅ Mnemonic is configured\n"
                    f"🔑 Masked value: `{masked}`\n\n"
                    f"Use /mnemonic export to view full value"
                )
                keyboard = [[
                    InlineKeyboardButton("🔍 View Full", callback_data="mnemonic:export"),
                    InlineKeyboardButton("🗑 Delete", callback_data="mnemonic:delete")
                ]]
            else:
                msg = (
                    "❌ No wallet mnemonic configured\n\n"
                    "Please set WALLET_MNEMONIC in your .env file\n"
                    "Or use /mnemonic generate to create new"
                )
                keyboard = [[InlineKeyboardButton("🆕 Generate New", callback_data="mnemonic:generate")]]
                
        elif action == "generate":
            msg = (
                "🔐 Generate New Mnemonic\n\n"
                "For security, please use:\n"
                "`python secure_import.py generate`\n\n"
                "This will:\n"
                "• Generate a secure mnemonic\n"
                "• Encrypt and store it\n"
                "• Set up your wallet addresses"
            )
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="mnemonic:status")]]
            
        elif action == "export":
            if not mnemonic:
                msg = "❌ No mnemonic configured"
                keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="mnemonic:status")]]
            else:
                msg = (
                    "🔐 Wallet Mnemonic\n\n"
                    f"`{mnemonic}`\n\n"
                    "⚠️ WARNING:\n"
                    "• Keep this safe\n"
                    "• Never share it\n"
                    "• Store securely"
                )
                keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="mnemonic:status")]]
                
        elif action == "delete":
            msg = (
                "🚨 Delete Mnemonic\n\n"
                "For security, please:\n"
                "1. Backup your mnemonic first\n"
                "2. Remove WALLET_MNEMONIC from .env\n"
                "3. Restart the bot\n\n"
                "❌ Direct deletion via bot is disabled"
            )
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="mnemonic:status")]]
            
        else:
            msg = "❌ Unknown mnemonic action"
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="mnemonic:status")]]
            
        # Send response with keyboard if present
        await query.edit_message_text(
            msg, 
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
        )
            
    except Exception as e:
        logger.error(f"Mnemonic callback error: {e}")
        await query.edit_message_text(
            "❌ Mnemonic action failed. Please try again.", 
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 Retry", callback_data="mnemonic:status")
            ]])
        )
"""
Callback handler implementations for Meme Trader V4 Pro
"""

"""
Callback handler implementations for Meme Trader V4 Pro
"""

import asyncio
import logging
import json
import os
from datetime import datetime
from typing import Optional, Dict, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, Application, CallbackQueryHandler
from config import Config
from db.models import get_session, Settings, Watchlist, Portfolio, Trade
from utils.key_manager import get_mnemonic
from utils.formatters import format_analysis_result, format_balance, format_portfolio
from utils.security import is_admin, mask_sensitive_data
from services.analyzer import analyze_token, get_token_price
from services.executor import execute_trade
from services.scanner import validate_token

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)

async def buy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle buy token callbacks"""
    query = update.callback_query
    
    try:
        # Acknowledge callback
        await query.answer()
        
        # Parse callback data (buy:<action>:<chain>:<address>)
        parts = query.data.split(":")
        if len(parts) < 4:
            await query.edit_message_text("Invalid buy request. Expected format: buy:action:chain:address")
            return
            
        action = parts[1]
        chain = parts[2] 
        address = parts[3]
        
        # Handle buy preview
        if action == "preview":
            logger.info(f"Getting trade preview for {address} on {chain}")
            preview = await get_trade_preview(chain, address)
            if not preview:
                msg = "❌ Could not get trade preview. Please check:\n- Token liquidity\n- Price impact\n- Gas fees"
                keyboard = [[
                    InlineKeyboardButton("🔄 Try Again", callback_data=f"buy:preview:{chain}:{address}"),
                    InlineKeyboardButton("❌ Cancel", callback_data=f"analyze:{chain}:{address}")
                ]]
                await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
                return
                
            # Format preview details
            msg = format_trade_preview(preview)
            keyboard = [
                [
                    InlineKeyboardButton("✅ Confirm Buy", callback_data=f"buy:confirm:{chain}:{address}"),
                    InlineKeyboardButton("❌ Cancel", callback_data=f"analyze:{chain}:{address}")
                ],
                [InlineKeyboardButton("⚙️ Adjust Settings", callback_data=f"buy:settings:{chain}:{address}")]
            ]
            await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
            
        # Handle buy confirmation
        elif action == "confirm":
            logger.info(f"Executing trade for {address} on {chain}")
            result = await execute_trade(chain, address)
            
            if result.get("success"):
                msg = (
                    "✅ Trade Successfully Executed!\n\n"
                    f"Chain: {chain}\n"
                    f"Token: {address}\n"
                    f"Amount: {result.get('amount')}\n"
                    f"Price: {result.get('price')}\n"
                    f"TX Hash: {result['tx_hash']}"
                )
                keyboard = [
                    [InlineKeyboardButton("🔍 View Transaction", url=result.get('explorer_url'))],
                    [InlineKeyboardButton("🔄 New Analysis", callback_data=f"analyze:{chain}:{address}")]
                ]
            else:
                error_msg = result.get('error', 'Unknown error')
                msg = (
                    f"❌ Trade Failed\n\n"
                    f"Error: {error_msg}\n\n"
                    "Common issues:\n"
                    "• Insufficient balance\n"
                    "• High price impact\n"
                    "• Network congestion"
                )
                keyboard = [
                    [
                        InlineKeyboardButton("🔄 Try Again", callback_data=f"buy:preview:{chain}:{address}"),
                        InlineKeyboardButton("❌ Cancel", callback_data=f"analyze:{chain}:{address}")
                    ]
                ]
            await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
            
        # Handle buy settings
        elif action == "settings":
            msg = (
                "⚙️ Trade Settings\n\n"
                "• Slippage: 0.5%\n"
                "• Gas Priority: Medium\n"
                "• Auto-approve: Yes"
            )
            keyboard = [
                [
                    InlineKeyboardButton("� Slippage", callback_data=f"buy:slippage:{chain}:{address}"),
                    InlineKeyboardButton("⛽ Gas", callback_data=f"buy:gas:{chain}:{address}")
                ],
                [InlineKeyboardButton("🔙 Back to Preview", callback_data=f"buy:preview:{chain}:{address}")]
            ]
            await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
    
    except Exception as e:
        logger.error(f"Buy callback error: {str(e)}")
        # Provide retry option
        keyboard = [[
            InlineKeyboardButton("🔄 Retry", callback_data=query.data),
            InlineKeyboardButton("❌ Cancel", callback_data=f"analyze:{chain}:{address}")
        ]]
        await query.edit_message_text(
            "❌ Trade action failed. Please try again.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def watchlist_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle watchlist callbacks"""
    query = update.callback_query
    
    try:
        # Acknowledge callback
        await query.answer()
        
        # Parse callback data (watch:<action>:<chain>:<address>)
        parts = query.data.split(":")
        if len(parts) < 4:
            await query.edit_message_text("Invalid watchlist request. Expected format: watch:action:chain:address")
            return
            
        action = parts[1]
        chain = parts[2]
        address = parts[3]
        
        session = get_session()
        user_id = query.from_user.id
        
        # Handle adding token to watchlist
        if action == "add":
            logger.info(f"Adding {address} on {chain} to watchlist for user {user_id}")
            
            # Check if already in watchlist
            existing = session.query(Watchlist).filter_by(
                user_id=user_id,
                chain=chain,
                address=address,
                active=True
            ).first()
            
            if existing:
                msg = "⚠️ Token is already in your watchlist!"
            else:
                # Add new entry
                item = Watchlist(
                    user_id=user_id,
                    chain=chain,
                    address=address,
                    active=True,
                    created_at=datetime.utcnow()
                )
                session.add(item)
                session.commit()
                msg = f"✅ Added to Watchlist:\n• Chain: {chain}\n• Token: {address}"
            
            keyboard = [
                [InlineKeyboardButton("📋 View Watchlist", callback_data=f"watch:list:{chain}:{address}")],
                [InlineKeyboardButton("🔄 Back to Analysis", callback_data=f"analyze:{chain}:{address}")]
            ]
            await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
            
        # Handle removing token from watchlist
        elif action == "remove":
            logger.info(f"Removing {address} on {chain} from watchlist for user {user_id}")
            
            # Find and deactivate entry
            item = session.query(Watchlist).filter_by(
                user_id=user_id,
                chain=chain,
                address=address,
                active=True
            ).first()
            
            if item:
                item.active = False
                session.commit()
                msg = f"✅ Removed from Watchlist:\n• Chain: {chain}\n• Token: {address}"
            else:
                msg = "⚠️ Token not found in your watchlist"
                
            keyboard = [
                [InlineKeyboardButton("📋 View Watchlist", callback_data=f"watch:list:{chain}:{address}")],
                [InlineKeyboardButton("🔄 Back to Analysis", callback_data=f"analyze:{chain}:{address}")]
            ]
            await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
            
        # Handle listing watchlist
        elif action == "list":
            logger.info(f"Listing watchlist for user {user_id}")
            items = session.query(Watchlist).filter_by(user_id=user_id, active=True).all()
            
            if not items:
                msg = (
                    "📋 Watchlist Empty\n\n"
                    "Use the 'Add to Watchlist' button when analyzing tokens to "
                    "track them here."
                )
                keyboard = [[InlineKeyboardButton("🔄 Back", callback_data=f"analyze:{chain}:{address}")]]
                await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
                return
                
            msg = "📋 Your Watchlist\n\n"
            keyboard = []
            
            # Build dynamic keyboard for each token
            for item in items:
                msg += f"• {item.chain}: {item.address}\n"
                keyboard.append([
                    InlineKeyboardButton("🔍 Analyze", callback_data=f"analyze:{item.chain}:{item.address}"),
                    InlineKeyboardButton("❌ Remove", callback_data=f"watch:remove:{item.chain}:{item.address}")
                ])
            
            # Add filter/sort options
            keyboard.append([
                InlineKeyboardButton("📊 Sort by Price", callback_data=f"watch:sort:price:{chain}:{address}"),
                InlineKeyboardButton("⏰ Sort by Age", callback_data=f"watch:sort:age:{chain}:{address}")
            ])
            keyboard.append([InlineKeyboardButton("🔄 Refresh List", callback_data=f"watch:list:{chain}:{address}")])
            
            await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
    
    except Exception as e:
        logger.error(f"Watchlist callback error: {str(e)}")
        keyboard = [[InlineKeyboardButton("🔄 Retry", callback_data=query.data)]]
        await query.edit_message_text(
            "❌ Watchlist action failed. Please try again.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def analyze_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle token analysis callbacks"""
    query = update.callback_query
    
    try:
        # Acknowledge callback
        await query.answer()
        
        # Parse callback data (analyze:<chain>:<address>)
        parts = query.data.split(":")
        if len(parts) < 3:
            await query.edit_message_text("Invalid analyze request. Expected format: analyze:chain:address")
            return
            
        chain = parts[1]
        address = parts[2]
        
        # Get analysis results
        logger.info(f"Analyzing token {address} on chain {chain}")
        analysis = await analyze_token(chain, address)
        if not analysis:
            msg = "❌ Analysis failed. This could mean:\n- Token is invalid\n- Chain is not supported\n- API error occurred"
            keyboard = [[InlineKeyboardButton("🔄 Retry", callback_data=f"analyze:{chain}:{address}")]]
            await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
            return
            
        # Format and display results
        msg = format_analysis_result(analysis)
        
        # Build keyboard with all available actions
        keyboard = [
            [
                InlineKeyboardButton("🛒 Buy Token", callback_data=f"buy:preview:{chain}:{address}"),
                InlineKeyboardButton("👀 Add to Watchlist", callback_data=f"watch:add:{chain}:{address}")
            ],
            [
                InlineKeyboardButton("🔄 Refresh Analysis", callback_data=f"analyze:{chain}:{address}"),
                InlineKeyboardButton("📊 Price Graph", callback_data=f"analyze:{chain}:{address}:graph")
            ]
        ]
        
        await query.edit_message_text(
            msg, 
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
    
    except Exception as e:
        logger.error(f"Analysis callback error: {e}")
        keyboard = [[InlineKeyboardButton("🔄 Retry", callback_data=query.data)]]
        await query.edit_message_text(
            "❌ Analysis failed. Please try again.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

def register_handlers(app: Application):
    """Register all callback handlers"""
    # Register all callback handlers with their patterns
    handlers = [
        (analyze_callback, "^analyze:"),
        (buy_callback, "^buy:"),
        (watchlist_callback, "^watch:"),
        (mnemonic_callback, "^mnemonic:"),
        (settings_callback, "^settings:")
    ]
    
    # Add each handler to the application
    for handler_func, pattern in handlers:
        try:
            app.add_handler(CallbackQueryHandler(handler_func, pattern=pattern))
            logger.info(f"Registered handler for pattern: {pattern}")
        except Exception as e:
            logger.error(f"Failed to register handler for {pattern}: {e}")
            
    logger.info(f"Successfully registered {len(handlers)} callback handlers")
