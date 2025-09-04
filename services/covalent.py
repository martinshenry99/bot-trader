"""
Covalent Service for Meme Trader V4 Pro
Handles Ethereum and BSC chain data with API key rotation
"""

import aiohttp
import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from config import Config
from utils.key_manager import get_api_key, mark_key_rate_limited, mark_key_quota_exhausted

logger = logging.getLogger(__name__)

@dataclass
class TokenTransfer:
    """Token transfer data"""
    tx_hash: str
    block_height: int
    block_signed_at: str
    from_address: str
    to_address: str
    token_address: str
    token_symbol: str
    token_name: str
    amount: str
    decimals: int
    value_usd: float
    gas_offered: int
    gas_spent: int
    gas_price: int
    fees_paid: float
    gas_quote_rate: float

@dataclass
class WalletMetrics:
    """Wallet performance metrics"""
    address: str
    chain: str
    win_rate: float
    max_multiplier: float
    avg_roi: float
    total_volume_usd: float
    trade_count: int
    recent_activity: int
    score: float
    risk_flags: List[str]

class CovalentClient:
    """Covalent API client with key rotation and comprehensive wallet analysis"""
    
    def __init__(self):
        # Allow overriding base via env if needed
        self.base_url = getattr(Config, 'COVALENT_API_BASE', None) or "https://api.covalenthq.com/v1"
        self.session = None
        self.cache = {}
        self.cache_ttl = Config.CACHE_TTL_SECONDS
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=45),
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) MemeTrader/1.0',
                    'Accept': 'application/json, text/plain, */*',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Origin': 'https://www.covalenthq.com',
                    'Referer': 'https://www.covalenthq.com/',
                    'Cache-Control': 'no-cache',
                    'Pragma': 'no-cache',
                    'Connection': 'keep-alive'
                },
                trust_env=True
            )
        return self.session
    
    async def _make_request(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """Make API request with key rotation and error handling"""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                api_key = get_api_key('covalent')
                if not api_key:
                    logger.error("No available Covalent API keys")
                    return None
                
                url = f"{self.base_url}{endpoint}"
                if params is None:
                    params = {}
                # Prefer header-based auth to reduce query param blocking
                request_headers = {'x-api-key': api_key}
                
                session = await self._get_session()
                async with session.get(url, params=params, headers=request_headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('error') or data.get('error_code'):
                            logger.error(f"Covalent API error: {data}")
                            return None
                        return data
                    
                    elif response.status == 429:  # Rate limited
                        logger.warning(f"Rate limited on attempt {attempt + 1}")
                        mark_key_rate_limited('covalent', api_key)
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)  # Exponential backoff
                            continue
                    
                    elif response.status == 402:  # Quota exceeded
                        logger.error(f"Quota exceeded for key {api_key[:8]}...")
                        mark_key_quota_exhausted('covalent', api_key)
                        if attempt < max_retries - 1:
                            continue
                    
                    elif response.status == 403:
                        body = await response.text()
                        if 'Cloudflare' in body or 'blocked' in body:
                            logger.error("Covalent request blocked by Cloudflare (HTTP 403). Consider using residential IP or proxy.")
                        else:
                            logger.error(f"HTTP 403: {body}")
                        # Cooldown the key briefly and try next key if available
                        mark_key_rate_limited('covalent', api_key)
                        if attempt < max_retries - 1:
                            await asyncio.sleep(1)
                            continue
                        return None
                    else:
                        logger.error(f"HTTP {response.status}: {await response.text()}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(1)
                            continue
                
            except asyncio.TimeoutError:
                logger.warning(f"Request timeout on attempt {attempt + 1}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                    continue
            
            except Exception as e:
                logger.error(f"Request error on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                    continue
        
        logger.error("All retry attempts failed")
        return None
    
    async def get_recent_transactions(self, chain_id: int, limit: int = 1000) -> List[Dict]:
        """Get recent transactions for discovery scanning"""
        try:
            # Use recent blocks endpoint for discovery
            endpoint = f"/{chain_id}/block_v3/latest/"
            params = {'page-size': min(limit, 1000)}
            
            data = await self._make_request(endpoint, params)
            if not data or 'data' not in data:
                return []
            
            # Extract transactions from recent blocks
            transactions = []
            for block in data['data']['items'][:10]:  # Last 10 blocks
                if 'transactions' in block:
                    transactions.extend(block['transactions'])
            
            return transactions[:limit]
            
        except Exception as e:
            logger.error(f"Failed to get recent transactions: {e}")
            return []
    
    async def get_wallet_transactions(self, address: str, chain_id: int, 
                                   start_block: int = None, end_block: int = None) -> List[TokenTransfer]:
        """Get wallet transactions with comprehensive data"""
        try:
            endpoint = f"/{chain_id}/address/{address}/transactions_v3/"
            params = {
                'page-size': 1000,
                'no-nft-fetch': 'true'
            }
            
            if start_block:
                params['start-block'] = start_block
            if end_block:
                params['end-block'] = end_block
            
            data = await self._make_request(endpoint, params)
            if not data or 'data' not in data:
                return []
            
            transfers = []
            for tx in data['data']['items']:
                # Extract token transfers
                for transfer in tx.get('transfers', []):
                    if transfer.get('token_address'):  # Skip native token transfers
                        transfers.append(TokenTransfer(
                            tx_hash=tx['tx_hash'],
                            block_height=tx['block_height'],
                            block_signed_at=tx['block_signed_at'],
                            from_address=transfer['from_address'],
                            to_address=transfer['to_address'],
                            token_address=transfer['token_address'],
                            token_symbol=transfer.get('contract_ticker_symbol', ''),
                            token_name=transfer.get('contract_name', ''),
                            amount=transfer['delta'],
                            decimals=transfer.get('contract_decimals', 18),
                            value_usd=float(transfer.get('quote', 0)),
                            gas_offered=tx.get('gas_offered', 0),
                            gas_spent=tx.get('gas_spent', 0),
                            gas_price=tx.get('gas_price', 0),
                            fees_paid=float(tx.get('fees_paid', 0)),
                            gas_quote_rate=float(tx.get('gas_quote_rate', 0))
                        ))
            
            return transfers
            
        except Exception as e:
            logger.error(f"Failed to get wallet transactions: {e}")
            return []
    
    async def get_token_holders(self, token_address: str, chain_id: int, 
                              page_size: int = 1000) -> List[Dict]:
        """Get token holders for graph analysis"""
        try:
            endpoint = f"/{chain_id}/tokens/{token_address}/token_holders_v3/"
            params = {'page-size': page_size}
            
            data = await self._make_request(endpoint, params)
            if not data or 'data' not in data:
                return []
            
            return data['data']['items']
            
        except Exception as e:
            logger.error(f"Failed to get token holders: {e}")
            return []
    
    async def get_token_metadata(self, token_address: str, chain_id: int) -> Optional[Dict]:
        """Get token metadata and pricing"""
        try:
            endpoint = f"/{chain_id}/tokens/{token_address}/"
            
            data = await self._make_request(endpoint)
            if not data or 'data' not in data:
                return None
            
            return data['data']['items'][0] if data['data']['items'] else None
            
        except Exception as e:
            logger.error(f"Failed to get token metadata: {e}")
            return None
    
    async def analyze_wallet_performance(self, address: str, chain_id: int) -> Optional[WalletMetrics]:
        """Analyze wallet performance for scoring"""
        try:
            # Get recent transactions
            transfers = await self.get_wallet_transactions(address, chain_id)
            if not transfers:
                return None
            
            # Group by token for buy/sell analysis
            token_trades = {}
            for transfer in transfers:
                token = transfer.token_address
                if token not in token_trades:
                    token_trades[token] = {'buys': [], 'sells': []}
                
                # Determine if buy or sell based on direction
                if transfer.from_address.lower() == address.lower():
                    token_trades[token]['sells'].append(transfer)
                else:
                    token_trades[token]['buys'].append(transfer)
            
            # Calculate performance metrics
            completed_trades = []
            total_volume_usd = 0
            recent_activity = 0
            thirty_days_ago = datetime.now() - timedelta(days=30)
            
            for token, trades in token_trades.items():
                if trades['buys'] and trades['sells']:
                    # Find matching buy/sell pairs
                    for buy in trades['buys']:
                        for sell in trades['sells']:
                            if sell.block_height > buy.block_height:
                                # Calculate ROI
                                buy_value = float(buy.value_usd) if buy.value_usd > 0 else 0
                                sell_value = float(sell.value_usd) if sell.value_usd > 0 else 0
                                
                                if buy_value > 0:
                                    roi = sell_value / buy_value
                                    completed_trades.append({
                                        'roi': roi,
                                        'buy_value': buy_value,
                                        'sell_value': sell_value,
                                        'buy_time': buy.block_signed_at,
                                        'sell_time': sell.block_signed_at
                                    })
                                    total_volume_usd += buy_value
                                    
                                    # Check recent activity
                                    sell_time = datetime.fromisoformat(sell.block_signed_at.replace('Z', '+00:00'))
                                    if sell_time > thirty_days_ago:
                                        recent_activity += 1
            
            if not completed_trades:
                return None
            
            # Calculate metrics
            win_rate = len([t for t in completed_trades if t['roi'] > 1]) / len(completed_trades) * 100
            max_multiplier = max(t['roi'] for t in completed_trades)
            avg_roi = sum(t['roi'] for t in completed_trades) / len(completed_trades)
            trade_count = len(completed_trades)
            
            # Calculate score based on exact weights from requirements
            score = 0
            
            # Win Rate (20 points)
            if win_rate >= 80:
                score += 20
            elif win_rate >= 70:
                score += 15
            elif win_rate >= 65:
                score += 10
            
            # Max Multiplier (20 points)
            if max_multiplier >= 200:
                score += 20
            elif max_multiplier >= 100:
                score += 15
            elif max_multiplier >= 50:
                score += 10
            
            # Average ROI (15 points)
            if avg_roi > 5:
                score += 15
            elif avg_roi > 3:
                score += 10
            elif avg_roi > 2:
                score += 5
            
            # Trading Volume (15 points)
            if total_volume_usd > 100000:
                score += 15
            elif total_volume_usd > 50000:
                score += 10
            elif total_volume_usd > 15000:
                score += 5
            
            # Consistency (10 points)
            if trade_count > 30:
                score += 10
            elif trade_count > 15:
                score += 5
            
            # Recency (10 points)
            if recent_activity > 0:
                score += 10
            
            # Risk flags (no negative points for now, could be enhanced)
            risk_flags = []
            
            return WalletMetrics(
                address=address,
                chain=self._get_chain_name(chain_id),
                win_rate=win_rate,
                max_multiplier=max_multiplier,
                avg_roi=avg_roi,
                total_volume_usd=total_volume_usd,
                trade_count=trade_count,
                recent_activity=recent_activity,
                score=score,
                risk_flags=risk_flags
            )
            
        except Exception as e:
            logger.error(f"Failed to analyze wallet performance: {e}")
            return None
    
    def _get_chain_name(self, chain_id: int) -> str:
        """Convert chain ID to name"""
        chain_map = {
            1: 'ethereum',
            56: 'bsc',
            137: 'polygon',
            42161: 'arbitrum',
            10: 'optimism'
        }
        return chain_map.get(chain_id, f'chain_{chain_id}')
    
    async def close(self):
        """Close aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()

# Global Covalent client instance
covalent_client = CovalentClient()

async def get_covalent_client() -> CovalentClient:
    """Get Covalent client instance"""
    return covalent_client 