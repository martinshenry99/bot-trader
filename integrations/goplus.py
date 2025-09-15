"""
Enhanced GoPlus API integration with security scoring
"""

import logging
from typing import Dict, Optional, List, Any
from decimal import Decimal
import aiohttp
import json
from datetime import datetime, timedelta
from .base import BaseAPIClient

logger = logging.getLogger(__name__)

class GoPlusAPI(BaseAPIClient):
    """Enhanced GoPlus API integration with security scoring"""
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.base_url = "https://api.gopluslabs.io/api/v1"
        self.cache_duration = timedelta(minutes=5)
        self._cache: Dict[str, Dict] = {}
        
        # Security scoring weights
        self.weights = {
            'honeypot_risk': 0.30,      # 30% weight for honeypot detection
            'owner_risk': 0.20,         # 20% for owner/admin risks
            'liquidity_risk': 0.15,     # 15% for liquidity risks
            'trading_risk': 0.15,       # 15% for trading restrictions
            'contract_risk': 0.20       # 20% for contract security issues
        }
    
    async def get_token_security(
        self,
        token_address: str,
        chain: str
    ) -> Dict:
        """Get comprehensive token security analysis"""
        try:
            # Check cache first
            cache_key = f"{chain}:{token_address}"
            cached = self._get_cached(cache_key)
            if cached:
                return cached
            
            # Get raw security data
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Bearer {self.api_key}"}
                
                url = f"{self.base_url}/token_security/{chain}/{token_address}"
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        raise Exception(
                            f"API request failed: {response.status}"
                        )
                    
                    data = await response.json()
            
            # Process and score security data
            security_info = self._process_security_data(data)
            
            # Cache result
            self._cache_result(cache_key, security_info)
            
            return security_info
            
        except Exception as e:
            logger.error(f"Error in GoPlus security check: {str(e)}")
            raise
    
    def _process_security_data(self, data: Dict) -> Dict:
        """Process and score raw security data"""
        try:
            security_scores = {
                'honeypot_risk': self._calculate_honeypot_risk(data),
                'owner_risk': self._calculate_owner_risk(data),
                'liquidity_risk': self._calculate_liquidity_risk(data),
                'trading_risk': self._calculate_trading_risk(data),
                'contract_risk': self._calculate_contract_risk(data)
            }
            
            # Calculate weighted overall risk score (0-1, lower is better)
            overall_risk = sum(
                score * self.weights[risk_type]
                for risk_type, score in security_scores.items()
            )
            
            # Generate security flags
            flags = self._generate_security_flags(data, security_scores)
            
            return {
                'is_honeypot': data.get('is_honeypot', False),
                'is_proxy': data.get('is_proxy', False),
                'proxy_verified': data.get('proxy_verified', False),
                'owner_address': data.get('owner_address'),
                'creator_address': data.get('creator_address'),
                'holder_count': data.get('holder_count', 0),
                'total_supply': data.get('total_supply'),
                'buy_tax': data.get('buy_tax', 0),
                'sell_tax': data.get('sell_tax', 0),
                'cannot_buy': data.get('cannot_buy', False),
                'cannot_sell': data.get('cannot_sell', False),
                'trading_cooldown': data.get('trading_cooldown', 0),
                'personal_slippage_modifiable': data.get(
                    'personal_slippage_modifiable',
                    True
                ),
                'is_blacklisted': data.get('is_blacklisted', False),
                'is_whitelisted': data.get('is_whitelisted', False),
                'can_take_back_ownership': data.get(
                    'can_take_back_ownership',
                    False
                ),
                'owner_change_balance': data.get(
                    'owner_change_balance',
                    False
                ),
                'hidden_owner': data.get('hidden_owner', False),
                'anti_whale': data.get('anti_whale', False),
                'anti_whale_modifiable': data.get(
                    'anti_whale_modifiable',
                    False
                ),
                'slippage_modifiable': data.get(
                    'slippage_modifiable',
                    False
                ),
                'is_mintable': data.get('is_mintable', False),
                'is_open_source': data.get('is_open_source', True),
                'is_proxy_contract': data.get('is_proxy_contract', False),
                'implementation_address': data.get('implementation_address'),
                'security_scores': security_scores,
                'overall_risk': overall_risk,
                'risk_level': self._get_risk_level(overall_risk),
                'security_flags': flags,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error processing security data: {str(e)}")
            raise
    
    def _calculate_honeypot_risk(self, data: Dict) -> float:
        """Calculate honeypot risk score"""
        risk = 0.0
        
        if data.get('is_honeypot'):
            risk = 1.0
        else:
            # Add risk for concerning factors
            if data.get('cannot_sell'):
                risk += 0.7
            if data.get('cannot_buy'):
                risk += 0.3
            if data.get('sell_tax', 0) > 10:
                risk += 0.3
            if data.get('buy_tax', 0) > 10:
                risk += 0.2
        
        return min(risk, 1.0)
    
    def _calculate_owner_risk(self, data: Dict) -> float:
        """Calculate ownership risk score"""
        risk = 0.0
        
        if data.get('hidden_owner'):
            risk += 0.4
        if data.get('can_take_back_ownership'):
            risk += 0.3
        if data.get('owner_change_balance'):
            risk += 0.3
        if data.get('is_mintable'):
            risk += 0.2
        if not data.get('is_open_source'):
            risk += 0.2
        
        return min(risk, 1.0)
    
    def _calculate_liquidity_risk(self, data: Dict) -> float:
        """Calculate liquidity risk score"""
        risk = 0.0
        
        # Add risk based on liquidity metrics
        if data.get('total_liquidity_usd', 0) < 10000:
            risk += 0.4
        if data.get('lp_holders_count', 0) < 2:
            risk += 0.3
        if data.get('lp_total_supply', 0) == 0:
            risk += 0.3
        
        return min(risk, 1.0)
    
    def _calculate_trading_risk(self, data: Dict) -> float:
        """Calculate trading restriction risk score"""
        risk = 0.0
        
        if data.get('trading_cooldown', 0) > 0:
            risk += 0.2
        if data.get('anti_whale_modifiable'):
            risk += 0.2
        if data.get('slippage_modifiable'):
            risk += 0.2
        if not data.get('personal_slippage_modifiable'):
            risk += 0.2
        if data.get('is_blacklisted'):
            risk += 0.4
        
        return min(risk, 1.0)
    
    def _calculate_contract_risk(self, data: Dict) -> float:
        """Calculate contract security risk score"""
        risk = 0.0
        
        if data.get('is_proxy') and not data.get('proxy_verified'):
            risk += 0.4
        if not data.get('is_open_source'):
            risk += 0.3
        if data.get('similar_honeypots', 0) > 0:
            risk += 0.3
        if data.get('contract_warnings', []):
            risk += 0.2
        
        return min(risk, 1.0)
    
    def _generate_security_flags(
        self,
        data: Dict,
        scores: Dict[str, float]
    ) -> List[str]:
        """Generate human-readable security flags"""
        flags = []
        
        # Honeypot flags
        if data.get('is_honeypot'):
            flags.append("⚠️ CRITICAL: Confirmed honeypot")
        elif scores['honeypot_risk'] > 0.7:
            flags.append("⚠️ HIGH RISK: Possible honeypot")
        
        # Owner risks
        if data.get('hidden_owner'):
            flags.append("⚠️ WARNING: Hidden owner")
        if data.get('can_take_back_ownership'):
            flags.append("⚠️ WARNING: Ownership can be reclaimed")
        if data.get('owner_change_balance'):
            flags.append("⚠️ WARNING: Owner can modify balances")
        
        # Trading risks
        if data.get('cannot_sell'):
            flags.append("⚠️ CRITICAL: Selling disabled")
        if data.get('cannot_buy'):
            flags.append("⚠️ CRITICAL: Buying disabled")
        if data.get('trading_cooldown', 0) > 0:
            flags.append(f"ℹ️ Trading cooldown: {data['trading_cooldown']}s")
        
        # Contract risks
        if not data.get('is_open_source'):
            flags.append("⚠️ WARNING: Contract not verified")
        if data.get('is_proxy') and not data.get('proxy_verified'):
            flags.append("⚠️ WARNING: Unverified proxy contract")
        
        # Tax warnings
        buy_tax = data.get('buy_tax', 0)
        sell_tax = data.get('sell_tax', 0)
        if buy_tax > 10 or sell_tax > 10:
            flags.append(
                f"⚠️ High taxes: Buy {buy_tax}%, Sell {sell_tax}%"
            )
        
        return flags
    
    def _get_risk_level(self, risk_score: float) -> str:
        """Convert risk score to level"""
        if risk_score >= 0.7:
            return "Critical"
        elif risk_score >= 0.5:
            return "High"
        elif risk_score >= 0.3:
            return "Medium"
        else:
            return "Low"
    
    def _get_cached(self, key: str) -> Optional[Dict]:
        """Get cached security info if not expired"""
        if key in self._cache:
            entry = self._cache[key]
            timestamp = datetime.fromisoformat(entry['timestamp'])
            
            if datetime.utcnow() - timestamp < self.cache_duration:
                return entry
            
            # Remove expired entry
            del self._cache[key]
        
        return None
    
    def _cache_result(self, key: str, data: Dict):
        """Cache security analysis result"""
        self._cache[key] = data
        
        # Clean old cache entries
        now = datetime.utcnow()
        expired_keys = [
            k for k, v in self._cache.items()
            if now - datetime.fromisoformat(v['timestamp']) >= self.cache_duration
        ]
        
        for k in expired_keys:
            del self._cache[k]


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