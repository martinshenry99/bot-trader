import logging
from typing import Dict, List, Optional, Any
import requests
import asyncio
from utils.key_manager import key_manager
from utils.key_manager import KeyRotationManager
from utils.cache import TTLCache

logger = logging.getLogger(__name__)

class HeliusClient:
    """
    Helius API integration with key rotation, error handling, and TTL caching.
    """
    BASE_URL = "https://api.helius.xyz/v0"

    def __init__(self, key_manager: KeyRotationManager, cache_ttl=60):
        self.key_manager = key_manager
        self.cache = TTLCache(ttl=cache_ttl)
        self.session = None

    def _request(self, endpoint, params=None, retry=True):
        if params is None:
            params = {}
        api_key = self.key_manager.get_key('HELIUS_API_KEY')
        params['api-key'] = api_key
        url = f"{self.BASE_URL}{endpoint}"
        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"Helius request error: {e}")
            if retry:
                self.key_manager.rotate_key('HELIUS_API_KEY')
                return self._request(endpoint, params, retry=False)
            return {"error": str(e)}

    async def _async_request(self, endpoint, params=None, retry=True):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._request, endpoint, params, retry)

    def get_wallet_activity(self, wallet_address):
        cache_key = f"helius:activity:{wallet_address}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        endpoint = f"/addresses/{wallet_address}/transactions"
        params = {}
        data = self._request(endpoint, params)
        self.cache.set(cache_key, data)
        return data

    async def async_get_wallet_activity(self, wallet_address):
        cache_key = f"helius:activity:{wallet_address}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        endpoint = f"/addresses/{wallet_address}/transactions"
        params = {}
        data = await self._async_request(endpoint, params)
        self.cache.set(cache_key, data)
        return data

# Global Helius client instance
helius_client = HeliusClient(key_manager)


def get_helius_client():
    """Get Helius client instance"""
    return helius_client