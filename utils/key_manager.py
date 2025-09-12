"""
API Key Rotation Manager for Meme Trader V4 Pro
Supports both comma-separated and individual key formats
"""

import os
import hashlib
import logging
import time
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from config import Config
from dotenv import load_dotenv
from collections import defaultdict

load_dotenv()
logger = logging.getLogger("key_manager")

@dataclass
class KeyInfo:
    """Key information for rotation"""
    key: str
    key_hash: str
    last_used: int
    usage_count: int
    cooldown_until: int
    is_active: bool

class KeyRotationManager:
    """Manages API key rotation with cooldown and fallback"""
    
    def __init__(self):
        self.services = ["covalent", "helius", "goplus", "coingecko", "zero_x", "jupiter"]
        self.keys: Dict[str, List[KeyInfo]] = defaultdict(list)
        self.cooldowns = defaultdict(dict)
        self.usage = defaultdict(lambda: defaultdict(int))
        self.service_configs = {
            'covalent': {
                'env_keys': [
                    # Preferred comma-separated variants
                    'COVALENT_KEYS', 'COVALENT_API_KEYS',
                    # Individual key variants (both KEY and API_KEY styles)
                    'COVALENT_KEY_1', 'COVALENT_KEY_2', 'COVALENT_KEY_3',
                    'COVALENT_API_KEY_1', 'COVALENT_API_KEY_2', 'COVALENT_API_KEY_3'
                ],
                'fallback_keys': ['COVALENT_API_KEY']
            },
            'helius': {
                'env_keys': ['HELIUS_KEYS', 'HELIUS_KEY_1', 'HELIUS_KEY_2', 'HELIUS_KEY_3', 'HELIUS_API_KEYS'],
                'fallback_keys': ['HELIUS_API_KEY', 'SOLANA_HELIUS_API']
            },
            'etherscan': {
                'env_keys': ['ETH_KEYS', 'ETH_KEY_1', 'ETH_KEY_2', 'ETH_KEY_3', 'ETH_API_KEYS', 'ETH_API_KEY_1', 'ETH_API_KEY_2', 'ETH_API_KEY_3'],
                'fallback_keys': ['ETHEREUM_API_KEY']
            },
            'bscscan': {
                'env_keys': ['BSC_KEYS', 'BSC_KEY_1', 'BSC_KEY_2', 'BSC_KEY_3', 'BSC_API_KEYS', 'BSC_API_KEY_1', 'BSC_API_KEY_2', 'BSC_API_KEY_3'],
                'fallback_keys': ['BSC_API_KEY']
            },
            'goplus': {
                'env_keys': ['GOPLUS_KEYS', 'GOPLUS_KEY_1', 'GOPLUS_KEY_2'],
                'fallback_keys': ['GOPLUS_API_KEY']
            },
            'coingecko': {
                'env_keys': ['COINGECKO_KEYS', 'COINGECKO_KEY_1', 'COINGECKO_KEY_2'],
                'fallback_keys': ['COINGECKO_API_KEY']
            }
        }
        self.load_keys()

    def load_keys(self):
        """Load API keys from environment variables"""
        for service, config in self.service_configs.items():
            pool = []
            # Try comma-separated format first (preferred)
            csv_var = f"{service.upper()}_KEYS"
            if os.getenv(csv_var):
                pool += [k.strip() for k in os.getenv(csv_var, "").split(",") if k.strip()]
                logger.info(f"Loaded {len(pool)} {service} keys from comma-separated format")
            
            # Try individual key format (fallback)
            i = 1
            while True:
                key_var = f"{service.upper()}_KEY_{i}"
                key = os.getenv(key_var)
                if not key:
                    break
                pool.append(key)
                i += 1
            
            # Try fallback keys
            key_var = f"{service.upper()}_API_KEY"
            key = os.getenv(key_var)
            if key:
                pool.append(key)
                logger.info(f"Loaded {len(pool)} {service} keys from fallback format")
            
            # Deduplicate
            pool = list(dict.fromkeys(pool))
            
            # Create KeyInfo objects
            key_infos = []
            for key in pool:
                if key and key.strip():
                    key_hash = self._hash_key(key)
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
    
    def _hash_key(self, key: str) -> str:
        """Create hash of API key for storage"""
        return hashlib.sha256(key.encode()).hexdigest()[:16]
    
    def get_key(self, service: str) -> Optional[str]:
        """Get next available key for service"""
        pool = self.keys.get(service, [])
        now = int(time.time())
        for idx, key in enumerate(pool):
            cooldown_until = self.cooldowns[service].get(idx, 0)
            if now >= cooldown_until:
                self.usage[service][idx] += 1
                logger.debug(f"Selected {service}:key[{idx}] (usage: {self.usage[service][idx]})")
                return key.key
        logger.warning(f"All {service} keys in cooldown!")
        return None

    def mark_key_cooldown(self, service, idx, base=60):
        now = int(time.time())
        prev = self.cooldowns[service].get(idx, 0)
        backoff = base * (2 if prev > now else 1)
        self.cooldowns[service][idx] = now + backoff
        logger.warning(f"Key {service}[{idx}] marked cooldown for {backoff}s")

    def mark_key_exhausted(self, service: str, key: str, cooldown_seconds: int = 3600):
        """Mark key as exhausted (quota reached) - longer cooldown"""
        self.mark_key_cooldown(service, key, cooldown_seconds)
        logger.error(f"Key {key[:8]}... for {service} marked exhausted - cooldown {cooldown_seconds}s")
    
    def get_key_status(self, service: str) -> Dict[str, Any]:
        """Get status of all keys for a service"""
        if service not in self.keys:
            return {'total': 0, 'active': 0, 'cooldown': 0, 'exhausted': 0}
        
        total = len(self.keys[service])
        active = len([k for k in self.keys[service] if k.is_active and k.cooldown_until < time.time()])
        cooldown = len([k for k in self.keys[service] if k.cooldown_until > time.time()])
        exhausted = total - active - cooldown
        
        return {
            'total': total,
            'active': active,
            'cooldown': cooldown,
            'exhausted': exhausted,
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
    
    def reset_key_cooldown(self, service: str, key_hash: str):
        """Reset cooldown for a specific key"""
        if service not in self.keys:
                    return

        for key_info in self.keys[service]:
            if key_info.key_hash == key_hash:
                key_info.cooldown_until = 0
                logger.info(f"Reset cooldown for {service} key {key_hash}")
                
                # Update database ledger
                from db.models import get_db_manager
                db = get_db_manager()
                db.update_key_usage(service, key_hash, 0)
                break
    
    def get_service_keys(self, service: str) -> List[str]:
        """Get all keys for a service (for debugging)"""
        if service not in self.keys:
            return []
        return [k.key for k in self.keys[service]]
    
    def is_service_available(self, service: str) -> bool:
        """Check if service has any available keys"""
        if service not in self.keys:
            return False
        return any(k.is_active and k.cooldown_until < time.time() for k in self.keys[service])
    
    def get_next_available_time(self, service: str) -> Optional[int]:
        """Get timestamp when next key will be available"""
        if service not in self.keys:
            return None
        
        available_times = [k.cooldown_until for k in self.keys[service] if k.cooldown_until > time.time()]
        return min(available_times) if available_times else None

# Global key manager instance
key_manager = KeyRotationManager()

def get_key_manager() -> KeyRotationManager:
    """Get key manager instance"""
    return key_manager

def get_api_key(service: str) -> Optional[str]:
    """Get API key for service (convenience function)"""
    return key_manager.get_key(service)

def mark_key_rate_limited(service: str, key: str):
    """Mark key as rate limited (convenience function)"""
    key_manager.mark_key_cooldown(service, key, 300)  # 5 minute cooldown

def mark_key_quota_exhausted(service: str, key: str):
    """Mark key as quota exhausted (convenience function)"""
    key_manager.mark_key_exhausted(service, key, 3600)  # 1 hour cooldown
