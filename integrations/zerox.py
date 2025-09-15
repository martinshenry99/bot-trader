"""
0x Protocol integration for Ethereum and BSC token swaps with enhanced monitoring
"""

import asyncio
import logging
from decimal import Decimal
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from .base import BaseAPIClient
from monitor.enhanced_api_monitor import EnhancedAPIMonitor

logger = logging.getLogger(__name__)

@dataclass
class PriceData:
    """0x price quote data"""
    base_token: str
    quote_token: str
    price: Decimal
    gas_price: Decimal
    gas_amount: int
    value: Decimal
    allowance_target: Optional[str]
    sources: List[Dict[str, Any]]

@dataclass
class QuoteData:
    """0x swap quote data"""
    price: Decimal
    guaranteed_price: Decimal
    to: str
    data: str
    value: Decimal
    gas: int
    estimated_gas: int
    gas_price: Decimal
    protocol_fee: Decimal
    min_output_amount: Decimal
    sources: List[Dict[str, Any]]

class ZeroXClient(BaseAPIClient):
    """0x Protocol API client with enhanced monitoring"""
    
    def __init__(self, api_key: str, chain_id: int = 1):
        # Map chain IDs to 0x API endpoints
        api_urls = {
            1: "https://api.0x.org",      # Ethereum mainnet
            11155111: "https://sepolia.api.0x.org",  # Sepolia testnet
            56: "https://bsc.api.0x.org",  # BSC mainnet
            97: "https://bsc-testnet.api.0x.org"  # BSC testnet
        }
        
        base_url = api_urls.get(chain_id, api_urls[1])
        super().__init__(api_key, base_url, rate_limit=50)
        self.monitor = EnhancedAPIMonitor()
        self.chain_id = chain_id
        self.default_chain = chain_id
        
    async def _monitored_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make API request with monitoring"""
        start_time = asyncio.get_event_loop().time()
        
        try:
            if not await self.monitor.can_make_request("zerox"):
                raise Exception("Circuit breaker is open")
                
            response = await self.make_request(method, endpoint, **kwargs)
            latency = asyncio.get_event_loop().time() - start_time
            
            self.monitor.track_request(
                api="zerox",
                endpoint=endpoint,
                status_code=200,
                latency=latency,
                response_data=response
            )
            
            return response
                
        except Exception as e:
            latency = asyncio.get_event_loop().time() - start_time
            self.monitor.track_request(
                api="zerox",
                endpoint=endpoint,
                status_code=500,
                latency=latency
            )
            raise
            
    async def get_price(
        self,
        sell_token: str,
        buy_token: str,
        sell_amount: Optional[int] = None,
        buy_amount: Optional[int] = None,
        chain_id: Optional[int] = None
    ) -> Optional[PriceData]:
        """Get price quote from 0x API"""
        try:
            params = {
                "sellToken": sell_token,
                "buyToken": buy_token,
            }
            
            if sell_amount:
                params["sellAmount"] = str(sell_amount)
            if buy_amount:
                params["buyAmount"] = str(buy_amount)
            if chain_id:
                params["chainId"] = chain_id
                
            data = await self._monitored_request(
                "GET",
                "/swap/v1/price",
                params=params
            )
            
            return PriceData(
                base_token=sell_token,
                quote_token=buy_token,
                price=Decimal(data["price"]),
                gas_price=Decimal(data["gasPrice"]),
                gas_amount=int(data["estimatedGas"]),
                value=Decimal(data.get("value", "0")),
                allowance_target=data.get("allowanceTarget"),
                sources=data.get("sources", [])
            )
            
        except Exception as e:
            logger.error(f"Error getting 0x price: {e}")
            return None
            
    async def get_quote(
        self,
        sell_token: str,
        buy_token: str,
        sell_amount: Optional[int] = None,
        buy_amount: Optional[int] = None,
        slippage: float = 0.01,
        chain_id: Optional[int] = None
    ) -> Optional[QuoteData]:
        """Get swap quote from 0x API"""
        try:
            params = {
                "sellToken": sell_token,
                "buyToken": buy_token,
                "slippagePercentage": str(slippage),
            }
            
            if sell_amount:
                params["sellAmount"] = str(sell_amount)
            if buy_amount:
                params["buyAmount"] = str(buy_amount)
            if chain_id:
                params["chainId"] = chain_id
                
            data = await self._monitored_request(
                "GET",
                "/swap/v1/quote",
                params=params
            )
            
            return QuoteData(
                price=Decimal(data["price"]),
                guaranteed_price=Decimal(data["guaranteedPrice"]),
                to=data["to"],
                data=data["data"],
                value=Decimal(data.get("value", "0")),
                gas=int(data["gas"]),
                estimated_gas=int(data["estimatedGas"]),
                gas_price=Decimal(data["gasPrice"]),
                protocol_fee=Decimal(data.get("protocolFee", "0")),
                min_output_amount=Decimal(data.get("minimumOutputAmount", "0")),
                sources=data.get("sources", [])
            )
            
        except Exception as e:
            logger.error(f"Error getting 0x quote: {e}")
            return None
            
    async def get_supported_tokens(self) -> List[Dict[str, Any]]:
        """Get list of tokens supported by 0x"""
        try:
            data = await self._monitored_request("GET", "/swap/v1/tokens")
            return data["records"]
        except Exception as e:
            logger.error(f"Error getting supported tokens: {e}")
            return []
            
    async def get_sources(self) -> List[Dict[str, Any]]:
        """Get available liquidity sources"""
        try:
            return await self._monitored_request("GET", "/swap/v1/sources")
        except Exception as e:
            logger.error(f"Error getting sources: {e}")
            return []
            
    async def health_check(self) -> bool:
        """Check if 0x API is healthy"""
        try:
            response = await self._monitored_request("GET", "/healthcheck")
            return response.get("success", False)
        except Exception as e:
            logger.error(f"0x health check failed: {e}")
            return False

    async def verify_api_key(self) -> bool:
        """Verify if the API key is valid"""
        try:
            headers = {
                "0x-api-key": self.api_key
            }
            if self.api_key:
                headers['0x-api-key'] = self.api_key
            # Use a simple endpoint for health check
            response = await self.make_request('GET', '', headers=headers)
            return isinstance(response, dict)
        except Exception as e:
            logger.error(f"0x health check failed: {e}")
            return False
    
    async def get_quote(self, sell_token: str, buy_token: str, sell_amount: str, 
                       taker_address: Optional[str] = None, slippage_percentage: float = 0.01) -> Optional[Dict]:
        """
        Get swap quote from 0x API
        
        Args:
            sell_token: Token to sell (address or symbol)
            buy_token: Token to buy (address or symbol)
            sell_amount: Amount to sell in wei/smallest unit
            taker_address: Taker wallet address
            slippage_percentage: Slippage tolerance (0.01 = 1%)
            
        Returns:
            Quote data or None if failed
        """
        try:
            endpoint = "swap/v1/quote"
            params = {
                'sellToken': sell_token,
                'buyToken': buy_token,
                'sellAmount': sell_amount,
                'slippagePercentage': str(slippage_percentage)
            }
            
            if taker_address:
                params['takerAddress'] = taker_address
            
            # Add API key to headers for authenticated requests
            headers = {}
            if self.api_key:
                headers['0x-api-key'] = self.api_key
            
            response = await self.make_request('GET', endpoint, params=params, headers=headers)
            
            if response:
                return {
                    'price': response.get('price'),
                    'buy_amount': response.get('buyAmount'),
                    'sell_amount': response.get('sellAmount'),
                    'estimated_gas': response.get('estimatedGas'),
                    'gas_price': response.get('gasPrice'),
                    'protocol_fee': response.get('protocolFee'),
                    'minimum_protocol_fee': response.get('minimumProtocolFee'),
                    'buy_token_address': response.get('buyTokenAddress'),
                    'sell_token_address': response.get('sellTokenAddress'),
                    'allowance_target': response.get('allowanceTarget'),
                    'to': response.get('to'),
                    'data': response.get('data'),
                    'value': response.get('value'),
                    'sources': response.get('sources', []),
                    'orders': response.get('orders', []),
                    'raw_response': response
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get 0x quote: {e}")
            return None
    
    async def get_price(self, sell_token: str, buy_token: str, sell_amount: str) -> Optional[Dict]:
        """
        Get price quote (without transaction data)
        
        Args:
            sell_token: Token to sell
            buy_token: Token to buy  
            sell_amount: Amount to sell
            
        Returns:
            Price data or None if failed
        """
        try:
            endpoint = "swap/v1/price"
            params = {
                'sellToken': sell_token,
                'buyToken': buy_token,
                'sellAmount': sell_amount
            }
            
            headers = {}
            if self.api_key:
                headers['0x-api-key'] = self.api_key
            
            response = await self.make_request('GET', endpoint, params=params, headers=headers)
            
            if response:
                return {
                    'price': response.get('price'),
                    'buy_amount': response.get('buyAmount'),
                    'sell_amount': response.get('sellAmount'),
                    'estimated_gas': response.get('estimatedGas'),
                    'sources': response.get('sources', [])
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get 0x price: {e}")
            return None
    
    async def get_swap_sources(self) -> List[Dict]:
        """Get available liquidity sources"""
        try:
            response = await self.make_request('GET', 'swap/v1/sources')
            
            if response and 'records' in response:
                return response['records']
            
            return []
            
        except Exception as e:
            logger.error(f"Failed to get swap sources: {e}")
            return []
    
    async def get_orderbook(self, base_asset: str, quote_asset: str) -> Optional[Dict]:
        """Get orderbook for trading pair"""
        try:
            endpoint = "sra/v3/orderbook"
            params = {
                'baseAssetData': base_asset,
                'quoteAssetData': quote_asset
            }
            
            response = await self.make_request('GET', endpoint, params=params)
            return response
            
        except Exception as e:
            logger.error(f"Failed to get orderbook: {e}")
            return None
    
    async def check_approval_needed(self, token_address: str, owner_address: str, 
                                  spender_address: str, amount: str) -> bool:
        """
        Check if token approval is needed for trading
        
        Args:
            token_address: ERC20 token contract address
            owner_address: Token owner address
            spender_address: Spender address (usually 0x allowance target)
            amount: Amount to approve
            
        Returns:
            True if approval is needed, False otherwise
        """
        try:
            # This would require Web3 integration to check allowance
            # For now, return True to be safe
            return True
            
        except Exception as e:
            logger.error(f"Failed to check approval: {e}")
            return True
    
    async def estimate_gas(self, quote_data: Dict) -> Optional[int]:
        """Estimate gas for swap transaction"""
        try:
            # Extract gas estimate from quote
            estimated_gas = quote_data.get('estimated_gas')
            if estimated_gas:
                return int(estimated_gas)
            
            # Fallback estimation based on transaction complexity
            if quote_data.get('sources'):
                # Multi-source swaps typically use more gas
                return 250000
            else:
                # Simple swaps
                return 150000
                
        except Exception as e:
            logger.error(f"Failed to estimate gas: {e}")
            return 200000  # Conservative fallback
    
    async def get_token_metadata(self, token_address: str) -> Optional[Dict]:
        """Get token metadata (name, symbol, decimals)"""
        try:
            endpoint = f"swap/v1/tokens/{token_address}"
            response = await self.make_request('GET', endpoint)
            
            if response:
                return {
                    'address': response.get('address'),
                    'symbol': response.get('symbol'),
                    'name': response.get('name'),
                    'decimals': response.get('decimals'),
                    'logo_uri': response.get('logoURI')
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get token metadata: {e}")
            return None
    
    async def build_swap_transaction(self, quote_data: Dict, taker_address: str) -> Optional[Dict]:
        """
        Build complete swap transaction from quote
        
        Args:
            quote_data: Quote response from get_quote()
            taker_address: Address executing the swap
            
        Returns:
            Transaction object ready for signing
        """
        try:
            if not quote_data or 'to' not in quote_data:
                return None
            
            transaction = {
                'to': quote_data['to'],
                'data': quote_data['data'],
                'value': quote_data.get('value', '0'),
                'gas': quote_data.get('estimated_gas', '200000'),
                'gasPrice': quote_data.get('gas_price'),
                'from': taker_address
            }
            
            # Add chain ID for EIP-155
            transaction['chainId'] = self.chain_id
            
            return transaction
            
        except Exception as e:
            logger.error(f"Failed to build swap transaction: {e}")
            return None
    
    async def validate_quote(self, quote_data: Dict) -> Dict[str, Any]:
        """
        Validate quote data for potential issues
        
        Returns:
            Validation results with warnings and recommendations
        """
        try:
            warnings = []
            recommendations = []
            is_valid = True
            
            # Check price impact
            buy_amount = float(quote_data.get('buy_amount', 0))
            sell_amount = float(quote_data.get('sell_amount', 0))
            
            if buy_amount == 0 or sell_amount == 0:
                warnings.append("Invalid amounts in quote")
                is_valid = False
            
            # Check gas estimate
            estimated_gas = int(quote_data.get('estimated_gas', 0))
            if estimated_gas > 500000:
                warnings.append(f"High gas estimate: {estimated_gas:,}")
            
            # Check protocol fee
            protocol_fee = quote_data.get('protocol_fee', '0')
            if int(protocol_fee) > 0:
                recommendations.append(f"Protocol fee: {protocol_fee} wei")
            
            # Check sources
            sources = quote_data.get('sources', [])
            if len(sources) > 3:
                recommendations.append(f"Complex route through {len(sources)} sources")
            
            return {
                'is_valid': is_valid,
                'warnings': warnings,
                'recommendations': recommendations,
                'gas_estimate': estimated_gas,
                'source_count': len(sources)
            }
            
        except Exception as e:
            logger.error(f"Failed to validate quote: {e}")
            return {
                'is_valid': False,
                'warnings': ['Validation failed'],
                'recommendations': []
            }