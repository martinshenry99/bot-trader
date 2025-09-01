"""
Daily reporting system for Meme Trader V4 Pro
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass

from db import get_db_session, User, Trade, DailyReport
from core.trading_engine import trading_engine

logger = logging.getLogger(__name__)


@dataclass
class DailyMetrics:
    """Daily trading metrics"""
    date: datetime
    total_trades: int
    successful_trades: int
    failed_trades: int
    total_pnl_usd: float
    best_trade_pnl: float
    worst_trade_pnl: float
    portfolio_value_usd: float
    portfolio_change_pct: float
    alerts_received: int
    alerts_acted_on: int
    win_rate: float


class DailyReportGenerator:
    """Generate daily trading reports"""
    
    def __init__(self):
        self.is_running = False
    
    async def start_daily_reporting(self):
        """Start daily reporting service"""
        if self.is_running:
            return
        
        self.is_running = True
        logger.info("📊 Starting daily reporting service...")
        
        # Schedule daily reports
        while self.is_running:
            try:
                # Run at 23:59 UTC daily
                now = datetime.utcnow()
                next_run = now.replace(hour=23, minute=59, second=0, microsecond=0)
                
                if next_run <= now:
                    next_run += timedelta(days=1)
                
                wait_seconds = (next_run - now).total_seconds()
                logger.info(f"📅 Next daily report in {wait_seconds/3600:.1f} hours")
                
                await asyncio.sleep(wait_seconds)
                await self.generate_all_daily_reports()
                
            except Exception as e:
                logger.error(f"Daily reporting error: {e}")
                await asyncio.sleep(3600)  # Wait 1 hour on error
    
    async def generate_all_daily_reports(self):
        """Generate daily reports for all users"""
        try:
            logger.info("📊 Generating daily reports for all users...")
            
            db = get_db_session()
            try:
                users = db.query(User).filter(User.is_active == True).all()
                
                for user in users:
                    try:
                        await self.generate_user_daily_report(user.telegram_id)
                    except Exception as e:
                        logger.error(f"Failed to generate report for user {user.telegram_id}: {e}")
                
                logger.info(f"✅ Generated daily reports for {len(users)} users")
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error generating daily reports: {e}")
    
    async def generate_user_daily_report(self, telegram_id: str) -> Optional[DailyMetrics]:
        """Generate daily report for specific user"""
        try:
            db = get_db_session()
            try:
                user = db.query(User).filter(User.telegram_id == telegram_id).first()
                if not user:
                    return None
                
                # Get today's data
                today = datetime.utcnow().date()
                start_of_day = datetime.combine(today, datetime.min.time())
                end_of_day = start_of_day + timedelta(days=1)
                
                # Get today's trades
                trades = db.query(Trade).filter(
                    Trade.user_id == user.id,
                    Trade.created_at >= start_of_day,
                    Trade.created_at < end_of_day
                ).all()
                
                # Calculate metrics
                metrics = await self._calculate_daily_metrics(user.telegram_id, trades, today)
                
                # Save to database
                existing_report = db.query(DailyReport).filter(
                    DailyReport.user_id == user.id,
                    DailyReport.report_date == start_of_day
                ).first()
                
                if existing_report:
                    self._update_daily_report(existing_report, metrics)
                else:
                    daily_report = DailyReport(
                        user_id=user.id,
                        report_date=start_of_day,
                        total_trades=metrics.total_trades,
                        successful_trades=metrics.successful_trades,
                        failed_trades=metrics.failed_trades,
                        total_pnl_usd=metrics.total_pnl_usd,
                        best_trade_pnl=metrics.best_trade_pnl,
                        worst_trade_pnl=metrics.worst_trade_pnl,
                        portfolio_value_usd=metrics.portfolio_value_usd,
                        portfolio_change_pct=metrics.portfolio_change_pct,
                        alerts_received=metrics.alerts_received,
                        alerts_acted_on=metrics.alerts_acted_on
                    )
                    db.add(daily_report)
                
                db.commit()
                
                # Send report to user
                await self.send_daily_report_to_user(telegram_id, metrics)
                
                return metrics
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error generating user daily report: {e}")
            return None
    
    async def _calculate_daily_metrics(self, telegram_id: str, trades: List[Trade], date: datetime.date) -> DailyMetrics:
        """Calculate daily metrics from trades"""
        try:
            # Basic trade metrics
            total_trades = len(trades)
            successful_trades = len([t for t in trades if t.status == 'confirmed'])
            failed_trades = total_trades - successful_trades
            
            # P&L calculations
            total_pnl_usd = sum(t.pnl_usd for t in trades if t.pnl_usd)
            trade_pnls = [t.pnl_usd for t in trades if t.pnl_usd is not None]
            best_trade_pnl = max(trade_pnls) if trade_pnls else 0.0
            worst_trade_pnl = min(trade_pnls) if trade_pnls else 0.0
            
            # Portfolio metrics
            portfolio = await trading_engine.get_portfolio_summary(telegram_id)
            portfolio_value_usd = portfolio.get('portfolio_value_usd', 0.0)
            
            # Calculate portfolio change (would need yesterday's value)
            portfolio_change_pct = 0.0  # Placeholder
            
            # Alert metrics (placeholder - would track from alert system)
            alerts_received = 0
            alerts_acted_on = successful_trades  # Approximation
            
            # Win rate
            win_rate = (successful_trades / total_trades * 100) if total_trades > 0 else 0.0
            
            return DailyMetrics(
                date=datetime.combine(date, datetime.min.time()),
                total_trades=total_trades,
                successful_trades=successful_trades,
                failed_trades=failed_trades,
                total_pnl_usd=total_pnl_usd,
                best_trade_pnl=best_trade_pnl,
                worst_trade_pnl=worst_trade_pnl,
                portfolio_value_usd=portfolio_value_usd,
                portfolio_change_pct=portfolio_change_pct,
                alerts_received=alerts_received,
                alerts_acted_on=alerts_acted_on,
                win_rate=win_rate
            )
            
        except Exception as e:
            logger.error(f"Error calculating daily metrics: {e}")
            # Return empty metrics on error
            return DailyMetrics(
                date=datetime.combine(date, datetime.min.time()),
                total_trades=0,
                successful_trades=0,
                failed_trades=0,
                total_pnl_usd=0.0,
                best_trade_pnl=0.0,
                worst_trade_pnl=0.0,
                portfolio_value_usd=0.0,
                portfolio_change_pct=0.0,
                alerts_received=0,
                alerts_acted_on=0,
                win_rate=0.0
            )
    
    def _update_daily_report(self, report: DailyReport, metrics: DailyMetrics):
        """Update existing daily report"""
        report.total_trades = metrics.total_trades
        report.successful_trades = metrics.successful_trades
        report.failed_trades = metrics.failed_trades
        report.total_pnl_usd = metrics.total_pnl_usd
        report.best_trade_pnl = metrics.best_trade_pnl
        report.worst_trade_pnl = metrics.worst_trade_pnl
        report.portfolio_value_usd = metrics.portfolio_value_usd
        report.portfolio_change_pct = metrics.portfolio_change_pct
        report.alerts_received = metrics.alerts_received
        report.alerts_acted_on = metrics.alerts_acted_on
    
    async def send_daily_report_to_user(self, telegram_id: str, metrics: DailyMetrics):
        """Send daily report to user via Telegram"""
        try:
            # Format report message
            pnl_emoji = "🟢" if metrics.total_pnl_usd >= 0 else "🔴"
            pnl_sign = "+" if metrics.total_pnl_usd >= 0 else ""
            
            date_str = metrics.date.strftime('%B %d, %Y')
            
            report_message = f"""
📊 **DAILY TRADING REPORT**
📅 {date_str}

**🎯 Trading Performance:**
• Total Trades: {metrics.total_trades}
• Successful: {metrics.successful_trades} ✅
• Failed: {metrics.failed_trades} ❌
• Win Rate: {metrics.win_rate:.1f}%

**💰 P&L Summary:**
• Daily P&L: {pnl_emoji} {pnl_sign}${metrics.total_pnl_usd:,.2f}
• Best Trade: 🟢 +${metrics.best_trade_pnl:,.2f}
• Worst Trade: 🔴 ${metrics.worst_trade_pnl:,.2f}

**📈 Portfolio Status:**
• Current Value: ${metrics.portfolio_value_usd:,.2f}
• Daily Change: {"🟢 +" if metrics.portfolio_change_pct >= 0 else "🔴 "}{metrics.portfolio_change_pct:+.1f}%

**🔔 Alert Activity:**
• Alerts Received: {metrics.alerts_received}
• Alerts Acted On: {metrics.alerts_acted_on}
• Action Rate: {(metrics.alerts_acted_on/metrics.alerts_received*100) if metrics.alerts_received > 0 else 0:.1f}%

**📈 Performance Summary:**
{"🎉 Great trading day!" if metrics.total_pnl_usd > 0 else "📉 Consider reviewing strategy" if metrics.total_pnl_usd < 0 else "⚖️ Break-even day"}

**Tomorrow's Focus:**
• Continue monitoring watchlist wallets
• Review {'winning' if metrics.total_pnl_usd > 0 else 'losing'} trade patterns
• Optimize entry/exit timing

*Report generated at {datetime.utcnow().strftime('%H:%M UTC')}*
            """
            
            # Send via bot (this would need bot instance)
            from bot import send_message_to_user
            await send_message_to_user(telegram_id, report_message)
            
            logger.info(f"📊 Daily report sent to user {telegram_id}")
            
        except Exception as e:
            logger.error(f"Error sending daily report: {e}")
    
    async def get_weekly_summary(self, telegram_id: str) -> Optional[Dict]:
        """Get weekly trading summary"""
        try:
            db = get_db_session()
            try:
                user = db.query(User).filter(User.telegram_id == telegram_id).first()
                if not user:
                    return None
                
                # Get last 7 days of reports
                end_date = datetime.utcnow().date()
                start_date = end_date - timedelta(days=7)
                
                reports = db.query(DailyReport).filter(
                    DailyReport.user_id == user.id,
                    DailyReport.report_date >= datetime.combine(start_date, datetime.min.time()),
                    DailyReport.report_date <= datetime.combine(end_date, datetime.min.time())
                ).all()
                
                if not reports:
                    return None
                
                # Calculate weekly metrics
                weekly_summary = {
                    'total_trades': sum(r.total_trades for r in reports),
                    'successful_trades': sum(r.successful_trades for r in reports),
                    'total_pnl_usd': sum(r.total_pnl_usd for r in reports),
                    'best_day_pnl': max(r.total_pnl_usd for r in reports),
                    'worst_day_pnl': min(r.total_pnl_usd for r in reports),
                    'avg_daily_pnl': sum(r.total_pnl_usd for r in reports) / len(reports),
                    'trading_days': len([r for r in reports if r.total_trades > 0]),
                    'current_portfolio_value': reports[-1].portfolio_value_usd if reports else 0.0
                }
                
                weekly_summary['win_rate'] = (
                    weekly_summary['successful_trades'] / weekly_summary['total_trades'] * 100
                    if weekly_summary['total_trades'] > 0 else 0.0
                )
                
                return weekly_summary
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error getting weekly summary: {e}")
            return None


# Global instance
daily_report_generator = DailyReportGenerator()