"""Command handler for token discovery and monitoring"""
from typing import Dict, List, Optional
import logging

from bot.commands import CommandHandler, command
from services.token_discovery import TokenDiscovery
from utils.formatting import (
    format_token_discovery,
    format_monitoring_alert,
    format_watchlist
)

logger = logging.getLogger(__name__)

class TokenDiscoveryHandler(CommandHandler):
    """Handler for token discovery and monitoring commands"""
    
    def __init__(self, token_discovery: TokenDiscovery):
        self.discovery = token_discovery
    
    @command(
        name='discover',
        help='Discover new trading opportunities on specified chain'
    )
    async def discover_tokens(
        self,
        chain: str = 'ethereum'
    ) -> str:
        """Discover new potential trading opportunities"""
        try:
            discovered = await self.discovery.discover_tokens(chain)
            
            if not discovered:
                return "No new trading opportunities found matching criteria"
            
            return format_token_discovery(discovered)
            
        except Exception as e:
            logger.error(f"Error in discover command: {str(e)}")
            raise
    
    @command(
        name='monitor',
        help='Get monitoring alerts for tracked tokens'
    )
    async def monitor_tokens(
        self,
        chain: str = 'ethereum'
    ) -> str:
        """Monitor tracked tokens for changes"""
        try:
            alerts = await self.discovery.monitor_tokens(chain)
            
            if not alerts:
                return "No significant changes detected in monitored tokens"
            
            return format_monitoring_alert(alerts)
            
        except Exception as e:
            logger.error(f"Error in monitor command: {str(e)}")
            raise
    
    @command(
        name='watchlist',
        help='Manage token watchlist'
    )
    async def manage_watchlist(
        self,
        action: str,
        token_address: Optional[str] = None,
        chain: str = 'ethereum'
    ) -> str:
        """Manage token monitoring watchlist"""
        try:
            if action == 'list':
                tokens = self.discovery.get_monitored_tokens()
                return format_watchlist(tokens)
                
            elif action == 'add' and token_address:
                result = await self.discovery.add_to_watchlist(
                    token_address,
                    chain
                )
                return f"Added {token_address} to watchlist\n\n{format_token_discovery([result])}"
                
            elif action == 'remove' and token_address:
                removed = self.discovery.remove_from_watchlist(token_address)
                return (
                    f"Removed {token_address} from watchlist"
                    if removed else
                    f"Token {token_address} not found in watchlist"
                )
                
            else:
                return "Invalid watchlist action. Use 'list', 'add <address>', or 'remove <address>'"
                
        except Exception as e:
            logger.error(f"Error in watchlist command: {str(e)}")
            raise
    
    @command(
        name='discovery_config',
        help='Update token discovery configuration'
    )
    async def update_discovery_config(
        self,
        min_liquidity: Optional[float] = None,
        min_holder_count: Optional[int] = None,
        max_holder_concentration: Optional[float] = None,
        min_daily_volume: Optional[float] = None,
        max_risk_score: Optional[float] = None
    ) -> str:
        """Update token discovery configuration"""
        try:
            config = {}
            
            if min_liquidity is not None:
                config['min_liquidity'] = min_liquidity
            if min_holder_count is not None:
                config['min_holder_count'] = min_holder_count
            if max_holder_concentration is not None:
                config['max_holder_concentration'] = max_holder_concentration
            if min_daily_volume is not None:
                config['min_daily_volume'] = min_daily_volume
            if max_risk_score is not None:
                config['max_risk_score'] = max_risk_score
            
            if not config:
                return "No configuration changes provided"
            
            updated = await self.discovery.update_discovery_config(config)
            
            return (
                "Discovery configuration updated:\n" +
                "\n".join(
                    f"• {k}: {v}" for k, v in updated.items()
                )
            )
            
        except Exception as e:
            logger.error(f"Error updating discovery config: {str(e)}")
            raise
    
    @command(
        name='alert_thresholds',
        help='Update monitoring alert thresholds'
    )
    async def update_alert_thresholds(
        self,
        price_change: Optional[float] = None,
        volume_spike: Optional[float] = None,
        liquidity_drop: Optional[float] = None,
        holder_change: Optional[float] = None
    ) -> str:
        """Update monitoring alert thresholds"""
        try:
            thresholds = {}
            
            if price_change is not None:
                thresholds['price_change'] = price_change
            if volume_spike is not None:
                thresholds['volume_spike'] = volume_spike
            if liquidity_drop is not None:
                thresholds['liquidity_drop'] = liquidity_drop
            if holder_change is not None:
                thresholds['holder_change'] = holder_change
            
            if not thresholds:
                return "No threshold changes provided"
            
            updated = await self.discovery.update_alert_thresholds(thresholds)
            
            return (
                "Alert thresholds updated:\n" +
                "\n".join(
                    f"• {k}: {v}" for k, v in updated.items()
                )
            )
            
        except Exception as e:
            logger.error(f"Error updating alert thresholds: {str(e)}")
            raise
