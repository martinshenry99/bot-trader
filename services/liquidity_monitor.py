import logging
from datetime import datetime
from typing import Dict, List, Optional

from db.models import LPPosition
from integrations.jupiter import JupiterAPI
from integrations.zerox import ZeroXClient
from utils.notifications import send_alert

logger = logging.getLogger(__name__)

class LiquidityMonitor:
    """Monitors liquidity positions and generates alerts for significant changes"""
    
    def __init__(self, jupiter_api: JupiterAPI, zerox_api: ZeroXClient):
        self.jupiter_api = jupiter_api
        self.zerox_api = zerox_api
        self.alert_thresholds = {
            'volume_change': 0.20,  # 20% change in volume
            'liquidity_change': 0.15,  # 15% change in liquidity
            'price_impact': 0.10,  # 10% price impact threshold
        }
        
    async def scan_lp_positions(self, positions: List[LPPosition]) -> List[Dict]:
        """Scan LP positions for significant changes that require alerts"""
        alerts = []
        
        for position in positions:
            try:
                current_metrics = await self._get_current_metrics(position)
                if not current_metrics:
                    continue
                    
                alert = self._check_for_alerts(position, current_metrics)
                if alert:
                    alerts.append(alert)
                    await self._send_alert(alert)
                    
                # Update historical metrics
                await position.update_metrics(current_metrics)
                
            except Exception as e:
                logger.error(f"Error monitoring position {position.id}: {str(e)}")
                
        return alerts
    
    async def _get_current_metrics(self, position: LPPosition) -> Optional[Dict]:
        """Fetch current liquidity metrics for a position"""
        try:
            if position.chain == "solana":
                metrics = await self.jupiter_api.get_pool_metrics(position.pool_address)
            else:
                metrics = await self.zerox_api.get_pool_metrics(
                    position.chain,
                    position.pool_address
                )
            
            return {
                'timestamp': datetime.utcnow(),
                'tvl': metrics['tvl'],
                'volume_24h': metrics['volume24h'],
                'price_impact': metrics['priceImpact'],
                'liquidity_depth': metrics['liquidityDepth']
            }
            
        except Exception as e:
            logger.error(f"Failed to get metrics for {position.pool_address}: {str(e)}")
            return None
            
    def _check_for_alerts(self, position: LPPosition, current: Dict) -> Optional[Dict]:
        """Check if current metrics warrant sending an alert"""
        if not position.last_metrics:
            return None
            
        alerts = []
        
        # Check volume change
        volume_change = abs(current['volume_24h'] - position.last_metrics['volume_24h']) / position.last_metrics['volume_24h']
        if volume_change > self.alert_thresholds['volume_change']:
            alerts.append(f"Volume changed by {volume_change:.1%}")
            
        # Check liquidity change    
        tvl_change = abs(current['tvl'] - position.last_metrics['tvl']) / position.last_metrics['tvl']
        if tvl_change > self.alert_thresholds['liquidity_change']:
            alerts.append(f"TVL changed by {tvl_change:.1%}")
            
        # Check price impact
        if current['price_impact'] > self.alert_thresholds['price_impact']:
            alerts.append(f"High price impact: {current['price_impact']:.1%}")
            
        if not alerts:
            return None
            
        return {
            'position_id': position.id,
            'pool_address': position.pool_address,
            'chain': position.chain,
            'alerts': alerts,
            'timestamp': current['timestamp']
        }
        
    async def _send_alert(self, alert: Dict):
        """Send notification for liquidity alert"""
        message = f"⚠️ Liquidity Alert for {alert['chain'].upper()} pool {alert['pool_address']}\n\n"
        message += "\n".join(f"• {alert_msg}" for alert_msg in alert['alerts'])
        
        await send_alert(
            title="Liquidity Monitor Alert",
            message=message,
            severity="warning"
        )
