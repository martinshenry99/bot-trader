"""
Jupiter API integration for Solana token swaps
"""

import base64
import logging
from typing import Dict, List, Optional, Any
from .base import BaseAPIClient

logger = logging.getLogger(__name__)


class JupiterClient(BaseAPIClient):
    """Jupiter API client for Solana token swaps"""
    
    def __init__(self, api_key: Optional[str] = None):
        # Jupiter API doesn't require authentication for basic usage
        # Use base URL without version, we'll add it in endpoints
        super().__init__(api_key or "", "https://quote-api.jup.ag", rate_limit=100)
        
    async def health_check(self) -> bool:
        """Check Jupiter API health"""
        try:
            # Test quote endpoint with USDC -> SOL
            # Use root endpoint for health check
            response = await self.make_request('GET', '')
            return response is not None and 'inAmount' in response
        except Exception as e:
            logger.error(f"Jupiter health check failed: {e}")
            return False
    
    async def get_quote(self, input_mint: str, output_mint: str, amount: int, 
                       slippage_bps: int = 50) -> Optional[Dict]:
        """
        Get swap quote from Jupiter
        
        Args:
            input_mint: Input token mint address
            output_mint: Output token mint address
            amount: Input amount in token's smallest unit
            slippage_bps: Slippage tolerance in basis points (50 = 0.5%)
            
        Returns:
            Quote data or None if failed
        """
        try:
            endpoint = "quote"
            params = {
                'inputMint': input_mint,
                'outputMint': output_mint,
                'amount': str(amount),
                'slippageBps': str(slippage_bps),
                'onlyDirectRoutes': 'false',
                'asLegacyTransaction': 'false'
            }
            
            response = await self.make_request('GET', endpoint, params=params)
            
            if response:
                return {
                    'input_mint': response.get('inputMint'),
                    'in_amount': response.get('inAmount'),
                    'output_mint': response.get('outputMint'),
                    'out_amount': response.get('outAmount'),
                    'other_amount_threshold': response.get('otherAmountThreshold'),
                    'swap_mode': response.get('swapMode'),
                    'slippage_bps': response.get('slippageBps'),
                    'platform_fee': response.get('platformFee'),
                    'price_impact_pct': response.get('priceImpactPct'),
                    'route_plan': response.get('routePlan', []),
                    'context_slot': response.get('contextSlot'),
                    'time_taken': response.get('timeTaken'),
                    'raw_response': response
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get Jupiter quote: {e}")
            return None
    
    async def get_swap_transaction(self, quote_data: Dict, user_public_key: str, 
                                  priority_fee: Optional[int] = None) -> Optional[Dict]:
        """
        Get swap transaction from Jupiter quote
        
        Args:
            quote_data: Quote response from get_quote()
            user_public_key: User's Solana public key
            priority_fee: Priority fee in microLamports (optional)
            
        Returns:
            Transaction data or None if failed
        """
        try:
            endpoint = "swap"
            
            payload = {
                'quoteResponse': quote_data.get('raw_response', quote_data),
                'userPublicKey': user_public_key,
                'wrapAndUnwrapSol': True,
                'useSharedAccounts': True,
                'feeAccount': None,
                'computeUnitPriceMicroLamports': priority_fee or 'auto'
            }
            
            response = await self.make_request('POST', endpoint, json=payload)
            
            if response:
                return {
                    'swap_transaction': response.get('swapTransaction'),
                    'last_valid_block_height': response.get('lastValidBlockHeight'),
                    'prioritization_fee_lamports': response.get('prioritizationFeeLamports'),
                    'compute_unit_limit': response.get('computeUnitLimit'),
                    'setup_transaction': response.get('setupTransaction'),
                    'cleanup_transaction': response.get('cleanupTransaction'),
                    'raw_response': response
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get swap transaction: {e}")
            return None
    
    async def get_tokens(self) -> List[Dict]:
        """Get list of all available tokens on Jupiter"""
        try:
            response = await self.make_request('GET', 'tokens')
            
            if response and isinstance(response, list):
                return response
            
            return []
            
        except Exception as e:
            logger.error(f"Failed to get tokens: {e}")
            return []
    
    async def get_indexed_route_map(self) -> Optional[Dict]:
        """Get indexed route map for all token pairs"""
        try:
            response = await self.make_request('GET', 'indexed-route-map')
            return response
            
        except Exception as e:
            logger.error(f"Failed to get route map: {e}")
            return None
    
    async def get_program_id_to_label(self) -> Optional[Dict]:
        """Get mapping of program IDs to human-readable labels"""
        try:
            response = await self.make_request('GET', 'program-id-to-label')
            return response
            
        except Exception as e:
            logger.error(f"Failed to get program labels: {e}")
            return None
    
    async def validate_quote(self, quote_data: Dict) -> Dict[str, Any]:
        """
        Validate Jupiter quote for potential issues
        
        Returns:
            Validation results with warnings and recommendations
        """
        try:
            warnings = []
            recommendations = []
            is_valid = True
            
            # Check amounts
            in_amount = int(quote_data.get('in_amount', 0))
            out_amount = int(quote_data.get('out_amount', 0))
            
            if in_amount == 0 or out_amount == 0:
                warnings.append("Invalid amounts in quote")
                is_valid = False
            
            # Check price impact
            price_impact = float(quote_data.get('price_impact_pct', 0))
            if price_impact > 5:
                warnings.append(f"High price impact: {price_impact:.2f}%")
            elif price_impact > 1:
                recommendations.append(f"Moderate price impact: {price_impact:.2f}%")
            
            # Check route complexity
            route_plan = quote_data.get('route_plan', [])
            if len(route_plan) > 3:
                recommendations.append(f"Complex route through {len(route_plan)} hops")
            
            # Check slippage
            slippage_bps = int(quote_data.get('slippage_bps', 0))
            if slippage_bps > 300:  # 3%
                warnings.append(f"High slippage tolerance: {slippage_bps/100:.1f}%")
            
            # Check platform fee
            platform_fee = quote_data.get('platform_fee')
            if platform_fee and int(platform_fee.get('amount', 0)) > 0:
                fee_amount = platform_fee['amount']
                recommendations.append(f"Platform fee: {fee_amount}")
            
            return {
                'is_valid': is_valid,
                'warnings': warnings,
                'recommendations': recommendations,
                'price_impact': price_impact,
                'route_hops': len(route_plan),
                'slippage_bps': slippage_bps
            }
            
        except Exception as e:
            logger.error(f"Failed to validate quote: {e}")
            return {
                'is_valid': False,
                'warnings': ['Validation failed'],
                'recommendations': []
            }
    
    async def estimate_fees(self, quote_data: Dict) -> Dict[str, int]:
        """
        Estimate various fees for the swap
        
        Returns:
            Dictionary with fee estimates in lamports
        """
        try:
            fees = {
                'transaction_fee': 5000,  # Base transaction fee
                'priority_fee': 0,
                'platform_fee': 0,
                'total_fee': 5000
            }
            
            # Add platform fee if present
            platform_fee = quote_data.get('platform_fee')
            if platform_fee:
                platform_fee_amount = int(platform_fee.get('amount', 0))
                fees['platform_fee'] = platform_fee_amount
                fees['total_fee'] += platform_fee_amount
            
            # Estimate priority fee based on route complexity
            route_plan = quote_data.get('route_plan', [])
            if len(route_plan) > 2:
                # More complex routes might need higher priority fees
                fees['priority_fee'] = 10000 * len(route_plan)
                fees['total_fee'] += fees['priority_fee']
            
            return fees
            
        except Exception as e:
            logger.error(f"Failed to estimate fees: {e}")
            return {
                'transaction_fee': 5000,
                'priority_fee': 0,
                'platform_fee': 0,
                'total_fee': 5000
            }
    
    async def decode_transaction(self, transaction_base64: str) -> Optional[Dict]:
        """
        Decode base64 transaction for inspection
        
        Args:
            transaction_base64: Base64 encoded transaction
            
        Returns:
            Decoded transaction data or None if failed
        """
        try:
            # Decode base64 transaction
            transaction_bytes = base64.b64decode(transaction_base64)
            
            # This would require Solana transaction parsing library
            # For now, return basic info
            return {
                'size_bytes': len(transaction_bytes),
                'raw_bytes': transaction_bytes.hex(),
                'is_valid': len(transaction_bytes) > 0
            }
            
        except Exception as e:
            logger.error(f"Failed to decode transaction: {e}")
            return None
    
    async def get_price_history(self, mint_address: str, timeframe: str = '1H') -> List[Dict]:
        """
        Get price history for a token (if available)
        
        Args:
            mint_address: Token mint address
            timeframe: Timeframe (1H, 4H, 1D, etc.)
            
        Returns:
            List of price data points
        """
        try:
            # Jupiter doesn't provide historical price data directly
            # This would need to be implemented with a different service
            logger.info("Price history not available through Jupiter API")
            return []
            
        except Exception as e:
            logger.error(f"Failed to get price history: {e}")
            return []
"""
Jupiter API Integration for Solana Trading and Route Optimization
"""

import logging
import aiohttp
import asyncio
from typing import Dict, List, Optional, Any
from decimal import Decimal
from .base import BaseAPIClient
from utils.key_manager import key_manager

logger = logging.getLogger(__name__)


class JupiterClient(BaseAPIClient):
    """Jupiter API client for Solana trading"""
    
    def __init__(self):
        super().__init__(None, "https://quote-api.jup.ag/v6", rate_limit=100)
        self.price_api_url = "https://api.jup.ag/price/v2"
        
    async def health_check(self) -> bool:
        """Check if Jupiter API is accessible"""
        try:
            result = await self.make_request('GET', '/tokens')
            return result is not None and len(result) > 0
        except Exception as e:
            logger.error(f"Jupiter health check failed: {e}")
            return False
    
    async def get_quote(self, input_mint: str, output_mint: str, amount: int, 
                       slippage_bps: int = 100) -> Optional[Dict]:
        """Get swap quote from Jupiter"""
        try:
            params = {
                'inputMint': input_mint,
                'outputMint': output_mint,
                'amount': amount,
                'slippageBps': slippage_bps,
                'onlyDirectRoutes': 'false',
                'asLegacyTransaction': 'false'
            }
            
            result = await self.make_request('GET', '/quote', params=params)
            
            if result:
                logger.info(f"Jupiter quote: {amount} -> {result.get('outAmount', 0)}")
                return result
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get Jupiter quote: {e}")
            return None
    
    async def get_swap_transaction(self, quote: Dict, wallet_address: str, 
                                 priority_fee: int = 0) -> Optional[Dict]:
        """Get swap transaction from Jupiter"""
        try:
            payload = {
                'quoteResponse': quote,
                'userPublicKey': wallet_address,
                'wrapAndUnwrapSol': True,
                'prioritizationFeeLamports': priority_fee,
                'asLegacyTransaction': False,
                'dynamicComputeUnitLimit': True,
                'skipUserAccountsRpcCalls': True
            }
            
            result = await self.make_request('POST', '/swap', data=payload)
            
            if result and 'swapTransaction' in result:
                return result
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get swap transaction: {e}")
            return None
    
    async def get_token_price(self, mint_address: str) -> Optional[float]:
        """Get token price from Jupiter"""
        try:
            session = await self.get_session()
            url = f"{self.price_api_url}"
            params = {'ids': mint_address}
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    price_data = data.get('data', {}).get(mint_address)
                    if price_data:
                        return float(price_data.get('price', 0))
                
                return None
                
        except Exception as e:
            logger.error(f"Failed to get token price: {e}")
            return None
    
    async def get_token_list(self) -> List[Dict]:
        """Get Jupiter token list"""
        try:
            result = await self.make_request('GET', '/tokens')
            
            if result and isinstance(result, list):
                return result
            
            return []
            
        except Exception as e:
            logger.error(f"Failed to get token list: {e}")
            return []
    
    async def simulate_swap(self, input_mint: str, output_mint: str, amount: int) -> Dict:
        """Simulate swap to check for honeypots and slippage"""
        try:
            # Get quote with high slippage tolerance for simulation
            quote = await self.get_quote(input_mint, output_mint, amount, slippage_bps=1000)
            
            if not quote:
                return {
                    'success': False,
                    'error': 'Failed to get quote',
                    'is_honeypot': True
                }
            
            # Analyze quote for potential issues
            input_amount = int(quote.get('inAmount', 0))
            output_amount = int(quote.get('outAmount', 0))
            
            if input_amount == 0 or output_amount == 0:
                return {
                    'success': False,
                    'error': 'Zero amounts detected',
                    'is_honeypot': True
                }
            
            # Check for excessive slippage
            price_impact = float(quote.get('priceImpactPct', 0))
            if price_impact > 50:  # 50% price impact indicates potential honeypot
                return {
                    'success': False,
                    'error': f'Excessive price impact: {price_impact}%',
                    'is_honeypot': True
                }
            
            return {
                'success': True,
                'price_impact': price_impact,
                'output_amount': output_amount,
                'is_honeypot': False,
                'route_plan': quote.get('routePlan', [])
            }
            
        except Exception as e:
            logger.error(f"Swap simulation failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'is_honeypot': True
            }
    
    async def get_route_map(self, input_mint: str, output_mint: str) -> List[str]:
        """Get available route map for token pair"""
        try:
            params = {
                'inputMint': input_mint,
                'outputMint': output_mint
            }
            
            result = await self.make_request('GET', '/route-map', params=params)
            
            if result and 'routes' in result:
                return result['routes']
            
            return []
            
        except Exception as e:
            logger.error(f"Failed to get route map: {e}")
            return []


# Global Jupiter client instance
jupiter_client = JupiterClient()
