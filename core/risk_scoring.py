"""
Risk scoring system for trade validation
"""
from typing import Dict, Any, List, Optional
from decimal import Decimal
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class RiskMetrics:
    """Container for risk metrics"""
    liquidity_score: int  # 0-100
    volatility_score: int  # 0-100  
    contract_score: int  # 0-100
    holder_score: int  # 0-100
    trade_score: int  # 0-100
    overall_score: int  # 0-100
    risk_level: str  # Low, Medium, High, Extreme
    warnings: List[str]

class RiskScorer:
    """Calculates risk scores for trades"""
    
    def __init__(
        self,
        min_liquidity_usd: int = 10000,
        max_volatility_pct: int = 200,
        min_holders: int = 100,
        max_holder_pct: int = 5,
        min_contract_score: int = 70
    ):
        self.min_liquidity_usd = min_liquidity_usd
        self.max_volatility_pct = max_volatility_pct
        self.min_holders = min_holders 
        self.max_holder_pct = max_holder_pct
        self.min_contract_score = min_contract_score

    def calculate_risk_metrics(
        self,
        token_info: Dict[str, Any],
        trade_params: Dict[str, Any]
    ) -> RiskMetrics:
        """Calculate comprehensive risk metrics"""
        
        # Calculate individual scores
        liquidity_score = self._calc_liquidity_score(token_info)
        volatility_score = self._calc_volatility_score(token_info)
        contract_score = self._calc_contract_score(token_info)
        holder_score = self._calc_holder_score(token_info)
        trade_score = self._calc_trade_score(trade_params, token_info)
        
        # Calculate weighted overall score
        overall_score = self._calc_overall_score([
            (liquidity_score, 0.25),  # 25% weight
            (volatility_score, 0.20),  # 20% weight
            (contract_score, 0.25),    # 25% weight
            (holder_score, 0.15),      # 15% weight
            (trade_score, 0.15)        # 15% weight
        ])
        
        # Determine risk level
        risk_level = self._determine_risk_level(overall_score)
        
        # Generate warnings
        warnings = self._generate_risk_warnings(
            token_info,
            trade_params,
            overall_score
        )
        
        return RiskMetrics(
            liquidity_score=liquidity_score,
            volatility_score=volatility_score,
            contract_score=contract_score,
            holder_score=holder_score,
            trade_score=trade_score,
            overall_score=overall_score,
            risk_level=risk_level,
            warnings=warnings
        )
    
    def _calc_liquidity_score(
        self,
        token_info: Dict[str, Any]
    ) -> int:
        """Calculate liquidity risk score (0-100)"""
        try:
            liquidity = Decimal(str(token_info.get('liquidity_usd', 0)))
            
            if liquidity >= self.min_liquidity_usd * 10:
                return 100
            elif liquidity <= self.min_liquidity_usd / 10:
                return 0
            else:
                # Linear score between min/10 and min*10
                score = int(
                    (liquidity - self.min_liquidity_usd/10) /
                    (self.min_liquidity_usd*10 - self.min_liquidity_usd/10) *
                    100
                )
                return max(0, min(100, score))
                
        except Exception as e:
            logger.error(f"Error calculating liquidity score: {e}")
            return 0
    
    def _calc_volatility_score(
        self,
        token_info: Dict[str, Any]
    ) -> int:
        """Calculate volatility risk score (0-100)"""
        try:
            volatility = Decimal(str(token_info.get('volatility_24h', 0)))
            
            if volatility <= self.max_volatility_pct / 4:
                return 100
            elif volatility >= self.max_volatility_pct:
                return 0
            else:
                # Linear score between max/4 and max
                score = int(
                    (self.max_volatility_pct - volatility) /
                    (self.max_volatility_pct - self.max_volatility_pct/4) *
                    100
                )
                return max(0, min(100, score))
                
        except Exception as e:
            logger.error(f"Error calculating volatility score: {e}")
            return 0
    
    def _calc_contract_score(
        self,
        token_info: Dict[str, Any]
    ) -> int:
        """Calculate contract safety score (0-100)"""
        try:
            base_score = 100
            
            # Major red flags
            if token_info.get('is_honeypot'):
                return 0
            if token_info.get('is_blacklisted'):
                return 0
            if token_info.get('cannot_sell'):
                return 0
                
            # Significant concerns
            if token_info.get('is_proxy') and not token_info.get('proxy_verified'):
                base_score -= 40
            if token_info.get('owner_change_balance'):
                base_score -= 30
            if token_info.get('trading_cooldown', 0) > 0:
                base_score -= 20
                
            # Minor concerns    
            if token_info.get('has_external_calls', False):
                base_score -= 10
            if token_info.get('has_loops', False):
                base_score -= 5
                
            return max(0, base_score)
            
        except Exception as e:
            logger.error(f"Error calculating contract score: {e}")
            return 0
    
    def _calc_holder_score(
        self,
        token_info: Dict[str, Any]
    ) -> int:
        """Calculate holder distribution score (0-100)"""
        try:
            holders = token_info.get('holder_count', 0)
            top_holder_pct = Decimal(str(token_info.get('top_holder_pct', 100)))
            
            # Calculate based on holder count
            if holders >= self.min_holders * 10:
                holder_count_score = 100
            elif holders <= self.min_holders / 10:
                holder_count_score = 0
            else:
                holder_count_score = int(
                    (holders - self.min_holders/10) /
                    (self.min_holders*10 - self.min_holders/10) *
                    100
                )
                
            # Calculate based on top holder %
            if top_holder_pct <= self.max_holder_pct:
                distribution_score = 100
            elif top_holder_pct >= self.max_holder_pct * 4:
                distribution_score = 0
            else:
                distribution_score = int(
                    (self.max_holder_pct*4 - top_holder_pct) /
                    (self.max_holder_pct*4 - self.max_holder_pct) *
                    100
                )
                
            # Combined score (40% holder count, 60% distribution)
            return int(
                holder_count_score * 0.4 +
                distribution_score * 0.6
            )
            
        except Exception as e:
            logger.error(f"Error calculating holder score: {e}")
            return 0
    
    def _calc_trade_score(
        self,
        trade_params: Dict[str, Any],
        token_info: Dict[str, Any]
    ) -> int:
        """Calculate trade-specific risk score (0-100)"""
        try:
            base_score = 100
            
            # Check slippage
            slippage = trade_params.get('slippage_bps', 0)
            if slippage > 100:  # > 1%
                base_score -= min(40, (slippage - 100) // 5)
                
            # Check price impact
            amount = Decimal(str(trade_params.get('amount', 0)))
            liquidity = Decimal(str(token_info.get('liquidity_usd', 0)))
            if liquidity > 0:
                impact = (amount / liquidity) * 10000  # bps
                if impact > 100:  # > 1%
                    base_score -= min(30, int(impact) // 10)
                    
            # Check wallet exposure
            wallet_info = trade_params.get('wallet_info', {})
            total_value = Decimal(str(wallet_info.get('total_value', 0)))
            if total_value > 0:
                exposure = (amount / total_value) * 100
                if exposure > 5:  # > 5%
                    base_score -= min(30, int(exposure * 2))
                    
            return max(0, base_score)
            
        except Exception as e:
            logger.error(f"Error calculating trade score: {e}")
            return 0
    
    def _calc_overall_score(
        self,
        weighted_scores: List[tuple[int, float]]
    ) -> int:
        """Calculate weighted overall risk score"""
        try:
            total_score = 0
            total_weight = 0
            
            for score, weight in weighted_scores:
                total_score += score * weight
                total_weight += weight
                
            if total_weight > 0:
                return int(total_score / total_weight)
            return 0
            
        except Exception as e:
            logger.error(f"Error calculating overall score: {e}")
            return 0
    
    def _determine_risk_level(
        self,
        overall_score: int
    ) -> str:
        """Determine risk level from overall score"""
        if overall_score >= 80:
            return "Low"
        elif overall_score >= 60:
            return "Medium"
        elif overall_score >= 40:
            return "High"
        else:
            return "Extreme"
    
    def _generate_risk_warnings(
        self,
        token_info: Dict[str, Any],
        trade_params: Dict[str, Any],
        overall_score: int
    ) -> List[str]:
        """Generate detailed risk warnings"""
        warnings = []
        
        # Liquidity warnings
        liquidity = Decimal(str(token_info.get('liquidity_usd', 0)))
        if liquidity < self.min_liquidity_usd:
            warnings.append(
                f"⚠️ Low liquidity: ${liquidity:,.2f} < "
                f"${self.min_liquidity_usd:,.2f}"
            )
            
        # Volatility warnings
        volatility = Decimal(str(token_info.get('volatility_24h', 0)))
        if volatility > self.max_volatility_pct:
            warnings.append(
                f"⚠️ High volatility: {volatility}% > "
                f"{self.max_volatility_pct}%"
            )
            
        # Contract warnings
        if token_info.get('is_proxy') and not token_info.get('proxy_verified'):
            warnings.append("⚠️ Unverified proxy contract")
            
        if token_info.get('owner_change_balance'):
            warnings.append("⚠️ Owner can modify balances")
            
        if token_info.get('trading_cooldown', 0) > 0:
            warnings.append(
                f"⚠️ Trading cooldown: "
                f"{token_info['trading_cooldown']}s"
            )
            
        # Holder warnings
        holders = token_info.get('holder_count', 0)
        if holders < self.min_holders:
            warnings.append(
                f"⚠️ Low holder count: {holders} < "
                f"{self.min_holders}"
            )
            
        top_holder_pct = Decimal(str(token_info.get('top_holder_pct', 0)))
        if top_holder_pct > self.max_holder_pct:
            warnings.append(
                f"⚠️ High concentration: Top holder "
                f"owns {top_holder_pct}%"
            )
            
        # Overall risk warning
        if overall_score < 60:
            warnings.append(
                f"⚠️ High risk trade: Overall score "
                f"{overall_score}/100"
            )
            
        return warnings
