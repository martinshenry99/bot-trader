"""
Settings handler for Meme Trader V4 Pro
"""

import logging
from typing import Optional, Dict, List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from db.models import get_db_manager
from settings.constants import SettingKeys, DEFAULT_SETTINGS, validate_setting

logger = logging.getLogger(__name__)

async def handle_settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /settings command"""
    
    if not update.message:
        return
        
    user_id = update.message.from_user.id
    args = context.args
    
    if not args:
        # Show settings menu
        await show_settings_menu(update, context)
        return
        
    command = args[0].lower()
    
    if command == "list":
        await list_settings(update, context)
        
    elif command == "get" and len(args) > 1:
        key = args[1]
        await get_setting(update, context, user_id, key)
        
    elif command == "set" and len(args) > 2:
        key = args[1]
        value = args[2]
        await set_setting(update, context, user_id, key, value)
        
    elif command == "reset":
        await reset_settings(update, context, user_id)
        
    else:
        await update.message.reply_text(
            "⚠️ Invalid command. Usage:\n"
            "/settings list - Show all settings\n"
            "/settings get <key> - Get setting value\n"
            "/settings set <key> <value> - Update setting\n"
            "/settings reset - Reset to defaults"
        )

async def show_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show settings management menu"""
    keyboard = [
        [InlineKeyboardButton("📋 List All Settings", callback_data="settings:list")],
        [
            InlineKeyboardButton("🔍 Scan Settings", callback_data="settings:category:scan"),
            InlineKeyboardButton("🔐 Insider Settings", callback_data="settings:category:insider")
        ],
        [InlineKeyboardButton("♻️ Reset All", callback_data="settings:reset:confirm")]
    ]
    
    await update.message.reply_text(
        "⚙️ Settings Management\n\n"
        "Configure scan thresholds, insider detection, and more.\n\n"
        "Choose an option:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def list_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all settings and their current values"""
    if not update.message:
        return
        
    user_id = update.message.from_user.id
    db = get_db_manager()
    
    # Get all user settings with defaults
    settings = get_all_settings(user_id)
    
    # Format settings by category
    scan_settings = []
    insider_settings = []
    
    for key, value in settings.items():
        if key.startswith('scan_'):
            scan_settings.append(f"• {key}: {value}")
        elif key.startswith('insider_'):
            insider_settings.append(f"• {key}: {value}")
    
    msg = (
        "⚙️ Your Settings\n\n"
        "🔍 Scan Settings:\n"
        f"{chr(10).join(scan_settings)}\n\n"
        "🔐 Insider Detection:\n"
        f"{chr(10).join(insider_settings)}"
    )
    
    keyboard = [[InlineKeyboardButton("✏️ Modify Settings", callback_data="settings:menu")]]
    
    await update.message.reply_text(
        msg,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def get_setting(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, key: str):
    """Get value of a specific setting"""
    db = get_db_manager()
    
    if key not in [e.value for e in SettingKeys]:
        await update.message.reply_text(f"❌ Invalid setting key: {key}")
        return
        
    value = db.get_user_setting(user_id, key, DEFAULT_SETTINGS.get(key))
    
    msg = f"⚙️ Setting: {key}\nCurrent value: {value}"
    keyboard = [[InlineKeyboardButton("✏️ Change", callback_data=f"settings:set:{key}")]]
    
    await update.message.reply_text(
        msg,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def set_setting(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, key: str, value: str):
    """Update a setting value"""
    if key not in [e.value for e in SettingKeys]:
        await update.message.reply_text(f"❌ Invalid setting key: {key}")
        return
        
    # Validate setting value
    if not validate_setting(key, value):
        await update.message.reply_text(
            "❌ Invalid value. Please check:\n"
            "• scan_min_score: 0-100\n"
            "• scan_max_results: 1-200\n"
            "• scan_chains: comma-separated list of eth,bsc,sol\n"
            "• insider_min_score: 0-100\n"
            "• insider_early_window_minutes: 1-60\n"
            "• insider_min_repeat: 1-10"
        )
        return
        
    db = get_db_manager()
    if db.set_user_setting(user_id, key, value):
        await update.message.reply_text(f"✅ Updated {key} to: {value}")
    else:
        await update.message.reply_text("❌ Failed to update setting")

async def reset_settings(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Reset all settings to defaults"""
    db = get_db_manager()
    success = True
    
    for key, value in DEFAULT_SETTINGS.items():
        if not db.set_user_setting(user_id, key, str(value)):
            success = False
            break
            
    if success:
        msg = "✅ All settings reset to defaults:\n\n"
        for key, value in DEFAULT_SETTINGS.items():
            msg += f"• {key}: {value}\n"
    else:
        msg = "❌ Failed to reset settings"
        
    await update.message.reply_text(msg)

def get_all_settings(user_id: int) -> Dict[str, str]:
    """Get all settings for a user with defaults"""
    db = get_db_manager()
    settings = {}
    
    for key in [e.value for e in SettingKeys]:
        value = db.get_user_setting(user_id, key, str(DEFAULT_SETTINGS.get(key)))
        settings[key] = value
        
    return settings
