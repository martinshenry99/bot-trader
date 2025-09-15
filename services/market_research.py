"""Market research and analysis service"""
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from decimal import Decimal

from integrations.coingecko import CoinGeckoAPI
from integrations.goplus import GoPlusAPI
from integrations.covalent import CovalentAPI
from services.risk_scorer import RiskScorer

logger = logging.getLogger(__name__)

class MarketResearch:
    """Market research and analysis service"""
    
    def __init__(
        self,
        coingecko_api: CoinGeckoAPI,
        goplus_api: GoPlusAPI,
        covalent_api: CovalentAPI,
        risk_scorer: RiskScorer
    ):
        self.coingecko = coingecko_api
        self.goplus = goplus_api
        self.covalent = covalent_api
        self.risk_scorer = risk_scorer
    
    async def get_token_analysis(
        self,
        token_address: str,
        chain: str
    ) -> Dict:
        """Get comprehensive token analysis"""
        try:
            # Get market data
            market_data = await self.coingecko.get_token_market_data(
                chain, token_address
            )
            
            # Get security info
            security_info = await self.goplus.get_token_security(
                chain, token_address
            )
            
            # Get holder distribution
            holder_info = await self.covalent.get_token_holders(
                chain, token_address
            )
            
            # Get risk assessment
            risk_metrics = await self.risk_scorer.calculate_risk_score(
                token_address, chain
            )
            
            return {
                'market_data': {
                    'price_usd': market_data['current_price'],
                    'market_cap': market_data['market_cap'],
                    'total_supply': market_data['total_supply'],
                    'circulating_supply': market_data['circulating_supply'],
                    'volume_24h': market_data['volume_24h'],
                    'price_change_24h': market_data['price_change_24h'],
                    'price_change_7d': market_data['price_change_7d'],
                    'ath': market_data['ath'],
                    'atl': market_data['atl']
                },
                'liquidity_data': {
                    'total_liquidity': market_data['total_liquidity'],
                    'liquidity_pairs': market_data['liquidity_pairs'],
                    'biggest_pools': market_data['biggest_pools']
                },
                'security_info': {
                    'contract_verified': security_info['is_contract_verified'],
                    'owner_status': 'Renounced' if security_info['is_ownership_renounced'] else 'Active',
                    'can_mint': security_info['can_mint'],
                    'can_pause': security_info['can_pause_trading'],
                    'has_blacklist': security_info['has_blacklist'],
                    'is_honeypot': security_info['is_honeypot']
                },
                'holder_analysis': {
                    'total_holders': holder_info['total_holders'],
                    'top_10_holdings': holder_info['top_10_holdings'],
                    'top_50_holdings': holder_info['top_50_holdings'],
                    'holder_distribution': holder_info['distribution'],
                    'locked_tokens': holder_info['locked_tokens']
                },
                'risk_assessment': risk_metrics.to_dict()
            }
            
        except Exception as e:
            logger.error(f"Error analyzing token: {str(e)}")
            raise
    
    async def get_trending_tokens(self, chain: str) -> List[Dict]:
        """Get trending tokens with basic analysis"""
        try:
            trending = await self.coingecko.get_trending_tokens(chain)
            
            analyzed_tokens = []
            for token in trending:
                try:
                    # Quick risk assessment
                    risk_metrics = await self.risk_scorer.calculate_risk_score(
                        token['address'],
                        chain
                    )
                    
                    analyzed_tokens.append({
                        'address': token['address'],
                        'symbol': token['symbol'],
                        'name': token['name'],
                        'price_usd': token['price_usd'],
                        'price_change_24h': token['price_change_24h'],
                        'volume_24h': token['volume_24h'],
                        'market_cap': token['market_cap'],
                        'risk_score': risk_metrics.overall_risk,
                        'risk_factors': risk_metrics.risk_factors[:3]  # Top 3 risks
                    })
                    
                except Exception as e:
                    logger.warning(
                        f"Error analyzing trending token {token['address']}: {str(e)}"
                    )
                    continue
            
            return analyzed_tokens
            
        except Exception as e:
            logger.error(f"Error getting trending tokens: {str(e)}")
            raise
    
    async def get_market_overview(self, chain: str) -> Dict:
        """Get market overview with key metrics"""
        try:
            # Get market stats
            stats = await self.coingecko.get_market_stats(chain)
            
            # Get recent trades
            recent_trades = await self.covalent.get_recent_trades(chain)
            
            # Calculate market metrics
            total_volume = sum(
                Decimal(str(trade['volume_usd']))
                for trade in recent_trades
            )
            avg_slippage = sum(
                Decimal(str(trade.get('price_impact', 0)))
                for trade in recent_trades
            ) / len(recent_trades) if recent_trades else Decimal('0')
            
            return {
                'global_stats': {
                    'total_market_cap': stats['total_market_cap'],
                    'total_volume_24h': stats['total_volume_24h'],
                    'btc_dominance': stats['btc_dominance'],
                    'defi_dominance': stats['defi_dominance']
                },
                'chain_stats': {
                    'chain_name': chain,
                    'active_pairs': stats['active_pairs'],
                    'total_liquidity': stats['total_liquidity'],
                    'unique_traders_24h': stats['unique_traders_24h']
                },
                'trade_analysis': {
                    'recent_volume': str(total_volume),
                    'average_slippage': str(avg_slippage),
                    'trade_count_1h': len(recent_trades),
                    'successful_trades': sum(
                        1 for t in recent_trades
                        if t.get('status') == 'success'
                    )
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting market overview: {str(e)}")
            raise
    
    async def get_pair_analytics(
        self,
        token_address: str,
        pair_address: str,
        chain: str,
        timeframe: str = '24h'
    ) -> Dict:
        """Get detailed analytics for a trading pair"""
        try:
            # Get trade history
            trades = await self.covalent.get_pair_trades(
                chain,
                pair_address,
                timeframe
            )
            
            # Calculate metrics
            buy_volume = sum(
                Decimal(str(t['amount_usd']))
                for t in trades if t['side'] == 'buy'
            )
            sell_volume = sum(
                Decimal(str(t['amount_usd']))
                for t in trades if t['side'] == 'sell'
            )
            
            # Get price data
            prices = await self.coingecko.get_price_history(
                chain,
                token_address,
                timeframe
            )
            
            return {
                'volume_analysis': {
                    'buy_volume': str(buy_volume),
                    'sell_volume': str(sell_volume),
                    'buy_count': sum(1 for t in trades if t['side'] == 'buy'),
                    'sell_count': sum(1 for t in trades if t['side'] == 'sell')
                },
                'price_analysis': {
                    'current_price': prices[-1]['price'],
                    'price_high': max(p['price'] for p in prices),
                    'price_low': min(p['price'] for p in prices),
                    'price_open': prices[0]['price'],
                    'price_history': prices
                },
                'liquidity_analysis': {
                    'current_liquidity': await self._get_current_liquidity(
                        chain, pair_address
                    ),
                    'liquidity_changes': await self._get_liquidity_changes(
                        chain, pair_address, timeframe
                    )
                },
                'trade_metrics': {
                    'average_trade_size': str(
                        sum(Decimal(str(t['amount_usd'])) for t in trades) /
                        len(trades) if trades else Decimal('0')
                    ),
                    'largest_trade': str(max(
                        Decimal(str(t['amount_usd'])) for t in trades
                    )) if trades else '0',
                    'unique_traders': len({t['wallet'] for t in trades})
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting pair analytics: {str(e)}")
            raise
    
    async def _get_current_liquidity(
        self,
        chain: str,
        pair_address: str
    ) -> Dict:
        """Get current liquidity metrics for a pair"""
        try:
            pool_data = await self.covalent.get_pool_data(chain, pair_address)
            
            return {
                'total_liquidity': pool_data['total_liquidity_usd'],
                'token0_reserve': pool_data['token0_reserve'],
                'token1_reserve': pool_data['token1_reserve'],
                'token0_price': pool_data['token0_price_usd'],
                'token1_price': pool_data['token1_price_usd']
            }
            
        except Exception as e:
            logger.error(f"Error getting current liquidity: {str(e)}")
            raise
    
    async def _get_liquidity_changes(
        self,
        chain: str,
        pair_address: str,
        timeframe: str
    ) -> List[Dict]:
        """Get liquidity change history"""
        try:
            events = await self.covalent.get_pool_events(
                chain,
                pair_address,
                timeframe
            )
            
            changes = []
            for event in events:
                if event['event_type'] in ['mint', 'burn']:
                    changes.append({
                        'timestamp': event['timestamp'],
                        'type': event['event_type'],
                        'amount_usd': event['amount_usd'],
                        'wallet': event['wallet']
                    })
                    
            return changes
            
        except Exception as e:
            logger.error(f"Error getting liquidity changes: {str(e)}")
            raise
