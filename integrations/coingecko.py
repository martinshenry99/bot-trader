"""
CoinGecko API integration for price data and market information
"""

import logging
from typing import Dict, List, Optional
from .base import BaseAPIClient

logger = logging.getLogger(__name__)


class CoinGeckoClient(BaseAPIClient):
    """CoinGecko API client for cryptocurrency prices and market data"""
    
    def __init__(self, api_key: str):
        super().__init__(api_key, "https://api.coingecko.com/api/v3", rate_limit=50)
        
    async def health_check(self) -> bool:
        """Check CoinGecko API health"""
        try:
            response = await self.make_request('GET', 'ping')
            return response is not None
        except Exception as e:
            logger.error(f"CoinGecko health check failed: {e}")
            return False
    
    async def get_token_price(self, contract_address: str, vs_currency: str = 'usd') -> Optional[float]:
        """Get current price for a token by contract address"""
        try:
            # Map chain prefixes for CoinGecko
            chain_mapping = {
                '0x': 'ethereum',
                'So': 'solana',  # Solana addresses start with letters
                'bnb': 'binance-smart-chain'
            }
            
            # Determine platform based on address format
            platform = 'ethereum'  # Default
            if contract_address.startswith('0x'):
                platform = 'ethereum'
            elif len(contract_address) > 40:  # Likely Solana
                platform = 'solana'
            
            endpoint = f"simple/token_price/{platform}"
            params = {
                'contract_addresses': contract_address,
                'vs_currencies': vs_currency
            }
            
            response = await self.make_request('GET', endpoint, params=params)
            
            if response and contract_address.lower() in response:
                return response[contract_address.lower()].get(vs_currency)
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get token price: {e}")
            return None
    
    async def get_token_info(self, contract_address: str) -> Optional[Dict]:
        """Get detailed token information"""
        try:
            platform = 'ethereum'
            if len(contract_address) > 40:
                platform = 'solana'
            
            endpoint = f"coins/{platform}/contract/{contract_address}"
            
            response = await self.make_request('GET', endpoint)
            
            if response:
                return {
                    'id': response.get('id'),
                    'symbol': response.get('symbol'),
                    'name': response.get('name'),
                    'current_price': response.get('market_data', {}).get('current_price', {}).get('usd'),
                    'market_cap': response.get('market_data', {}).get('market_cap', {}).get('usd'),
                    'total_volume': response.get('market_data', {}).get('total_volume', {}).get('usd'),
                    'price_change_24h': response.get('market_data', {}).get('price_change_percentage_24h'),
                    'market_cap_rank': response.get('market_cap_rank'),
                    'description': response.get('description', {}).get('en', ''),
                    'homepage': response.get('links', {}).get('homepage', []),
                    'blockchain_site': response.get('links', {}).get('blockchain_site', [])
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get token info: {e}")
            return None
    
    async def get_trending_tokens(self, limit: int = 10) -> List[Dict]:
        """Get trending tokens from CoinGecko"""
        try:
            response = await self.make_request('GET', 'search/trending')
            
            if response and 'coins' in response:
                trending = []
                for coin in response['coins'][:limit]:
                    coin_data = coin.get('item', {})
                    trending.append({
                        'id': coin_data.get('id'),
                        'symbol': coin_data.get('symbol'),
                        'name': coin_data.get('name'),
                        'market_cap_rank': coin_data.get('market_cap_rank'),
                        'price_btc': coin_data.get('price_btc'),
                        'score': coin_data.get('score')
                    })
                return trending
            
            return []
            
        except Exception as e:
            logger.error(f"Failed to get trending tokens: {e}")
            return []
    
    async def get_price_history(self, coin_id: str, days: int = 7, vs_currency: str = 'usd') -> List[Dict]:
        """Get historical price data"""
        try:
            endpoint = f"coins/{coin_id}/market_chart"
            params = {
                'vs_currency': vs_currency,
                'days': days,
                'interval': 'daily' if days > 1 else 'hourly'
            }
            
            response = await self.make_request('GET', endpoint, params=params)
            
            if response and 'prices' in response:
                history = []
                for price_point in response['prices']:
                    history.append({
                        'timestamp': price_point[0],
                        'price': price_point[1]
                    })
                return history
            
            return []
            
        except Exception as e:
            logger.error(f"Failed to get price history: {e}")
            return []
    
    async def search_tokens(self, query: str) -> List[Dict]:
        """Search for tokens by name or symbol"""
        try:
            endpoint = "search"
            params = {'query': query}
            
            response = await self.make_request('GET', endpoint, params=params)
            
            if response and 'coins' in response:
                results = []
                for coin in response['coins'][:10]:  # Limit results
                    results.append({
                        'id': coin.get('id'),
                        'symbol': coin.get('symbol'),
                        'name': coin.get('name'),
                        'market_cap_rank': coin.get('market_cap_rank'),
                        'thumb': coin.get('thumb')
                    })
                return results
            
            return []
            
        except Exception as e:
            logger.error(f"Failed to search tokens: {e}")
            return []
    
    async def convert_currency(self, amount: float, from_currency: str, to_currency: str) -> Optional[float]:
        """Convert between currencies using current rates"""
        try:
            endpoint = "simple/price"
            params = {
                'ids': from_currency,
                'vs_currencies': to_currency
            }
            
            response = await self.make_request('GET', endpoint, params=params)
            
            if response and from_currency in response:
                rate = response[from_currency].get(to_currency)
                if rate:
                    return amount * rate
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to convert currency: {e}")
            return None