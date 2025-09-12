
import requests
from utils.key_manager import key_manager
from utils.key_manager import KeyRotationManager
from utils.cache import TTLCache

class JupiterService:
    """
    Jupiter API integration with error handling and TTL caching.
    """
    BASE_URL = "https://quote-api.jup.ag/v6"

    def __init__(self, key_manager: KeyRotationManager = None, cache_ttl=60):
        self.key_manager = key_manager
        self.cache = TTLCache(ttl=cache_ttl)

    def _request(self, endpoint, params=None, retry=True):
        if params is None:
            params = {}
        url = f"{self.BASE_URL}{endpoint}"
        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"error": str(e)}

    def get_swap_quote(self, input_mint, output_mint, amount):
        cache_key = f"jupiter:quote:{input_mint}:{output_mint}:{amount}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        endpoint = "/quote"
        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": amount
        }
        data = self._request(endpoint, params)
        if 'error' not in data:
            self.cache.set(cache_key, data)
        return data
