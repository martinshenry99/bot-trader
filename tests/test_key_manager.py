"""
Test suite for key management and security
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from services.key_manager.manager import KeyManager, KeyInfo
from config import Config

@pytest.fixture
def key_manager():
    """Create test key manager instance"""
    manager = KeyManager()
    yield manager

def test_key_rotation(key_manager):
    """Test API key rotation logic"""
    # Add test keys
    test_keys = [
        KeyInfo(
            key=f"test_key_{i}",
            key_hash=f"hash_{i}",
            last_used=int(datetime.now().timestamp()),
            usage_count=i,
            cooldown_until=0,
            is_active=True
        )
        for i in range(3)
    ]
    
    key_manager.keys['test_service'] = test_keys
    
    # Get first key - should be test_key_0 (lowest usage)
    key1 = key_manager.get_key('test_service')
    assert key1 == "test_key_0"
    
    # Mark key1 as rate limited
    key_manager.mark_key_rate_limited('test_service', key1)
    
    # Get next key - should be test_key_1
    key2 = key_manager.get_key('test_service')
    assert key2 == "test_key_1"
    
    # Mark all keys as rate limited
    for key in [key1, key2, "test_key_2"]:
        key_manager.mark_key_rate_limited('test_service', key)
    
    # Should return None when all keys are rate limited
    assert key_manager.get_key('test_service') is None

def test_key_cooldown(key_manager):
    """Test key cooldown periods"""
    # Add test key
    test_key = KeyInfo(
        key="test_key",
        key_hash="test_hash",
        last_used=int(datetime.now().timestamp()),
        usage_count=0,
        cooldown_until=0,
        is_active=True
    )
    
    key_manager.keys['test_service'] = [test_key]
    
    # Mark key as rate limited (5 minute cooldown)
    key_manager.mark_key_rate_limited('test_service', "test_key")
    
    # Key should be in cooldown
    assert key_manager.get_key('test_service') is None
    
    # Advance time
    test_key.cooldown_until = 0
    
    # Key should be available again
    assert key_manager.get_key('test_service') == "test_key"

def test_key_quota_exhaustion(key_manager):
    """Test quota exhaustion handling"""
    # Add test key
    test_key = KeyInfo(
        key="test_key",
        key_hash="test_hash",
        last_used=int(datetime.now().timestamp()),
        usage_count=0,
        cooldown_until=0,
        is_active=True
    )
    
    key_manager.keys['test_service'] = [test_key]
    
    # Mark key as quota exhausted (1 hour cooldown)
    key_manager.mark_key_quota_exhausted('test_service', "test_key")
    
    # Key should be in cooldown
    assert key_manager.get_key('test_service') is None
    
    # Should still be in cooldown after 30 minutes
    test_key.cooldown_until = int((datetime.now() + timedelta(minutes=30)).timestamp())
    assert key_manager.get_key('test_service') is None

def test_key_usage_tracking(key_manager):
    """Test key usage tracking"""
    # Add test key
    test_key = KeyInfo(
        key="test_key",
        key_hash="test_hash",
        last_used=0,
        usage_count=0,
        cooldown_until=0,
        is_active=True
    )
    
    key_manager.keys['test_service'] = [test_key]
    
    # Use key multiple times
    for _ in range(3):
        key = key_manager.get_key('test_service')
        assert key == "test_key"
    
    # Check usage count
    assert test_key.usage_count == 3
    assert test_key.last_used > 0

def test_key_health_status(key_manager):
    """Test key health status reporting"""
    # Add mix of healthy and unhealthy keys
    test_keys = [
        KeyInfo(
            key="healthy_key",
            key_hash="hash_1",
            last_used=int(datetime.now().timestamp()),
            usage_count=10,
            cooldown_until=0,
            is_active=True
        ),
        KeyInfo(
            key="rate_limited_key",
            key_hash="hash_2",
            last_used=int(datetime.now().timestamp()),
            usage_count=100,
            cooldown_until=int((datetime.now() + timedelta(minutes=5)).timestamp()),
            is_active=True
        ),
        KeyInfo(
            key="quota_exhausted_key",
            key_hash="hash_3",
            last_used=int(datetime.now().timestamp()),
            usage_count=1000,
            cooldown_until=int((datetime.now() + timedelta(hours=1)).timestamp()),
            is_active=True
        )
    ]
    
    key_manager.keys['test_service'] = test_keys
    
    # Get health status
    health = key_manager.get_service_health('test_service')
    
    assert health['total'] == 3
    assert health['active'] == 1
    assert health['rate_limited'] == 1
    assert health['quota_exceeded'] == 1

def test_key_service_config(key_manager):
    """Test service-specific configuration"""
    # Check rate limit configs
    assert key_manager.service_configs['covalent']['rate_limit']['requests_per_second'] == 5
    assert key_manager.service_configs['helius']['rate_limit']['requests_per_second'] == 10
    assert key_manager.service_configs['coingecko']['rate_limit']['requests_per_minute'] == 50

@pytest.mark.asyncio
async def test_db_persistence(key_manager):
    """Test database persistence of key usage"""
    # Mock DB
    db = Mock()
    key_manager.db = db
    
    # Add test key
    test_key = KeyInfo(
        key="test_key",
        key_hash="test_hash",
        last_used=int(datetime.now().timestamp()),
        usage_count=0,
        cooldown_until=0,
        is_active=True
    )
    
    key_manager.keys['test_service'] = [test_key]
    
    # Update key usage
    await key_manager.update_key_usage(
        service='test_service',
        key="test_key",
        error="Rate limit exceeded"
    )
    
    # Verify DB was updated
    db.update_key_usage.assert_called_once()
