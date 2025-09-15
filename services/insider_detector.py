
"""
Insider trading detection and analysis module
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Set
from decimal import Decimal
import time
import logging
from datetime import datetime, timedelta
import networkx as nx
from functools import lru_cache
from utils.cache import cache_result
from services.covalent import CovalentService
from services.helius import HeliusService

logger = logging.getLogger(__name__)

@dataclass
class InsiderSignal:
    """Detected insider trading signal"""
    wallet: str
    signal_type: str
    confidence: float  # 0-1 scale
    evidence: Dict
    timestamp: int

@dataclass
class InsiderScore:
    """Comprehensive insider score"""
    score: float  # 0-100 scale
    signals: List[InsiderSignal]
    wallet_cluster: Set[str]
    deployer_proximity: float  # 0-1 scale
    early_trading_score: float  # 0-1 scale

class InsiderDetector:
    """Insider trading detection system"""
    
    def __init__(self, covalent: CovalentService, helius: HeliusService):
        self.covalent = covalent
        self.helius = helius
        
        # Configuration
        self.settings = {
            'insider_min_score': 70,  # Minimum score to flag as insider
            'insider_early_window_minutes': 30,  # Window for early trading
            'insider_min_repeat': 3,  # Minimum repeats for pattern
            'min_profit_multiplier': 2.0,  # Minimum profit for significance
            'max_deployer_distance': 3,  # Max hops from deployer
            'min_cluster_size': 3  # Minimum size for suspicious cluster
        }
        
        # Cache settings
        self._cache_ttl = 3600  # 1 hour cache
        self._scan_results = {}
    
    @cache_result(ttl=3600)
    async def analyze_wallet(self, wallet: str, chain: str) -> InsiderScore:
        """Analyze wallet for insider trading signals"""
        try:
            # Get trading history
            if chain == "solana":
                history = await self.helius.get_wallet_history(wallet)
            else:
                history = await self.covalent.get_wallet_history(wallet)
            
            signals = []
            
            # Check deployer proximity
            deployer_prox = await self._check_deployer_proximity(wallet, chain)
            if deployer_prox > 0.5:
                signals.append(InsiderSignal(
                    wallet=wallet,
                    signal_type="deployer_proximity",
                    confidence=deployer_prox,
                    evidence={"distance": deployer_prox},
                    timestamp=int(time.time())
                ))
            
            # Analyze early trading patterns
            early_score = await self._analyze_early_trading(history)
            if early_score > 0.7:
                signals.append(InsiderSignal(
                    wallet=wallet,
                    signal_type="early_trading",
                    confidence=early_score,
                    evidence={"score": early_score},
                    timestamp=int(time.time())
                ))
            
            # Check repeated multipliers
            mult_score = self._check_repeated_multipliers(history)
            if mult_score > 0.6:
                signals.append(InsiderSignal(
                    wallet=wallet,
                    signal_type="repeated_multipliers",
                    confidence=mult_score,
                    evidence={"score": mult_score},
                    timestamp=int(time.time())
                ))
            
            # Get trading cluster
            cluster = await self._get_trading_cluster(wallet, chain)
            cluster_score = len(cluster) / self.settings['min_cluster_size']
            if cluster_score > 1:
                signals.append(InsiderSignal(
                    wallet=wallet,
                    signal_type="cluster_trading",
                    confidence=min(cluster_score / 2, 1.0),
                    evidence={"cluster_size": len(cluster)},
                    timestamp=int(time.time())
                ))
            
            # Check suspicious inflows
            inflow_score = await self._check_suspicious_inflows(wallet, chain)
            if inflow_score > 0.5:
                signals.append(InsiderSignal(
                    wallet=wallet,
                    signal_type="suspicious_inflows",
                    confidence=inflow_score,
                    evidence={"score": inflow_score},
                    timestamp=int(time.time())
                ))
            
            # Calculate final score
            final_score = self._calculate_insider_score(
                signals,
                deployer_prox,
                early_score
            )
            
            return InsiderScore(
                score=final_score,
                signals=signals,
                wallet_cluster=cluster,
                deployer_proximity=deployer_prox,
                early_trading_score=early_score
            )
            
        except Exception as e:
            logger.error(f"Error analyzing wallet for insider trading: {str(e)}")
            raise
    
    async def _check_deployer_proximity(self, wallet: str, chain: str) -> float:
        """Check proximity to token deployers"""
        try:
            # Get recent token deployments
            if chain == "solana":
                deployments = await self.helius.get_token_deployments(days=7)
            else:
                deployments = await self.covalent.get_token_deployments(chain, days=7)
            
            closest_distance = float('inf')
            
            for deployment in deployments:
                deployer = deployment['deployer']
                distance = await self._calculate_wallet_distance(
                    wallet,
                    deployer,
                    chain
                )
                
                if distance < closest_distance:
                    closest_distance = distance
            
            if closest_distance == float('inf'):
                return 0.0
            
            # Convert distance to proximity score
            proximity = max(
                0,
                1 - (closest_distance / self.settings['max_deployer_distance'])
            )
            
            return proximity
            
        except Exception as e:
            logger.error(f"Error checking deployer proximity: {str(e)}")
            return 0.0
    
    async def _analyze_early_trading(self, history: List[Dict]) -> float:
        """Analyze early trading patterns"""
        try:
            early_trades = 0
            profitable_early = 0
            total_trades = len(history)
            
            if not total_trades:
                return 0.0
            
            early_window = timedelta(
                minutes=self.settings['insider_early_window_minutes']
            )
            
            for trade in history:
                token_age = trade.get('token_age_minutes', float('inf'))
                if token_age <= self.settings['insider_early_window_minutes']:
                    early_trades += 1
                    
                    if trade.get('profit_percentage', 0) > 50:
                        profitable_early += 1
            
            if not early_trades:
                return 0.0
            
            # Calculate early trading score
            base_score = early_trades / total_trades
            profit_score = profitable_early / early_trades
            
            return (base_score * 0.4 + profit_score * 0.6)
            
        except Exception as e:
            logger.error(f"Error analyzing early trading: {str(e)}")
            return 0.0
    
    def _check_repeated_multipliers(self, history: List[Dict]) -> float:
        """Check for repeated high profit multipliers"""
        try:
            high_profit_trades = 0
            consecutive = 0
            max_consecutive = 0
            
            for trade in history:
                profit = trade.get('profit_percentage', 0)
                
                if profit >= 100:  # 2x or more
                    high_profit_trades += 1
                    consecutive += 1
                    max_consecutive = max(max_consecutive, consecutive)
                else:
                    consecutive = 0
            
            if not history:
                return 0.0
            
            # Calculate multiplier score
            frequency = high_profit_trades / len(history)
            streak_score = max_consecutive / self.settings['insider_min_repeat']
            
            return (frequency * 0.4 + streak_score * 0.6)
            
        except Exception as e:
            logger.error(f"Error checking repeated multipliers: {str(e)}")
            return 0.0
    
    @cache_result(ttl=3600)
    async def _get_trading_cluster(self, wallet: str, chain: str) -> Set[str]:
        """Get related trading cluster"""
        try:
            # Get transaction history
            if chain == "solana":
                txs = await self.helius.get_wallet_history(wallet, days=7)
            else:
                txs = await self.covalent.get_wallet_history(wallet, days=7)
            
            # Build trading graph
            G = nx.Graph()
            
            for tx in txs:
                from_addr = tx['from_address']
                to_addr = tx['to_address']
                
                G.add_edge(from_addr, to_addr)
            
            # Get connected component
            if not G.has_node(wallet):
                return set()
                
            cluster = nx.node_connected_component(G, wallet)
            
            # Filter by minimum size
            if len(cluster) < self.settings['min_cluster_size']:
                return set()
            
            return cluster
            
        except Exception as e:
            logger.error(f"Error getting trading cluster: {str(e)}")
            return set()
    
    async def _check_suspicious_inflows(self, wallet: str, chain: str) -> float:
        """Check for suspicious fund inflows"""
        try:
            # Get recent inflows
            if chain == "solana":
                transfers = await self.helius.get_token_transfers(wallet, days=7)
            else:
                transfers = await self.covalent.get_token_transfers(wallet, days=7)
            
            suspicious_count = 0
            total_transfers = len(transfers)
            
            if not total_transfers:
                return 0.0
            
            for transfer in transfers:
                # Check for suspicious patterns
                if transfer.get('from_new_wallet', False):
                    suspicious_count += 1
                if transfer.get('mixed_funds', False):
                    suspicious_count += 1
                if transfer.get('tornado_cash_proximity', False):
                    suspicious_count += 2
            
            return min(suspicious_count / (total_transfers * 2), 1.0)
            
        except Exception as e:
            logger.error(f"Error checking suspicious inflows: {str(e)}")
            return 0.0
    
    @lru_cache(maxsize=1000)
    async def _calculate_wallet_distance(
        self,
        wallet1: str,
        wallet2: str,
        chain: str
    ) -> int:
        """Calculate transaction distance between wallets"""
        try:
            if chain == "solana":
                path = await self.helius.find_wallet_path(wallet1, wallet2)
            else:
                path = await self.covalent.find_wallet_path(wallet1, wallet2)
            
            return len(path) - 1 if path else float('inf')
            
        except Exception as e:
            logger.error(f"Error calculating wallet distance: {str(e)}")
            return float('inf')
    
    def _calculate_insider_score(
        self,
        signals: List[InsiderSignal],
        deployer_prox: float,
        early_score: float
    ) -> float:
        """Calculate final insider trading score"""
        if not signals:
            return 0.0
        
        # Base score from signals
        signal_scores = [s.confidence for s in signals]
        base_score = sum(signal_scores) / len(signal_scores) * 60
        
        # Boost from key metrics
        deployer_boost = deployer_prox * 25
        early_boost = early_score * 15
        
        final_score = base_score + deployer_boost + early_boost
        
        return min(final_score, 100.0)
