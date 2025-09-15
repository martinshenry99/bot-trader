"""
Simple formatting utilities for Meme Trader V4 Pro
"""

from typing import Tuple, List, Dict, Optional, Any
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def format_main_menu(settings: Dict[str, Any]) -> str:
    """Format main menu text based on user settings"""
    safe_mode = settings.get("safe_mode", True)
    
    return (
        "🤖 **Meme Trader Pro V4**\n\n"
        "Welcome to the most advanced meme token trading bot!\n\n"
        f"🔒 Safe Mode: {'ON' if safe_mode else 'OFF'}\n\n"
        "Choose an option below to get started:\n\n"
        "📊 Portfolio - View your holdings and trades\n"
        "🔍 Scan Wallets - Monitor whale wallets\n" 
        "📈 Buy Token - Execute buys with analysis\n"
        "📉 Sell Token - Execute sells and take profits\n"
        "🏆 Leaderboard - Top performing traders\n"
        "⚙️ Settings - Configure bot behavior\n"
        "❓ Help - Bot usage guide\n"
        "🔐 Keys - Manage API keys"
    )

def format_error_message(error: str) -> str:
    """Format error message with emoji and styling"""
    return f"❌ Error: {error}\n\nPlease try again or contact support if the issue persists."

def format_success_message(msg: str) -> str:
    """Format success message with emoji"""
    return f"✅ {msg}"

def format_warning_message(msg: str) -> str:
    """Format warning message with emoji"""
    return f"⚠️ {msg}"


class AddressFormatter:
    """Format addresses with block explorer links"""
    
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
            display_addr = f"{address[:6]}...{address[-4:]}" if len(address) > 20 else address
            explorer_base = cls.BLOCK_EXPLORERS.get(chain.lower(), cls.BLOCK_EXPLORERS['ethereum'])

            if chain.lower() == 'solana':
                explorer_url = f"{explorer_base}/account/{address}"
            else:
                explorer_url = f"{explorer_base}/address/{address}"

            if name:
                return f"[{name} ({display_addr})]({explorer_url})"
            else:
                return f"[{display_addr}]({explorer_url})"
                
        except Exception:
            return f"`{address[:10]}...{address[-6:]}`" if len(address) > 20 else f"`{address}`"
    
    @classmethod
    def format_token_address(cls, address: str, chain: str = 'ethereum', symbol: str = None) -> str:
        """Format token contract address with block explorer link"""
        try:
            display_addr = f"{address[:6]}...{address[-4:]}" if len(address) > 20 else address
            explorer_base = cls.BLOCK_EXPLORERS.get(chain.lower(), cls.BLOCK_EXPLORERS['ethereum'])
            explorer_url = f"{explorer_base}/token/{address}"

            if symbol:
                return f"[{symbol} ({display_addr})]({explorer_url})"
            else:
                return f"[{display_addr}]({explorer_url})"
        except Exception:
            return f"`{address[:10]}...{address[-6:]}`" if len(address) > 20 else f"`{address}`"
    
    @classmethod
    def format_transaction_hash(cls, tx_hash: str, chain: str = 'ethereum') -> str:
        """Format transaction hash with block explorer link"""
        try:
            display_hash = f"{tx_hash[:8]}...{tx_hash[-6:]}" if len(tx_hash) > 20 else tx_hash
            explorer_base = cls.BLOCK_EXPLORERS.get(chain.lower(), cls.BLOCK_EXPLORERS['ethereum'])
            explorer_url = f"{explorer_base}/tx/{tx_hash}"

            return f"[{display_hash}]({explorer_url})"
        except Exception:
            return f"`{tx_hash[:12]}...`" if len(tx_hash) > 20 else f"`{tx_hash}`"
    

def format_wallet_analysis(analysis: Dict) -> Tuple[str, InlineKeyboardMarkup]:
    """Format wallet analysis results for Telegram"""
    try:
        address = analysis.get('address', 'Unknown')
        short_addr = f"{address[:8]}...{address[-6:]}" if len(address) > 20 else address
        
        message = f"🔍 **Wallet Analysis: `{short_addr}`**\n\n"
        
        score = analysis.get('score', 0)
        classification = analysis.get('classification', 'Unknown')
        
        if classification == "Safe":
            score_emoji = "🟢"
        elif classification == "Watch":
            score_emoji = "🟡"
        else:
            score_emoji = "🔴"
        
        message += f"{score_emoji} **Score:** {score}/100 ({classification})\n\n"
        
        # Trading metrics
        message += f"📊 **Trading Performance:**\n"
        message += f"• Max multiplier: {analysis.get('max_multiplier', 0):.1f}x\n"
        message += f"• Win rate: {analysis.get('win_rate', 0):.1f}%\n"
        message += f"• Avg hold: {analysis.get('avg_hold_time', 0):.1f} days\n"
        message += f"• Tokens traded: {analysis.get('tokens_traded', 0)}\n"
        message += f"• Total volume: ${analysis.get('total_volume_usd', 0):,.0f}\n\n"
        
        # Create simple buttons
        buttons = [
            [InlineKeyboardButton("📋 Copy Address", callback_data=f"copy_{address}")],
            [InlineKeyboardButton("🔍 View on Explorer", url=f"https://etherscan.io/address/{address}")]
        ]
        
        reply_markup = InlineKeyboardMarkup(buttons)
        return message, reply_markup
        
    except Exception as e:
        error_msg = f"❌ Analysis formatting failed: {e}"
        return error_msg, None


def format_token_analysis(analysis: Dict) -> Tuple[str, InlineKeyboardMarkup]:
    """Format token analysis results for Telegram"""
    try:
        address = analysis.get('address', 'Unknown')
        symbol = analysis.get('symbol', 'UNK')
        name = analysis.get('name', 'Unknown Token')
        
        short_addr = f"{address[:8]}...{address[-6:]}" if len(address) > 20 else address
        
        message = f"🪙 **Token Analysis: {name} ({symbol})**\n"
        message += f"📍 `{short_addr}`\n\n"
        
        # Price info
        price = analysis.get('price_usd', 0)
        market_cap = analysis.get('market_cap', 0)
        liquidity = analysis.get('liquidity_usd', 0)
        
        message += f"💰 **Market Data:**\n"
        message += f"• Price: ${price:.8f}\n"
        message += f"• Market Cap: ${market_cap:,.0f}\n"
        message += f"• Liquidity: ${liquidity:,.0f}\n\n"
        
        # Risk assessment
        risk_score = analysis.get('risk_score', 50)
        is_honeypot = analysis.get('is_honeypot', False)
        
        if is_honeypot:
            message += f"⚠️ **HONEYPOT DETECTED** 🚨\n\n"
        elif risk_score >= 70:
            message += f"🔴 **HIGH RISK** (Score: {risk_score}/100)\n\n"
        elif risk_score >= 40:
            message += f"🟡 **MEDIUM RISK** (Score: {risk_score}/100)\n\n"
        else:
            message += f"🟢 **LOW RISK** (Score: {risk_score}/100)\n\n"
        
        # Create simple buttons
        buttons = [
            [InlineKeyboardButton("📋 Copy Contract", callback_data=f"copy_{address}")],
            [InlineKeyboardButton("🔍 View on Explorer", url=f"https://etherscan.io/token/{address}")]
        ]
        
        reply_markup = InlineKeyboardMarkup(buttons)
        return message, reply_markup
        
    except Exception as e:
        error_msg = f"❌ Token analysis formatting failed: {e}"
        return error_msg, None


def format_price_alert(token_address: str, token_symbol: str, old_price: float, new_price: float, change_pct: float) -> str:
    """Format price alert message"""
    try:
        short_addr = f"{token_address[:8]}...{token_address[-6:]}" if len(token_address) > 20 else token_address
        
        change_emoji = "🟢" if change_pct >= 0 else "🔴"
        change_sign = "+" if change_pct >= 0 else ""
        
        message = f"{change_emoji} **PRICE ALERT: {token_symbol}**\n\n"
        message += f"📍 Contract: `{short_addr}`\n"
        message += f"💰 Old Price: ${old_price:.8f}\n"
        message += f"💰 New Price: ${new_price:.8f}\n"
        message += f"📈 Change: {change_sign}{change_pct:.2f}%\n"
        
        return message
        
    except Exception as e:
        return f"❌ Price alert formatting failed: {e}"


def format_token_security(analysis: Dict) -> Tuple[str, InlineKeyboardMarkup]:
    """Format token security analysis for Telegram"""
    try:
        contract = analysis.get('contract_address', 'Unknown')
        short_contract = f"{contract[:8]}...{contract[-6:]}" if len(contract) > 20 else contract
        
        token_data = analysis.get('token_data', {})
        name = token_data.get('name', 'Unknown')
        symbol = token_data.get('symbol', 'UNK')
        
        message = f"🔒 **Token Security: {name} ({symbol})**\n"
        message += f"📍 `{short_contract}`\n\n"
        
        # Risk assessment
        is_honeypot = analysis.get('is_honeypot', False)
        risk_score = analysis.get('risk_score', 0)
        
        if is_honeypot:
            message += f"⚠️ **HONEYPOT DETECTED** 🚨\n\n"
        elif risk_score >= 70:
            message += f"🔴 **HIGH RISK** (Score: {risk_score}/100)\n\n"
        elif risk_score >= 40:
            message += f"🟡 **MEDIUM RISK** (Score: {risk_score}/100)\n\n"
        else:
            message += f"🟢 **LOW RISK** (Score: {risk_score}/100)\n\n"
        
        # Create simple buttons
        buttons = [
            [InlineKeyboardButton("📋 Copy Contract", callback_data=f"copy_{contract}")],
            [InlineKeyboardButton("🔍 View on Explorer", url=f"https://etherscan.io/token/{contract}")]
        ]
        
        reply_markup = InlineKeyboardMarkup(buttons)
        return message, reply_markup
        
    except Exception as e:
        error_msg = f"❌ Security analysis formatting failed: {e}"
        return error_msg, None 

def format_token_discovery(discoveries: List[Dict]) -> str:
    """Format discovered tokens for display"""
    lines = ["🔍 New Trading Opportunities"]
    
    for discovery in discoveries:
        lines.extend([
            "",
            f"Token: {discovery['name']} ({discovery['symbol']})",
            f"Address: {discovery['token_address']}",
            f"Chain: {discovery['chain']}",
            f"Liquidity: ${discovery['liquidity']:,.2f}",
            f"24h Volume: ${discovery['volume_24h']:,.2f}",
            f"Holders: {discovery['holder_count']:,}",
            f"Risk Score: {discovery['risk_score']:.2f}",
            f"Discovered: {discovery['discovery_time']}"
        ])
        
        # Add risk factors if available
        if 'risk_factors' in discovery['analysis']:
            lines.append("Risk Factors:")
            for factor, score in discovery['analysis']['risk_factors'].items():
                lines.append(f"  • {factor}: {score:.2f}")
    
    return "\n".join(lines)

def format_monitoring_alert(alerts: List[Dict]) -> str:
    """Format monitoring alerts for display"""
    lines = ["⚠️ Token Monitoring Alerts"]
    
    for alert in alerts:
        lines.extend([
            "",
            f"Token: {alert['token_address']}",
            f"Chain: {alert['chain']}",
            f"Time: {alert['timestamp']}",
            "Changes Detected:"
        ])
        
        for change in alert['changes']:
            lines.append(f"  • {change}")
        
        # Add current metrics
        lines.extend([
            "Current Metrics:",
            f"  • Price: ${alert['current_data']['price_usd']:,.6f}",
            f"  • Liquidity: ${alert['current_data']['liquidity']:,.2f}",
            f"  • 24h Volume: ${alert['current_data']['volume_24h']:,.2f}",
            f"  • Risk Score: {alert['current_data']['risk_score']:.2f}"
        ])
    
    return "\n".join(lines)

def format_watchlist(tokens: List[str]) -> str:
    """Format watchlist tokens for display"""
    if not tokens:
        return "No tokens in watchlist"
    
    lines = ["📋 Token Watchlist"]
    
    for token in sorted(tokens):
        lines.append(f"• {token}")
    
    return "\n".join(lines)