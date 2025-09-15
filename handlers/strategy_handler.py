"""
Strategy command handlers
"""

import logging
from typing import Dict, List, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from services.strategy_manager import StrategyManager
from services.chain_manager import ChainManager
from handlers.key_management import KeyManager
from utils.formatting import format_usd, format_percentage

logger = logging.getLogger(__name__)

class StrategyCommandHandler:
    """Handler for strategy-related commands"""
    
    def __init__(
        self,
        strategy_manager: StrategyManager,
        chain_manager: ChainManager,
        key_manager: KeyManager
    ):
        self.strategy_manager = strategy_manager
        self.chain_manager = chain_manager
        self.key_manager = key_manager
        
    async def handle_strategy_list(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /strategy list command"""
        try:
            # Get available strategies
            strategies = await self.strategy_manager.list_strategies()
            
            # Format response
            response = "📊 Available Trading Strategies:\n\n"
            
            for strategy in strategies:
                response += f"*{strategy['name']}*\n"
                response += f"_{strategy['description']}_\n"
                response += "\nParameters:\n"
                
                for param, desc in strategy['parameters'].items():
                    response += f"• `{param}`: {desc}\n"
                    
                response += "\n"
                
            # Add apply instructions
            response += "\nTo apply a strategy:\n"
            response += "`/strategy apply <name> [params...]`\n\n"
            response += "Example:\n"
            response += "`/strategy apply conservative_buy "
            response += "max_risk_score=2 min_liquidity_locked_days=30`"
            
            # Add keyboard with quick apply buttons
            keyboard = []
            for strategy in strategies:
                keyboard.append([
                    InlineKeyboardButton(
                        f"Apply {strategy['name']}",
                        callback_data=f"strategy_apply_{strategy['name']}"
                    )
                ])
                
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                response,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Error in strategy list: {str(e)}")
            await update.message.reply_text(
                "❌ Error fetching strategy list. Please try again."
            )
            
    async def handle_strategy_apply(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /strategy apply command"""
        try:
            args = context.args
            if not args:
                await update.message.reply_text(
                    "❌ Please specify a strategy name and parameters.\n"
                    "Example: `/strategy apply conservative_buy "
                    "max_risk_score=2`",
                    parse_mode='Markdown'
                )
                return
                
            strategy_name = args[0].lower()
            
            # Parse parameters
            config = {}
            for arg in args[1:]:
                if '=' in arg:
                    key, value = arg.split('=', 1)
                    # Convert value types
                    if value.isdigit():
                        value = int(value)
                    elif value.replace('.', '').isdigit():
                        value = float(value)
                    elif value.lower() in ('true', 'false'):
                        value = value.lower() == 'true'
                    config[key] = value
                    
            # Add user ID to config
            user_id = update.effective_user.id
            config['user_id'] = user_id
            
            # Apply strategy
            result = await self.strategy_manager.apply_strategy(
                user_id,
                strategy_name,
                config
            )
            
            if result['status'] == 'applied':
                response = f"✅ Successfully applied {strategy_name} strategy!\n\n"
                
                # Add preview if available
                if 'preview' in result:
                    preview = result['preview']
                    response += "*Strategy Preview:*\n"
                    
                    if 'estimated_trades' in preview:
                        response += "\nEstimated trades per day: "
                        response += f"`{preview['estimated_trades']}`"
                        
                    if 'position_sizes' in preview:
                        response += "\nTypical position sizes: "
                        response += f"`{format_usd(preview['position_sizes'])}`"
                        
                    if 'risk_metrics' in preview:
                        response += "\nRisk metrics:\n"
                        for metric, value in preview['risk_metrics'].items():
                            response += f"• {metric}: `{value}`\n"
                            
                # Add control buttons
                keyboard = [
                    [
                        InlineKeyboardButton(
                            "🔄 Update Parameters",
                            callback_data=f"strategy_params_{strategy_name}"
                        ),
                        InlineKeyboardButton(
                            "▶️ Start Live",
                            callback_data=f"strategy_live_{strategy_name}"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "📊 View Performance",
                            callback_data=f"strategy_stats_{strategy_name}"
                        ),
                        InlineKeyboardButton(
                            "❌ Delete Strategy",
                            callback_data=f"strategy_delete_{strategy_name}"
                        )
                    ]
                ]
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    response,
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
                
            else:
                await update.message.reply_text(
                    "❌ Failed to apply strategy. Please check parameters."
                )
                
        except ValueError as ve:
            await update.message.reply_text(
                f"❌ Configuration error: {str(ve)}"
            )
        except Exception as e:
            logger.error(f"Error applying strategy: {str(e)}")
            await update.message.reply_text(
                "❌ Error applying strategy. Please try again."
            )
            
    async def handle_strategy_callback(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle strategy-related callback queries"""
        query = update.callback_query
        await query.answer()
        
        try:
            action, *params = query.data.split('_')
            
            if action == 'strategy':
                command = params[0]
                strategy_name = '_'.join(params[1:])
                
                if command == 'apply':
                    # Show parameter input form
                    await self._show_strategy_params(
                        query,
                        strategy_name
                    )
                elif command == 'params':
                    # Update strategy parameters
                    await self._update_strategy_params(
                        query,
                        strategy_name
                    )
                elif command == 'live':
                    # Start live trading
                    await self._start_live_trading(
                        query,
                        strategy_name
                    )
                elif command == 'stats':
                    # Show strategy stats
                    await self._show_strategy_stats(
                        query,
                        strategy_name
                    )
                elif command == 'delete':
                    # Delete strategy
                    await self._delete_strategy(
                        query,
                        strategy_name
                    )
                    
        except Exception as e:
            logger.error(f"Error in strategy callback: {str(e)}")
            await query.edit_message_text(
                "❌ Error processing request. Please try again."
            )
            
    async def _show_strategy_params(
        self,
        query: Update.callback_query,
        strategy_name: str
    ) -> None:
        """Show strategy parameter input form"""
        # Get strategy parameters
        strategies = await self.strategy_manager.list_strategies()
        strategy = next(
            (s for s in strategies if s['name'] == strategy_name),
            None
        )
        
        if not strategy:
            await query.edit_message_text(
                "❌ Strategy not found."
            )
            return
            
        # Create parameter form
        text = f"📝 Configure {strategy_name} Strategy\n\n"
        text += "*Required Parameters:*\n"
        
        for param, desc in strategy['parameters'].items():
            text += f"• `{param}`: {desc}\n"
            
        text += "\nSend parameters in format:\n"
        text += f"`/strategy apply {strategy_name} param1=value1 param2=value2`"
        
        # Add example configuration
        text += "\n\nExample configuration:\n"
        if strategy_name == 'mirror_sell':
            text += "`/strategy apply mirror_sell "
            text += "watched_wallets=['0x123','0x456'] "
            text += "slippage=0.01`"
        elif strategy_name == 'conservative_buy':
            text += "`/strategy apply conservative_buy "
            text += "max_risk_score=2 "
            text += "min_liquidity_locked_days=30 "
            text += "min_liquidity_amount=10000`"
        elif strategy_name == 'momentum_entry':
            text += "`/strategy apply momentum_entry "
            text += "min_watchers=3 "
            text += "consensus_threshold=0.7 "
            text += "time_window=24`"
            
        # Add preview option
        keyboard = [[
            InlineKeyboardButton(
                "👁️ Preview Strategy",
                callback_data=f"strategy_preview_{strategy_name}"
            ),
            InlineKeyboardButton(
                "📜 List Strategies",
                callback_data="strategy_list"
            )
        ]]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
    async def _update_strategy_params(
        self,
        query: Update.callback_query,
        strategy_name: str
    ) -> None:
        """Update strategy parameters"""
        # This will be handled through a conversation handler
        pass
        
    async def _start_live_trading(
        self,
        query: Update.callback_query,
        strategy_name: str
    ) -> None:
        """Start live trading with strategy"""
        user_id = query.from_user.id
        
        # Get user's strategy config
        strategy = await self.strategy_manager.get_user_strategy(
            user_id,
            strategy_name
        )
        
        if not strategy:
            await query.edit_message_text(
                "❌ Strategy not found. Please apply the strategy first."
            )
            return
            
        try:
            # Update config for live trading
            config = strategy.config
            config['dry_run'] = False
            
            # Reapply strategy with live config
            result = await self.strategy_manager.apply_strategy(
                user_id,
                strategy_name,
                config
            )
            
            text = "🚀 Strategy activated for live trading!\n\n"
            text += "*Initial Setup:*\n"
            text += f"• Strategy: `{strategy_name}`\n"
            text += f"• Mode: Live Trading\n"
            text += f"• Status: Active\n\n"
            
            # Add control buttons
            keyboard = [[
                InlineKeyboardButton(
                    "⏸️ Pause Strategy",
                    callback_data=f"strategy_pause_{strategy_name}"
                ),
                InlineKeyboardButton(
                    "📊 View Stats",
                    callback_data=f"strategy_stats_{strategy_name}"
                )
            ]]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Error starting live trading: {str(e)}")
            await query.edit_message_text(
                "❌ Error activating live trading. Please try again."
            )
            
    async def _show_strategy_stats(
        self,
        query: Update.callback_query,
        strategy_name: str
    ) -> None:
        """Show strategy performance stats"""
        user_id = query.from_user.id
        
        try:
            # Get strategy instance
            strategy = await self.strategy_manager.get_user_strategy(
                user_id,
                strategy_name
            )
            
            if not strategy:
                await query.edit_message_text(
                    "❌ Strategy not found. Please apply the strategy first."
                )
                return
                
            # Get performance stats
            stats = await strategy.get_stats()
            
            text = f"📈 {strategy_name} Performance\n\n"
            
            # Add general stats
            text += "*General Statistics:*\n"
            text += f"• Total Trades: `{stats['total_trades']}`\n"
            text += f"• Win Rate: `{format_percentage(stats['win_rate'])}`\n"
            text += f"• Avg ROI: `{format_percentage(stats['avg_roi'])}`\n"
            text += f"• Total Profit: `{format_usd(stats['total_profit'])}`\n\n"
            
            # Add recent trades
            text += "*Recent Trades:*\n"
            for trade in stats['recent_trades'][:5]:
                text += f"• {trade['token']}: "
                text += f"`{format_percentage(trade['roi'])} "
                text += f"({format_usd(trade['profit'])})`\n"
                
            # Add risk metrics
            text += "\n*Risk Metrics:*\n"
            text += f"• Max Drawdown: `{format_percentage(stats['max_drawdown'])}`\n"
            text += f"• Sharpe Ratio: `{stats['sharpe_ratio']:.2f}`\n"
            text += f"• Win/Loss Ratio: `{stats['win_loss_ratio']:.2f}`\n"
            
            # Add control buttons
            keyboard = [[
                InlineKeyboardButton(
                    "🔄 Refresh Stats",
                    callback_data=f"strategy_stats_{strategy_name}"
                ),
                InlineKeyboardButton(
                    "📊 Detailed Report",
                    callback_data=f"strategy_report_{strategy_name}"
                )
            ]]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Error showing strategy stats: {str(e)}")
            await query.edit_message_text(
                "❌ Error fetching strategy stats. Please try again."
            )
            
    async def _delete_strategy(
        self,
        query: Update.callback_query,
        strategy_name: str
    ) -> None:
        """Delete user strategy"""
        user_id = query.from_user.id
        
        try:
            # Delete strategy
            await self.strategy_manager.delete_user_strategy(
                user_id,
                strategy_name
            )
            
            text = f"✅ Successfully deleted {strategy_name} strategy.\n\n"
            text += "You can apply a new strategy using:\n"
            text += "`/strategy list`"
            
            # Add quick actions
            keyboard = [[
                InlineKeyboardButton(
                    "📜 List Strategies",
                    callback_data="strategy_list"
                ),
                InlineKeyboardButton(
                    "↩️ Undo Delete",
                    callback_data=f"strategy_restore_{strategy_name}"
                )
            ]]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Error deleting strategy: {str(e)}")
            await query.edit_message_text(
                "❌ Error deleting strategy. Please try again."
            )
