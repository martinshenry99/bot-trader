"""
Portfolio command handlers
"""

import logging
from typing import Dict, List
from decimal import Decimal
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from services.portfolio_manager import PortfolioManager
from services.chain_manager import ChainManager
from utils.formatting import format_usd, format_percentage
from utils.chart_utils import generate_portfolio_chart

logger = logging.getLogger(__name__)

class PortfolioCommandHandler:
    """Handler for portfolio-related commands"""
    
    def __init__(
        self,
        portfolio_manager: PortfolioManager,
        chain_manager: ChainManager
    ):
        self.portfolio_manager = portfolio_manager
        self.chain_manager = chain_manager
        
    async def handle_portfolio_summary(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /portfolio summary command"""
        try:
            user_id = update.effective_user.id
            
            # Get portfolio summary
            portfolio = await self.portfolio_manager.get_portfolio_summary(
                user_id
            )
            
            # Format response
            text = "📊 *Cross-Chain Portfolio Summary*\n\n"
            
            # Total value
            text += f"💰 Total Value: `{format_usd(portfolio['total_value_usd'])}`\n\n"
            
            # Performance
            text += "*Performance:*\n"
            for period, change in portfolio['performance'].items():
                emoji = "📈" if change >= 0 else "📉"
                text += f"{emoji} {period}: `{format_percentage(change)}`\n"
            text += "\n"
            
            # Chain distribution
            text += "*Chain Distribution:*\n"
            for chain, data in portfolio['chains'].items():
                text += f"• {self._get_chain_emoji(chain)} {chain.upper()}: "
                text += f"`{format_usd(data['value_usd'])} "
                text += f"({format_percentage(data['percentage'])})`\n"
            text += "\n"
            
            # Top positions
            text += "*Top 5 Positions:*\n"
            for pos in portfolio['top_positions']:
                change_emoji = "📈" if pos['24h_change'] >= 0 else "📉"
                text += f"• {pos['token']} ({pos['chain']})\n"
                text += f"  Value: `{format_usd(pos['value_usd'])}` "
                text += f"{change_emoji} `{format_percentage(pos['24h_change'])} 24h`\n"
            text += "\n"
            
            # Risk metrics
            text += "*Risk Analysis:*\n"
            risk_metrics = portfolio['risk_metrics']
            text += f"• Concentration Risk: `{format_percentage(risk_metrics['concentration_risk'])}`\n"
            text += f"• Chain Risk: `{format_percentage(risk_metrics['chain_risk'])}`\n"
            text += f"• Overall Risk: `{format_percentage(risk_metrics['overall_risk'])}`\n\n"
            
            # Last update
            text += f"_Last updated: {portfolio['updated_at']}_"
            
            # Generate portfolio chart
            chart_path = await generate_portfolio_chart(portfolio)
            
            # Add action buttons
            keyboard = [
                [
                    InlineKeyboardButton(
                        "🔄 Refresh",
                        callback_data="portfolio_refresh"
                    ),
                    InlineKeyboardButton(
                        "📊 Detailed Analysis",
                        callback_data="portfolio_analysis"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "📈 Performance History",
                        callback_data="portfolio_history"
                    ),
                    InlineKeyboardButton(
                        "⚖️ Rebalance",
                        callback_data="portfolio_rebalance"
                    )
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Send response with chart
            if chart_path:
                await update.message.reply_photo(
                    photo=open(chart_path, 'rb'),
                    caption=text,
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
            else:
                await update.message.reply_text(
                    text,
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
                
        except Exception as e:
            logger.error(f"Error in portfolio summary: {str(e)}")
            await update.message.reply_text(
                "❌ Error fetching portfolio summary. Please try again."
            )
            
    async def handle_portfolio_callback(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle portfolio-related callback queries"""
        query = update.callback_query
        await query.answer()
        
        try:
            action = query.data.split('_')[1]
            
            if action == 'refresh':
                # Refresh portfolio summary
                await self._refresh_portfolio(query)
            elif action == 'analysis':
                # Show detailed analysis
                await self._show_detailed_analysis(query)
            elif action == 'history':
                # Show performance history
                await self._show_performance_history(query)
            elif action == 'rebalance':
                # Show rebalancing options
                await self._show_rebalance_options(query)
                
        except Exception as e:
            logger.error(f"Error in portfolio callback: {str(e)}")
            await query.edit_message_text(
                "❌ Error processing request. Please try again."
            )
            
    async def _refresh_portfolio(
        self,
        query: Update.callback_query
    ) -> None:
        """Refresh portfolio summary"""
        user_id = query.from_user.id
        
        try:
            # Get fresh portfolio data
            portfolio = await self.portfolio_manager.get_portfolio_summary(
                user_id,
                force_refresh=True
            )
            
            # Update message with new data
            text = "📊 *Cross-Chain Portfolio Summary*\n\n"
            # ... (same formatting as handle_portfolio_summary)
            
            # Generate new chart
            chart_path = await generate_portfolio_chart(portfolio)
            
            if chart_path:
                await query.edit_message_media(
                    media=InputMediaPhoto(
                        media=open(chart_path, 'rb'),
                        caption=text,
                        parse_mode='Markdown'
                    ),
                    reply_markup=query.message.reply_markup
                )
            else:
                await query.edit_message_text(
                    text,
                    parse_mode='Markdown',
                    reply_markup=query.message.reply_markup
                )
                
        except Exception as e:
            logger.error(f"Error refreshing portfolio: {str(e)}")
            await query.answer(
                "Error refreshing portfolio data",
                show_alert=True
            )
            
    async def _show_detailed_analysis(
        self,
        query: Update.callback_query
    ) -> None:
        """Show detailed portfolio analysis"""
        user_id = query.from_user.id
        
        try:
            portfolio = await self.portfolio_manager.get_portfolio_summary(
                user_id
            )
            
            text = "📈 *Detailed Portfolio Analysis*\n\n"
            
            # Asset allocation
            text += "*Asset Allocation:*\n"
            total_value = portfolio['total_value_usd']
            for pos in portfolio['top_positions']:
                percentage = pos['value_usd'] / total_value * 100
                text += f"• {pos['token']}: `{format_percentage(percentage)}`\n"
            text += "\n"
            
            # Risk analysis
            text += "*Risk Analysis:*\n"
            risk = portfolio['risk_metrics']
            text += "• Concentration Risk:\n"
            text += f"  `{format_percentage(risk['concentration_risk'])}` "
            text += self._get_risk_description(
                'concentration',
                risk['concentration_risk']
            )
            text += "\n"
            
            text += "• Chain Risk:\n"
            text += f"  `{format_percentage(risk['chain_risk'])}` "
            text += self._get_risk_description(
                'chain',
                risk['chain_risk']
            )
            text += "\n"
            
            text += "• Volatility Risk:\n"
            text += f"  `{format_percentage(risk['volatility_risk'])}` "
            text += self._get_risk_description(
                'volatility',
                risk['volatility_risk']
            )
            text += "\n"
            
            # Add back button
            keyboard = [[
                InlineKeyboardButton(
                    "« Back to Summary",
                    callback_data="portfolio_summary"
                )
            ]]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Error showing analysis: {str(e)}")
            await query.answer(
                "Error fetching analysis data",
                show_alert=True
            )
            
    def _get_chain_emoji(self, chain: str) -> str:
        """Get emoji for chain"""
        emojis = {
            'ethereum': '⟠',
            'bsc': '🟡',
            'solana': '◎'
        }
        return emojis.get(chain.lower(), '•')
        
    def _get_risk_description(
        self,
        risk_type: str,
        risk_value: float
    ) -> str:
        """Get description for risk level"""
        if risk_type == 'concentration':
            if risk_value < 20:
                return "(Well diversified)"
            elif risk_value < 50:
                return "(Moderately concentrated)"
            else:
                return "(Highly concentrated)"
                
        elif risk_type == 'chain':
            if risk_value < 30:
                return "(Good chain diversity)"
            elif risk_value < 60:
                return "(Chain concentration present)"
            else:
                return "(High chain dependency)"
                
        elif risk_type == 'volatility':
            if risk_value < 25:
                return "(Low volatility)"
            elif risk_value < 50:
                return "(Moderate volatility)"
            else:
                return "(High volatility)"
                
        return ""
