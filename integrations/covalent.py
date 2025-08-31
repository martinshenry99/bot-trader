"""
Covalent API integration for blockchain data
"""

import logging
from typing import Dict, List, Optional, Any
from .base import BaseAPIClient

logger = logging.getLogger(__name__)


class CovalentClient(BaseAPIClient):
    """Covalent API client for blockchain data"""
    
    def __init__(self, api_key: str):
        super().__init__(api_key, "https://api.covalenthq.com/v1", rate_limit=100)
        
    async def health_check(self) -> bool:
        """Check if Covalent API is accessible"""
        try:
            # Test with a simple chains endpoint
            result = await self.make_request('GET', '/chains/')
            return result is not None and 'data' in result
        except Exception as e:
            logger.error(f"Covalent health check failed: {e}")
            return False
    
    async def get_token_balances(self, chain_id: int, address: str) -> List[Dict]:
        """Get token balances for an address"""
        try:
            endpoint = f"/{chain_id}/address/{address}/balances_v2/"
            result = await self.make_request('GET', endpoint)
            
            if result and 'data' in result:
                return result['data'].get('items', [])
            return []
            
        except Exception as e:
            logger.error(f"Failed to get token balances: {e}")
            return []
    
    async def get_token_metadata(self, chain_id: int, token_address: str) -> Optional[Dict]:
        """Get token metadata"""
        try:
            endpoint = f"/{chain_id}/tokens/{token_address}/"
            result = await self.make_request('GET', endpoint)
            
            if result and 'data' in result:
                return result['data'].get('items', [{}])[0] if result['data'].get('items') else {}
            return None
            
        except Exception as e:
            logger.error(f"Failed to get token metadata: {e}")
            return None
    
    async def get_transactions(self, chain_id: int, address: str, page_size: int = 100) -> List[Dict]:
        """Get transactions for an address"""
        try:
            endpoint = f"/{chain_id}/address/{address}/transactions_v2/"
            params = {'page-size': page_size}
            result = await self.make_request('GET', endpoint, params=params)
            
            if result and 'data' in result:
                return result['data'].get('items', [])
            return []
            
        except Exception as e:
            logger.error(f"Failed to get transactions: {e}")
            return []
    
    async def get_token_holders(self, chain_id: int, token_address: str) -> List[Dict]:
        """Get token holders"""
        try:
            endpoint = f"/{chain_id}/tokens/{token_address}/token_holders/"
            result = await self.make_request('GET', endpoint)
            
            if result and 'data' in result:
                return result['data'].get('items', [])
            return []
            
        except Exception as e:
            logger.error(f"Failed to get token holders: {e}")
            return []
    
    async def get_log_events(self, chain_id: int, contract_address: str, 
                           starting_block: int = None, ending_block: int = None) -> List[Dict]:
        """Get log events for a contract"""
        try:
            endpoint = f"/{chain_id}/events/"
            params = {
                'contract-address': contract_address,
                'page-size': 1000
            }
            
            if starting_block:
                params['starting-block'] = starting_block
            if ending_block:
                params['ending-block'] = ending_block
                
            result = await self.make_request('GET', endpoint, params=params)
            
            if result and 'data' in result:
                return result['data'].get('items', [])
            return []
            
        except Exception as e:
            logger.error(f"Failed to get log events: {e}")
            return []