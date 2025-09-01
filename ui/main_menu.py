"""
Main Menu UI System for Meme Trader V4 Pro
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class MainMenu:
    """Main menu interface for the bot"""
    
    @classmethod
    async def get_main_menu(cls, user_id: str = None) -> tuple[str, InlineKeyboardMarkup]:
        """Get the main menu message and keyboard"""
        try:
            # Get current status information
            from core.trading_engine import trading_engine
            
            # Get current configuration
            safe_mode = trading_engine.config.get('safe_mode', True)
            safe_mode_text = "🛡️ Safe Mode: ON" if safe_mode else "🛡️ Safe Mode: OFF"
            
            # Get portfolio summary
            portfolio_value = 0.0
            active_positions = 0
            
            if user_id:
                try:
                    portfolio = await trading_engine.get_portfolio_summary(user_id)
                    portfolio_value = portfolio.get('portfolio_value_usd', 0.0)
                    active_positions = portfolio.get('position_count', 0)
                except Exception:
                    pass
            
            # Format main menu message
            message = f"""
🚀 **MEME TRADER V4 PRO**

**💰 Quick Stats:**
• Portfolio Value: ${portfolio_value:,.2f}
• Active Positions: {active_positions}
• Safe Mode: {'🛡️ ON' if safe_mode else '⚠️ OFF'}

**⚡ Choose an action below:**
            """
            
            # Create main menu keyboard
            keyboard = [
                [
                    InlineKeyboardButton("📊 Portfolio", callback_data="main_portfolio"),
                    InlineKeyboardButton("🔍 Scan Wallets", callback_data="main_scan")
                ],
                [
                    InlineKeyboardButton("💰 Buy Token", callback_data="main_buy"),
                    InlineKeyboardButton("💸 Sell Token", callback_data="main_sell")
                ],
                [
                    InlineKeyboardButton("📈 Moonshot Leaderboard", callback_data="main_leaderboard"),
                    InlineKeyboardButton("🚨 Panic Sell", callback_data="main_panic_sell")
                ],
                [
                    InlineKeyboardButton("⚙️ Settings", callback_data="main_settings"),
                    InlineKeyboardButton(safe_mode_text, callback_data="main_toggle_safe_mode")
                ],
                [
                    InlineKeyboardButton("🔄 Refresh Menu", callback_data="main_refresh"),
                    InlineKeyboardButton("❓ Help", callback_data="main_help")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            return message, reply_markup
            
        except Exception as e:
            logger.error(f"Error creating main menu: {e}")
            # Fallback menu
            message = "🚀 **MEME TRADER V4 PRO**\n\nChoose an action:"
            keyboard = [
                [InlineKeyboardButton("📊 Portfolio", callback_data="main_portfolio")],
                [InlineKeyboardButton("⚙️ Settings", callback_data="main_settings")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            return message, reply_markup
    
    @classmethod
    async def get_portfolio_menu(cls, user_id: str) -> tuple[str, InlineKeyboardMarkup]:
        """Get enhanced portfolio view with sell buttons"""
        try:
            from core.trading_engine import trading_engine
            from utils.formatting import AddressFormatter
            
            # Get portfolio data
            portfolio = await trading_engine.get_portfolio_summary(user_id)
            
            if 'error' in portfolio:
                message = f"❌ **Portfolio Error**\n\n{portfolio['error']}\n\n"
                keyboard = [[InlineKeyboardButton("🔄 Back to Main Menu", callback_data="main_menu")]]
                return message, InlineKeyboardMarkup(keyboard)
            
            # Format portfolio header
            total_value = portfolio.get('portfolio_value_usd', 0)
            total_pnl = portfolio.get('total_pnl_usd', 0)
            position_count = portfolio.get('position_count', 0)
            positions = portfolio.get('positions', [])
            
            pnl_emoji = "🟢" if total_pnl >= 0 else "🔴"
            pnl_sign = "+" if total_pnl >= 0 else ""
            
            message = f"""
📊 **Your Portfolio**

**💰 Overview:**
• Total Value: ${total_value:,.2f}
• Total P&L: {pnl_emoji} {pnl_sign}${total_pnl:,.2f}
• Active Positions: {position_count}

**🎯 Holdings:**
            """
            
            keyboard = []
            
            if positions:
                # Show positions with sell buttons
                for i, pos in enumerate(positions[:8], 1):  # Show max 8 positions
                    token_address = pos.get('token_address', '')
                    token_symbol = pos.get('token_symbol', 'UNKNOWN')
                    chain = pos.get('chain', 'ethereum')
                    current_value = pos.get('current_value_usd', 0)
                    token_amount = pos.get('amount', 0)
                    pnl_usd = pos.get('pnl_usd', 0)
                    pnl_pct = pos.get('pnl_percentage', 0)
                    
                    # Format position with enhanced link
                    position_text = AddressFormatter.format_portfolio_position(
                        token_address=token_address,
                        token_symbol=token_symbol,
                        chain=chain,
                        current_value=current_value,
                        pnl_usd=pnl_usd,
                        pnl_pct=pnl_pct
                    )
                    
                    message += f"\n{i}. {position_text}"
                    message += f"   Amount: {token_amount:,.4f} {token_symbol}\n"
                    
                    # Add sell buttons for this token
                    token_id = token_address[:10]  # Use first 10 chars as ID
                    keyboard.extend([
                        [
                            InlineKeyboardButton(f"Sell 25% {token_symbol}", callback_data=f"sell_25_{token_id}"),
                            InlineKeyboardButton(f"Sell 50% {token_symbol}", callback_data=f"sell_50_{token_id}")
                        ],
                        [
                            InlineKeyboardButton(f"Sell 100% {token_symbol}", callback_data=f"sell_100_{token_id}"),
                            InlineKeyboardButton(f"Custom {token_symbol}", callback_data=f"sell_custom_{token_id}")
                        ],
                        [
                            InlineKeyboardButton("🔗 View Contract", callback_data=f"view_contract_{token_id}"),
                            InlineKeyboardButton("🚫 Blacklist Token", callback_data=f"blacklist_token_{token_id}")
                        ]
                    ])
                    
                    if i < len(positions) and i < 8:  # Add separator if not last
                        keyboard.append([InlineKeyboardButton("─────────────", callback_data="separator")])
                
                if len(positions) > 8:
                    message += f"\n... and {len(positions) - 8} more positions"
            else:
                message += "\nNo active positions"
            
            # Add portfolio action buttons
            keyboard.extend([
                [InlineKeyboardButton("━━━━━━━━━━━━━━━━━━━━━━", callback_data="separator")],
                [
                    InlineKeyboardButton("🔄 Refresh Portfolio", callback_data="refresh_portfolio"),
                    InlineKeyboardButton("📋 Detailed Report", callback_data="detailed_portfolio")
                ],
                [
                    InlineKeyboardButton("🚨 Panic Sell All", callback_data="confirm_panic_sell"),
                    InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")
                ]
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            return message, reply_markup
            
        except Exception as e:
            logger.error(f"Error creating portfolio menu: {e}")
            message = "❌ **Portfolio Error**\n\nFailed to load portfolio data"
            keyboard = [[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]]
            return message, InlineKeyboardMarkup(keyboard)
    
    @classmethod
    async def get_scan_menu(cls) -> tuple[str, InlineKeyboardMarkup]:
        """Get wallet scanning menu"""
        message = """
🔍 **Wallet & Token Scanner**

**📋 Choose scan type:**

**🏆 Top Traders:** Scan high-performing wallets
**📋 Manual Entry:** Paste wallet address or token contract
**🔍 Quick Analyze:** Analyze any address immediately

**Or use commands:**
• `/scan` - Force manual wallet scan
• `/analyze [address]` - Analyze specific address
        """
        
        keyboard = [
            [InlineKeyboardButton("🏆 Scan Top Traders", callback_data="scan_top_traders")],
            [InlineKeyboardButton("📋 Paste Address", callback_data="scan_paste_address")],
            [InlineKeyboardButton("🔍 Quick Analyze", callback_data="scan_quick_analyze")],
            [InlineKeyboardButton("📈 View Leaderboard", callback_data="main_leaderboard")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        return message, reply_markup
    
    @classmethod
    async def get_settings_menu(cls, user_id: str) -> tuple[str, InlineKeyboardMarkup]:
        """Get comprehensive settings menu"""
        try:
            from core.trading_engine import trading_engine
            
            config = trading_engine.config
            
            message = f"""
⚙️ **Trading Settings**

**🔄 Mirror Trading:**
• Mirror Sell: {'✅ ON' if config.get('mirror_sell_enabled', True) else '❌ OFF'}
• Mirror Buy: {'✅ ON' if config.get('mirror_buy_enabled', False) else '❌ OFF'}

**💵 Trading Amounts:**
• Default Buy: ${config.get('max_auto_buy_usd', 50):.0f}
• Max Position: ${config.get('max_position_size_usd', 500):.0f}
• Max Slippage: {config.get('max_slippage', 0.05)*100:.1f}%

**🛡️ Safety Settings:**
• Safe Mode: {'✅ ON' if config.get('safe_mode', True) else '❌ OFF'}
• Panic Confirmation: {'✅ ON' if config.get('panic_confirmation', True) else '❌ OFF'}
• Min Liquidity: ${config.get('min_liquidity_usd', 10000):,.0f}

**Configure your preferences:**
            """
            
            keyboard = [
                [
                    InlineKeyboardButton("🔄 Toggle Mirror Sell", callback_data="settings_mirror_sell"),
                    InlineKeyboardButton("🔄 Toggle Mirror Buy", callback_data="settings_mirror_buy")
                ],
                [
                    InlineKeyboardButton("💵 Default Buy Amount", callback_data="settings_buy_amount"),
                    InlineKeyboardButton("📊 Position Limits", callback_data="settings_position_limits")
                ],
                [
                    InlineKeyboardButton("🛡️ Toggle Safe Mode", callback_data="settings_safe_mode"),
                    InlineKeyboardButton("🔐 Panic Confirmation", callback_data="settings_panic_confirm")
                ],
                [
                    InlineKeyboardButton("🔔 Alert Settings", callback_data="settings_alerts"),
                    InlineKeyboardButton("🚫 Blacklist Manager", callback_data="settings_blacklist")
                ],
                [
                    InlineKeyboardButton("👁️ Watchlist Manager", callback_data="settings_watchlist"),
                    InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            return message, reply_markup
            
        except Exception as e:
            logger.error(f"Error creating settings menu: {e}")
            message = "⚙️ **Settings**\n\nConfigure your trading preferences"
            keyboard = [[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]]
            return message, InlineKeyboardMarkup(keyboard)
    
    @classmethod
    def get_buy_amount_menu(cls) -> tuple[str, InlineKeyboardMarkup]:
        """Get buy amount selection menu"""
        message = """
💵 **Default Buy Amount**

**Select your default buy amount for new trades:**

This amount will be used for:
• Quick buy buttons
• Mirror trading (when enabled)
• Auto-buy features
        """
        
        keyboard = [
            [
                InlineKeyboardButton("$10", callback_data="set_buy_amount_10"),
                InlineKeyboardButton("$25", callback_data="set_buy_amount_25")
            ],
            [
                InlineKeyboardButton("$50", callback_data="set_buy_amount_50"),
                InlineKeyboardButton("$100", callback_data="set_buy_amount_100")
            ],
            [
                InlineKeyboardButton("$250", callback_data="set_buy_amount_250"),
                InlineKeyboardButton("$500", callback_data="set_buy_amount_500")
            ],
            [
                InlineKeyboardButton("💬 Custom Amount", callback_data="set_buy_amount_custom"),
                InlineKeyboardButton("⬅️ Back to Settings", callback_data="main_settings")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        return message, reply_markup
    
    @classmethod
    def create_confirmation_popup(cls, action: str, details: Dict[str, Any]) -> tuple[str, InlineKeyboardMarkup]:
        """Create trade confirmation popup"""
        try:
            if action == "sell":
                token_symbol = details.get('token_symbol', 'UNKNOWN')
                percentage = details.get('percentage', 0)
                estimated_value = details.get('estimated_value', 0)
                token_amount = details.get('token_amount', 0)
                
                message = f"""
💸 **Confirm Sell Order**

**You are about to sell:**
• {percentage}% of your {token_symbol}
• ≈ {token_amount:,.4f} {token_symbol}
• ≈ ${estimated_value:,.2f}

**⚠️ This action cannot be undone**

Are you sure you want to proceed?
                """
                
                keyboard = [
                    [
                        InlineKeyboardButton("✅ Confirm Sell", callback_data=f"execute_sell_{details.get('token_id', '')}__{percentage}"),
                        InlineKeyboardButton("❌ Cancel", callback_data="cancel_trade")
                    ],
                    [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
                ]
                
            elif action == "buy":
                token_symbol = details.get('token_symbol', 'UNKNOWN')
                amount_usd = details.get('amount_usd', 0)
                
                message = f"""
💰 **Confirm Buy Order**

**You are about to buy:**
• ${amount_usd:,.2f} worth of {token_symbol}
• Chain: {details.get('chain', 'ethereum').upper()}

**⚠️ This will use real funds**

Are you sure you want to proceed?
                """
                
                keyboard = [
                    [
                        InlineKeyboardButton("✅ Confirm Buy", callback_data=f"execute_buy_{details.get('token_id', '')}__{amount_usd}"),
                        InlineKeyboardButton("❌ Cancel", callback_data="cancel_trade")
                    ],
                    [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
                ]
                
            elif action == "panic_sell":
                total_value = details.get('total_value', 0)
                position_count = details.get('position_count', 0)
                
                message = f"""
🚨 **CONFIRM PANIC SELL**

**⚠️ WARNING: This will liquidate ALL positions!**

**What will be sold:**
• ALL {position_count} active positions
• Total Portfolio Value: ≈ ${total_value:,.2f}
• This action is IRREVERSIBLE

**Are you absolutely sure?**
                """
                
                keyboard = [
                    [InlineKeyboardButton("🚨 YES - LIQUIDATE ALL", callback_data="execute_panic_sell")],
                    [InlineKeyboardButton("❌ Cancel", callback_data="cancel_trade")],
                    [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
                ]
            
            else:
                # Generic confirmation
                message = f"Confirm {action}?"
                keyboard = [
                    [
                        InlineKeyboardButton("✅ Confirm", callback_data=f"execute_{action}"),
                        InlineKeyboardButton("❌ Cancel", callback_data="cancel_trade")
                    ]
                ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            return message, reply_markup
            
        except Exception as e:
            logger.error(f"Error creating confirmation popup: {e}")
            message = f"Confirm {action}?"
            keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="main_menu")]]
            return message, InlineKeyboardMarkup(keyboard)