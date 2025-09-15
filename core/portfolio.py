"""
Enhanced portfolio management with cross-chain aggregation
"""
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging
from decimal import Decimal
from collections import defaultdict

from core.cache_manager import CacheManager
from core.multicall import MulticallHelper
from integrations.coingecko import CoinGeckoAPI
from integrations.helius import HeliusAPI

logger = logging.getLogger(__name__)

class PortfolioManager:
    """Manages cross-chain portfolio tracking and analysis"""
    
    def __init__(
        self,
        cache: CacheManager,
        coingecko: CoinGeckoAPI,
        helius: HeliusAPI,
        multicall: Dict[str, MulticallHelper]
    ):
        self.cache = cache
        self.coingecko = coingecko
        self.helius = helius
        self.multicall = multicall  # Chain ID -> MulticallHelper
        
        # Price cache
        self._price_cache = {}
        self._last_portfolio = None
    
    async def get_portfolio_summary(
        self,
        wallet_addresses: Dict[str, List[str]]  # Chain -> [addresses]
    ) -> Dict[str, Any]:
        """Get comprehensive portfolio summary across chains"""
        try:
            # Try cache first
            cache_key = f"portfolio:summary:{str(wallet_addresses)}"
            cached = await self.cache.get(cache_key, 'portfolio')
            if cached:
                return cached
            
            # Initialize portfolio data
            portfolio = {
                'total_value': 0,
                'daily_change': 0,
                'chains': {},
                'tokens': [],
                'top_holdings': {
                    'tokens': [],
                    'percentage': 0
                }
            }
            
            # Track total value for percentage calculations
            total_value = Decimal('0')
            all_tokens = []
            
            # Process each chain
            for chain, addresses in wallet_addresses.items():
                chain_data = await self._get_chain_portfolio(
                    chain,
                    addresses
                )
                
                portfolio['chains'][chain] = {
                    'value': float(chain_data['total_value']),
                    'change_24h': chain_data['change_24h'],
                    'token_count': len(chain_data['tokens'])
                }
                
                total_value += Decimal(str(chain_data['total_value']))
                all_tokens.extend(chain_data['tokens'])
            
            # Calculate chain percentages
            for chain_data in portfolio['chains'].values():
                chain_data['percentage'] = float(
                    Decimal(str(chain_data['value'])) / total_value * 100
                ) if total_value > 0 else 0
            
            # Sort tokens by value
            all_tokens.sort(
                key=lambda x: x['value_usd'],
                reverse=True
            )
            
            # Calculate concentration risk
            top_3_value = sum(
                Decimal(str(t['value_usd']))
                for t in all_tokens[:3]
            )
            portfolio['top_holdings'] = {
                'tokens': [
                    {
                        'symbol': t['symbol'],
                        'value_usd': t['value_usd'],
                        'percentage': float(
                            Decimal(str(t['value_usd'])) / total_value * 100
                        ) if total_value > 0 else 0
                    }
                    for t in all_tokens[:3]
                ],
                'percentage': float(
                    top_3_value / total_value * 100
                ) if total_value > 0 else 0
            }
            
            # Calculate total portfolio stats
            portfolio.update({
                'total_value': float(total_value),
                'token_count': len(all_tokens),
                'daily_change': self._calculate_weighted_change(
                    [
                        (
                            Decimal(str(chain['value'])),
                            Decimal(str(chain['change_24h']))
                        )
                        for chain in portfolio['chains'].values()
                    ]
                ),
                'tokens': all_tokens
            })
            
            # Cache the result
            await self.cache.set(cache_key, portfolio, 'portfolio')
            self._last_portfolio = portfolio
            
            return portfolio
            
        except Exception as e:
            logger.error(f"Error getting portfolio summary: {e}")
            return self._last_portfolio or {
                'error': 'Failed to fetch portfolio data',
                'total_value': 0,
                'chains': {}
            }
    
    async def _get_chain_portfolio(
        self,
        chain: str,
        addresses: List[str]
    ) -> Dict[str, Any]:
        """Get portfolio data for a specific chain"""
        if chain in ('ETH', 'BSC'):
            return await self._get_evm_portfolio(chain, addresses)
        elif chain == 'SOL':
            return await self._get_solana_portfolio(addresses)
        else:
            raise ValueError(f"Unsupported chain: {chain}")
    
    async def _get_evm_portfolio(
        self,
        chain: str,
        addresses: List[str]
    ) -> Dict[str, Any]:
        """Get EVM chain portfolio data using multicall"""
        try:
            multicall = self.multicall[chain]
            all_tokens = []
            total_value = Decimal('0')
            change_24h = Decimal('0')
            
            for address in addresses:
                # Get token balances and metadata
                token_info = await multicall.batch_token_info(
                    await self._get_tracked_tokens(chain),
                    address
                )
                
                # Get token prices
                prices = await self._get_token_prices(
                    list(token_info.keys()),
                    chain
                )
                
                # Calculate token values
                for token, info in token_info.items():
                    if info['balance'] > 0:
                        price = Decimal(str(prices.get(token, {}).get('usd', 0)))
                        value = (
                            Decimal(str(info['balance'])) *
                            price /
                            Decimal(f"1e{info['decimals']}")
                        )
                        
                        if value > 0:
                            all_tokens.append({
                                'token': token,
                                'chain': chain,
                                'symbol': info['symbol'],
                                'name': info['name'],
                                'balance': float(info['balance']),
                                'price_usd': float(price),
                                'value_usd': float(value),
                                'change_24h': float(
                                    prices.get(token, {}).get('usd_24h_change', 0)
                                ),
                                'allowance': info['allowance']
                            })
                            
                            total_value += value
                            change_24h += (
                                value *
                                Decimal(str(
                                    prices.get(token, {}).get('usd_24h_change', 0)
                                )) /
                                Decimal('100')
                            )
            
            return {
                'total_value': float(total_value),
                'change_24h': float(
                    change_24h / total_value * 100
                ) if total_value > 0 else 0,
                'tokens': all_tokens
            }
            
        except Exception as e:
            logger.error(f"Error getting {chain} portfolio: {e}")
            return {
                'total_value': 0,
                'change_24h': 0,
                'tokens': []
            }
    
    async def _get_solana_portfolio(
        self,
        addresses: List[str]
    ) -> Dict[str, Any]:
        """Get Solana portfolio data using Helius API"""
        try:
            total_value = Decimal('0')
            change_24h = Decimal('0')
            all_tokens = []
            
            for address in addresses:
                # Get token balances
                balances = await self.helius.get_token_balances(address)
                
                if not balances:
                    continue
                
                # Get token prices
                token_addresses = [
                    b['mint']
                    for b in balances
                    if Decimal(str(b['amount'])) > 0
                ]
                prices = await self._get_token_prices(
                    token_addresses,
                    'SOL'
                )
                
                # Calculate token values
                for balance in balances:
                    if Decimal(str(balance['amount'])) > 0:
                        price = Decimal(
                            str(
                                prices.get(
                                    balance['mint'],
                                    {}
                                ).get('usd', 0)
                            )
                        )
                        value = (
                            Decimal(str(balance['amount'])) *
                            price /
                            Decimal(f"1e{balance['decimals']}")
                        )
                        
                        if value > 0:
                            all_tokens.append({
                                'token': balance['mint'],
                                'chain': 'SOL',
                                'symbol': balance.get('symbol', 'Unknown'),
                                'name': balance.get('name', 'Unknown'),
                                'balance': float(balance['amount']),
                                'price_usd': float(price),
                                'value_usd': float(value),
                                'change_24h': float(
                                    prices.get(
                                        balance['mint'],
                                        {}
                                    ).get('usd_24h_change', 0)
                                )
                            })
                            
                            total_value += value
                            change_24h += (
                                value *
                                Decimal(str(
                                    prices.get(
                                        balance['mint'],
                                        {}
                                    ).get('usd_24h_change', 0)
                                )) /
                                Decimal('100')
                            )
            
            return {
                'total_value': float(total_value),
                'change_24h': float(
                    change_24h / total_value * 100
                ) if total_value > 0 else 0,
                'tokens': all_tokens
            }
            
        except Exception as e:
            logger.error(f"Error getting Solana portfolio: {e}")
            return {
                'total_value': 0,
                'change_24h': 0,
                'tokens': []
            }
    
    async def _get_token_prices(
        self,
        tokens: List[str],
        chain: str
    ) -> Dict[str, Dict[str, float]]:
        """Get token prices with caching"""
        prices = {}
        tokens_to_fetch = []
        
        # Check cache first
        for token in tokens:
            cache_key = f"price:{chain}:{token}"
            cached = await self.cache.get(cache_key, 'price')
            if cached:
                prices[token] = cached
            else:
                tokens_to_fetch.append(token)
        
        if tokens_to_fetch:
            # Fetch new prices
            try:
                new_prices = await self.coingecko.get_token_prices(
                    tokens_to_fetch,
                    chain
                )
                
                # Cache and add to results
                for token, price_data in new_prices.items():
                    cache_key = f"price:{chain}:{token}"
                    await self.cache.set(cache_key, price_data, 'price')
                    prices[token] = price_data
                    
            except Exception as e:
                logger.error(f"Error fetching token prices: {e}")
        
        return prices
    
    async def _get_tracked_tokens(self, chain: str) -> List[str]:
        """Get list of tracked tokens for a chain"""
        # This would be implemented based on your token tracking system
        pass
    
    def _calculate_weighted_change(
        self,
        values_and_changes: List[tuple]
    ) -> float:
        """Calculate weighted average change"""
        total_value = sum(value for value, _ in values_and_changes)
        if total_value == 0:
            return 0
            
        weighted_change = sum(
            value * change / total_value
            for value, change in values_and_changes
        )
        
        return float(weighted_change)
