"""
Token and Wallet Risk Scoring System
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from decimal import Decimal
import logging
from services.goplus import GoPlusService
from services.helius import HeliusService
from services.covalent import CovalentService
from core.secure_wallet import get_lp_info, simulate_honeypot
from utils.cache import cache_result

logger = logging.getLogger(__name__)

@dataclass
class RiskFactors:
    """Risk factors used in scoring calculation"""
    is_honeypot: bool = False
    liquidity_usd: Decimal = Decimal('0')
    lp_locked: bool = False
    owner_concentration: Decimal = Decimal('0')  # As percentage
    blacklisted: bool = False
    suspicious_flags: List[str] = None
    insider_score: Decimal = Decimal('0')  # 0-100 scale

@dataclass
class RiskScore:
    """Complete risk assessment result"""
    score: int  # 0-100, higher is riskier
    factors: RiskFactors
    warnings: List[str]
    chain: str
    timestamp: int

class RiskScoringService:
    """Token and wallet risk scoring service"""
    
    def __init__(self, goplus: GoPlusService, helius: HeliusService, covalent: CovalentService):
        self.goplus = goplus
        self.helius = helius
        self.covalent = covalent
        
        # Scoring weights (must sum to 100)
        self.weights = {
            'honeypot': 30,       # Binary but heavily weighted
            'liquidity': 20,      # Based on USD thresholds
            'lp_lock': 10,        # Binary
            'concentration': 15,   # Linear scale
            'blacklist': 15,      # Binary
            'suspicious': 5,       # Per-flag penalty
            'insider': 5          # From insider detection module
        }
        
        # Thresholds
        self.min_liquidity = Decimal('10000')  # $10k min
        self.safe_liquidity = Decimal('100000')  # $100k considered safe
        self.high_concentration = Decimal('50')  # 50% ownership is concerning
        
        self._validate_weights()
    
    def _validate_weights(self):
        """Ensure weights sum to 100"""
        total = sum(self.weights.values())
        if total != 100:
            raise ValueError(f"Risk scoring weights must sum to 100, got {total}")
    
    @cache_result(ttl=300)  # Cache for 5 minutes
    async def get_token_risk_score(self, token_address: str, chain: str) -> RiskScore:
        """Calculate comprehensive risk score for a token"""
        factors = RiskFactors()
        warnings = []
        
        try:
            # Get honeypot status
            factors.is_honeypot = await simulate_honeypot(token_address, chain)
            if factors.is_honeypot:
                warnings.append("Token appears to be a honeypot - selling may be restricted")
            
            # Get liquidity info
            lp_info = await get_lp_info(token_address, chain)
            factors.liquidity_usd = lp_info.liquidity_usd
            factors.lp_locked = lp_info.is_locked
            
            if factors.liquidity_usd < self.min_liquidity:
                warnings.append(f"Very low liquidity (${factors.liquidity_usd:,.2f})")
            
            # Get ownership concentration
            if chain == "solana":
                holder_info = await self.helius.get_token_holders(token_address)
            else:
                holder_info = await self.covalent.get_token_holders(token_address, chain)
            
            factors.owner_concentration = holder_info.top_holder_percentage
            if factors.owner_concentration > self.high_concentration:
                warnings.append(f"High ownership concentration ({factors.owner_concentration:.1f}%)")
            
            # Check GoPlus security info
            security = await self.goplus.check_token_security(token_address, chain)
            factors.blacklisted = security.is_blacklisted
            factors.suspicious_flags = security.suspicious_flags
            
            if factors.blacklisted:
                warnings.append("Token is blacklisted")
            for flag in factors.suspicious_flags:
                warnings.append(f"Suspicious: {flag}")
            
            # Calculate final score
            score = self._calculate_score(factors)
            
            return RiskScore(
                score=score,
                factors=factors,
                warnings=warnings,
                chain=chain,
                timestamp=int(time.time())
            )
            
        except Exception as e:
            logger.error(f"Error calculating risk score: {str(e)}")
            raise
    
    @cache_result(ttl=300)  # Cache for 5 minutes
    async def get_wallet_risk_score(self, wallet_address: str, chain: str) -> RiskScore:
        """Calculate risk score for a wallet address"""
        factors = RiskFactors()
        warnings = []
        
        try:
            # Get transaction history and trading patterns
            if chain == "solana":
                tx_history = await self.helius.get_wallet_history(wallet_address)
            else:
                tx_history = await self.covalent.get_wallet_history(wallet_address, chain)
            
            # Analyze trading patterns
            analysis = self._analyze_trading_patterns(tx_history)
            factors.suspicious_flags = analysis.suspicious_flags
            factors.insider_score = analysis.insider_likelihood
            
            for flag in factors.suspicious_flags:
                warnings.append(f"Suspicious activity: {flag}")
            
            if factors.insider_score > 70:
                warnings.append(f"High likelihood of insider trading ({factors.insider_score:.1f}%)")
            
            # Get wallet concentration
            portfolio = await self._get_portfolio_concentration(wallet_address, chain)
            factors.owner_concentration = portfolio.concentration
            
            if factors.owner_concentration > self.high_concentration:
                warnings.append(f"Highly concentrated portfolio ({factors.owner_concentration:.1f}%)")
            
            # Calculate final score
            score = self._calculate_wallet_score(factors)
            
            return RiskScore(
                score=score,
                factors=factors,
                warnings=warnings,
                chain=chain,
                timestamp=int(time.time())
            )
            
        except Exception as e:
            logger.error(f"Error calculating wallet risk score: {str(e)}")
            raise
    
    def _calculate_score(self, factors: RiskFactors) -> int:
        """Calculate final risk score from factors"""
        score = 0
        
        # Honeypot (binary but weighted)
        if factors.is_honeypot:
            score += self.weights['honeypot']
        
        # Liquidity score (0-20 based on thresholds)
        if factors.liquidity_usd <= self.min_liquidity:
            score += self.weights['liquidity']
        elif factors.liquidity_usd < self.safe_liquidity:
            # Linear interpolation between min and safe
            liquidity_score = (
                (self.safe_liquidity - factors.liquidity_usd) /
                (self.safe_liquidity - self.min_liquidity) *
                self.weights['liquidity']
            )
            score += liquidity_score
        
        # LP lock status (binary)
        if not factors.lp_locked:
            score += self.weights['lp_lock']
        
        # Owner concentration (linear 0-15)
        concentration_score = (
            factors.owner_concentration /
            self.high_concentration *
            self.weights['concentration']
        )
        score += min(concentration_score, self.weights['concentration'])
        
        # Blacklist status (binary)
        if factors.blacklisted:
            score += self.weights['blacklist']
        
        # Suspicious flags (2.5 points per flag, max 5)
        if factors.suspicious_flags:
            flag_score = len(factors.suspicious_flags) * 2.5
            score += min(flag_score, self.weights['suspicious'])
        
        # Insider score (scaled from 0-5)
        insider_score = factors.insider_score / 100 * self.weights['insider']
        score += insider_score
        
        return min(int(score), 100)
    
    def _calculate_wallet_score(self, factors: RiskFactors) -> int:
        """Calculate wallet risk score"""
        score = 0
        
        # Concentration risk (0-30)
        concentration_score = (
            factors.owner_concentration /
            self.high_concentration * 30
        )
        score += min(concentration_score, 30)
        
        # Suspicious flags (5 points per flag, max 40)
        if factors.suspicious_flags:
            flag_score = len(factors.suspicious_flags) * 5
            score += min(flag_score, 40)
        
        # Insider score (0-30)
        insider_score = factors.insider_score / 100 * 30
        score += insider_score
        
        return min(int(score), 100)
    
    async def _get_portfolio_concentration(self, wallet: str, chain: str) -> Dict:
        """Calculate portfolio concentration metrics"""
        if chain == "solana":
            portfolio = await self.helius.get_token_accounts(wallet)
        else:
            portfolio = await self.covalent.get_token_balances(wallet, chain)
        
        total_value = sum(token.usd_value for token in portfolio)
        if total_value == 0:
            return {'concentration': Decimal('0')}
        
        # Get highest value holding as percentage
        max_value = max(token.usd_value for token in portfolio)
        concentration = (max_value / total_value) * 100
        
        return {'concentration': concentration}
    
    def _analyze_trading_patterns(self, history: List[Dict]) -> Dict:
        """Analyze wallet trading patterns for suspicious activity"""
        flags = []
        insider_score = Decimal('0')
        
        # Sample period stats
        num_trades = len(history)
        if num_trades == 0:
            return {'suspicious_flags': [], 'insider_likelihood': insider_score}
        
        # Look for patterns
        quick_flips = 0
        large_wins = 0
        early_buys = 0
        
        for tx in history:
            # Quick flips (buy/sell within 5 minutes)
            if tx.get('flip_time_minutes', float('inf')) < 5:
                quick_flips += 1
            
            # Large gains (>50% in single trade)
            if tx.get('profit_percentage', 0) > 50:
                large_wins += 1
            
            # Early buys (within first hour of trading)
            if tx.get('token_age_hours', float('inf')) < 1:
                early_buys += 1
        
        # Calculate suspicious patterns
        if quick_flips / num_trades > 0.3:
            flags.append("Frequent quick flips")
            insider_score += 20
        
        if large_wins / num_trades > 0.2:
            flags.append("Unusually high win rate")
            insider_score += 30
        
        if early_buys / num_trades > 0.4:
            flags.append("Frequent early position entry")
            insider_score += 40
        
        return {
            'suspicious_flags': flags,
            'insider_likelihood': min(insider_score, Decimal('100'))
        }
