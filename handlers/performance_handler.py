"""Command handler for performance analytics system"""
import logging
from typing import Optional
from datetime import datetime, timedelta

from bot.commands import command_handler
from services.performance_analytics import PerformanceAnalytics
from utils.formatting import (
    format_table, format_money, format_percentage,
    format_number, format_timestamp
)

logger = logging.getLogger(__name__)

class PerformanceHandler:
    """Handler for performance analysis commands"""
    
    def __init__(self, analytics: PerformanceAnalytics):
        self.analytics = analytics
    
    @command_handler("portfolio")
    async def show_portfolio_stats(
        self,
        wallet: str,
        timeframe: str = "all"
    ) -> str:
        """Show portfolio performance statistics"""
        try:
            stats = await self.analytics.get_portfolio_stats(wallet, timeframe)
            
            # Format sections
            overview = [
                "📊 Portfolio Overview",
                "==================",
                f"Total Sessions: {stats['overview']['total_sessions']}",
                f"Total Trades: {stats['overview']['total_trades']}",
                f"Active Sessions: {stats['overview']['active_sessions']}",
                "",
                f"Total Investment: {format_money(stats['overview']['total_investment'])}",
                f"Current Value: {format_money(stats['overview']['total_final_value'])}",
                f"Total P/L: {format_money(stats['overview']['total_profit_loss'])}"
            ]
            
            performance = [
                "",
                "📈 Performance Metrics",
                "===================",
                f"Win Rate: {format_percentage(stats['performance']['win_rate'])}",
                f"Average ROI: {format_percentage(stats['performance']['average_roi'])}",
                f"Best ROI: {format_percentage(stats['performance']['best_roi'])}",
                f"Worst ROI: {format_percentage(stats['performance']['worst_roi'])}",
                f"ROI Volatility: {format_percentage(stats['performance']['roi_volatility'])}"
            ]
            
            risk = [
                "",
                "⚠️ Risk Metrics",
                "=============",
                f"Average Risk Score: {format_percentage(stats['risk_metrics']['average_risk_score'])}",
                f"High Risk Exposure: {format_percentage(stats['risk_metrics']['high_risk_exposure'])}",
                f"Risk-Adjusted Return: {format_percentage(stats['risk_metrics']['risk_adjusted_return'])}"
            ]
            
            trades = [
                "",
                "🔄 Trade Metrics",
                "==============",
                f"Average Trade Size: {format_money(stats['trade_metrics']['average_trade_size'])}",
                f"Average Slippage: {format_percentage(stats['trade_metrics']['average_slippage'])}",
                f"Execution Success: {format_percentage(stats['trade_metrics']['execution_success_rate'])}"
            ]
            
            return "\n".join([*overview, *performance, *risk, *trades])
            
        except Exception as e:
            logger.error(f"Error showing portfolio stats: {str(e)}")
            return f"❌ Error retrieving portfolio statistics: {str(e)}"
    
    @command_handler("strategies")
    async def analyze_strategies(
        self,
        timeframe: str = "all",
        strategy: Optional[str] = None
    ) -> str:
        """Analyze performance by trading strategy"""
        try:
            performance = await self.analytics.get_strategy_performance(
                strategy,
                timeframe
            )
            
            if not performance:
                return "No strategy data found for the specified period"
            
            # Format table data
            headers = [
                "Strategy",
                "Sessions",
                "Win Rate",
                "Avg ROI",
                "Total Profit",
                "Risk Score"
            ]
            rows = []
            
            for strategy_name, metrics in performance.items():
                rows.append([
                    strategy_name,
                    str(metrics['total_sessions']),
                    format_percentage(metrics['win_rate']),
                    format_percentage(metrics['average_roi']),
                    format_money(metrics['total_profit']),
                    format_percentage(metrics['risk_metrics']['average_risk_score'])
                ])
            
            response = [
                "📊 Strategy Performance Analysis",
                "============================",
                format_table(headers, rows),
                "",
                "Detailed Metrics:",
            ]
            
            # Add detailed metrics for each strategy
            for strategy_name, metrics in performance.items():
                response.extend([
                    "",
                    f"🎯 {strategy_name}:",
                    f"• ROI Volatility: {format_percentage(metrics['roi_volatility'])}",
                    f"• Risk-Adjusted Return: {format_percentage(metrics['risk_metrics']['risk_adjusted_return'])}",
                    f"• High Risk Exposure: {format_percentage(metrics['risk_metrics']['high_risk_exposure'])}"
                ])
            
            return "\n".join(response)
            
        except Exception as e:
            logger.error(f"Error analyzing strategies: {str(e)}")
            return f"❌ Error analyzing strategy performance: {str(e)}"
    
    @command_handler("analyze_pair")
    async def analyze_pair(
        self,
        token: str,
        chain: str = "ethereum",
        timeframe: str = "all"
    ) -> str:
        """Analyze performance for a specific trading pair"""
        try:
            performance = await self.analytics.get_pair_performance(
                token,
                chain,
                timeframe
            )
            
            if not performance:
                return f"No trading data found for {chain}:{token}"
            
            # Format sections
            overview = [
                "📊 Pair Analysis",
                "==============",
                f"Total Sessions: {performance['overview']['total_sessions']}",
                f"Total Trades: {performance['overview']['total_trades']}",
                f"Total Volume: {format_money(performance['overview']['total_volume'])}"
            ]
            
            timing = [
                "",
                "⏱️ Timing Performance",
                "===================",
                f"Average Score: {format_percentage(performance['timing']['average_timing_score'])}",
                f"Best Entry/Exit: {format_percentage(performance['timing']['best_timing_score'])}",
                f"Worst Entry/Exit: {format_percentage(performance['timing']['worst_timing_score'])}"
            ]
            
            slippage = [
                "",
                "💫 Slippage Analysis",
                "==================",
                "Entry Trades:",
                f"• Average: {format_percentage(performance['slippage']['entry_slippage']['average'])}",
                f"• Maximum: {format_percentage(performance['slippage']['entry_slippage']['max'])}",
                "",
                "Exit Trades:",
                f"• Average: {format_percentage(performance['slippage']['exit_slippage']['average'])}",
                f"• Maximum: {format_percentage(performance['slippage']['exit_slippage']['max'])}"
            ]
            
            profit = [
                "",
                "💰 Profit Analysis",
                "================",
                f"Total Sessions: {performance['profit']['total_sessions']}",
                f"Profitable Sessions: {performance['profit']['profitable_sessions']}",
                f"Average ROI: {format_percentage(performance['profit']['average_roi'])}",
                f"Best ROI: {format_percentage(performance['profit']['best_roi'])}",
                f"Worst ROI: {format_percentage(performance['profit']['worst_roi'])}",
                f"ROI Volatility: {format_percentage(performance['profit']['roi_volatility'])}"
            ]
            
            return "\n".join([*overview, *timing, *slippage, *profit])
            
        except Exception as e:
            logger.error(f"Error analyzing pair: {str(e)}")
            return f"❌ Error analyzing pair performance: {str(e)}"
    
    @command_handler("report")
    async def generate_report(
        self,
        wallet: str,
        timeframe: str = "all",
        include_trades: bool = False
    ) -> str:
        """Generate comprehensive performance report"""
        try:
            report = await self.analytics.generate_performance_report(
                wallet,
                timeframe,
                include_trades
            )
            
            # Format main sections
            overview = [
                "📊 Performance Report",
                "===================",
                f"Wallet: {wallet}",
                f"Period: {timeframe}",
                "",
                "Portfolio Summary:",
                f"• Total Sessions: {report['portfolio']['overview']['total_sessions']}",
                f"• Total Trades: {report['portfolio']['overview']['total_trades']}",
                f"• Total P/L: {format_money(report['portfolio']['overview']['total_profit_loss'])}",
                f"• Win Rate: {format_percentage(report['portfolio']['performance']['win_rate'])}",
                f"• Average ROI: {format_percentage(report['portfolio']['performance']['average_roi'])}"
            ]
            
            # Strategy summary
            strategies = [
                "",
                "Strategy Performance:",
            ]
            for strategy, metrics in report['strategies'].items():
                strategies.extend([
                    f"",
                    f"📈 {strategy}:",
                    f"• Sessions: {metrics['total_sessions']}",
                    f"• Win Rate: {format_percentage(metrics['win_rate'])}",
                    f"• Total Profit: {format_money(metrics['total_profit'])}",
                    f"• Risk-Adjusted Return: {format_percentage(metrics['risk_metrics']['risk_adjusted_return'])}"
                ])
            
            # Recent sessions
            sessions = [
                "",
                "Recent Trading Sessions:",
                "----------------------"
            ]
            for s in report['sessions'][:5]:  # Show last 5 sessions
                status = "🟢 Active" if s['is_active'] else "⚫ Closed"
                roi = f"{format_percentage(s['roi'])}" if s['roi'] else "N/A"
                sessions.extend([
                    f"",
                    f"{status} - {s['strategy']}",
                    f"Token: {s['chain']}:{s['token_address']}",
                    f"Started: {format_timestamp(s['start_time'])}",
                    f"Investment: {format_money(s['initial_investment'])}",
                    f"ROI: {roi}",
                    f"Risk Score: {format_percentage(s['risk_score'])}"
                ])
            
            response = [*overview, *strategies, *sessions]
            
            # Add trade details if requested
            if include_trades and 'trades' in report:
                trades = [
                    "",
                    "Recent Trades:",
                    "-------------"
                ]
                for t in report['trades'][:10]:  # Show last 10 trades
                    trades.extend([
                        f"",
                        f"{t['trade_type']} - {format_timestamp(t['timestamp'])}",
                        f"Amount: {t['amount']} @ {format_money(t['price_usd'])}",
                        f"Total: {format_money(t['total_value_usd'])}",
                        f"Slippage: {format_percentage(t['slippage_percentage'])}"
                    ])
                response.extend(trades)
            
            return "\n".join(response)
            
        except Exception as e:
            logger.error(f"Error generating report: {str(e)}")
            return f"❌ Error generating performance report: {str(e)}"
