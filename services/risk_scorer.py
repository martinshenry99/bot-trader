"""Advanced risk scoring system for evaluating trading opportunities"""
import logging
from typing import Dict, List, Optional
from decimal import Decimal
from dataclasses import dataclass

from integrations.goplus import GoPlusAPI
from integrations.coingecko import CoinGeckoAPI
from db.models.lp_position import LPPosition

logger = logging.getLogger(__name__)

@dataclass
class RiskMetrics:
    """Container for calculated risk metrics"""
    token_score: float
    liquidity_score: float
    volatility_score: float
    market_score: float
    security_score: float
    overall_risk: float
    risk_factors: List[str]
    
    def to_dict(self) -> Dict:
        return {
            'token_score': round(self.token_score, 2),
            'liquidity_score': round(self.liquidity_score, 2),
            'volatility_score': round(self.volatility_score, 2),
            'market_score': round(self.market_score, 2),
            'security_score': round(self.security_score, 2),
            'overall_risk': round(self.overall_risk, 2),
            'risk_factors': self.risk_factors
        }

class RiskScorer:
    """Advanced risk scoring system"""
    
    def __init__(self, goplus_api: GoPlusAPI, coingecko_api: CoinGeckoAPI):
        self.goplus_api = goplus_api
        self.coingecko_api = coingecko_api
        
        # Risk scoring weights
        self.weights = {
            'token': 0.25,
            'liquidity': 0.20,
            'volatility': 0.20,
            'market': 0.15,
            'security': 0.20
        }
        
        # Risk thresholds
        self.thresholds = {
            'high_risk': 0.7,
            'medium_risk': 0.4,
            'low_risk': 0.2
        }
    
    async def calculate_risk_score(
        self,
        token_address: str,
        chain: str,
        lp_data: Optional[LPPosition] = None
    ) -> RiskMetrics:
        """Calculate comprehensive risk score for a token"""
        try:
            # Gather security data
            security_data = await self.goplus_api.get_token_security(chain, token_address)
            
            # Gather market data
            market_data = await self.coingecko_api.get_token_market_data(chain, token_address)
            
            # Calculate individual risk components
            token_score = await self._calculate_token_score(security_data)
            liquidity_score = await self._calculate_liquidity_score(market_data, lp_data)
            volatility_score = self._calculate_volatility_score(market_data)
            market_score = self._calculate_market_score(market_data)
            security_score = self._calculate_security_score(security_data)
            
            # Calculate overall risk score (0-1, higher = riskier)
            overall_risk = (
                token_score * self.weights['token'] +
                liquidity_score * self.weights['liquidity'] +
                volatility_score * self.weights['volatility'] +
                market_score * self.weights['market'] +
                security_score * self.weights['security']
            )
            
            # Identify specific risk factors
            risk_factors = self._identify_risk_factors(
                token_score,
                liquidity_score,
                volatility_score,
                market_score,
                security_score,
                security_data,
                market_data
            )
            
            return RiskMetrics(
                token_score=token_score,
                liquidity_score=liquidity_score,
                volatility_score=volatility_score,
                market_score=market_score,
                security_score=security_score,
                overall_risk=overall_risk,
                risk_factors=risk_factors
            )
            
        except Exception as e:
            logger.error(f"Error calculating risk score: {str(e)}")
            raise
    
    async def _calculate_token_score(self, security_data: Dict) -> float:
        """Calculate token-specific risk score"""
        score = 0.0
        
        # Check contract verification
        if not security_data.get('is_contract_verified'):
            score += 0.3
            
        # Check ownership renounced
        if not security_data.get('is_ownership_renounced'):
            score += 0.2
            
        # Check proxy contract
        if security_data.get('is_proxy'):
            score += 0.1
            
        # Check mint function
        if security_data.get('can_mint'):
            score += 0.2
            
        # Check trading pause function
        if security_data.get('can_pause_trading'):
            score += 0.2
            
        return min(score, 1.0)
    
    async def _calculate_liquidity_score(
        self,
        market_data: Dict,
        lp_data: Optional[LPPosition]
    ) -> float:
        """Calculate liquidity risk score"""
        score = 0.0
        
        # Check total liquidity
        total_liquidity = Decimal(str(market_data.get('total_liquidity', 0)))
        if total_liquidity < 10000:  # Less than $10k
            score += 0.5
        elif total_liquidity < 50000:  # Less than $50k
            score += 0.3
        elif total_liquidity < 100000:  # Less than $100k
            score += 0.1
            
        # Check liquidity distribution
        if lp_data:
            top_holder_share = Decimal(str(lp_data.get('top_holder_share', 0)))
            if top_holder_share > 0.5:  # Over 50% held by top wallet
                score += 0.3
            elif top_holder_share > 0.3:  # Over 30% held by top wallet
                score += 0.2
                
        # Check number of liquidity pairs
        num_pairs = len(market_data.get('liquidity_pairs', []))
        if num_pairs < 2:
            score += 0.2
            
        return min(score, 1.0)
    
    def _calculate_volatility_score(self, market_data: Dict) -> float:
        """Calculate volatility risk score"""
        score = 0.0
        
        # Check price volatility
        price_change_24h = abs(float(market_data.get('price_change_24h', 0)))
        if price_change_24h > 50:  # >50% change
            score += 0.4
        elif price_change_24h > 25:  # >25% change
            score += 0.2
            
        # Check volume volatility
        volume_change_24h = abs(float(market_data.get('volume_change_24h', 0)))
        if volume_change_24h > 200:  # >200% change
            score += 0.3
        elif volume_change_24h > 100:  # >100% change
            score += 0.2
            
        # Check price impact
        price_impact = float(market_data.get('price_impact_1000usd', 0))
        if price_impact > 0.05:  # >5% impact for $1000
            score += 0.3
            
        return min(score, 1.0)
    
    def _calculate_market_score(self, market_data: Dict) -> float:
        """Calculate market risk score"""
        score = 0.0
        
        # Check market cap
        market_cap = float(market_data.get('market_cap', 0))
        if market_cap < 100000:  # <$100k
            score += 0.4
        elif market_cap < 500000:  # <$500k
            score += 0.2
            
        # Check holder distribution
        holders = market_data.get('holder_distribution', {})
        if holders.get('top_10_share', 0) > 0.8:  # Top 10 hold >80%
            score += 0.3
            
        # Check age
        days_old = market_data.get('days_since_launch', 0)
        if days_old < 7:  # Less than a week old
            score += 0.3
        elif days_old < 30:  # Less than a month old
            score += 0.2
            
        return min(score, 1.0)
    
    def _calculate_security_score(self, security_data: Dict) -> float:
        """Calculate security risk score"""
        score = 0.0
        
        # Check for honeypot
        if security_data.get('is_honeypot', False):
            return 1.0
            
        # Check transfer restrictions
        if security_data.get('has_transfer_restrictions'):
            score += 0.3
            
        # Check blacklist function
        if security_data.get('has_blacklist'):
            score += 0.2
            
        # Check anti-bot measures
        if security_data.get('has_antibot'):
            score += 0.1
            
        # Check hidden owner
        if security_data.get('has_hidden_owner'):
            score += 0.4
            
        return min(score, 1.0)
    
    def _identify_risk_factors(
        self,
        token_score: float,
        liquidity_score: float,
        volatility_score: float,
        market_score: float,
        security_score: float,
        security_data: Dict,
        market_data: Dict
    ) -> List[str]:
        """Identify specific risk factors based on scores and data"""
        factors = []
        
        # Token risks
        if not security_data.get('is_contract_verified'):
            factors.append("Unverified contract")
        if not security_data.get('is_ownership_renounced'):
            factors.append("Ownership not renounced")
        if security_data.get('can_mint'):
            factors.append("Token can be minted")
            
        # Liquidity risks
        total_liquidity = Decimal(str(market_data.get('total_liquidity', 0)))
        if total_liquidity < 50000:
            factors.append(f"Low liquidity (${total_liquidity:,.0f})")
            
        # Volatility risks
        price_change_24h = abs(float(market_data.get('price_change_24h', 0)))
        if price_change_24h > 25:
            factors.append(f"High price volatility ({price_change_24h:.1f}%)")
            
        # Market risks
        market_cap = float(market_data.get('market_cap', 0))
        if market_cap < 500000:
            factors.append(f"Low market cap (${market_cap:,.0f})")
            
        # Security risks
        if security_data.get('is_honeypot', False):
            factors.append("HONEYPOT DETECTED")
        if security_data.get('has_blacklist'):
            factors.append("Has blacklist function")
            
        return factors
