
"""
Helius API Integration for Solana Wallet Scanning and Monitoring
"""

import logging
import aiohttp
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from .base import BaseAPIClient
from utils.key_manager import key_manager

logger = logging.getLogger(__name__)


class HeliusClient(BaseAPIClient):
    """Helius API client for Solana blockchain data"""
    
    def __init__(self):
        super().__init__(None, "https://api.helius.xyz/v0", rate_limit=1000)
        
    async def _get_headers(self) -> Dict[str, str]:
        """Get headers with rotated API key"""
        api_key = await key_manager.get_key('solana')
        if not api_key:
            raise Exception("No Solana API keys available")
        
        return {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
    
    async def health_check(self) -> bool:
        """Check if Helius API is accessible"""
        try:
            headers = await self._get_headers()
            result = await self.make_request('GET', '/health', headers=headers)
            return result is not None
        except Exception as e:
            logger.error(f"Helius health check failed: {e}")
            return False
    
    async def get_wallet_transactions(self, wallet_address: str, limit: int = 100) -> List[Dict]:
        """Get wallet transactions from Helius"""
        try:
            headers = await self._get_headers()
            endpoint = f'/addresses/{wallet_address}/transactions'
            params = {'limit': limit}
            
            result = await self.make_request('GET', endpoint, params=params, headers=headers)
            
            if result and 'transactions' in result:
                return result['transactions']
            return []
            
        except Exception as e:
            logger.error(f"Failed to get Solana transactions: {e}")
            await key_manager.record_api_error('solana', headers.get('Authorization', '').split(' ')[-1])
            return []
    
    async def get_token_accounts(self, wallet_address: str) -> List[Dict]:
        """Get token accounts for a wallet"""
        try:
            headers = await self._get_headers()
            endpoint = f'/addresses/{wallet_address}/balances'
            
            result = await self.make_request('GET', endpoint, headers=headers)
            
            if result and 'tokens' in result:
                return result['tokens']
            return []
            
        except Exception as e:
            logger.error(f"Failed to get token accounts: {e}")
            await key_manager.record_api_error('solana', headers.get('Authorization', '').split(' ')[-1])
            return []
    
    async def get_token_metadata(self, mint_address: str) -> Optional[Dict]:
        """Get token metadata"""
        try:
            headers = await self._get_headers()
            endpoint = f'/tokens/{mint_address}'
            
            result = await self.make_request('GET', endpoint, headers=headers)
            return result
            
        except Exception as e:
            logger.error(f"Failed to get token metadata: {e}")
            await key_manager.record_api_error('solana', headers.get('Authorization', '').split(' ')[-1])
            return None
    
    async def scan_profitable_wallets(self, timeframe_days: int = 7, min_multiplier: float = 200.0) -> List[Dict]:
        """Scan for profitable wallets using Helius enhanced APIs"""
        try:
            headers = await self._get_headers()
            
            # Use Helius enhanced APIs to find profitable wallets
            endpoint = '/enhanced-transactions'
            params = {
                'type': 'SWAP',
                'from_date': (datetime.utcnow() - timedelta(days=timeframe_days)).isoformat(),
                'min_profit_multiple': min_multiplier,
                'limit': 100
            }
            
            result = await self.make_request('GET', endpoint, params=params, headers=headers)
            
            if result and 'transactions' in result:
                # Process and rank wallets by profitability
                wallet_profits = {}
                
                for tx in result['transactions']:
                    wallet = tx.get('feePayer')  # Transaction signer
                    profit_usd = tx.get('profitUsd', 0)
                    
                    if wallet and profit_usd > 0:
                        if wallet not in wallet_profits:
                            wallet_profits[wallet] = {
                                'address': wallet,
                                'total_profit': 0,
                                'trade_count': 0,
                                'max_multiplier': 1.0,
                                'last_activity': datetime.utcnow()
                            }
                        
                        wallet_profits[wallet]['total_profit'] += profit_usd
                        wallet_profits[wallet]['trade_count'] += 1
                        
                        multiplier = tx.get('profitMultiple', 1.0)
                        if multiplier > wallet_profits[wallet]['max_multiplier']:
                            wallet_profits[wallet]['max_multiplier'] = multiplier
                
                # Sort by total profit and return top performers
                top_wallets = sorted(
                    wallet_profits.values(),
                    key=lambda x: x['total_profit'],
                    reverse=True
                )[:20]
                
                return top_wallets
                
            return []
            
        except Exception as e:
            logger.error(f"Failed to scan profitable wallets: {e}")
            await key_manager.record_api_error('solana', headers.get('Authorization', '').split(' ')[-1])
            return []
    
    async def monitor_wallet_activity(self, wallet_address: str) -> List[Dict]:
        """Monitor real-time wallet activity"""
        try:
            headers = await self._get_headers()
            endpoint = f'/addresses/{wallet_address}/transactions'
            params = {
                'limit': 10,
                'commitment': 'confirmed'
            }
            
            result = await self.make_request('GET', endpoint, params=params, headers=headers)
            
            if result and 'transactions' in result:
                # Filter for recent transactions (last 5 minutes)
                recent_txs = []
                cutoff_time = datetime.utcnow() - timedelta(minutes=5)
                
                for tx in result['transactions']:
                    tx_time = datetime.fromtimestamp(tx.get('timestamp', 0))
                    if tx_time > cutoff_time:
                        recent_txs.append(tx)
                
                return recent_txs
                
            return []
            
        except Exception as e:
            logger.error(f"Failed to monitor wallet activity: {e}")
            await key_manager.record_api_error('solana', headers.get('Authorization', '').split(' ')[-1])
            return []


# Global Helius client instance
helius_client = HeliusClient()
