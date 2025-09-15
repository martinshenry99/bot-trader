"""Command handler for trade logging system"""
import logging
from typing import Optional, List
from datetime import datetime, timedelta

from bot.commands import command_handler
from services.trade_logger import TradeLogger
from utils.formatting import (
    format_table, format_money, format_percentage,
    format_timestamp
)

logger = logging.getLogger(__name__)

class TradeLogHandler:
    """Handler for trade log related commands"""
    
    def __init__(self, trade_logger: TradeLogger):
        self.trade_logger = trade_logger
    
    @command_handler("history")
    async def show_trading_history(
        self,
        wallet: Optional[str] = None,
        token: Optional[str] = None,
        strategy: Optional[str] = None,
        limit: int = 10
    ) -> str:
        """Show trading session history"""
        try:
            sessions = await self.trade_logger.get_session_history(
                wallet_address=wallet,
                token_address=token,
                strategy_name=strategy,
                limit=limit
            )
            
            if not sessions:
                return "No trading sessions found matching the criteria"
                
            # Calculate total stats
            total_roi = sum(s['roi_percentage'] or 0 for s in sessions)
            avg_roi = total_roi / len(sessions)
            profitable = sum(1 for s in sessions if s.get('roi_percentage', 0) > 0)
            win_rate = (profitable / len(sessions)) * 100
            
            # Format session table
            headers = ["Date", "Token", "Strategy", "Investment", "Final", "ROI", "Trades"]
            rows = []
            
            for s in sessions:
                rows.append([
                    format_timestamp(s['start_time']),
                    f"{s['chain']}:{s['token_address'][:8]}",
                    s['strategy_name'],
                    format_money(s['initial_investment']),
                    format_money(s['final_value']) if s['final_value'] else "-",
                    format_percentage(s['roi_percentage']) if s['roi_percentage'] else "-",
                    str(s['num_trades'])
                ])
            
            response = [
                "📊 Trading History",
                "================",
                format_table(headers, rows),
                "",
                f"Total Sessions: {len(sessions)}",
                f"Average ROI: {format_percentage(avg_roi)}",
                f"Win Rate: {format_percentage(win_rate)}"
            ]
            
            return "\n".join(response)
            
        except Exception as e:
            logger.error(f"Error showing trading history: {str(e)}")
            return f"❌ Error retrieving trading history: {str(e)}"
    
    @command_handler("trades")
    async def show_trade_details(self, session_id: int) -> str:
        """Show detailed trade logs for a session"""
        try:
            trades = await self.trade_logger.get_trade_details(session_id)
            
            if not trades:
                return f"No trades found for session {session_id}"
                
            # Format trade table
            headers = ["Time", "Type", "Amount", "Price", "Value", "Slippage"]
            rows = []
            
            for t in trades:
                rows.append([
                    format_timestamp(t['timestamp']),
                    t['trade_type'].upper(),
                    f"{float(t['amount']):.4f}",
                    format_money(float(t['price_usd'])),
                    format_money(float(t['total_value_usd'])),
                    format_percentage(t['slippage_percentage']) if t['slippage_percentage'] else "-"
                ])
            
            response = [
                f"🔍 Trade Details - Session {session_id}",
                "==============================",
                format_table(headers, rows)
            ]
            
            # Add trade reasons if available
            for t in trades:
                reasons = []
                if t['entry_reasons']:
                    reasons.extend([
                        "",
                        f"Entry Reasons ({format_timestamp(t['timestamp'])}):",
                        *[f"• {r}" for r in t['entry_reasons']]
                    ])
                if t['exit_reasons']:
                    reasons.extend([
                        "",
                        f"Exit Reasons ({format_timestamp(t['timestamp'])}):",
                        *[f"• {r}" for r in t['exit_reasons']]
                    ])
                if reasons:
                    response.extend(reasons)
            
            return "\n".join(response)
            
        except Exception as e:
            logger.error(f"Error showing trade details: {str(e)}")
            return f"❌ Error retrieving trade details: {str(e)}"
    
    @command_handler("performance")
    async def analyze_performance(
        self,
        wallet: Optional[str] = None,
        days: int = 30
    ) -> str:
        """Analyze trading performance statistics"""
        try:
            since = datetime.utcnow() - timedelta(days=days)
            
            # Get recent sessions
            sessions = await self.trade_logger.get_session_history(
                wallet_address=wallet,
                limit=None  # Get all within time range
            )
            
            # Filter by date
            sessions = [
                s for s in sessions
                if datetime.fromisoformat(s['start_time']) >= since
            ]
            
            if not sessions:
                return f"No trading sessions found in the last {days} days"
                
            # Calculate performance metrics
            total_trades = sum(s['num_trades'] for s in sessions)
            total_investment = sum(s['initial_investment'] for s in sessions)
            total_final = sum(s['final_value'] for s in sessions if s['final_value'])
            total_profit = total_final - total_investment if total_final else 0
            
            profitable = sum(1 for s in sessions if s.get('roi_percentage', 0) > 0)
            win_rate = (profitable / len(sessions)) * 100
            
            # Get best and worst sessions
            sessions.sort(key=lambda x: x.get('roi_percentage', 0) or -float('inf'))
            worst_session = sessions[0]
            best_session = sessions[-1]
            
            response = [
                "📈 Performance Analysis",
                "=====================",
                f"Period: Last {days} days",
                f"Total Sessions: {len(sessions)}",
                f"Total Trades: {total_trades}",
                "",
                "Investment Summary:",
                f"Total Invested: {format_money(total_investment)}",
                f"Final Value: {format_money(total_final)}",
                f"Net Profit: {format_money(total_profit)}",
                f"Win Rate: {format_percentage(win_rate)}",
                "",
                "Best Performance:",
                f"Strategy: {best_session['strategy_name']}",
                f"ROI: {format_percentage(best_session['roi_percentage'])}",
                "",
                "Worst Performance:",
                f"Strategy: {worst_session['strategy_name']}",
                f"ROI: {format_percentage(worst_session['roi_percentage'])}"
            ]
            
            return "\n".join(response)
            
        except Exception as e:
            logger.error(f"Error analyzing performance: {str(e)}")
            return f"❌ Error analyzing performance: {str(e)}"
