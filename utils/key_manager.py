
"""
API Key Rotation Manager for Meme Trader V4 Pro
Handles rotation across Covalent, Ethereum, BSC, and Solana APIs
"""

import json
import logging
import random
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class APIKey:
    """API Key with usage tracking"""
    key: str
    service: str
    daily_usage: int = 0
    monthly_usage: int = 0
    daily_limit: int = 10000
    monthly_limit: int = 300000
    last_used: Optional[datetime] = None
    is_active: bool = True
    error_count: int = 0
    max_errors: int = 5

    def is_available(self) -> bool:
        """Check if key is available for use"""
        now = datetime.utcnow()
        
        # Reset daily counter if new day
        if self.last_used and self.last_used.date() < now.date():
            self.daily_usage = 0
        
        # Reset monthly counter if new month
        if self.last_used and self.last_used.month != now.month:
            self.monthly_usage = 0
        
        return (
            self.is_active and 
            self.error_count < self.max_errors and
            self.daily_usage < self.daily_limit and 
            self.monthly_usage < self.monthly_limit
        )

    def record_usage(self):
        """Record API key usage"""
        self.daily_usage += 1
        self.monthly_usage += 1
        self.last_used = datetime.utcnow()

    def record_error(self):
        """Record API error"""
        self.error_count += 1
        if self.error_count >= self.max_errors:
            logger.warning(f"API key {self.key[:8]}... disabled due to errors")

    def reset_errors(self):
        """Reset error count"""
        self.error_count = 0


class KeyManager:
    """Manages API key rotation across all services"""
    
    def __init__(self, config_file: str = "keys.json"):
        self.config_file = config_file
        self.keys: Dict[str, List[APIKey]] = {
            'covalent': [],
            'ethereum': [],
            'bsc': [],
            'solana': []
        }
        self.current_indices: Dict[str, int] = {
            'covalent': 0,
            'ethereum': 0,
            'bsc': 0,
            'solana': 0
        }
        self.alert_cooldown: Dict[str, datetime] = {}
        self.load_keys()

    def load_keys(self):
        """Load API keys from configuration"""
        try:
            # Initialize with provided keys
            self.keys = {
                'covalent': [
                    APIKey('cqt_rQJXx3mfdTDHFHBX8xJPpcy9hR4v', 'covalent', daily_limit=10000, monthly_limit=300000),
                    APIKey('cqt_rQV4Bx4GQHXcxHQrJdg9qm6GdDWt', 'covalent', daily_limit=10000, monthly_limit=300000),
                    APIKey('cqt_rQRkmDYG9JbxqQyVMCGXDq4RfY8t', 'covalent', daily_limit=10000, monthly_limit=300000)
                ],
                'ethereum': [
                    APIKey('I4ER457K252CT11NDYE911KXPP7TMASPUU', 'ethereum', daily_limit=30000, monthly_limit=1000000),
                    APIKey('BTVWNAXRG72VXPVVYK3QKH4HDDYF39CE47', 'ethereum', daily_limit=30000, monthly_limit=1000000),
                    APIKey('AE3H9J89R8HN6RX7569E8DPN4TQE6SRFVR', 'ethereum', daily_limit=30000, monthly_limit=1000000)
                ],
                'bsc': [
                    APIKey('USB89XSPH7U6Y9JMC1473AH9YERQUXWU3H', 'bsc', daily_limit=30000, monthly_limit=1000000),
                    APIKey('5XTS6WGV32YQSHJS83MM2UEIUS5R2574NA', 'bsc', daily_limit=30000, monthly_limit=1000000),
                    APIKey('ENBQHWWFQAUGEYP5ZET8JJ9SVRR5DJ4RT5', 'bsc', daily_limit=30000, monthly_limit=1000000)
                ],
                'solana': []  # Will be populated from config file
            }

            # Load from config file if exists
            if Path(self.config_file).exists():
                with open(self.config_file, 'r') as f:
                    config_data = json.load(f)
                    
                    for service, key_list in config_data.items():
                        if service in self.keys:
                            for key_data in key_list:
                                if isinstance(key_data, dict):
                                    api_key = APIKey(**key_data)
                                    # Convert string datetime back to datetime object
                                    if isinstance(api_key.last_used, str):
                                        api_key.last_used = datetime.fromisoformat(api_key.last_used)
                                    self.keys[service].append(api_key)

            logger.info(f"Loaded keys: {sum(len(keys) for keys in self.keys.values())} total")
            
        except Exception as e:
            logger.error(f"Failed to load keys: {e}")

    def save_keys(self):
        """Save current key state to config file"""
        try:
            config_data = {}
            for service, key_list in self.keys.items():
                config_data[service] = []
                for key in key_list:
                    key_dict = asdict(key)
                    # Convert datetime to string for JSON serialization
                    if key_dict['last_used']:
                        key_dict['last_used'] = key.last_used.isoformat()
                    config_data[service].append(key_dict)

            with open(self.config_file, 'w') as f:
                json.dump(config_data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save keys: {e}")

    async def get_key(self, service: str) -> Optional[str]:
        """Get next available API key for service with rotation"""
        try:
            if service not in self.keys or not self.keys[service]:
                await self._send_alert(service, "No API keys configured")
                return None

            available_keys = [key for key in self.keys[service] if key.is_available()]
            
            if not available_keys:
                await self._send_alert(service, "All API keys exhausted")
                return None

            # Smart rotation: slightly randomize to avoid detection
            if len(available_keys) > 1:
                # 80% chance to use next in rotation, 20% random
                if random.random() < 0.8:
                    key = available_keys[self.current_indices[service] % len(available_keys)]
                else:
                    key = random.choice(available_keys)
            else:
                key = available_keys[0]

            # Record usage
            key.record_usage()
            
            # Update rotation index
            try:
                current_index = available_keys.index(key)
                self.current_indices[service] = (current_index + 1) % len(available_keys)
            except ValueError:
                pass

            # Save state periodically
            if random.random() < 0.1:  # 10% chance to save
                self.save_keys()

            logger.debug(f"Using {service} key: {key.key[:8]}... (usage: {key.daily_usage}/{key.daily_limit})")
            return key.key

        except Exception as e:
            logger.error(f"Failed to get {service} key: {e}")
            return None

    async def record_api_error(self, service: str, key: str):
        """Record API error for key"""
        try:
            for api_key in self.keys.get(service, []):
                if api_key.key == key:
                    api_key.record_error()
                    logger.warning(f"Error recorded for {service} key {key[:8]}...")
                    break
        except Exception as e:
            logger.error(f"Failed to record error: {e}")

    async def add_key(self, service: str, key: str, daily_limit: int = None, monthly_limit: int = None):
        """Add new API key to service"""
        try:
            if service not in self.keys:
                logger.error(f"Unknown service: {service}")
                return False

            # Set default limits based on service
            if daily_limit is None:
                daily_limit = 10000 if service == 'covalent' else 30000
            if monthly_limit is None:
                monthly_limit = 300000 if service == 'covalent' else 1000000

            new_key = APIKey(key, service, daily_limit=daily_limit, monthly_limit=monthly_limit)
            self.keys[service].append(new_key)
            self.save_keys()
            
            logger.info(f"Added new {service} API key: {key[:8]}...")
            return True

        except Exception as e:
            logger.error(f"Failed to add key: {e}")
            return False

    async def remove_key(self, service: str, key_prefix: str):
        """Remove API key by prefix"""
        try:
            if service not in self.keys:
                return False

            original_count = len(self.keys[service])
            self.keys[service] = [k for k in self.keys[service] if not k.key.startswith(key_prefix)]
            
            removed_count = original_count - len(self.keys[service])
            if removed_count > 0:
                self.save_keys()
                logger.info(f"Removed {removed_count} {service} key(s)")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to remove key: {e}")
            return False

    def get_key_stats(self) -> Dict:
        """Get statistics for all API keys"""
        stats = {}
        
        for service, key_list in self.keys.items():
            total_keys = len(key_list)
            active_keys = len([k for k in key_list if k.is_available()])
            total_daily_usage = sum(k.daily_usage for k in key_list)
            total_monthly_usage = sum(k.monthly_usage for k in key_list)
            
            stats[service] = {
                'total_keys': total_keys,
                'active_keys': active_keys,
                'daily_usage': total_daily_usage,
                'monthly_usage': total_monthly_usage,
                'health': 'good' if active_keys > 0 else 'critical'
            }

        return stats

    async def _send_alert(self, service: str, message: str):
        """Send Telegram alert for API issues"""
        try:
            # Implement cooldown to avoid spam
            now = datetime.utcnow()
            if service in self.alert_cooldown:
                if now - self.alert_cooldown[service] < timedelta(hours=1):
                    return

            self.alert_cooldown[service] = now
            
            # This would integrate with your telegram bot
            alert_message = f"⚠️ API Alert: {service.upper()}\n{message}"
            logger.critical(alert_message)
            
            # TODO: Send actual Telegram message
            # await bot.send_message(admin_chat_id, alert_message)
            
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")

    async def health_check(self) -> Dict:
        """Perform health check on all services"""
        health_status = {}
        
        for service in self.keys.keys():
            available_keys = [k for k in self.keys[service] if k.is_available()]
            
            health_status[service] = {
                'status': 'healthy' if available_keys else 'critical',
                'available_keys': len(available_keys),
                'total_keys': len(self.keys[service]),
                'next_reset': self._get_next_reset_time()
            }

        return health_status

    def _get_next_reset_time(self) -> str:
        """Get next daily reset time"""
        now = datetime.utcnow()
        tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        return tomorrow.isoformat()

# Global key manager instance
key_manager = KeyManager()
