"""
API key rotation and management implementation
"""

import os
import hashlib
import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from collections import defaultdict
from datetime import datetime
from db.models import get_db_manager

logger = logging.getLogger(__name__)

@dataclass
class KeyInfo:
    """Key information for rotation"""
    key: str  # The actual API key
    key_hash: str  # Hashed version for storage/lookup
    last_used: int  # Timestamp of last use
    usage_count: int  # Number of times used
    cooldown_until: int  # Timestamp when cooldown expires  
    is_active: bool  # Whether key is currently active

class KeyManager:
    """Manages API keys with rotation, cooldown and usage tracking"""
    
    def __init__(self):
        """Initialize key manager"""
        self.services = [
            "covalent", "helius", "goplus", 
            "coingecko", "zero_x", "jupiter"
        ]
        self.keys: Dict[str, List[KeyInfo]] = defaultdict(list)
        self.cooldowns = defaultdict(dict)
        self.usage = defaultdict(lambda: defaultdict(int))
        
        # Configuration for different services
        self.service_configs = {
            'covalent': {
                'env_keys': [
                    'COVALENT_KEYS', 'COVALENT_API_KEYS',
                    'COVALENT_KEY_1', 'COVALENT_KEY_2', 'COVALENT_KEY_3',
                    'COVALENT_API_KEY_1', 'COVALENT_API_KEY_2', 'COVALENT_API_KEY_3'
                ],
                'fallback_keys': ['COVALENT_API_KEY'],
                'rate_limit': {
                    'requests_per_second': 5,
                    'requests_per_day': 100000
                }
            },
            'helius': {
                'env_keys': ['HELIUS_KEYS', 'HELIUS_KEY_1', 'HELIUS_KEY_2', 'HELIUS_KEY_3'],
                'fallback_keys': ['HELIUS_API_KEY', 'SOLANA_HELIUS_API'],
                'rate_limit': {
                    'requests_per_second': 10,
                    'requests_per_day': 200000
                }
            },
            'goplus': {
                'env_keys': ['GOPLUS_KEYS', 'GOPLUS_KEY_1', 'GOPLUS_KEY_2'],
                'fallback_keys': ['GOPLUS_API_KEY'],
                'rate_limit': {
                    'requests_per_second': 3,
                    'requests_per_day': 50000
                }
            },
            'coingecko': {
                'env_keys': ['COINGECKO_KEYS', 'COINGECKO_KEY_1', 'COINGECKO_KEY_2'],
                'fallback_keys': ['COINGECKO_API_KEY'],
                'rate_limit': {
                    'requests_per_second': 10,
                    'requests_per_minute': 50
                }
            }
        }
        
        self.load_keys()
        
    def _hash_key(self, key: str) -> str:
        """Create hash of API key for storage/lookup"""
        return hashlib.sha256(key.encode()).hexdigest()[:16]
    
    def load_keys(self):
        """Load API keys from environment variables"""
        for service, config in self.service_configs.items():
            pool = []
            
            # Try comma-separated format first (preferred)
            csv_var = f"{service.upper()}_KEYS"
            if os.getenv(csv_var):
                pool += [k.strip() for k in os.getenv(csv_var, "").split(",") if k.strip()]
                logger.info(f"Loaded {len(pool)} {service} keys from comma-separated format")
            
            # Try individual key format
            i = 1
            while True:
                key_var = f"{service.upper()}_KEY_{i}"
                key = os.getenv(key_var)
                if not key:
                    break
                pool.append(key)
                i += 1
            
            # Try fallback keys
            for key_var in config['fallback_keys']:
                key = os.getenv(key_var)
                if key:
                    pool.append(key)
                    logger.info(f"Added fallback key from {key_var}")
            
            # Deduplicate and create KeyInfo objects
            seen = set()
            key_infos = []
            for key in pool:
                if key and key.strip():
                    key_hash = self._hash_key(key.strip())
                    if key_hash not in seen:
                        seen.add(key_hash)
                        key_infos.append(KeyInfo(
                            key=key.strip(),
                            key_hash=key_hash,
                            last_used=0,
                            usage_count=0,
                            cooldown_until=0,
                            is_active=True
                        ))
            
            self.keys[service] = key_infos
            logger.info(f"Total {service} keys loaded: {len(key_infos)}")
            
            # Load historical usage from database
            db = get_db_manager()
            for key_info in key_infos:
                usage = db.get_key_usage(service, key_info.key_hash)
                if usage:
                    key_info.usage_count = usage.get('count', 0)
                    key_info.last_used = usage.get('last_used', 0)
                    key_info.cooldown_until = usage.get('cooldown_until', 0)
    
    async def get_key(self, service: str) -> Optional[str]:
        """Get next available API key for service"""
        if service not in self.keys:
            return None
            
        now = int(time.time())
        db = get_db_manager()
        
        # Find key with lowest usage that isn't in cooldown
        available_keys = []
        for key_info in self.keys[service]:
            if key_info.is_active and now >= key_info.cooldown_until:
                available_keys.append(key_info)
                
        if not available_keys:
            logger.warning(f"No available keys for {service}")
            return None
            
        # Sort by usage count ascending
        available_keys.sort(key=lambda k: k.usage_count)
        selected = available_keys[0]
        
        # Update usage
        selected.usage_count += 1
        selected.last_used = now
        await db.update_key_usage(service, selected.key_hash)
        
        return selected.key
        
    async def update_key_usage(
        self,
        service: str,
        key: str,
        error: Optional[str] = None
    ):
        """Update API key usage stats"""
        if service not in self.keys:
            return
            
        key_hash = self._hash_key(key)
        db = get_db_manager()
        now = int(time.time())
        
        for key_info in self.keys[service]:
            if key_info.key_hash == key_hash:
                key_info.last_used = now
                key_info.usage_count += 1
                
                if error:
                    if "rate limit" in error.lower():
                        # Rate limit for 5 minutes
                        key_info.cooldown_until = now + 300
                    elif "quota" in error.lower():
                        # Quota exceeded - cool down for 1 hour
                        key_info.cooldown_until = now + 3600
                        
                    await db.update_key_usage(
                        service=service,
                        key_hash=key_hash,
                        error=error,
                        cooldown_until=key_info.cooldown_until
                    )
                else:
                    await db.update_key_usage(service, key_hash)
                    
                break
    
    def get_service_health(self, service: str) -> Dict[str, Any]:
        """Get health status of service's API keys"""
        if service not in self.keys:
            return {
                'total': 0,
                'active': 0,
                'cooldown': 0,
                'rate_limited': 0,
                'quota_exceeded': 0
            }
            
        now = int(time.time())
        total = len(self.keys[service])
        active = sum(1 for k in self.keys[service] if k.is_active and now >= k.cooldown_until)
        cooldown = sum(1 for k in self.keys[service] if k.cooldown_until > now)
        rate_limited = sum(1 for k in self.keys[service] if now < k.cooldown_until <= now + 300)
        quota_exceeded = sum(1 for k in self.keys[service] if k.cooldown_until > now + 300)
        
        return {
            'total': total,
            'active': active,
            'cooldown': cooldown,
            'rate_limited': rate_limited,
            'quota_exceeded': quota_exceeded,
            'keys': [
                {
                    'hash': k.key_hash,
                    'last_used': k.last_used,
                    'usage_count': k.usage_count,
                    'cooldown_until': k.cooldown_until,
                    'is_active': k.is_active
                }
                for k in self.keys[service]
            ]
        }

# Global instance
key_manager = KeyManager()

def get_key_manager() -> KeyManager:
    """Get key manager instance"""
    return key_manager

def mark_key_rate_limited(service: str, key: str):
    """Mark key as rate limited"""
    key_hash = key_manager._hash_key(key)
    for key_info in key_manager.keys[service]:
        if key_info.key_hash == key_hash:
            now = int(time.time())
            key_info.cooldown_until = now + 300  # 5 minute cooldown
            key_info.usage_count += 1
            key_info.last_used = now
            break
            
def mark_key_quota_exhausted(service: str, key: str):
    """Mark key as quota exhausted"""
    key_hash = key_manager._hash_key(key)
    for key_info in key_manager.keys[service]:
        if key_info.key_hash == key_hash:
            now = int(time.time())
            key_info.cooldown_until = now + 3600  # 1 hour cooldown
            key_info.usage_count += 1
            key_info.last_used = now
            break
