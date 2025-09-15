"""
Cross-chain portfolio aggregation service
"""

import logging
from typing import Dict, List, Optional
from decimal import Decimal
from datetime import datetime, timedelta
import asyncio

from services.chain_manager import ChainManager
from handlers.key_management import KeyManager
from db.models import UserWallet, TokenBalance
from utils.cache import TTLCache
from utils.price_utils import format_usd, calculate_change

logger = logging.getLogger(__name__)

class PortfolioManager:
    """
    Cross-chain portfolio management and aggregation service.
    Supports ETH, BSC, and SOL chains.
    """
    
    def __init__(
        self,
        chain_manager: ChainManager,
        key_manager: KeyManager,
        cache_ttl: int = 300  # 5 minutes
    ):
        self.chain_manager = chain_manager
        self.key_manager = key_manager
        self.cache = TTLCache(ttl=cache_ttl)
        
        # Supported chains
        self.chains = ['ethereum', 'bsc', 'solana']
        
        # Cache settings
        self._portfolio_cache = {}
        self._last_update = {}
        
    async def get_portfolio_summary(
        self,
        user_id: int,
        force_refresh: bool = False
    ) -> Dict:
        """
        Get aggregated portfolio summary across all chains
        """
        cache_key = f"portfolio:{user_id}"
        
        # Check cache unless force refresh requested
        if (not force_refresh and
            cache_key in self._portfolio_cache and
            cache_key in self._last_update and
            datetime.now() - self._last_update[cache_key] <
            timedelta(seconds=300)):  # 5 minute cache
            return self._portfolio_cache[cache_key]
            
        # Get user wallets
        wallets = await UserWallet.get_by_user(user_id)
        if not wallets:
            return {
                'total_value_usd': Decimal('0'),
                'chains': {},
                'top_positions': [],
                'performance': {
                    '24h': Decimal('0'),
                    '7d': Decimal('0'),
                    '30d': Decimal('0')
                }
            }
            
        # Get balances for each chain in parallel
        tasks = []
        for wallet in wallets:
            tasks.append(
                self._get_chain_portfolio(
                    wallet.chain,
                    wallet.address
                )
            )
            
        chain_portfolios = await asyncio.gather(*tasks)
        
        # Aggregate results
        total_value = Decimal('0')
        all_positions = []
        chain_values = {}
        
        for portfolio, chain in zip(chain_portfolios, self.chains):
            if portfolio:
                total_value += portfolio['total_value_usd']
                chain_values[chain] = portfolio['total_value_usd']
                all_positions.extend(portfolio['positions'])
                
        # Sort positions by value
        all_positions.sort(
            key=lambda x: x['value_usd'],
            reverse=True
        )
        
        # Calculate chain distribution
        distribution = {
            chain: (value / total_value * 100 if total_value > 0 else 0)
            for chain, value in chain_values.items()
        }
        
        # Get historical performance
        performance = await self._get_portfolio_performance(
            user_id,
            total_value
        )
        
        summary = {
            'total_value_usd': total_value,
            'chains': {
                chain: {
                    'value_usd': value,
                    'percentage': distribution[chain]
                }
                for chain, value in chain_values.items()
            },
            'top_positions': all_positions[:5],  # Top 5 positions
            'performance': performance,
            'risk_metrics': await self._calculate_risk_metrics(all_positions),
            'updated_at': datetime.now().isoformat()
        }
        
        # Update cache
        self._portfolio_cache[cache_key] = summary
        self._last_update[cache_key] = datetime.now()
        
        return summary
        
    async def _get_chain_portfolio(
        self,
        chain: str,
        address: str
    ) -> Optional[Dict]:
        """Get portfolio data for a specific chain"""
        try:
            # Get token balances
            balances = await self.chain_manager.get_token_accounts(
                chain,
                address
            )
            
            if not balances:
                return None
                
            total_value = Decimal('0')
            positions = []
            
            for balance in balances:
                if balance.amount > 0:
                    # Get token info
                    token_info = await self.chain_manager.get_token_info(
                        chain,
                        balance.token
                    )
                    
                    if token_info:
                        value_usd = balance.usd_value
                        total_value += value_usd
                        
                        # Add position details
                        positions.append({
                            'token': token_info['symbol'],
                            'chain': chain,
                            'amount': balance.amount,
                            'value_usd': value_usd,
                            'token_address': balance.token,
                            'price_usd': value_usd / balance.amount,
                            '24h_change': token_info.get('price_change_24h', 0)
                        })
                        
            return {
                'total_value_usd': total_value,
                'positions': positions
            }
            
        except Exception as e:
            logger.error(
                f"Error getting {chain} portfolio: {str(e)}"
            )
            return None
            
    async def _get_portfolio_performance(
        self,
        user_id: int,
        current_value: Decimal
    ) -> Dict:
        """Calculate portfolio performance metrics"""
        # Get historical snapshots
        snapshots = await self._get_historical_snapshots(user_id)
        
        performance = {}
        periods = {
            '24h': timedelta(days=1),
            '7d': timedelta(days=7),
            '30d': timedelta(days=30)
        }
        
        for period, delta in periods.items():
            timestamp = datetime.now() - delta
            historical_value = self._get_snapshot_value(
                snapshots,
                timestamp
            )
            
            if historical_value:
                change = calculate_change(
                    historical_value,
                    current_value
                )
                performance[period] = change
            else:
                performance[period] = Decimal('0')
                
        return performance
        
    async def _calculate_risk_metrics(
        self,
        positions: List[Dict]
    ) -> Dict:
        """Calculate portfolio risk metrics"""
        if not positions:
            return {
                'concentration_risk': 0,
                'volatility_risk': 0,
                'chain_risk': 0,
                'overall_risk': 0
            }
            
        total_value = sum(p['value_usd'] for p in positions)
        
        # Calculate concentration risk
        max_position_pct = max(
            p['value_usd'] / total_value * 100
            for p in positions
        )
        
        concentration_risk = min(max_position_pct / 20, 1) * 100
        
        # Calculate volatility risk
        volatility_risk = sum(
            abs(p.get('24h_change', 0)) * (p['value_usd'] / total_value)
            for p in positions
        )
        
        # Calculate chain risk
        chain_values = {}
        for p in positions:
            chain = p['chain']
            if chain not in chain_values:
                chain_values[chain] = 0
            chain_values[chain] += p['value_usd']
            
        max_chain_pct = max(
            value / total_value * 100
            for value in chain_values.values()
        )
        
        chain_risk = min(max_chain_pct / 50, 1) * 100
        
        # Calculate overall risk score
        overall_risk = (
            concentration_risk * 0.4 +
            volatility_risk * 0.3 +
            chain_risk * 0.3
        )
        
        return {
            'concentration_risk': concentration_risk,
            'volatility_risk': volatility_risk,
            'chain_risk': chain_risk,
            'overall_risk': overall_risk
        }
        
    async def _get_historical_snapshots(
        self,
        user_id: int
    ) -> List[Dict]:
        """Get historical portfolio snapshots"""
        # This would typically fetch from a time-series database
        # For now, we'll return mock data
        return []
        
    def _get_snapshot_value(
        self,
        snapshots: List[Dict],
        timestamp: datetime
    ) -> Optional[Decimal]:
        """Get portfolio value from historical snapshot"""
        # Find closest snapshot
        if not snapshots:
            return None
            
        closest = min(
            snapshots,
            key=lambda x: abs(x['timestamp'] - timestamp)
        )
        
        # Only use if within 1 hour of target time
        if abs(closest['timestamp'] - timestamp) <= timedelta(hours=1):
            return closest['value']
            
        return None
        
    async def update_portfolio_tracking(
        self,
        user_id: int,
        transaction: Dict
    ) -> None:
        """Update portfolio tracking after transaction"""
        try:
            # Get current portfolio
            portfolio = await self.get_portfolio_summary(
                user_id,
                force_refresh=True
            )
            
            # Store snapshot
            await self._store_portfolio_snapshot(
                user_id,
                portfolio
            )
            
            # Update token balance
            await TokenBalance.update_balance(
                user_id=user_id,
                chain=transaction['chain'],
                token_address=transaction['token'],
                amount=transaction['amount'],
                price_usd=transaction['price_usd']
            )
            
        except Exception as e:
            logger.error(
                f"Error updating portfolio tracking: {str(e)}"
            )
            
    async def _store_portfolio_snapshot(
        self,
        user_id: int,
        portfolio: Dict
    ) -> None:
        """Store portfolio snapshot for historical tracking"""
        # This would typically store in a time-series database
        # Implementation depends on chosen database solution
        pass
