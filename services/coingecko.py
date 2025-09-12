import requests
from utils.cache import TTLCache

class CoinGeckoService:
    BASE_URL = "https://api.coingecko.com/api/v3"

    def __init__(self, cache_ttl=60):
    def _request(self, endpoint, params=None):
        params = params or {}
        url = f"{self.BASE_URL}{endpoint}"
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
    def get_token_price(self, token_id, vs_currency='usd'):
        cache_key = f"cg:price:{token_id}:{vs_currency}"
        cached = self.cache.get(cache_key)
        data = self._request(endpoint, params)
        if 'error' not in data:
            self.cache.set(cache_key, data)

import requests
from utils.cache import TTLCache

class CoinGeckoService:
    """
    CoinGecko API integration with TTL caching and error handling.
    """
    BASE_URL = "https://api.coingecko.com/api/v3"

    def __init__(self, cache_ttl=60):
        self.cache = TTLCache(ttl=cache_ttl)

    def _request(self, endpoint, params=None):
        if params is None:
            params = {}
        url = f"{self.BASE_URL}{endpoint}"
        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"error": str(e)}

    def get_token_price(self, token_id, vs_currency='usd'):
        cache_key = f"cg:price:{token_id}:{vs_currency}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        endpoint = "/simple/price"
        params = {"ids": token_id, "vs_currencies": vs_currency}
        data = self._request(endpoint, params)
        if 'error' not in data:
            self.cache.set(cache_key, data)
        return data
