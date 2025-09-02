"""
Address and contract formatting utilities for enhanced user experience
"""

from typing import Tuple, List, Dict, Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


class AddressFormatter:
    """Format addresses with block explorer links and action buttons"""
    
    BLOCK_EXPLORERS = {
        'ethereum': 'https://etherscan.io',
        'bsc': 'https://bscscan.com', 
        'solana': 'https://solscan.io'
    }
    
    CHAIN_NAMES = {
        'ethereum': 'ETH',
        'bsc': 'BSC',
        'solana': 'SOL'
    }
    
    @classmethod
    def format_wallet_address(cls, address: str, chain: str = 'ethereum', name: str = None) -> str:
        """Format wallet address with block explorer link"""
        try:
            # Shorten address for display
            if chain == 'solana':
                display_addr = f"{address[:6]}...{address[-4:]}" if len(address) > 20 else address
            else:
                display_addr = f"{address[:6]}...{address[-4:]}" if len(address) > 20 else address
            
            # Get block explorer URL
            explorer_base = cls.BLOCK_EXPLORERS.get(chain.lower(), cls.BLOCK_EXPLORERS['ethereum'])
            
            if chain.lower() == 'solana':
                explorer_url = f"{explorer_base}/account/{address}"
            else:
                explorer_url = f"{explorer_base}/address/{address}"
            
            # Format with name if provided
            if name:
                return f"[{name} ({display_addr})]({explorer_url})"
            else:
                return f"[{display_addr}]({explorer_url})"
                
        except Exception:
            # Fallback to simple formatting
            return f"`{address[:10]}...{address[-6:]}`" if len(address) > 20 else f"`{address}`"
    
    @classmethod
    def format_token_address(cls, address: str, chain: str = 'ethereum', symbol: str = None) -> str:
        """Format token contract address with block explorer link"""
        try:
            # Shorten address for display
            if chain == 'solana':
                display_addr = f"{address[:6]}...{address[-4:]}" if len(address) > 20 else address
            else:
                display_addr = f"{address[:6]}...{address[-4:]}" if len(address) > 20 else address
            
            # Get block explorer URL
            explorer_base = cls.BLOCK_EXPLORERS.get(chain.lower(), cls.BLOCK_EXPLORERS['ethereum'])
            
            if chain.lower() == 'solana':
                explorer_url = f"{explorer_base}/token/{address}"
            else:
                explorer_url = f"{explorer_base}/token/{address}"
            
            # Format with symbol if provided
            if symbol:
                return f"[{symbol} ({display_addr})]({explorer_url})"
            else:
                return f"[{display_addr}]({explorer_url})"
                
        except Exception:
            # Fallback to simple formatting
            return f"`{address[:10]}...{address[-6:]}`" if len(address) > 20 else f"`{address}`"
    
    @classmethod
    def format_transaction_hash(cls, tx_hash: str, chain: str = 'ethereum') -> str:
        """Format transaction hash with block explorer link"""
        try:
            display_hash = f"{tx_hash[:8]}...{tx_hash[-6:]}" if len(tx_hash) > 20 else tx_hash
            
            explorer_base = cls.BLOCK_EXPLORERS.get(chain.lower(), cls.BLOCK_EXPLORERS['ethereum'])
            
            if chain.lower() == 'solana':
                explorer_url = f"{explorer_base}/tx/{tx_hash}"
            else:
                explorer_url = f"{explorer_base}/tx/{tx_hash}"
            
            return f"[{display_hash}]({explorer_url})"
            
        except Exception:
            return f"`{tx_hash[:12]}...`" if len(tx_hash) > 20 else f"`{tx_hash}`"
    
    @classmethod
    def create_wallet_action_buttons(cls, wallet_address: str, chain: str = 'ethereum', 

def format_wallet_analysis(analysis: Dict) -> Tuple[str, InlineKeyboardMarkup]:
    """Format wallet analysis results for Telegram"""
    try:
        address = analysis['address']
        short_addr = f"{address[:8]}...{address[-6:]}"
        
        # Main analysis info
        message = f"🔍 **Wallet Analysis: `{short_addr}`**\n\n"
        
        # Score and classification
        score = analysis['score']
        classification = analysis['classification']
        
        if classification == "Safe":
            score_emoji = "🟢"
        elif classification == "Watch":
            score_emoji = "🟡"
        else:
            score_emoji = "🔴"
        
        message += f"{score_emoji} **Score:** {score}/100 ({classification})\n\n"
        
        # Trading metrics
        message += f"📊 **Trading Performance:**\n"
        message += f"• Max multiplier: {analysis['max_multiplier']:.1f}x\n"
        message += f"• Win rate: {analysis['win_rate']:.1f}%\n"
        message += f"• Avg hold: {analysis['avg_hold_time']:.1f} days\n"
        message += f"• Tokens traded: {analysis['tokens_traded']}\n"
        message += f"• Total volume: ${analysis['total_volume_usd']:,.0f}\n\n"
        
        # Top profitable tokens
        top_tokens = analysis.get('top_tokens', [])
        if top_tokens:
            message += f"💰 **Top Profitable Tokens:**\n"
            for i, token in enumerate(top_tokens[:3], 1):
                profit_mult = token.get('profit_multiplier', 1)
                usd_gain = token.get('usd_gain', 0)
                message += f"{i}. {token['symbol']}: {profit_mult:.1f}x (${usd_gain:,.0f})\n"
            message += "\n"
        
        # Graph metrics
        graph_metrics = analysis.get('graph_metrics', {})
        message += f"🌐 **Network Analysis:**\n"
        message += f"• Cluster size: {graph_metrics.get('cluster_size', 0)} addresses\n"
        message += f"• Funding sources: {graph_metrics.get('funding_sources', 0)}\n"
        message += f"• Centrality: {graph_metrics.get('centrality', 0):.3f}\n"
        
        if graph_metrics.get('is_dev_involved'):
            message += f"⚠️ Dev/founder patterns detected\n"
        
        message += "\n"
        
        # Risk flags
        risk_flags = analysis.get('risk_flags', [])
        if risk_flags:
            message += f"⚠️ **Risk Flags:** {', '.join(risk_flags)}\n\n"
        
        # Top counterparties
        counterparties = analysis.get('top_counterparties', [])
        if counterparties:
            message += f"🤝 **Top Counterparties:**\n"
            for i, cp in enumerate(counterparties[:3], 1):
                cp_short = f"{cp['address'][:8]}...{cp['address'][-6:]}"
                cex_flag = " (CEX)" if cp.get('is_cex') else ""
                message += f"{i}. `{cp_short}`{cex_flag} - ${cp['volume_usd']:,.0f}\n"
        
        # Analysis timestamp
        timestamp = analysis.get('analysis_timestamp', '')
        if timestamp:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            message += f"\n🕐 Analyzed: {dt.strftime('%Y-%m-%d %H:%M')} UTC"
        
        # Create inline buttons
        buttons = [
            [
                InlineKeyboardButton("👥 Follow Wallet", callback_data=f"follow_{address}"),
                InlineKeyboardButton("📋 Add to Watchlist", callback_data=f"watchlist_add_{address}")
            ]
        ]
        
        # Add counterparty analysis buttons
        if counterparties:
            for cp in counterparties[:2]:
                cp_short = f"{cp['address'][:6]}..."
                buttons.append([
                    InlineKeyboardButton(f"🔍 Analyze {cp_short}", callback_data=f"analyze_{cp['address']}")
                ])
        
        buttons.extend([
            [InlineKeyboardButton("📋 Copy Address", callback_data=f"copy_{address}")],
            [InlineKeyboardButton("🔍 View on Explorer", url=get_explorer_url(address, analysis.get('chain', 'ethereum')))]
        ])
        
        reply_markup = InlineKeyboardMarkup(buttons)
        
        return message, reply_markup
        
    except Exception as e:
        logger.error(f"Failed to format wallet analysis: {e}")
        return f"❌ Analysis formatting failed: {e}", None


def format_token_security(analysis: Dict) -> Tuple[str, InlineKeyboardMarkup]:
    """Format token security analysis for Telegram"""
    try:
        contract = analysis['contract_address']
        short_contract = f"{contract[:8]}...{contract[-6:]}"
        
        token_data = analysis.get('token_data', {})
        name = token_data.get('name', 'Unknown')
        symbol = token_data.get('symbol', 'UNK')
        
        # Header
        message = f"🔒 **Token Security: {name} ({symbol})**\n"
        message += f"📍 `{short_contract}`\n\n"
        
        # Risk assessment
        is_honeypot = analysis.get('is_honeypot', False)
        risk_score = analysis.get('risk_score', 0)
        risk_flags = analysis.get('risk_flags', [])
        
        if is_honeypot:
            message += f"⚠️ **HONEYPOT DETECTED** 🚨\n\n"
        elif risk_score >= 70:
            message += f"🔴 **HIGH RISK** (Score: {risk_score}/100)\n\n"
        elif risk_score >= 40:
            message += f"🟡 **MEDIUM RISK** (Score: {risk_score}/100)\n\n"
        else:
            message += f"🟢 **LOW RISK** (Score: {risk_score}/100)\n\n"
        
        # Honeypot test results
        honeypot_result = analysis.get('honeypot_result', {})
        if honeypot_result:
            simulation_passed = honeypot_result.get('simulation_passed', False)
            message += f"🧪 **Honeypot Test:** {'✅ PASSED' if simulation_passed else '❌ FAILED'}\n"
            
            if not simulation_passed:
                error_msg = honeypot_result.get('error_message', 'Unknown error')
                message += f"   Error: {error_msg}\n"
            
            buy_tax = honeypot_result.get('buy_tax', 0)
            sell_tax = honeypot_result.get('sell_tax', 0)
            if buy_tax > 0 or sell_tax > 0:
                message += f"   Buy tax: {buy_tax}% | Sell tax: {sell_tax}%\n"
            
            message += "\n"
        
        # Liquidity analysis
        liquidity_data = analysis.get('liquidity_data', {})
        if liquidity_data:
            total_liquidity = liquidity_data.get('total_liquidity_usd', 0)
            message += f"💧 **Liquidity:** ${total_liquidity:,.0f}\n"
            
            if total_liquidity < 5000:
                message += f"   ⚠️ LOW LIQUIDITY WARNING\n"
            
            is_locked = liquidity_data.get('liquidity_locked', False)
            message += f"   Lock status: {'🔒 Locked' if is_locked else '🔓 Unlocked'}\n\n"
        
        # Ownership analysis
        ownership_data = analysis.get('ownership_data', {})
        if ownership_data:
            owner_pct = ownership_data.get('owner_percentage', 0)
            is_renounced = ownership_data.get('renounced', False)
            
            message += f"👑 **Ownership:**\n"
            message += f"   Owner holds: {owner_pct:.1f}%\n"
            message += f"   Renounced: {'✅ Yes' if is_renounced else '❌ No'}\n\n"
        
        # Risk flags
        if risk_flags:
            message += f"⚠️ **Risk Flags:**\n"
            for flag in risk_flags:
                flag_emoji = {
                    'HONEYPOT': '🍯',
                    'LOW_LIQUIDITY': '💧',
                    'LIQUIDITY_RISK': '🌊',
                    'DEV_CONTROL': '👑',
                    'UNVERIFIED_CODE': '❓',
                    'HIGH_TAX': '💸'
                }.get(flag, '⚠️')
                message += f"   {flag_emoji} {flag.replace('_', ' ').title()}\n"
            message += "\n"
        
        # Recommendation
        recommendation = analysis.get('recommendation', 'UNKNOWN')
        rec_emoji = {
            'BUY': '🟢',
            'HOLD': '🟡', 
            'WATCH': '👀',
            'AVOID': '🔴'
        }.get(recommendation, '❓')
        
        message += f"{rec_emoji} **Recommendation: {recommendation}**\n\n"
        
        # Analysis timestamp
        timestamp = analysis.get('analysis_timestamp', '')
        if timestamp:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            message += f"🕐 Analyzed: {dt.strftime('%Y-%m-%d %H:%M')} UTC"
        
        # Create inline buttons
        buttons = []
        
        if is_honeypot or 'HONEYPOT' in risk_flags:
            buttons.append([
                InlineKeyboardButton("🚫 Add to Blacklist", callback_data=f"blacklist_{contract}")
            ])
        else:
            buttons.append([
                InlineKeyboardButton("📋 Add to Watchlist", callback_data=f"watchlist_add_{contract}"),
                InlineKeyboardButton("💰 Quick Buy", callback_data=f"quick_buy_{contract}")
            ])
        
        buttons.extend([
            [InlineKeyboardButton("📋 Copy Contract", callback_data=f"copy_{contract}")],
            [InlineKeyboardButton("🔍 View on Explorer", url=get_explorer_url(contract, analysis.get('chain', 'ethereum')))]
        ])
        
        reply_markup = InlineKeyboardMarkup(buttons)
        
        return message, reply_markup
        
    except Exception as e:
        logger.error(f"Failed to format token security: {e}")
        return f"❌ Security analysis formatting failed: {e}", None

                                   extra_buttons: List[Tuple[str, str]] = None) -> InlineKeyboardMarkup:
        """Create action buttons for wallet addresses"""
        keyboard = []
        
        # Analyze wallet button
        keyboard.append([
            InlineKeyboardButton("🔍 Analyze Wallet", callback_data=f"analyze_wallet_{wallet_address[:10]}")
        ])
        
        # Add to watchlist button
        keyboard.append([
            InlineKeyboardButton("👁️ Add to Watchlist", callback_data=f"add_watchlist_{wallet_address[:10]}")
        ])
        
        # Blacklist button  
        keyboard.append([
            InlineKeyboardButton("🚫 Blacklist", callback_data=f"blacklist_wallet_{wallet_address[:10]}")
        ])
        
        # Add extra buttons if provided
        if extra_buttons:
            for button_text, callback_data in extra_buttons:
                keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        
        return InlineKeyboardMarkup(keyboard)
    
    @classmethod
    def create_token_action_buttons(cls, token_address: str, chain: str = 'ethereum',
                                  extra_buttons: List[Tuple[str, str]] = None) -> InlineKeyboardMarkup:
        """Create action buttons for token addresses"""
        keyboard = []
        
        # Analyze token button
        keyboard.append([
            InlineKeyboardButton("🔍 Analyze Token", callback_data=f"analyze_token_{token_address[:10]}")
        ])
        
        # Quick buy button
        keyboard.append([
            InlineKeyboardButton("💰 Quick Buy", callback_data=f"quick_buy_{token_address[:10]}")
        ])
        
        # Blacklist token button
        keyboard.append([
            InlineKeyboardButton("🚫 Blacklist Token", callback_data=f"blacklist_token_{token_address[:10]}")
        ])
        
        # Add extra buttons if provided
        if extra_buttons:
            for button_text, callback_data in extra_buttons:
                keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        
        return InlineKeyboardMarkup(keyboard)
    
    @classmethod
    def create_combined_action_buttons(cls, wallet_address: str, token_address: str, 
                                     chain: str = 'ethereum') -> InlineKeyboardMarkup:
        """Create combined action buttons for wallet + token scenarios"""
        keyboard = []
        
        # First row: Analyze buttons
        keyboard.append([
            InlineKeyboardButton("🔍 Analyze Wallet", callback_data=f"analyze_wallet_{wallet_address[:10]}"),
            InlineKeyboardButton("🔍 Analyze Token", callback_data=f"analyze_token_{token_address[:10]}")
        ])
        
        # Second row: Action buttons
        keyboard.append([
            InlineKeyboardButton("👁️ Watch Wallet", callback_data=f"add_watchlist_{wallet_address[:10]}"),
            InlineKeyboardButton("💰 Buy Token", callback_data=f"quick_buy_{token_address[:10]}")
        ])
        
        # Third row: Blacklist buttons
        keyboard.append([
            InlineKeyboardButton("🚫 Block Wallet", callback_data=f"blacklist_wallet_{wallet_address[:10]}"),
            InlineKeyboardButton("🚫 Block Token", callback_data=f"blacklist_token_{token_address[:10]}")
        ])
        
        return InlineKeyboardMarkup(keyboard)
    
    @classmethod
    def format_trading_alert(cls, wallet_address: str, wallet_name: str, action: str, 
                           token_address: str, token_symbol: str, amount_usd: float,
                           chain: str, tx_hash: str = None, confidence: float = None) -> Tuple[str, InlineKeyboardMarkup]:
        """Format a complete trading alert with all enhancements"""
        
        # Format addresses with links
        wallet_link = cls.format_wallet_address(wallet_address, chain, wallet_name)
        token_link = cls.format_token_address(token_address, chain, token_symbol)
        
        # Action emoji
        action_emoji = "🟢" if action.lower() == "buy" else "🔴"
        confidence_emoji = "🎯" if confidence and confidence > 0.8 else "⚠️" if confidence and confidence > 0.5 else "🔍"
        
        # Chain display
        chain_display = cls.CHAIN_NAMES.get(chain.lower(), chain.upper())
        
        # Format message
        message = f"""
{action_emoji} **WALLET ALERT** {confidence_emoji}

**👤 Wallet:** {wallet_link}
**🪙 Token:** {token_link}
**💰 Amount:** ${amount_usd:,.2f}
**⛓️ Chain:** {chain_display}
**📈 Action:** {action.upper()}
"""
        
        # Add confidence if available
        if confidence:
            message += f"**🎯 Confidence:** {confidence*100:.1f}%\n"
        
        # Add transaction if available
        if tx_hash:
            tx_link = cls.format_transaction_hash(tx_hash, chain)
            message += f"**📋 Transaction:** {tx_link}\n"
        
        # Add timestamp
        from datetime import datetime
        message += f"**⏰ Time:** {datetime.utcnow().strftime('%H:%M:%S UTC')}"
        
        # Create action buttons
        buttons = cls.create_combined_action_buttons(wallet_address, token_address, chain)
        
        return message, buttons
    
    @classmethod
    def format_portfolio_position(cls, token_address: str, token_symbol: str, 
                                chain: str, current_value: float, pnl_usd: float, 
                                pnl_pct: float) -> str:
        """Format a portfolio position with enhanced links"""
        
        token_link = cls.format_token_address(token_address, chain, token_symbol)
        chain_display = cls.CHAIN_NAMES.get(chain.lower(), chain.upper())
        
        pnl_emoji = "🟢" if pnl_usd >= 0 else "🔴"
        pnl_sign = "+" if pnl_usd >= 0 else ""
        
        return f"""
**{token_link}** ({chain_display})
Value: ${current_value:,.2f}
P&L: {pnl_emoji} {pnl_sign}${pnl_usd:,.2f} ({pnl_sign}{pnl_pct:.1f}%)
"""
    
    @classmethod
    def format_leaderboard_entry(cls, rank: int, wallet_address: str, 
                                multiplier: float, total_pnl: float, win_rate: float,
                                chains: List[str]) -> str:
        """Format a leaderboard entry with enhanced wallet link"""
        
        # Medal for top 3
        medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"{rank}."
        
        # Format main chain for link
        main_chain = chains[0] if chains else 'ethereum'
        wallet_link = cls.format_wallet_address(wallet_address, main_chain)
        
        # Format multiplier and PnL
        multiplier_str = f"{multiplier:.0f}x" if multiplier >= 10 else f"{multiplier:.1f}x"
        pnl_str = f"${total_pnl/1000000:.1f}M" if total_pnl >= 1000000 else f"${total_pnl/1000:.0f}K"
        
        # Format chains
        chain_display = ', '.join([cls.CHAIN_NAMES.get(c.lower(), c.upper()) for c in chains[:2]])
        
        return f"""
{medal} **{wallet_link}**
💰 Best: {multiplier_str} | Total: {pnl_str}
📊 Win Rate: {win_rate:.1f}% | Chains: {chain_display}
"""