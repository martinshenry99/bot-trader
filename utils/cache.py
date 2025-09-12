import time
import threading

class TTLCache:
    def __init__(self, ttl=600):
        self.ttl = ttl
        self.cache = {}
        self.lock = threading.Lock()

    def set(self, key, value):
        with self.lock:
            self.cache[key] = (value, time.time())

    def get(self, key):
        with self.lock:
            item = self.cache.get(key)
            if not item:
                return None
            value, ts = item
            if time.time() - ts > self.ttl:
                del self.cache[key]
                return None
            return value

    def invalidate(self, key):
        with self.lock:
            if key in self.cache:
                del self.cache[key]

    def clear(self):
        with self.lock:
            self.cache.clear()

cache = TTLCache()
