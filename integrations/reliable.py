"""
Reliable API integrations with error handling, caching, and rate limiting
"""
from typing import Dict, Any, Optional, List
import logging
from decimal import Decimal
import aiohttp
from core.reliability import (
    APIConfig,
    Cache,
    with_reliability,
    APIError
)

logger = logging.getLogger(__name__)

class BaseIntegration:
    """Base class for API integrations"""
    
    def __init__(
        self,
        cache: Optional[Cache] = None
    ):
        self.cache = cache
        self._session: Optional[aiohttp.ClientSession] = None
        
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if not self._session:
            self._session = aiohttp.ClientSession()
        return self._session
        
    async def close(self):
        """Close aiohttp session"""
        if self._session:
            await self._session.close()
            self._session = None

class ZeroXIntegration(BaseIntegration):
    """0x Protocol Integration"""
    
    def __init__(
        self,
        api_key: str,
        cache: Optional[Cache] = None
    ):
        super().__init__(cache)
        self.api_key = api_key
        self.zerox_config = APIConfig(
            name="0x",
            calls_per_minute=60,
            cache_ttl=30  # Price quotes valid for 30s
        )
        
    @with_reliability("zerox", cache_key_template="0x_quote_{0}_{1}_{2}")
    async def get_swap_quote(
        self,
        token_in: str,
        token_out: str,
        amount: Decimal
    ) -> Dict[str, Any]:
        """Get swap quote from 0x API"""
        session = await self._get_session()
        
        try:
            async with session.get(
                "https://api.0x.org/swap/v1/quote",
                params={
                    "sellToken": token_in,
                    "buyToken": token_out,
                    "sellAmount": str(amount),
                    "slippagePercentage": "0.01"
                },
                headers={"0x-api-key": self.api_key}
            ) as response:
                response.raise_for_status()
                return await response.json()
                
        except aiohttp.ClientResponseError as e:
            if e.status == 400:
                raise APIError("0x", "Invalid parameters", e.status)
            raise

class JupiterIntegration(BaseIntegration):
    """Jupiter Integration for Solana"""
    
    def __init__(self, cache: Optional[Cache] = None):
        super().__init__(cache)
        self.jupiter_config = APIConfig(
            name="Jupiter",
            calls_per_minute=120,
            cache_ttl=30
        )
        
    @with_reliability("jupiter", cache_key_template="jupiter_quote_{0}_{1}_{2}")
    async def get_swap_quote(
        self,
        token_in: str,
        token_out: str,
        amount: Decimal
    ) -> Dict[str, Any]:
        """Get swap quote from Jupiter API"""
        session = await self._get_session()
        
        try:
            async with session.get(
                "https://quote-api.jup.ag/v4/quote",
                params={
                    "inputMint": token_in,
                    "outputMint": token_out,
                    "amount": str(amount),
                    "slippageBps": 100
                }
            ) as response:
                response.raise_for_status()
                return await response.json()
                
        except aiohttp.ClientResponseError as e:
            if e.status == 400:
                raise APIError("Jupiter", "Invalid parameters", e.status)
            raise

class GoPlusIntegration(BaseIntegration):
    """GoPlus Security API Integration"""
    
    def __init__(
        self,
        api_key: str,
        cache: Optional[Cache] = None
    ):
        super().__init__(cache)
        self.api_key = api_key
        self.goplus_config = APIConfig(
            name="GoPlus",
            calls_per_minute=30,
            cache_ttl=300  # Cache security checks for 5 minutes
        )
        
    @with_reliability("goplus", cache_key_template="goplus_security_{0}_{1}")
    async def check_token_security(
        self,
        token_address: str,
        chain_id: str
    ) -> Dict[str, Any]:
        """Check token security with GoPlus"""
        session = await self._get_session()
        
        try:
            async with session.get(
                "https://api.gopluslabs.io/api/v1/token_security",
                params={
                    "contract_addresses": token_address,
                    "chain_id": chain_id
                },
                headers={"X-API-KEY": self.api_key}
            ) as response:
                response.raise_for_status()
                return await response.json()
                
        except aiohttp.ClientResponseError as e:
            if e.status == 429:
                raise APIError(
                    "GoPlus",
                    "Rate limit exceeded",
                    e.status
                )
            raise

class CovalentIntegration(BaseIntegration):
    """Covalent API Integration"""
    
    def __init__(
        self,
        api_key: str,
        cache: Optional[Cache] = None
    ):
        super().__init__(cache)
        self.api_key = api_key
        self.covalent_config = APIConfig(
            name="Covalent",
            calls_per_minute=50,
            cache_ttl=60  # Cache balances for 1 minute
        )
        
    @with_reliability("covalent", cache_key_template="covalent_balance_{0}_{1}")
    async def get_token_balances(
        self,
        address: str,
        chain_id: int
    ) -> List[Dict[str, Any]]:
        """Get token balances from Covalent"""
        session = await self._get_session()
        
        try:
            async with session.get(
                f"https://api.covalenthq.com/v1/{chain_id}/address/{address}/balances_v2/",
                headers={"Authorization": f"Bearer {self.api_key}"}
            ) as response:
                response.raise_for_status()
                data = await response.json()
                return data.get("data", {}).get("items", [])
                
        except aiohttp.ClientResponseError as e:
            if e.status == 401:
                raise APIError(
                    "Covalent",
                    "Invalid API key",
                    e.status
                )
            raise

class HeliusIntegration(BaseIntegration):
    """Helius API Integration for Solana"""
    
    def __init__(
        self,
        api_key: str,
        cache: Optional[Cache] = None
    ):
        super().__init__(cache)
        self.api_key = api_key
        self.helius_config = APIConfig(
            name="Helius",
            calls_per_minute=40,
            cache_ttl=60
        )
        
    @with_reliability("helius", cache_key_template="helius_balance_{0}")
    async def get_token_balances(
        self,
        address: str
    ) -> List[Dict[str, Any]]:
        """Get token balances from Helius"""
        session = await self._get_session()
        
        try:
            async with session.post(
                f"https://api.helius.xyz/v0/addresses/{address}/balances",
                headers={"Authorization": f"Bearer {self.api_key}"}
            ) as response:
                response.raise_for_status()
                return await response.json()
                
        except aiohttp.ClientResponseError as e:
            if e.status == 401:
                raise APIError(
                    "Helius",
                    "Invalid API key",
                    e.status
                )
            raise

class CoinGeckoIntegration(BaseIntegration):
    """CoinGecko API Integration"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        cache: Optional[Cache] = None
    ):
        super().__init__(cache)
        self.api_key = api_key
        self.coingecko_config = APIConfig(
            name="CoinGecko",
            calls_per_minute=30,
            cache_ttl=60  # Cache prices for 1 minute
        )
        
    @with_reliability("coingecko", cache_key_template="coingecko_price_{0}_{1}")
    async def get_token_price(
        self,
        token_id: str,
        vs_currency: str = "usd"
    ) -> Dict[str, Any]:
        """Get token price from CoinGecko"""
        session = await self._get_session()
        
        # Use Pro API if key is provided
        base_url = (
            "https://pro-api.coingecko.com/api/v3"
            if self.api_key
            else "https://api.coingecko.com/api/v3"
        )
        
        headers = (
            {"X-CG-Pro-API-Key": self.api_key}
            if self.api_key
            else {}
        )
        
        try:
            async with session.get(
                f"{base_url}/simple/price",
                params={
                    "ids": token_id,
                    "vs_currencies": vs_currency
                },
                headers=headers
            ) as response:
                response.raise_for_status()
                return await response.json()
                
        except aiohttp.ClientResponseError as e:
            if e.status == 429:
                raise APIError(
                    "CoinGecko",
                    "Rate limit exceeded",
                    e.status
                )
            raise
