import logging
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from bot.commands import command_handler
from db.models.lp_position import LPPosition
from services.liquidity_monitor import LiquidityMonitor
from utils.formatting import format_table

logger = logging.getLogger(__name__)

class LPMonitoringHandler:
    """Handler for LP monitoring related commands"""
    
    def __init__(self, session: AsyncSession, monitor: LiquidityMonitor):
        self.session = session
        self.monitor = monitor
        
    @command_handler("lp list")
    async def list_positions(self, wallet_address: Optional[str] = None) -> str:
        """List all tracked LP positions"""
        positions = await LPPosition.get_active_positions(self.session, wallet_address)
        
        if not positions:
            return "No LP positions found"
            
        headers = ["Pool", "Chain", "Size", "Last Update"]
        rows = []
        
        for pos in positions:
            rows.append([
                f"{pos.token0_symbol}-{pos.token1_symbol}",
                pos.chain,
                f"{pos.position_size:.4f}",
                pos.last_updated.strftime("%Y-%m-%d %H:%M")
            ])
            
        return format_table(headers, rows)
        
    @command_handler("lp scan")
    async def scan_positions(self, wallet_address: Optional[str] = None) -> str:
        """Manually trigger a scan of LP positions"""
        positions = await LPPosition.get_active_positions(self.session, wallet_address)
        
        if not positions:
            return "No LP positions to scan"
            
        alerts = await self.monitor.scan_lp_positions(positions)
        
        if not alerts:
            return "Scan complete - No alerts generated"
            
        return "Scan complete - Generated alerts:\n" + "\n".join(
            f"• {alert['chain'].upper()} {alert['pool_address']}: {', '.join(alert['alerts'])}"
            for alert in alerts
        )
        
    @command_handler("lp alerts")
    async def configure_alerts(self, setting: str, value: float) -> str:
        """Configure alert thresholds"""
        if setting not in self.monitor.alert_thresholds:
            return f"Invalid setting. Available options: {', '.join(self.monitor.alert_thresholds.keys())}"
            
        if not 0 < value < 1:
            return "Threshold must be between 0 and 1 (e.g., 0.15 for 15%)"
            
        self.monitor.alert_thresholds[setting] = value
        return f"Updated {setting} threshold to {value:.1%}"
