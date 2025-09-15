"""
Metrics reporting and monitoring commands
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from monitor.metrics import metrics_manager

logger = logging.getLogger(__name__)

async def handle_metrics_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /metrics command"""
    try:
        keyboard = [
            [
                InlineKeyboardButton("System Health", callback_data="metrics_health"),
                InlineKeyboardButton("API Stats", callback_data="metrics_api")
            ],
            [
                InlineKeyboardButton("Trade Stats", callback_data="metrics_trades"),
                InlineKeyboardButton("Alert Stats", callback_data="metrics_alerts")
            ],
            [
                InlineKeyboardButton("Performance", callback_data="metrics_performance"),
                InlineKeyboardButton("🔙 Back", callback_data="main_menu")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "📊 **System Metrics**\n\n"
            "Choose a category to view detailed metrics:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Metrics command failed: {e}")
        await update.message.reply_text("❌ Failed to load metrics menu")

async def handle_metrics_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle metrics menu callbacks"""
    try:
        query = update.callback_query
        await query.answer()
        
        action = query.data.split('_')[1]
        
        if action == 'health':
            await show_system_health(query)
        elif action == 'api':
            await show_api_stats(query)
        elif action == 'trades':
            await show_trade_stats(query)
        elif action == 'alerts':
            await show_alert_stats(query)
        elif action == 'performance':
            await show_performance_stats(query)
        else:
            await query.edit_message_text("❌ Unknown metrics category")
            
    except Exception as e:
        logger.error(f"Metrics callback failed: {e}")

async def show_system_health(query):
    """Show system health summary"""
    try:
        summary = metrics_manager.get_system_summary()
        
        message = (
            "🏥 **System Health Overview**\n\n"
            f"🕒 Uptime: {summary['uptime']}\n"
            f"📨 Total Alerts: {summary['total_alerts']:,}\n"
            f"💰 Total Trades: {summary['total_trades']:,}\n\n"
            "**API Calls:**\n"
        )
        
        for service, calls in summary['api_calls'].items():
            message += f"• {service}: {calls:,}\n"
        
        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=get_metrics_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Failed to show system health: {e}")

async def show_api_stats(query):
    """Show API performance stats"""
    try:
        message = "📡 **API Performance**\n\n"
        
        for service in ['covalent', 'helius', 'goplus', 'coingecko']:
            health = metrics_manager.get_api_health(service)
            status = "🟢" if health['error_rate'] < 0.1 else "🔴"
            
            message += (
                f"{status} **{service.title()}**\n"
                f"• Error Rate: {health['error_rate']:.1%}\n"
                f"• Avg Latency: {health['avg_latency']:.2f}s\n"
                f"• Rate Limits: {health['rate_limits']}\n"
                f"• Quota Exceeded: {health['quota_exceeded']}\n\n"
            )
        
        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=get_metrics_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Failed to show API stats: {e}")

async def show_trade_stats(query):
    """Show trading statistics"""
    try:
        health = metrics_manager.get_trade_health()
        
        message = (
            "💰 **Trading Statistics**\n\n"
            f"Success Rate: {health['success_rate']:.1%}\n"
            f"Avg Execution: {health['avg_execution_time']:.2f}s\n"
            f"Avg Slippage: {health['avg_slippage']:.2%}\n"
            f"Preflight Blocks: {health['preflight_blocks']}\n\n"
            "**Recent Trades:**\n"
        )
        
        # Add recent trade summary
        for trade in metrics_manager.time_series['trades'][-5:]:
            status = "✅" if trade['success'] else "❌"
            message += (
                f"{status} {trade['type'].upper()} "
                f"({trade['execution_time']:.1f}s)\n"
            )
        
        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=get_metrics_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Failed to show trade stats: {e}")

async def show_alert_stats(query):
    """Show alert system statistics"""
    try:
        health = metrics_manager.get_alert_health()
        
        message = (
            "🔔 **Alert System Statistics**\n\n"
            f"Success Rate: {health['success_rate']:.1%}\n"
            f"Avg Latency: {health['avg_latency']:.2f}s\n"
            f"Consensus Alerts: {health['consensus_alerts']}\n"
            f"Duplicates Prevented: {health['duplicates_prevented']}\n\n"
            "**Recent Alerts:**\n"
        )
        
        # Add recent alert summary
        for alert in metrics_manager.time_series['alerts'][-5:]:
            status = "✅" if alert['success'] else "❌"
            message += (
                f"{status} Alert sent "
                f"({alert['latency']:.1f}s)\n"
            )
        
        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=get_metrics_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Failed to show alert stats: {e}")

async def show_performance_stats(query):
    """Show system performance metrics"""
    try:
        # Calculate performance metrics
        api_latencies = []
        for service in metrics_manager.time_series['api_calls'].values():
            api_latencies.extend(call['latency'] for call in service)
        
        avg_api_latency = sum(api_latencies) / len(api_latencies) if api_latencies else 0
        
        message = (
            "⚡ **Performance Metrics**\n\n"
            f"API Latency (avg): {avg_api_latency:.2f}s\n"
            f"Alert Latency (avg): {metrics_manager.alert_metrics.avg_latency:.2f}s\n"
            f"Trade Execution (avg): {metrics_manager.trade_metrics.avg_execution_time:.2f}s\n\n"
            "**System Load:**\n"
            "• API calls/min: calculating...\n"
            "• Alerts/min: calculating...\n"
            "• Memory usage: calculating...\n"
        )
        
        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=get_metrics_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Failed to show performance stats: {e}")

def get_metrics_keyboard() -> InlineKeyboardMarkup:
    """Get metrics menu keyboard"""
    keyboard = [
        [
            InlineKeyboardButton("System Health", callback_data="metrics_health"),
            InlineKeyboardButton("API Stats", callback_data="metrics_api")
        ],
        [
            InlineKeyboardButton("Trade Stats", callback_data="metrics_trades"),
            InlineKeyboardButton("Alert Stats", callback_data="metrics_alerts")
        ],
        [
            InlineKeyboardButton("Performance", callback_data="metrics_performance"),
            InlineKeyboardButton("🔙 Back", callback_data="main_menu")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)
