
import requests
from utils.key_manager import key_manager
from utils.key_manager import KeyRotationManager
from utils.cache import TTLCache

class ZeroXService:
    """
    0x API integration with key rotation, error handling, and TTL caching.
    """
    BASE_URL = "https://api.0x.org/swap/v1"

    def __init__(self, key_manager: KeyRotationManager, cache_ttl=60):
        self.key_manager = key_manager
        self.cache = TTLCache(ttl=cache_ttl)

    def _request(self, endpoint, params=None, retry=True):
        if params is None:
            params = {}
        api_key = self.key_manager.get_key('ZEROX_API_KEY')
        params['apiKey'] = api_key
        url = f"{self.BASE_URL}{endpoint}"
        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            if retry:
                self.key_manager.rotate_key('ZEROX_API_KEY')
                return self._request(endpoint, params, retry=False)
            return {"error": str(e)}

    def get_swap_quote(self, sell_token, buy_token, amount):
        cache_key = f"0x:quote:{sell_token}:{buy_token}:{amount}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        endpoint = "/quote"
        params = {
            "sellToken": sell_token,
            "buyToken": buy_token,
            "sellAmount": amount
        }
        data = self._request(endpoint, params)
        if 'error' not in data:
            self.cache.set(cache_key, data)
        return data
