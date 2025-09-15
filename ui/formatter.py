"""
Message formatting and UI components for Telegram bot interface
"""
from typing import Dict, List, Optional, Union, Any
from datetime import datetime
import emoji
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
    CallbackQuery
)

class UIFormatter:
    """Handles message formatting and UI element generation"""
    
    # Emoji constants
    EMOJIS = {
        'success': '✅',
        'error': '❌',
        'warning': '⚠️',
        'info': 'ℹ️',
        'money': '💰',
        'chart': '📊',
        'rocket': '🚀',
        'fire': '🔥',
        'lock': '🔒',
        'unlock': '🔓',
        'time': '⏰',
        'alert': '🔔',
        'settings': '⚙️',
        'scan': '🔍',
        'wallet': '👛',
        'globe': '🌍',
        'eth': 'Ξ',
        'bsc': '🟡',
        'sol': '◎',
        'check': '✓',
        'cross': '×',
        'up': '📈',
        'down': '📉',
        'neutral': '➖'
    }
    
    # Risk level indicators
    RISK_LEVELS = {
        'LOW': '🟢',
        'MEDIUM': '🟡',
        'HIGH': '🔴',
        'CRITICAL': '⛔'
    }
    
    @classmethod
    def format_trade_alert(
        cls,
        alert_data: Dict[str, Any]
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """Format trade alert message with inline buttons"""
        # Extract data
        action = alert_data['action']
        token_name = alert_data['token_name']
        token_symbol = alert_data['token_symbol']
        amount_usd = alert_data['amount_usd']
        chain = alert_data['chain']
        
        # Format header based on action
        if action == 'BUY':
            header = f"{cls.EMOJIS['info']} New Buy Alert"
        else:
            header = f"{cls.EMOJIS['alert']} Sell Opportunity"
        
        # Format risk indicators
        risk_indicators = []
        if alert_data.get('is_honeypot'):
            risk_indicators.append(f"{cls.EMOJIS['warning']} Honeypot Risk")
        if alert_data.get('high_tax'):
            risk_indicators.append(f"{cls.EMOJIS['warning']} High Tax")
        if alert_data.get('low_liquidity'):
            risk_indicators.append(f"{cls.EMOJIS['warning']} Low Liquidity")
            
        risk_level = cls.RISK_LEVELS[alert_data.get('risk_level', 'MEDIUM')]
        
        # Format message
        message = (
            f"{header}\n\n"
            f"Token: {token_name} ({token_symbol})\n"
            f"Chain: {cls._get_chain_emoji(chain)} {chain}\n"
            f"Size: {cls.EMOJIS['money']} ${amount_usd:,.2f}\n"
            f"Risk: {risk_level} {' '.join(risk_indicators)}\n\n"
            f"Trader Stats:\n"
            f"Win Rate: {alert_data['trader_win_rate']}%\n"
            f"Avg ROI: {alert_data['trader_roi']}%\n"
            f"Recent Trades: {alert_data['trader_trades_30d']}"
        )
        
        # Create inline keyboard
        keyboard = cls._create_trade_keyboard(alert_data)
        
        return message, keyboard
    
    @classmethod
    def format_portfolio_summary(
        cls,
        portfolio_data: Dict[str, Any]
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """Format portfolio summary message"""
        total_value = portfolio_data['total_value']
        daily_change = portfolio_data['daily_change']
        chains = portfolio_data['chains']
        
        # Format header with total value
        header = (
            f"{cls.EMOJIS['money']} Portfolio Summary\n\n"
            f"Total Value: ${total_value:,.2f}\n"
            f"24h Change: {cls._format_change(daily_change)}\n\n"
        )
        
        # Format chain breakdowns
        chain_sections = []
        for chain, data in chains.items():
            chain_sections.append(
                f"{cls._get_chain_emoji(chain)} {chain}:\n"
                f"${data['value']:,.2f} ({data['percentage']}%)"
            )
        
        # Format concentration risk
        top_holdings = portfolio_data['top_holdings']
        risk_section = (
            f"\n{cls.EMOJIS['warning']} Concentration Risk:\n"
            f"Top 3 holdings = {top_holdings['percentage']}%\n"
        )
        
        message = header + "\n".join(chain_sections) + risk_section
        
        # Create inline keyboard
        keyboard = cls._create_portfolio_keyboard()
        
        return message, keyboard
    
    @classmethod
    def format_error_message(
        cls,
        error_type: str,
        details: Dict[str, Any]
    ) -> str:
        """Format user-friendly error message"""
        base_messages = {
            'insufficient_funds': (
                f"{cls.EMOJIS['error']} Insufficient Funds\n\n"
                f"Required: ${details.get('required', 0):,.2f}\n"
                f"Available: ${details.get('available', 0):,.2f}"
            ),
            'price_impact': (
                f"{cls.EMOJIS['warning']} High Price Impact\n\n"
                f"Expected Impact: {details.get('impact', 0)}%\n"
                f"Maximum Allowed: {details.get('max_impact', 0)}%"
            ),
            'api_error': (
                f"{cls.EMOJIS['error']} Service Temporarily Unavailable\n\n"
                f"Error: {details.get('message', 'Unknown error')}\n"
                f"Please try again in a few minutes"
            ),
            'execution_error': (
                f"{cls.EMOJIS['error']} Transaction Failed\n\n"
                f"Reason: {details.get('reason', 'Unknown error')}\n"
                f"Try adjusting slippage or amount"
            )
        }
        
        return base_messages.get(
            error_type,
            f"{cls.EMOJIS['error']} An error occurred"
        )
    
    @classmethod
    def _create_trade_keyboard(
        cls,
        alert_data: Dict[str, Any]
    ) -> InlineKeyboardMarkup:
        """Create inline keyboard for trade alerts"""
        token = alert_data['token_address']
        chain = alert_data['chain']
        
        keyboard = [
            [
                InlineKeyboardButton(
                    f"{cls.EMOJIS['money']} Buy Token",
                    callback_data=f"buy_{chain}_{token}"
                ),
                InlineKeyboardButton(
                    f"{cls.EMOJIS['chart']} Analysis",
                    callback_data=f"analyze_{chain}_{token}"
                )
            ],
            [
                InlineKeyboardButton(
                    "Sell 50%",
                    callback_data=f"sell_{chain}_{token}_50"
                ),
                InlineKeyboardButton(
                    "Sell 100%",
                    callback_data=f"sell_{chain}_{token}_100"
                )
            ],
            [
                InlineKeyboardButton(
                    f"{cls.EMOJIS['warning']} Blacklist",
                    callback_data=f"blacklist_{chain}_{token}"
                )
            ]
        ]
        
        return InlineKeyboardMarkup(keyboard)
    
    @classmethod
    def _create_portfolio_keyboard(cls) -> InlineKeyboardMarkup:
        """Create inline keyboard for portfolio view"""
        keyboard = [
            [
                InlineKeyboardButton(
                    f"{cls.EMOJIS['scan']} Scan",
                    callback_data="menu_scan"
                ),
                InlineKeyboardButton(
                    f"{cls.EMOJIS['wallet']} Watchlist",
                    callback_data="menu_watchlist"
                ),
                InlineKeyboardButton(
                    f"{cls.EMOJIS['settings']} Settings",
                    callback_data="menu_settings"
                )
            ],
            [
                InlineKeyboardButton(
                    f"{cls.EMOJIS['chart']} Charts",
                    callback_data="view_charts"
                ),
                InlineKeyboardButton(
                    f"{cls.EMOJIS['money']} Trade History",
                    callback_data="view_history"
                )
            ]
        ]
        
        return InlineKeyboardMarkup(keyboard)
    
    @classmethod
    def _format_change(cls, change: float) -> str:
        """Format price/value change with emoji"""
        if change > 0:
            return f"{cls.EMOJIS['up']} +{change:,.2f}%"
        elif change < 0:
            return f"{cls.EMOJIS['down']} {change:,.2f}%"
        return f"{cls.EMOJIS['neutral']} {change:,.2f}%"
    
    @classmethod
    def _get_chain_emoji(cls, chain: str) -> str:
        """Get emoji for blockchain"""
        chain_emojis = {
            'ETH': cls.EMOJIS['eth'],
            'BSC': cls.EMOJIS['bsc'],
            'SOL': cls.EMOJIS['sol']
        }
        return chain_emojis.get(chain.upper(), '🔗')
    
    @classmethod
    def create_start_menu(cls) -> Tuple[str, InlineKeyboardMarkup]:
        """Create start menu message and keyboard"""
        message = (
            f"Welcome to Meme Trader V4 Pro! {cls.EMOJIS['rocket']}\n\n"
            f"What would you like to do?\n\n"
            f"{cls.EMOJIS['scan']} Scan - Monitor top traders\n"
            f"{cls.EMOJIS['wallet']} Portfolio - View your holdings\n"
            f"{cls.EMOJIS['chart']} Watchlist - Track tokens\n"
            f"{cls.EMOJIS['settings']} Settings - Configure bot\n"
            f"{cls.EMOJIS['info']} Help - Usage guide"
        )
        
        keyboard = [
            [
                InlineKeyboardButton(
                    f"{cls.EMOJIS['scan']} Scan",
                    callback_data="menu_scan"
                ),
                InlineKeyboardButton(
                    f"{cls.EMOJIS['wallet']} Portfolio",
                    callback_data="menu_portfolio"
                )
            ],
            [
                InlineKeyboardButton(
                    f"{cls.EMOJIS['chart']} Watchlist",
                    callback_data="menu_watchlist"
                ),
                InlineKeyboardButton(
                    f"{cls.EMOJIS['settings']} Settings",
                    callback_data="menu_settings"
                )
            ],
            [
                InlineKeyboardButton(
                    f"{cls.EMOJIS['info']} Help Guide",
                    callback_data="menu_help"
                )
            ]
        ]
        
        return message, InlineKeyboardMarkup(keyboard)
    
    @classmethod
    def create_help_menu(cls) -> Tuple[str, InlineKeyboardMarkup]:
        """Create help menu message and keyboard"""
        message = (
            f"{cls.EMOJIS['info']} Meme Trader V4 Pro Help\n\n"
            f"Available Commands:\n\n"
            f"/scan - Start monitoring traders\n"
            f"/portfolio - View your portfolio\n"
            f"/watchlist - Manage tracked tokens\n"
            f"/settings - Bot configuration\n"
            f"/status - System health check\n"
            f"/help - Show this menu\n\n"
            f"Quick Tips:\n"
            f"• Use inline buttons for faster actions\n"
            f"• Set up alerts in Settings\n"
            f"• Check token security before trading"
        )
        
        keyboard = [
            [
                InlineKeyboardButton(
                    f"{cls.EMOJIS['scan']} Start Scanning",
                    callback_data="menu_scan"
                )
            ],
            [
                InlineKeyboardButton(
                    f"{cls.EMOJIS['settings']} Settings Guide",
                    callback_data="help_settings"
                ),
                InlineKeyboardButton(
                    f"{cls.EMOJIS['info']} Trading Guide",
                    callback_data="help_trading"
                )
            ],
            [
                InlineKeyboardButton(
                    "Back to Menu",
                    callback_data="menu_main"
                )
            ]
        ]
        
        return message, InlineKeyboardMarkup(keyboard)
