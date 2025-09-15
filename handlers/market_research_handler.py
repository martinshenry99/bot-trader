"""Market research command handler"""
import logging
from typing import Optional
from datetime import datetime

from bot.commands import command_handler
from services.market_research import MarketResearch
from utils.formatting import (
    format_table, format_money, format_percentage,
    format_number, format_timestamp
)

logger = logging.getLogger(__name__)

class MarketResearchHandler:
    """Handler for market research commands"""
    
    def __init__(self, market_research: MarketResearch):
        self.research = market_research
    
    @command_handler("analyze")
    async def analyze_token(self, token_address: str, chain: str = "ethereum") -> str:
        """Get comprehensive token analysis"""
        try:
            analysis = await self.research.get_token_analysis(token_address, chain)
            
            # Format response sections
            market_section = [
                "📊 Market Data",
                "------------",
                f"Price: {format_money(analysis['market_data']['price_usd'])}",
                f"Market Cap: {format_money(analysis['market_data']['market_cap'])}",
                f"24h Volume: {format_money(analysis['market_data']['volume_24h'])}",
                f"24h Change: {format_percentage(analysis['market_data']['price_change_24h'])}",
                f"7d Change: {format_percentage(analysis['market_data']['price_change_7d'])}"
            ]
            
            liquidity_section = [
                "",
                "💧 Liquidity",
                "-----------",
                f"Total Liquidity: {format_money(analysis['liquidity_data']['total_liquidity'])}",
                f"Active Pairs: {len(analysis['liquidity_data']['liquidity_pairs'])}",
                "Top Pools:",
                *[
                    f"• {p['dex']}: {format_money(p['liquidity'])}"
                    for p in analysis['liquidity_data']['biggest_pools'][:3]
                ]
            ]
            
            security_section = [
                "",
                "🔒 Security",
                "----------",
                f"Contract: {'✅ Verified' if analysis['security_info']['contract_verified'] else '❌ Unverified'}",
                f"Ownership: {analysis['security_info']['owner_status']}",
                f"Mint Function: {'🚨 Yes' if analysis['security_info']['can_mint'] else '✅ No'}",
                f"Blacklist: {'🚨 Yes' if analysis['security_info']['has_blacklist'] else '✅ No'}",
                f"Honeypot: {'🚨 YES!' if analysis['security_info']['is_honeypot'] else '✅ No'}"
            ]
            
            holder_section = [
                "",
                "👥 Holder Analysis",
                "----------------",
                f"Total Holders: {format_number(analysis['holder_analysis']['total_holders'])}",
                f"Top 10 Hold: {format_percentage(analysis['holder_analysis']['top_10_holdings'])}",
                f"Top 50 Hold: {format_percentage(analysis['holder_analysis']['top_50_holdings'])}",
                f"Locked Tokens: {format_percentage(analysis['holder_analysis']['locked_tokens'])}"
            ]
            
            risk_section = [
                "",
                "⚠️ Risk Assessment",
                "----------------",
                f"Overall Risk: {self._format_risk_level(analysis['risk_assessment']['overall_risk'])}",
                "",
                "Risk Factors:"
            ]
            if analysis['risk_assessment']['risk_factors']:
                risk_section.extend([
                    f"• {factor}" for factor in analysis['risk_assessment']['risk_factors']
                ])
            else:
                risk_section.append("• No significant risk factors identified")
            
            response = [
                f"🔍 Analysis for {chain}:{token_address}",
                "================================",
                *market_section,
                *liquidity_section,
                *security_section,
                *holder_section,
                *risk_section
            ]
            
            return "\n".join(response)
            
        except Exception as e:
            logger.error(f"Error analyzing token: {str(e)}")
            return f"❌ Error analyzing token: {str(e)}"
    
    @command_handler("trending")
    async def show_trending(self, chain: str = "ethereum") -> str:
        """Show trending tokens with analysis"""
        try:
            tokens = await self.research.get_trending_tokens(chain)
            
            if not tokens:
                return "No trending tokens found"
                
            headers = ["Token", "Price", "24h Change", "Risk", "Key Risks"]
            rows = []
            
            for token in tokens:
                rows.append([
                    f"{token['symbol']} ({token['address'][:6]}...)",
                    format_money(token['price_usd']),
                    format_percentage(token['price_change_24h']),
                    self._format_risk_level(token['risk_score']),
                    ", ".join(token['risk_factors']) or "None"
                ])
                
            response = [
                "🔥 Trending Tokens",
                "================",
                format_table(headers, rows)
            ]
            
            return "\n".join(response)
            
        except Exception as e:
            logger.error(f"Error showing trending tokens: {str(e)}")
            return f"❌ Error getting trending tokens: {str(e)}"
    
    @command_handler("market")
    async def show_market_overview(self, chain: str = "ethereum") -> str:
        """Show market overview"""
        try:
            overview = await self.research.get_market_overview(chain)
            
            response = [
                "🌍 Market Overview",
                "================",
                "",
                "Global Statistics:",
                f"Total Market Cap: {format_money(overview['global_stats']['total_market_cap'])}",
                f"24h Volume: {format_money(overview['global_stats']['total_volume_24h'])}",
                f"BTC Dominance: {format_percentage(overview['global_stats']['btc_dominance'])}",
                f"DeFi Dominance: {format_percentage(overview['global_stats']['defi_dominance'])}",
                "",
                f"Chain: {overview['chain_stats']['chain_name']}",
                f"Active Pairs: {format_number(overview['chain_stats']['active_pairs'])}",
                f"Total Liquidity: {format_money(overview['chain_stats']['total_liquidity'])}",
                f"24h Active Traders: {format_number(overview['chain_stats']['unique_traders_24h'])}",
                "",
                "Recent Activity:",
                f"1h Volume: {format_money(overview['trade_analysis']['recent_volume'])}",
                f"Average Slippage: {format_percentage(overview['trade_analysis']['average_slippage'])}",
                f"Trades (1h): {overview['trade_analysis']['trade_count_1h']}",
                f"Success Rate: {format_percentage(overview['trade_analysis']['successful_trades'] / overview['trade_analysis']['trade_count_1h'] * 100)}"
            ]
            
            return "\n".join(response)
            
        except Exception as e:
            logger.error(f"Error showing market overview: {str(e)}")
            return f"❌ Error getting market overview: {str(e)}"
    
    @command_handler("pair")
    async def analyze_pair(
        self,
        token_address: str,
        pair_address: str,
        chain: str = "ethereum",
        timeframe: str = "24h"
    ) -> str:
        """Analyze trading pair performance"""
        try:
            analytics = await self.research.get_pair_analytics(
                token_address,
                pair_address,
                chain,
                timeframe
            )
            
            volume_section = [
                "📊 Volume Analysis",
                "----------------",
                f"Buy Volume: {format_money(analytics['volume_analysis']['buy_volume'])}",
                f"Sell Volume: {format_money(analytics['volume_analysis']['sell_volume'])}",
                f"Buy Trades: {analytics['volume_analysis']['buy_count']}",
                f"Sell Trades: {analytics['volume_analysis']['sell_count']}"
            ]
            
            price_section = [
                "",
                "💰 Price Analysis",
                "---------------",
                f"Current: {format_money(analytics['price_analysis']['current_price'])}",
                f"High: {format_money(analytics['price_analysis']['price_high'])}",
                f"Low: {format_money(analytics['price_analysis']['price_low'])}",
                f"Open: {format_money(analytics['price_analysis']['price_open'])}"
            ]
            
            liquidity_section = [
                "",
                "💧 Liquidity Analysis",
                "------------------",
                f"Current Liquidity: {format_money(analytics['liquidity_analysis']['current_liquidity']['total_liquidity'])}",
                "",
                "Recent Changes:"
            ]
            
            changes = analytics['liquidity_analysis']['liquidity_changes']
            if changes:
                for change in changes[:5]:  # Show last 5 changes
                    liquidity_section.append(
                        f"• {change['type'].upper()}: {format_money(change['amount_usd'])} "
                        f"({format_timestamp(change['timestamp'])})"
                    )
            else:
                liquidity_section.append("• No recent liquidity changes")
            
            metrics_section = [
                "",
                "📈 Trading Metrics",
                "----------------",
                f"Average Trade: {format_money(analytics['trade_metrics']['average_trade_size'])}",
                f"Largest Trade: {format_money(analytics['trade_metrics']['largest_trade'])}",
                f"Unique Traders: {analytics['trade_metrics']['unique_traders']}"
            ]
            
            response = [
                f"🔍 Pair Analysis - {timeframe.upper()}",
                f"Chain: {chain}",
                f"Pair: {pair_address}",
                "================================",
                *volume_section,
                *price_section,
                *liquidity_section,
                *metrics_section
            ]
            
            return "\n".join(response)
            
        except Exception as e:
            logger.error(f"Error analyzing pair: {str(e)}")
            return f"❌ Error analyzing pair: {str(e)}"
    
    def _format_risk_level(self, risk_score: float) -> str:
        """Format risk score with color indicator"""
        if risk_score >= 0.7:
            return f"🔴 HIGH ({risk_score:.1%})"
        elif risk_score >= 0.4:
            return f"🟡 MEDIUM ({risk_score:.1%})"
        else:
            return f"🟢 LOW ({risk_score:.1%})"
