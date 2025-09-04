"""
Mock data source for testing when APIs are blocked
"""

import random
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class MockTransaction:
    """Mock transaction data"""
    hash: str
    from_address: str
    to_address: str
    value_usd: float
    token_symbol: str
    timestamp: int

@dataclass
class MockWalletMetrics:
    """Mock wallet metrics"""
    score: float
    win_rate: float
    max_multiplier: float
    avg_roi: float
    total_volume_usd: float
    recent_activity: int
    risk_flags: List[str]

class MockDataProvider:
    """Provides mock data for testing when APIs are blocked"""
    
    def __init__(self):
        # Known profitable wallets for testing
        self.test_wallets = [
            "0x8ba1f109551bD432803012645Hac136c22C501e3",
            "0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b", 
            "0xA0b86a4c3C6D3a6e1D8A6eC0b5E2C8a7d3C1E7B6",
            "0x1234567890123456789012345678901234567890",
            "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd",
            "0x9876543210987654321098765432109876543210",
            "0xfedcba0987654321fedcba0987654321fedcba09",
            "0x1111111111111111111111111111111111111111",
            "0x2222222222222222222222222222222222222222",
            "0x3333333333333333333333333333333333333333"
        ]
        
        # Mock token symbols
        self.token_symbols = [
            "PEPE", "DOGE", "SHIB", "FLOKI", "BONK", "WIF", "BOME", 
            "MYRO", "POPCAT", "MEW", "PNUT", "GOAT", "CHILLGUY", "TURBO"
        ]
    
    def get_mock_recent_transactions(self, chain_id: int, limit: int = 1000) -> List[Dict[str, Any]]:
        """Generate mock recent transactions"""
        transactions = []
        
        for i in range(min(limit, 500)):  # Limit to 500 for performance
            # Random addresses
            from_addr = random.choice(self.test_wallets)
            to_addr = random.choice(self.test_wallets)
            
            # Avoid self-transfers
            while to_addr == from_addr:
                to_addr = random.choice(self.test_wallets)
            
            transaction = {
                'hash': f"0x{''.join(random.choices('0123456789abcdef', k=64))}",
                'from_address': from_addr,
                'to_address': to_addr,
                'value_usd': random.uniform(100, 100000),
                'token_symbol': random.choice(self.token_symbols),
                'timestamp': int((datetime.now() - timedelta(days=random.randint(0, 30))).timestamp())
            }
            transactions.append(transaction)
        
        logger.info(f"Generated {len(transactions)} mock transactions for chain {chain_id}")
        return transactions
    
    def get_mock_wallet_transactions(self, address: str, chain_id: int) -> List[MockTransaction]:
        """Generate mock wallet transactions"""
        transactions = []
        
        # Generate 20-100 transactions for the wallet
        num_txs = random.randint(20, 100)
        
        for i in range(num_txs):
            # Random counterparty
            counterparty = random.choice(self.test_wallets)
            while counterparty == address:
                counterparty = random.choice(self.test_wallets)
            
            # Random direction (buy/sell)
            is_buy = random.choice([True, False])
            from_addr = counterparty if is_buy else address
            to_addr = address if is_buy else counterparty
            
            transaction = MockTransaction(
                hash=f"0x{''.join(random.choices('0123456789abcdef', k=64))}",
                from_address=from_addr,
                to_address=to_addr,
                value_usd=random.uniform(1000, 50000),
                token_symbol=random.choice(self.token_symbols),
                timestamp=int((datetime.now() - timedelta(days=random.randint(0, 90))).timestamp())
            )
            transactions.append(transaction)
        
        logger.info(f"Generated {len(transactions)} mock transactions for wallet {address}")
        return transactions
    
    def get_mock_wallet_metrics(self, address: str, chain_id: int) -> MockWalletMetrics:
        """Generate mock wallet metrics"""
        # Generate realistic metrics based on address hash for consistency
        address_hash = hash(address) % 1000
        
        # Score between 50-95
        score = 50 + (address_hash % 45)
        
        # Win rate between 60-90%
        win_rate = 60 + (address_hash % 30)
        
        # Max multiplier between 2x-50x
        max_multiplier = 2 + (address_hash % 48)
        
        # Avg ROI between 10-200%
        avg_roi = 10 + (address_hash % 190)
        
        # Volume between $10k-$1M
        total_volume_usd = 10000 + (address_hash * 1000)
        
        # Recent activity (days since last trade)
        recent_activity = max(1, 30 - (address_hash % 30))
        
        # Risk flags (some wallets have risks)
        risk_flags = []
        if address_hash % 10 == 0:
            risk_flags.append('high_volume')
        if address_hash % 15 == 0:
            risk_flags.append('new_wallet')
        
        metrics = MockWalletMetrics(
            score=score,
            win_rate=win_rate,
            max_multiplier=max_multiplier,
            avg_roi=avg_roi,
            total_volume_usd=total_volume_usd,
            recent_activity=recent_activity,
            risk_flags=risk_flags
        )
        
        logger.info(f"Generated mock metrics for {address}: score={score}, win_rate={win_rate}%")
        return metrics
    
    def get_mock_token_holders(self, token_address: str, chain_id: int) -> List[Dict[str, Any]]:
        """Generate mock token holders"""
        holders = []
        
        # Generate 10-50 holders
        num_holders = random.randint(10, 50)
        
        for i in range(num_holders):
            holder = {
                'address': random.choice(self.test_wallets),
                'balance': str(random.randint(1000000, 1000000000)),  # Token balance
                'balance_usd': random.uniform(1000, 100000)
            }
            holders.append(holder)
        
        logger.info(f"Generated {len(holders)} mock token holders for {token_address}")
        return holders

# Global mock data provider
mock_provider = MockDataProvider()

def get_mock_provider() -> MockDataProvider:
    """Get mock data provider instance"""
    return mock_provider