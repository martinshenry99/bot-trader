import asyncio
import aiohttp
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from config import Config

logger = logging.getLogger(__name__)

class APIClient:
    """API Client utilities for Meme Trader V4 Pro"""
    def __init__(self):
        self.session = None

    async def get_session(self):
        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def close(self):
        if self.session:
            await self.session.close()

    async def get(self, url: str, params: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
        """Make GET request"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.error(f"API request failed: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"API request error: {e}")
            return None

    async def post(self, url: str, data: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
        """Make POST request"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.error(f"API request failed: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"API request error: {e}")
            return None

class CovalentAPI:
    """Covalent API client for blockchain data"""

    def __init__(self):
        self.base_url = "https://api.covalenthq.com/v1"
        self.chain_id = Config.CHAIN_ID
        self.session = None
        self.rate_limit_reset = datetime.utcnow()
        self.requests_made = 0
        self.max_requests_per_minute = 100

    async def get_session(self):
        """Get or create aiohttp session with rotated API key"""
        from utils.key_manager import key_manager
        if self.session is None or self.session.closed:
            api_key = await key_manager.get_key('covalent')
            if not api_key:
                raise Exception("No Covalent API keys available")
            # Use async with for session management if possible
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=Config.REQUEST_TIMEOUT),
                headers={'Authorization': f'Bearer {api_key}'}
            )
        return self.session

    async def close_session(self):
        """Close aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()

    async def make_request(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """Make rate-limited API request"""
        try:
            # Rate limiting
            await self.handle_rate_limit()

            session = await self.get_session()
            url = f"{self.base_url}/{endpoint}"

            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('data')
                elif response.status == 429:
                    logger.warning("Rate limit exceeded, rotating API key...")
                    # Close current session to force key rotation
                    await self.close_session()
                    await asyncio.sleep(2)
                    return await self.make_request(endpoint, params)
                elif response.status in [401, 403]:
                    logger.error(f"API authentication failed: {response.status}")
                    # Record error for current key
                    from utils.key_manager import key_manager
                    current_key = self.session.headers.get('Authorization', '').split(' ')[-1]
                    await key_manager.record_api_error('covalent', current_key)
                    # Close session to force key rotation
                    await self.close_session()
                    return None
                else:
                    logger.error(f"API request failed: {response.status}")
                    return None

        except Exception as e:
            logger.error(f"API request error: {e}")
            return None

    async def handle_rate_limit(self):
        """Handle API rate limiting"""
        now = datetime.utcnow()

        # Reset counter every minute
        if now >= self.rate_limit_reset:
            self.requests_made = 0
            self.rate_limit_reset = now + timedelta(minutes=1)

        # Wait if we've hit the limit
        if self.requests_made >= self.max_requests_per_minute:
            wait_time = (self.rate_limit_reset - now).total_seconds()
            if wait_time > 0:
                logger.info(f"Rate limit reached, waiting {wait_time:.1f} seconds")
                await asyncio.sleep(wait_time)
                self.requests_made = 0
                self.rate_limit_reset = datetime.utcnow() + timedelta(minutes=1)

        self.requests_made += 1

    async def get_token_data(self, token_address: str) -> Optional[Dict]:
        """Get token information"""
        try:
            endpoint = f"{self.chain_id}/tokens/{token_address}"
            response = await self.make_request(endpoint)

            if response:
                items = response.get('items', [])
                if items:
                    token_data = items[0]
                    return {
                        'address': token_data.get('contract_address'),
                        'name': token_data.get('contract_name'),
                        'symbol': token_data.get('contract_ticker_symbol'),
                        'decimals': token_data.get('contract_decimals'),
                        'logo_url': token_data.get('logo_url'),
                        'price_usd': float(token_data.get('quote', 0) or 0),
                        'market_cap': 0,  # Not available in this endpoint
                        'liquidity_usd': 0,  # Not available in this endpoint
                        'volume_24h': 0  # Not available in this endpoint
                    }

            return None

        except Exception as e:
            logger.error(f"Failed to get token data: {e}")
            return None

    async def get_token_holders(self, token_address: str, page: int = 0) -> Optional[List[Dict]]:
        """Get token holders"""
        try:
            endpoint = f"{self.chain_id}/tokens/{token_address}/token_holders"
            params = {'page-number': page, 'page-size': 100}

            response = await self.make_request(endpoint, params)

            if response:
                return response.get('items', [])

            return []

        except Exception as e:
            logger.error(f"Failed to get token holders: {e}")
            return []

    async def get_wallet_transactions(self, wallet_address: str, from_block: int = 0) -> List[Dict]:
        """Get wallet transactions"""
        try:
            endpoint = f"{self.chain_id}/address/{wallet_address}/transactions_v2"
            params = {
                'block-signed-at-asc': 'false',
                'no-logs': 'false',
                'page-size': 100
            }

            if from_block > 0:
                params['starting-block'] = from_block

            response = await self.make_request(endpoint, params)

            if response:
                transactions = []
                for item in response.get('items', []):
                    transactions.append({
                        'tx_hash': item.get('tx_hash'),
                        'block_number': item.get('block_height'),
                        'timestamp': item.get('block_signed_at'),
                        'from_address': item.get('from_address'),
                        'to_address': item.get('to_address'),
                        'value': float(item.get('value', 0)) / 1e18,  # Convert wei to ETH
                        'gas_used': item.get('gas_spent'),
                        'gas_price': float(item.get('gas_price', 0)) / 1e9,  # Convert to Gwei
                        'successful': item.get('successful')
                    })

                return transactions

            return []

        except Exception as e:
            logger.error(f"Failed to get wallet transactions: {e}")
            return []

    async def get_wallet_balances(self, wallet_address: str) -> List[Dict]:
        """Get wallet token balances"""
        try:
            endpoint = f"{self.chain_id}/address/{wallet_address}/balances_v2"
            response = await self.make_request(endpoint)

            if response:
                balances = []
                for item in response.get('items', []):
                    if float(item.get('balance', 0)) > 0:
                        balances.append({
                            'token_address': item.get('contract_address'),
                            'symbol': item.get('contract_ticker_symbol'),
                            'name': item.get('contract_name'),
                            'decimals': item.get('contract_decimals'),
                            'balance': float(item.get('balance', 0)) / (10 ** item.get('contract_decimals', 18)),
                            'balance_raw': item.get('balance'),
                            'price_usd': float(item.get('quote', 0) or 0),
                            'value_usd': float(item.get('quote', 0) or 0) * (float(item.get('balance', 0)) / (10 ** item.get('contract_decimals', 18)))
                        })

                return balances

            return []

        except Exception as e:
            logger.error(f"Failed to get wallet balances: {e}")
            return []

class CovalentClient:
    """Main Covalent client with connection pooling"""

    def __init__(self):
        self.apis = [CovalentAPI()]  # Can add multiple API instances for rotation
        self.current_api_index = 0

    def get_current_api(self) -> CovalentAPI:
        """Get current API instance"""
        return self.apis[self.current_api_index]

    def rotate_api(self):
        """Rotate to next API instance"""
        self.current_api_index = (self.current_api_index + 1) % len(self.apis)

    async def get_token_data(self, token_address: str) -> Optional[Dict]:
        """Get token data with API rotation on failure"""
        for _ in range(len(self.apis)):
            try:
                api = self.get_current_api()
                result = await api.get_token_data(token_address)
                if result:
                    return result
            except Exception as e:
                logger.error(f"API call failed: {e}")

            self.rotate_api()

        return None

    async def get_token_holders(self, token_address: str, page: int = 0) -> List[Dict]:
        """Get token holders with API rotation"""
        for _ in range(len(self.apis)):
            try:
                api = self.get_current_api()
                result = await api.get_token_holders(token_address, page)
                if result is not None:
                    return result
            except Exception as e:
                logger.error(f"API call failed: {e}")

            self.rotate_api()

        return []

    async def get_wallet_transactions(self, wallet_address: str, from_block: int = 0) -> List[Dict]:
        """Get wallet transactions with API rotation"""
        for _ in range(len(self.apis)):
            try:
                api = self.get_current_api()
                result = await api.get_wallet_transactions(wallet_address, from_block)
                if result is not None:
                    return result
            except Exception as e:
                logger.error(f"API call failed: {e}")

            self.rotate_api()

        return []

    async def get_wallet_balances(self, wallet_address: str) -> List[Dict]:
        """Get wallet balances with API rotation"""
        for _ in range(len(self.apis)):
            try:
                api = self.get_current_api()
                result = await api.get_wallet_balances(wallet_address)
                if result is not None:
                    return result
            except Exception as e:
                logger.error(f"API call failed: {e}")

            self.rotate_api()

        return []

    async def close_all_sessions(self):
        """Close all API sessions"""
        for api in self.apis:
            await api.close_session()

# Global client instance
covalent_client = CovalentClient()