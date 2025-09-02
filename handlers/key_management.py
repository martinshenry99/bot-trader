
"""
API Key Management Handlers
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils.key_manager import key_manager
from utils.formatting import format_api_key_stats

logger = logging.getLogger(__name__)


async def handle_keys_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /keys command - show key management menu"""
    try:
        keyboard = [
            [
                InlineKeyboardButton("📊 View Stats", callback_data="keys_stats"),
                InlineKeyboardButton("➕ Add Key", callback_data="keys_add")
            ],
            [
                InlineKeyboardButton("🗑️ Remove Key", callback_data="keys_remove"),
                InlineKeyboardButton("🔄 Force Rotation", callback_data="keys_rotate")
            ],
            [
                InlineKeyboardButton("🏥 Health Check", callback_data="keys_health"),
                InlineKeyboardButton("🔙 Back", callback_data="main_menu")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🔑 **API Key Management**\n\n"
            "Manage API keys for all integrated services:\n"
            "• Covalent (Blockchain data)\n"
            "• Ethereum/Alchemy (EVM chains)\n" 
            "• BSC (Binance Smart Chain)\n"
            "• Solana/Helius (Solana network)\n\n"
            "Choose an option below:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Keys command failed: {e}")
        await update.message.reply_text("❌ Failed to load key management menu")


async def handle_rotation_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /rotation_stats command"""
    try:
        stats = key_manager.get_key_stats()
        health = await key_manager.health_check()
        
        message = "📊 **API Key Rotation Statistics**\n\n"
        
        for service, service_stats in stats.items():
            status_emoji = "🟢" if service_stats['health'] == 'good' else "🔴"
            message += f"{status_emoji} **{service.upper()}**\n"
            message += f"   • Active Keys: {service_stats['active_keys']}/{service_stats['total_keys']}\n"
            message += f"   • Daily Usage: {service_stats['daily_usage']:,}\n"
            message += f"   • Monthly Usage: {service_stats['monthly_usage']:,}\n\n"
        
        message += f"⏰ **Next Reset:** {health.get('ethereum', {}).get('next_reset', 'Unknown')[:10]}"
        
        await update.message.reply_text(message, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Rotation stats failed: {e}")
        await update.message.reply_text("❌ Failed to get rotation statistics")


async def handle_keys_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle key management callbacks"""
    try:
        query = update.callback_query
        await query.answer()
        
        action = query.data.split('_', 1)[1]  # Remove 'keys_' prefix
        
        if action == 'stats':
            await _show_detailed_stats(query)
        elif action == 'health':
            await _show_health_status(query)
        elif action == 'rotate':
            await _force_key_rotation(query)
        else:
            await query.edit_message_text("❌ Unknown action")
            
    except Exception as e:
        logger.error(f"Key callback handling failed: {e}")


async def _show_detailed_stats(query):
    """Show detailed API key statistics"""
    try:
        stats = key_manager.get_key_stats()
        
        message = "📊 **Detailed API Key Statistics**\n\n"
        
        for service, data in stats.items():
            status = "🟢 Healthy" if data['health'] == 'good' else "🔴 Critical"
            message += f"**{service.upper()}:** {status}\n"
            message += f"├── Active: {data['active_keys']}/{data['total_keys']} keys\n"
            message += f"├── Daily: {data['daily_usage']:,} requests\n"
            message += f"└── Monthly: {data['monthly_usage']:,} requests\n\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="keys_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Failed to show detailed stats: {e}")


async def _show_health_status(query):
    """Show API health status"""
    try:
        health = await key_manager.health_check()
        
        message = "🏥 **API Health Status**\n\n"
        
        for service, status in health.items():
            emoji = "🟢" if status['status'] == 'healthy' else "🔴"
            message += f"{emoji} **{service.upper()}:** {status['status']}\n"
            message += f"   Available: {status['available_keys']}/{status['total_keys']}\n\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="keys_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Failed to show health status: {e}")


async def _force_key_rotation(query):
    """Force rotation of all API keys"""
    try:
        # Force rotation by advancing indices
        for service in key_manager.current_indices:
            key_manager.current_indices[service] = (key_manager.current_indices[service] + 1) % max(1, len(key_manager.keys[service]))
        
        await query.edit_message_text(
            "🔄 **Key Rotation Completed**\n\n"
            "All API services have been rotated to next available keys.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="keys_menu")]])
        )
        
    except Exception as e:
        logger.error(f"Force rotation failed: {e}")
        await query.edit_message_text("❌ Key rotation failed")
