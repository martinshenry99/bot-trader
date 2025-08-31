"""
GoPlus API integration for token security and honeypot detection
"""

import logging
from typing import Dict, List, Optional, Any
from .base import BaseAPIClient

logger = logging.getLogger(__name__)


class GoPlusClient(BaseAPIClient):
    """GoPlus API client for token security analysis"""
    
    def __init__(self, api_key: str):
        super().__init__(api_key, "https://api.gopluslabs.io/api/v1", rate_limit=100)
        
    async def health_check(self) -> bool:
        """Check GoPlus API health"""
        try:
            # GoPlus doesn't have a dedicated ping endpoint, so we'll check supported chains
            response = await self.make_request('GET', 'supported_chains')
            return response is not None and isinstance(response, dict)
        except Exception as e:
            logger.error(f"GoPlus health check failed: {e}")
            return False
    
    async def check_token_security(self, chain_id: str, contract_address: str) -> Optional[Dict]:
        """
        Check token security using GoPlus API
        
        Args:
            chain_id: Chain identifier (1 for ETH, 56 for BSC, etc.)
            contract_address: Token contract address
            
        Returns:
            Security analysis results or None if failed
        """
        try:
            endpoint = f"token_security/{chain_id}"
            params = {'contract_addresses': contract_address}
            
            response = await self.make_request('GET', endpoint, params=params)
            
            if response and 'result' in response:
                token_data = response['result'].get(contract_address.lower())
                if token_data:
                    return self._parse_security_result(token_data)
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to check token security: {e}")
            return None
    
    def _parse_security_result(self, token_data: Dict) -> Dict:
        """Parse GoPlus security result into standardized format"""
        try:
            # Parse honeypot indicators
            is_honeypot = (
                token_data.get('is_honeypot') == '1' or
                token_data.get('buy_tax', '0') == '100' or
                token_data.get('sell_tax', '0') == '100' or
                token_data.get('cannot_sell_all') == '1'
            )
            
            # Calculate risk score based on various factors
            risk_score = 0
            risk_factors = []
            
            # Honeypot checks
            if token_data.get('is_honeypot') == '1':
                risk_score += 100
                risk_factors.append('Confirmed honeypot')
            
            # Tax checks
            buy_tax = float(token_data.get('buy_tax', '0'))
            sell_tax = float(token_data.get('sell_tax', '0'))
            
            if buy_tax > 10:
                risk_score += 20
                risk_factors.append(f'High buy tax: {buy_tax}%')
            
            if sell_tax > 10:
                risk_score += 20
                risk_factors.append(f'High sell tax: {sell_tax}%')
            
            # Ownership checks
            if token_data.get('is_proxy') == '1':
                risk_score += 15
                risk_factors.append('Proxy contract')
            
            if token_data.get('is_mintable') == '1':
                risk_score += 10
                risk_factors.append('Mintable token')
            
            if token_data.get('owner_change_balance') == '1':
                risk_score += 25
                risk_factors.append('Owner can change balance')
            
            # Liquidity checks
            if token_data.get('is_anti_whale') == '1':
                risk_score += 5
                risk_factors.append('Anti-whale mechanism')
            
            if token_data.get('slippage_modifiable') == '1':
                risk_score += 15
                risk_factors.append('Modifiable slippage')
            
            # Trading restrictions
            if token_data.get('cannot_sell_all') == '1':
                risk_score += 30
                risk_factors.append('Cannot sell all tokens')
            
            if token_data.get('trading_cooldown') == '1':
                risk_score += 10
                risk_factors.append('Trading cooldown')
            
            # Determine risk level
            if risk_score >= 50:
                risk_level = 'HIGH'
            elif risk_score >= 25:
                risk_level = 'MEDIUM'
            elif risk_score >= 10:
                risk_level = 'LOW'
            else:
                risk_level = 'SAFE'
            
            return {
                'is_honeypot': is_honeypot,
                'risk_score': min(risk_score, 100),
                'risk_level': risk_level,
                'risk_factors': risk_factors,
                'buy_tax': buy_tax,
                'sell_tax': sell_tax,
                'is_proxy': token_data.get('is_proxy') == '1',
                'is_mintable': token_data.get('is_mintable') == '1',
                'owner_can_change_balance': token_data.get('owner_change_balance') == '1',
                'cannot_sell_all': token_data.get('cannot_sell_all') == '1',
                'trading_cooldown': token_data.get('trading_cooldown') == '1',
                'is_anti_whale': token_data.get('is_anti_whale') == '1',
                'slippage_modifiable': token_data.get('slippage_modifiable') == '1',
                'holder_count': int(token_data.get('holder_count', '0')),
                'owner_address': token_data.get('owner_address'),
                'creator_address': token_data.get('creator_address'),
                'total_supply': token_data.get('total_supply'),
                'raw_data': token_data
            }
            
        except Exception as e:
            logger.error(f"Failed to parse security result: {e}")
            return {
                'is_honeypot': True,
                'risk_score': 100,
                'risk_level': 'HIGH',
                'risk_factors': ['Analysis failed'],
                'raw_data': token_data
            }
    
    async def check_approval_security(self, chain_id: str, contract_address: str) -> Optional[Dict]:
        """Check token approval security"""
        try:
            endpoint = f"approval_security/{chain_id}"
            params = {'contract_addresses': contract_address}
            
            response = await self.make_request('GET', endpoint, params=params)
            
            if response and 'result' in response:
                return response['result'].get(contract_address.lower())
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to check approval security: {e}")
            return None
    
    async def check_dex_info(self, chain_id: str, contract_address: str) -> Optional[Dict]:
        """Get DEX trading information for token"""
        try:
            endpoint = f"dex_info/{chain_id}"
            params = {'contract_addresses': contract_address}
            
            response = await self.make_request('GET', endpoint, params=params)
            
            if response and 'result' in response:
                return response['result'].get(contract_address.lower())
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get DEX info: {e}")
            return None
    
    async def get_supported_chains(self) -> List[Dict]:
        """Get list of supported blockchain networks"""
        try:
            response = await self.make_request('GET', 'supported_chains')
            
            if response and isinstance(response, list):
                return response
            
            return []
            
        except Exception as e:
            logger.error(f"Failed to get supported chains: {e}")
            return []
    
    async def bulk_check_tokens(self, chain_id: str, contract_addresses: List[str]) -> Dict[str, Dict]:
        """
        Check multiple tokens at once (batch request)
        
        Args:
            chain_id: Chain identifier
            contract_addresses: List of contract addresses (max 50)
            
        Returns:
            Dictionary mapping addresses to security results
        """
        try:
            # Limit batch size to prevent API limits
            batch_size = 50
            all_results = {}
            
            for i in range(0, len(contract_addresses), batch_size):
                batch = contract_addresses[i:i + batch_size]
                addresses_param = ','.join(batch)
                
                endpoint = f"token_security/{chain_id}"
                params = {'contract_addresses': addresses_param}
                
                response = await self.make_request('GET', endpoint, params=params)
                
                if response and 'result' in response:
                    for address, data in response['result'].items():
                        all_results[address] = self._parse_security_result(data)
                
                # Add delay between batches to respect rate limits
                if i + batch_size < len(contract_addresses):
                    await asyncio.sleep(1)
            
            return all_results
            
        except Exception as e:
            logger.error(f"Failed to bulk check tokens: {e}")
            return {}