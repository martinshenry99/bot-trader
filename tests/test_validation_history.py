"""
Tests for historical validation database
"""
import pytest
import asyncio
from datetime import datetime, timedelta
import os
from db.validation_history import ValidationDatabase, ValidationResult

@pytest.fixture
async def db():
    """Create test database"""
    db_path = "test_validations.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    
    db = ValidationDatabase(db_path)
    yield db
    
    if os.path.exists(db_path):
        os.remove(db_path)

@pytest.fixture
def sample_validation():
    """Create sample validation result"""
    return ValidationResult(
        token_address="0x123",
        chain="ethereum",
        timestamp=datetime.utcnow(),
        liquidity_usd="100000",
        volume_24h="50000",
        holder_count=100,
        is_honeypot=False,
        is_blacklisted=False,
        price_impact_bps=50,
        owner_balance_pct=5.0,
        contract_verified=True,
        validation_score=80,
        extra_data={"key": "value"},
        is_valid=True
    )

@pytest.mark.asyncio
async def test_store_and_retrieve(db, sample_validation):
    """Test storing and retrieving validation"""
    await db.store_validation(sample_validation)
    
    result = await db.get_validation(
        sample_validation.token_address,
        sample_validation.chain
    )
    
    assert result is not None
    assert result.token_address == sample_validation.token_address
    assert result.chain == sample_validation.chain
    assert result.liquidity_usd == sample_validation.liquidity_usd
    assert result.is_valid == sample_validation.is_valid
    assert result.validation_score == sample_validation.validation_score

@pytest.mark.asyncio
async def test_ttl_expiration(db, sample_validation):
    """Test validation expiration"""
    # Set short TTL
    sample_validation.ttl = 1
    await db.store_validation(sample_validation)
    
    # Verify retrieval works immediately
    result = await db.get_validation(
        sample_validation.token_address,
        sample_validation.chain
    )
    assert result is not None
    
    # Wait for expiration
    await asyncio.sleep(1.1)
    
    # Should return None after expiration
    result = await db.get_validation(
        sample_validation.token_address,
        sample_validation.chain
    )
    assert result is None

@pytest.mark.asyncio
async def test_get_valid_tokens(db):
    """Test filtering valid tokens"""
    # Store multiple validations
    validations = [
        ValidationResult(
            token_address=f"0x{i}",
            chain="ethereum",
            timestamp=datetime.utcnow(),
            liquidity_usd=str(100000 * (i + 1)),
            volume_24h=str(50000 * (i + 1)),
            holder_count=100 * (i + 1),
            is_honeypot=False,
            is_blacklisted=False,
            price_impact_bps=50,
            owner_balance_pct=5.0,
            contract_verified=True,
            validation_score=20 * (i + 1),
            extra_data={"key": "value"},
            is_valid=True
        )
        for i in range(5)
    ]
    
    for v in validations:
        await db.store_validation(v)
    
    # Test min liquidity filter
    results = await db.get_valid_tokens(
        chain="ethereum",
        min_liquidity="200000"
    )
    assert len(results) == 4  # First token has 100k liquidity
    
    # Test min score filter
    results = await db.get_valid_tokens(
        chain="ethereum",
        min_score=60
    )
    assert len(results) == 3  # First 2 tokens have scores < 60

@pytest.mark.asyncio
async def test_cleanup_expired(db):
    """Test cleanup of expired validations"""
    # Create old validation
    old_validation = ValidationResult(
        token_address="0xold",
        chain="ethereum",
        timestamp=datetime.utcnow() - timedelta(hours=2),
        liquidity_usd="100000",
        volume_24h="50000",
        holder_count=100,
        is_honeypot=False,
        is_blacklisted=False,
        price_impact_bps=50,
        owner_balance_pct=5.0,
        contract_verified=True,
        validation_score=80,
        extra_data={"key": "value"},
        is_valid=True,
        ttl=3600  # 1 hour
    )
    
    # Create recent validation
    recent_validation = ValidationResult(
        token_address="0xrecent",
        chain="ethereum",
        timestamp=datetime.utcnow(),
        liquidity_usd="100000",
        volume_24h="50000",
        holder_count=100,
        is_honeypot=False,
        is_blacklisted=False,
        price_impact_bps=50,
        owner_balance_pct=5.0,
        contract_verified=True,
        validation_score=80,
        extra_data={"key": "value"},
        is_valid=True,
        ttl=3600
    )
    
    await db.store_validation(old_validation)
    await db.store_validation(recent_validation)
    
    # Cleanup expired
    await db.cleanup_expired()
    
    # Old validation should be gone
    result = await db.get_validation(
        old_validation.token_address,
        old_validation.chain
    )
    assert result is None
    
    # Recent validation should remain
    result = await db.get_validation(
        recent_validation.token_address,
        recent_validation.chain
    )
    assert result is not None

@pytest.mark.asyncio
async def test_statistics(db, sample_validation):
    """Test validation statistics"""
    # Store multiple validations
    validations = [
        ValidationResult(
            token_address=f"0x{i}",
            chain="ethereum" if i % 2 == 0 else "bsc",
            timestamp=datetime.utcnow(),
            liquidity_usd=str(100000 * (i + 1)),
            volume_24h=str(50000 * (i + 1)),
            holder_count=100 * (i + 1),
            is_honeypot=False,
            is_blacklisted=False,
            price_impact_bps=50,
            owner_balance_pct=5.0,
            contract_verified=True,
            validation_score=20 * (i + 1),
            extra_data={"key": "value"},
            is_valid=i < 3  # First 3 are valid
        )
        for i in range(5)
    ]
    
    for v in validations:
        await db.store_validation(v)
        
    stats = await db.get_statistics()
    
    assert stats['total_validations'] == 5
    assert round(stats['valid_ratio']) == 60  # 3/5 = 60%
    assert stats['avg_score'] == 60  # (20 + 40 + 60 + 80 + 100) / 5
    assert stats['chain_distribution']['ethereum'] == 3
    assert stats['chain_distribution']['bsc'] == 2
    assert stats['recent_validations'] == 5

@pytest.mark.asyncio
async def test_calculate_ttl(db):
    """Test TTL calculation based on score"""
    # Test minimum score
    ttl = db.calculate_ttl(0)
    assert ttl == db.min_ttl
    
    # Test maximum score
    ttl = db.calculate_ttl(100)
    assert ttl == db.max_ttl
    
    # Test mid-range score
    ttl = db.calculate_ttl(50)
    expected = db.min_ttl + (db.max_ttl - db.min_ttl) * 0.5
    assert ttl == int(expected)
