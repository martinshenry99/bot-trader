"""Automated token discovery and monitoring service"""
import logging
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta
from decimal import Decimal
import asyncio

from services.risk_scorer import RiskScorer
from services.market_research import MarketResearch
from integrations.covalent import CovalentAPI
from integrations.goplus import GoPlusAPI
from utils.notifications import send_alert

logger = logging.getLogger(__name__)

class TokenDiscovery:
    """Service for discovering and monitoring new trading opportunities"""
    
    def __init__(
        self,
        market_research: MarketResearch,
        risk_scorer: RiskScorer,
        covalent_api: CovalentAPI,
        goplus_api: GoPlusAPI
    ):
        self.market_research = market_research
        self.risk_scorer = risk_scorer
        self.covalent = covalent_api
        self.goplus = goplus_api
        
        # Tracking sets
        self._monitored_tokens: Set[str] = set()
        self._blacklisted_tokens: Set[str] = set()
        
        # Configuration
        self.discovery_config = {
            'min_liquidity': Decimal('10000'),  # Minimum $10k liquidity
            'min_holder_count': 50,
            'max_holder_concentration': 0.7,  # Max 70% held by top 10
            'min_daily_volume': Decimal('5000'),  # Minimum $5k daily volume
            'max_risk_score': 0.7  # Maximum risk score threshold
        }
        
        # Alert thresholds
        self.alert_thresholds = {
            'price_change': 0.15,  # 15% price change
            'volume_spike': 3.0,    # 3x volume increase
            'liquidity_drop': 0.3,  # 30% liquidity decrease
            'holder_change': 0.1    # 10% change in holder concentration
        }
    
    async def discover_tokens(self, chain: str) -> List[Dict]:
        """Discover new potential trading opportunities"""
        try:
            discovered_tokens = []
            
            # Get recent token pairs
            new_pairs = await self.covalent.get_new_pairs(chain)
            
            for pair in new_pairs:
                token_address = pair['token_address']
                
                # Skip if already monitored or blacklisted
                if (token_address in self._monitored_tokens or
                    token_address in self._blacklisted_tokens):
                    continue
                
                try:
                    # Get initial analysis
                    analysis = await self._analyze_token(token_address, chain)
                    
                    if self._meets_criteria(analysis):
                        discovered_tokens.append({
                            'token_address': token_address,
                            'chain': chain,
                            'symbol': analysis['symbol'],
                            'name': analysis['name'],
                            'liquidity': analysis['liquidity'],
                            'volume_24h': analysis['volume_24h'],
                            'holder_count': analysis['holder_count'],
                            'risk_score': analysis['risk_score'],
                            'discovery_time': datetime.utcnow().isoformat(),
                            'analysis': analysis
                        })
                        
                        # Add to monitored tokens
                        self._monitored_tokens.add(token_address)
                        
                except Exception as e:
                    logger.warning(
                        f"Error analyzing token {token_address}: {str(e)}"
                    )
                    continue
            
            return discovered_tokens
            
        except Exception as e:
            logger.error(f"Error discovering tokens: {str(e)}")
            raise
    
    async def monitor_tokens(self, chain: str) -> List[Dict]:
        """Monitor tracked tokens for significant changes"""
        try:
            alerts = []
            tokens_to_remove = set()
            
            for token_address in self._monitored_tokens:
                try:
                    # Get current analysis
                    current = await self._analyze_token(token_address, chain)
                    
                    # Check for significant changes
                    changes = await self._detect_changes(
                        token_address,
                        chain,
                        current
                    )
                    
                    if changes:
                        alerts.append({
                            'token_address': token_address,
                            'chain': chain,
                            'timestamp': datetime.utcnow().isoformat(),
                            'changes': changes,
                            'current_data': current
                        })
                        
                        # Send alert
                        await self._send_monitoring_alert(
                            token_address,
                            chain,
                            changes
                        )
                    
                    # Check if token still meets criteria
                    if not self._meets_criteria(current):
                        tokens_to_remove.add(token_address)
                        
                except Exception as e:
                    logger.warning(
                        f"Error monitoring token {token_address}: {str(e)}"
                    )
                    continue
            
            # Remove tokens that no longer meet criteria
            self._monitored_tokens -= tokens_to_remove
            
            return alerts
            
        except Exception as e:
            logger.error(f"Error monitoring tokens: {str(e)}")
            raise
    
    async def add_to_watchlist(
        self,
        token_address: str,
        chain: str
    ) -> Dict:
        """Add token to monitoring watchlist"""
        try:
            # Analyze token
            analysis = await self._analyze_token(token_address, chain)
            
            # Add to monitored tokens
            self._monitored_tokens.add(token_address)
            
            return {
                'token_address': token_address,
                'chain': chain,
                'added_time': datetime.utcnow().isoformat(),
                'analysis': analysis
            }
            
        except Exception as e:
            logger.error(f"Error adding token to watchlist: {str(e)}")
            raise
    
    def remove_from_watchlist(self, token_address: str) -> bool:
        """Remove token from monitoring watchlist"""
        try:
            if token_address in self._monitored_tokens:
                self._monitored_tokens.remove(token_address)
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error removing token from watchlist: {str(e)}")
            raise
    
    def get_monitored_tokens(self) -> Set[str]:
        """Get set of currently monitored tokens"""
        return self._monitored_tokens.copy()
    
    async def update_discovery_config(self, config: Dict) -> Dict:
        """Update token discovery configuration"""
        try:
            # Validate config values
            if 'min_liquidity' in config:
                self.discovery_config['min_liquidity'] = Decimal(
                    str(config['min_liquidity'])
                )
            if 'min_holder_count' in config:
                self.discovery_config['min_holder_count'] = int(
                    config['min_holder_count']
                )
            if 'max_holder_concentration' in config:
                self.discovery_config['max_holder_concentration'] = float(
                    config['max_holder_concentration']
                )
            if 'min_daily_volume' in config:
                self.discovery_config['min_daily_volume'] = Decimal(
                    str(config['min_daily_volume'])
                )
            if 'max_risk_score' in config:
                self.discovery_config['max_risk_score'] = float(
                    config['max_risk_score']
                )
                
            return self.discovery_config
            
        except Exception as e:
            logger.error(f"Error updating discovery config: {str(e)}")
            raise
    
    async def update_alert_thresholds(self, thresholds: Dict) -> Dict:
        """Update monitoring alert thresholds"""
        try:
            # Validate threshold values
            if 'price_change' in thresholds:
                self.alert_thresholds['price_change'] = float(
                    thresholds['price_change']
                )
            if 'volume_spike' in thresholds:
                self.alert_thresholds['volume_spike'] = float(
                    thresholds['volume_spike']
                )
            if 'liquidity_drop' in thresholds:
                self.alert_thresholds['liquidity_drop'] = float(
                    thresholds['liquidity_drop']
                )
            if 'holder_change' in thresholds:
                self.alert_thresholds['holder_change'] = float(
                    thresholds['holder_change']
                )
                
            return self.alert_thresholds
            
        except Exception as e:
            logger.error(f"Error updating alert thresholds: {str(e)}")
            raise
    
    async def _analyze_token(self, token_address: str, chain: str) -> Dict:
        """Perform comprehensive token analysis"""
        try:
            # Get market data
            market_data = await self.market_research.get_token_analysis(
                token_address,
                chain
            )
            
            # Get risk assessment
            risk_metrics = await self.risk_scorer.calculate_risk_score(
                token_address,
                chain
            )
            
            return {
                'symbol': market_data['market_data'].get('symbol', 'UNKNOWN'),
                'name': market_data['market_data'].get('name', 'Unknown Token'),
                'liquidity': Decimal(str(
                    market_data['liquidity_data']['total_liquidity']
                )),
                'volume_24h': Decimal(str(
                    market_data['market_data']['volume_24h']
                )),
                'holder_count': market_data['holder_analysis']['total_holders'],
                'holder_concentration': market_data['holder_analysis']['top_10_holdings'],
                'price_usd': Decimal(str(
                    market_data['market_data']['price_usd']
                )),
                'market_cap': Decimal(str(
                    market_data['market_data']['market_cap']
                )),
                'risk_score': risk_metrics.overall_risk,
                'risk_factors': risk_metrics.risk_factors,
                'security_info': market_data['security_info']
            }
            
        except Exception as e:
            logger.error(f"Error analyzing token: {str(e)}")
            raise
    
    def _meets_criteria(self, analysis: Dict) -> bool:
        """Check if token meets discovery criteria"""
        try:
            return (
                analysis['liquidity'] >= self.discovery_config['min_liquidity'] and
                analysis['holder_count'] >= self.discovery_config['min_holder_count'] and
                analysis['holder_concentration'] <= self.discovery_config['max_holder_concentration'] and
                analysis['volume_24h'] >= self.discovery_config['min_daily_volume'] and
                analysis['risk_score'] <= self.discovery_config['max_risk_score'] and
                not analysis['security_info']['is_honeypot']
            )
            
        except Exception as e:
            logger.error(f"Error checking token criteria: {str(e)}")
            return False
    
    async def _detect_changes(
        self,
        token_address: str,
        chain: str,
        current: Dict
    ) -> Optional[List[str]]:
        """Detect significant changes in token metrics"""
        try:
            changes = []
            
            # Get historical data
            historical = await self.market_research.get_token_analysis(
                token_address,
                chain
            )
            
            # Check price change
            price_change = abs(
                (current['price_usd'] - historical['market_data']['price_usd']) /
                historical['market_data']['price_usd']
            )
            if price_change > self.alert_thresholds['price_change']:
                changes.append(
                    f"Price changed by {price_change:.1%}"
                )
            
            # Check volume spike
            volume_change = (
                current['volume_24h'] /
                historical['market_data']['volume_24h']
            )
            if volume_change > self.alert_thresholds['volume_spike']:
                changes.append(
                    f"Volume increased {volume_change:.1f}x"
                )
            
            # Check liquidity drop
            liquidity_change = abs(
                (current['liquidity'] - historical['liquidity_data']['total_liquidity']) /
                historical['liquidity_data']['total_liquidity']
            )
            if liquidity_change > self.alert_thresholds['liquidity_drop']:
                changes.append(
                    f"Liquidity changed by {liquidity_change:.1%}"
                )
            
            # Check holder concentration change
            holder_change = abs(
                current['holder_concentration'] -
                historical['holder_analysis']['top_10_holdings']
            )
            if holder_change > self.alert_thresholds['holder_change']:
                changes.append(
                    f"Holder concentration changed by {holder_change:.1%}"
                )
            
            return changes if changes else None
            
        except Exception as e:
            logger.error(f"Error detecting changes: {str(e)}")
            return None
    
    async def _send_monitoring_alert(
        self,
        token_address: str,
        chain: str,
        changes: List[str]
    ):
        """Send alert for significant token changes"""
        try:
            message = (
                f"⚠️ Token Alert - {chain}:{token_address}\n\n"
                "Significant changes detected:\n" +
                "\n".join(f"• {change}" for change in changes)
            )
            
            await send_alert(
                title="Token Monitor Alert",
                message=message,
                severity="warning"
            )
            
        except Exception as e:
            logger.error(f"Error sending monitoring alert: {str(e)}")
            raise
