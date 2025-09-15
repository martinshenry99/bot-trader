"""
API key rotation and management
"""

import logging
import asyncio
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from db.models import db_manager
from services.api_manager import APIError

logger = logging.getLogger(__name__)

class KeyManager:
    """Manages API keys with rotation and rate limiting"""
    
    def __init__(self):
        self.db = db_manager
        self._rotation_task = None
        self._start_rotation_task()
        
    def _start_rotation_task(self):
        """Start background task for key rotation"""
        async def rotate_keys():
            while True:
                try:
                    # Reset daily counts at UTC midnight
                    now = datetime.utcnow()
                    tomorrow = now.replace(
                        hour=0, minute=0, second=0, microsecond=0
                    ) + timedelta(days=1)
                    
                    # Sleep until midnight
                    await asyncio.sleep((tomorrow - now).total_seconds())
                    
                    # Reset counts
                    await self.db.reset_daily_counts()
                    
                except Exception as e:
                    logger.error(f"Error in key rotation task: {e}")
                    await asyncio.sleep(60)  # Retry after a minute
                    
        if not self._rotation_task:
            self._rotation_task = asyncio.create_task(rotate_keys())
        
    async def get_key(self, service: str) -> Optional[str]:
        """Get a valid API key for a service"""
        try:
            # Get all enabled keys with current usage
            keys = await self.db.get_api_keys(service)
            
            if not keys:
                logger.error(f"No API keys found for {service}")
                return None
                
            # Return random key from available keys
            return random.choice(keys)
            
        except Exception as e:
            logger.error(f"Error getting API key: {e}")
            return None
            
    async def add_key(self, service: str, key: str) -> bool:
        """Add a new API key"""
        try:
            # Validate key format
            if not self._validate_key_format(service, key):
                raise ValueError("Invalid API key format")
                
            # Add to database
            return await self.db.add_api_key(service, key)
            
        except Exception as e:
            logger.error(f"Error adding API key: {e}")
            return False
            
    async def remove_key(self, service: str, key: str) -> bool:
        """Remove an API key"""
        try:
            return await self.db.remove_api_key(service, key)
            
        except Exception as e:
            logger.error(f"Error removing API key: {e}")
            return False
            
    async def update_key_usage(self, service: str, key: str, error: Optional[str] = None):
        """Update API key usage stats"""
        try:
            await self.db.update_key_usage(service, key, error)
            
        except Exception as e:
            logger.error(f"Error updating key usage: {e}")
            
    def _validate_key_format(self, service: str, key: str) -> bool:
        """Validate API key format"""
        if not key:
            return False
            
        # Service-specific validation
        if service == "covalent":
            return len(key) == 64 and key.isalnum()
        elif service in ["alchemy", "infura"]:
            return key.startswith("0x") and len(key) >= 32
        elif service == "helius":
            return len(key) >= 32 and key.isalnum()
        elif service == "bscscan":
            return len(key) >= 32 and key.isalnum()
        elif service == "etherscan":
            return len(key) >= 32 and key.isalnum()
        elif service == "solscan":
            return len(key) >= 32 and key.isalnum()
            
        return True  # Default to true for unknown services

# Global instance
key_manager = KeyManager()
