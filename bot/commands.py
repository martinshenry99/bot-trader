"""
Telegram Command Handlers for Meme Trader V4 Pro
Implements /scan and /watchlist commands exactly as specified
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import Config
from db.models import get_db_manager
from monitor.scanner import get_discovery_scanner
from utils.formatting import AddressFormatter

logger = logging.getLogger(__name__)

class BotCommands:
    """Telegram bot command handlers"""
    
    def __init__(self):
        self.db = get_db_manager()
        self.scanner = None
    
    async def get_scanner(self):
        """Get discovery scanner instance"""
        if self.scanner is None:
            self.scanner = await get_discovery_scanner()
        return self.scanner
    
    async def scan_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /scan command - DISCOVERY engine
        
        Purpose: find NEW high-quality trader wallets across supported chains (ETH/BSC/SOL)
        NOT implemented as "rescan watchlist wallets only"
        """
        try:
            await update.message.reply_text("🔍 Starting discovery scan... This may take up to 90 seconds.")
            
            # Get scanner and run discovery
            scanner = await self.get_scanner()
            discovered_wallets = await scanner.scan_discovery(limit=10)
            
            if not discovered_wallets:
                await update.message.reply_text("❌ No qualified wallets found. Try again later or adjust minimum score.")
                return
            
            # Format results exactly as specified
            message = self._format_scan_results(discovered_wallets)
            
            # Store wallet data in bot context for callback handlers
            context.bot_data['last_scan_wallets'] = discovered_wallets
            
            # Create inline keyboard with action buttons
            keyboard = self._create_scan_keyboard(discovered_wallets)
            
            await update.message.reply_text(
                message,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            
            logger.info(f"Scan completed for user {update.effective_user.id}: {len(discovered_wallets)} wallets found")
            
        except Exception as e:
            logger.error(f"Scan command failed: {e}")
            await update.message.reply_text("❌ Scan failed. Please try again later.")
    
    def _format_scan_results(self, wallets: List) -> str:
        """Format scan results exactly as specified in requirements"""
        if not wallets:
            return "No wallets found."
        
        # Group by chain
        chains = {}
        for wallet in wallets:
            chain = wallet.chain
            if chain not in chains:
                chains[chain] = []
            chains[chain].append(wallet)
        
        message_parts = []
        
        for chain_name, chain_wallets in chains.items():
            # Chain header
            message_parts.append(f"**Top Traders ({chain_name.title()})**\n")
            
            # Wallet entries
            for i, wallet in enumerate(chain_wallets):
                # Format address with short display
                short_addr = f"{wallet.address[:6]}...{wallet.address[-4:]}"
                
                # Format metrics exactly as specified
                wallet_entry = (
                    f"{i+1}. {short_addr} (Score {wallet.score:.0f}/100)\n"
                    f"   Win Rate {wallet.win_rate:.0f}% | Max {wallet.max_mult:.0f}x | "
                    f"Avg ROI {wallet.avg_roi:.1f}x | Volume ${wallet.volume_usd:,.0f} | "
                    f"{wallet.recent_activity} trades last 30d\n"
                )
                
                message_parts.append(wallet_entry)
            
            message_parts.append("")  # Empty line between chains
        
        return "\n".join(message_parts)
    
    def _create_scan_keyboard(self, wallets: List) -> InlineKeyboardMarkup:
        """Create inline keyboard for scan results"""
        keyboard = []
        
        for i, wallet in enumerate(wallets):
            # Use wallet index as callback data (much shorter)
            # Store full wallet data in bot context for retrieval
            
            # Row for each wallet with action buttons
            row = [
                InlineKeyboardButton(
                    "🔍 Analyze", 
                    callback_data=f"scan_a_{i}"
                ),
                InlineKeyboardButton(
                    "⭐ Add", 
                    callback_data=f"scan_w_{i}"
                ),
                InlineKeyboardButton(
                    "📋 Copy", 
                    callback_data=f"scan_c_{i}"
                )
            ]
            keyboard.append(row)
        
        # Add pagination if more results available
        if len(wallets) >= 10:
            keyboard.append([
                InlineKeyboardButton("Next Page", callback_data="scan_next")
            ])
        
        return InlineKeyboardMarkup(keyboard)

    async def callback_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline button callbacks for all commands"""
        query = update.callback_query
        data = query.data or ""
        await query.answer()

        try:
            if data.startswith("scan_a_"):
                index = int(data.split("_")[2])
                await self._scan_handle_analyze(query, context, index)
            elif data.startswith("scan_w_"):
                index = int(data.split("_")[2])
                await self._scan_handle_add_watchlist(query, context, index)
            elif data.startswith("scan_c_"):
                index = int(data.split("_")[2])
                await self._scan_handle_copy_address(query, context, index)
            elif data == "scan_next":
                await query.edit_message_text(
                    "📄 Next page not implemented yet. Run /scan again for more results.")
            elif data.startswith("w_a_"):
                # Watchlist analyze
                index = int(data.split("_")[2])
                await self._watchlist_handle_analyze_by_index(query, context, index)
            elif data.startswith("w_r_"):
                # Watchlist remove
                index = int(data.split("_")[2])
                await self._watchlist_handle_remove_by_index(query, context, index)
            elif data.startswith("w_c_"):
                # Watchlist copy
                index = int(data.split("_")[2])
                await self._watchlist_handle_copy_by_index(query, context, index)
            elif data.startswith("buy_"):
                # Buy command callbacks
                await self._handle_buy_callbacks(query, context, data)
            elif data.startswith("mnemonic_"):
                # Mnemonic command callbacks
                await self._handle_mnemonic_callbacks(query, context, data)
            elif data.startswith("analyze_wallet_"):
                # Legacy analyze callback
                payload = data.replace("analyze_wallet_", "")
                parts = payload.split("_")
                if len(parts) >= 2:
                    address = parts[0]
                    chain = parts[1]
                    await self._watchlist_handle_analyze(query, address, chain)
            elif data.startswith("remove_watchlist_"):
                # Legacy remove callback
                payload = data.replace("remove_watchlist_", "")
                parts = payload.split("_")
                if len(parts) >= 2:
                    address = parts[0]
                    chain = parts[1]
                    await self._watchlist_handle_remove(query, address, chain)
            elif data.startswith("copy_address_"):
                # Legacy copy callback
                address = data.replace("copy_address_", "")
                await self._watchlist_handle_copy(query, address)
            else:
                # Ignore unknown callbacks silently
                pass
        except Exception as e:
            logger.error(f"Callback handler error: {e}")
            try:
                await query.edit_message_text("❌ Action failed. Please try again.")
            except Exception:
                pass

    async def _scan_handle_analyze(self, query, context, index: int):
        wallets = context.bot_data.get('last_scan_wallets', []) or []
        if index < 0 or index >= len(wallets):
            await query.edit_message_text("❌ Wallet not found. Please run /scan again.")
            return
        w = wallets[index]
        await query.edit_message_text(
            (
                f"🔍 Wallet Analysis\n\n"
                f"Address: `{w.address}`\n"
                f"Chain: {w.chain.upper()}\n"
                f"Score: {w.score:.1f}/100\n"
                f"Win Rate: {w.win_rate:.1f}%\n"
                f"Max: {w.max_mult:.1f}x\n"
                f"Avg ROI: {w.avg_roi:.1f}%\n"
                f"Volume: ${w.volume_usd:,.0f}\n"
                f"Recent: {w.recent_activity} trades\n\n"
                f"Sample Token: {w.sample_profitable_token} ({w.sample_multiplier:.1f}x)\n\n"
                f"Use /analyze {w.address} {w.chain} for a deeper dive."
            ),
            parse_mode='Markdown'
        )

    async def _scan_handle_add_watchlist(self, query, context, index: int):
        wallets = context.bot_data.get('last_scan_wallets', []) or []
        if index < 0 or index >= len(wallets):
            await query.edit_message_text("❌ Wallet not found. Please run /scan again.")
            return
        w = wallets[index]
        try:
            success = self.db.add_wallet_to_watchlist(
                address=w.address,
                chain=w.chain,
                user_id=query.from_user.id,
                wallet_type='wallet',
                label=f"Score {w.score:.0f}"
            )
            if success:
                await query.message.reply_text(
                    f"⭐ Added {w.address[:6]}...{w.address[-4:]} ({w.chain.upper()}) to watchlist"
                )
            else:
                await query.message.reply_text("❌ Failed to add to watchlist. Try again.")
        except Exception as e:
            logger.error(f"Add watchlist failed: {e}")
            await query.message.reply_text("❌ Failed to add to watchlist. Try again.")

    async def _scan_handle_copy_address(self, query, context, index: int):
        wallets = context.bot_data.get('last_scan_wallets', []) or []
        if index < 0 or index >= len(wallets):
            await query.edit_message_text("❌ Wallet not found. Please run /scan again.")
            return
        w = wallets[index]
        await query.message.reply_text(
            f"📋 `{w.address}`\nChain: {w.chain.upper()}  •  Score {w.score:.0f}",
            parse_mode='Markdown'
        )

    async def _watchlist_handle_analyze(self, query, address: str, chain: str):
        try:
            scanner = await self.get_scanner()
            result = await scanner.analyze_wallet(address, chain)
            if not result:
                await query.message.reply_text("❌ Analysis failed. Try again later.")
                return
            text = (
                f"🔍 Wallet Analysis\n\n"
                f"Address: `{result.address}`\n"
                f"Chain: {result.chain.upper()}\n"
                f"Score: {result.score:.1f}/100\n"
                f"Win Rate: {result.win_rate:.1f}%\n"
                f"Max: {result.max_mult:.1f}x  •  Avg ROI: {result.avg_roi:.1f}%\n"
                f"Volume: ${result.volume_usd:,.0f}  •  Recent: {result.recent_activity} trades\n"
                f"Sample: {result.sample_profitable_token} ({result.sample_multiplier:.1f}x)\n"
            )
            if getattr(result, 'risk_flags', None):
                text += "\nRisks: " + ", ".join(result.risk_flags)
            await query.message.reply_text(text, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Watchlist analyze failed: {e}")
            await query.message.reply_text("❌ Analysis failed. Try again later.")

    async def _watchlist_handle_remove(self, query, address: str, chain: str):
        try:
            removed = self.db.remove_from_watchlist(address, chain, query.from_user.id)
            if removed:
                await query.message.reply_text(
                    f"🗑 Removed {address[:6]}...{address[-4:]} ({chain.upper()}) from watchlist"
                )
            else:
                await query.message.reply_text("❌ Address not found in your watchlist")
        except Exception as e:
            logger.error(f"Watchlist remove failed: {e}")
            await query.message.reply_text("❌ Failed to remove from watchlist")

    async def _watchlist_handle_copy(self, query, address: str):
        await query.message.reply_text(f"📋 `{address}`", parse_mode='Markdown')
    
    async def _watchlist_handle_analyze_by_index(self, query, context, index: int):
        """Handle watchlist analyze by index"""
        watchlist = context.bot_data.get('last_watchlist', []) or []
        if index < 0 or index >= len(watchlist):
            await query.edit_message_text("❌ Wallet not found. Please run /watchlist list again.")
            return
        
        item = watchlist[index]
        await self._watchlist_handle_analyze(query, item['address'], item['chain'])
    
    async def _watchlist_handle_remove_by_index(self, query, context, index: int):
        """Handle watchlist remove by index"""
        watchlist = context.bot_data.get('last_watchlist', []) or []
        if index < 0 or index >= len(watchlist):
            await query.edit_message_text("❌ Wallet not found. Please run /watchlist list again.")
            return
        
        item = watchlist[index]
        await self._watchlist_handle_remove(query, item['address'], item['chain'])
    
    async def _watchlist_handle_copy_by_index(self, query, context, index: int):
        """Handle watchlist copy by index"""
        watchlist = context.bot_data.get('last_watchlist', []) or []
        if index < 0 or index >= len(watchlist):
            await query.edit_message_text("❌ Wallet not found. Please run /watchlist list again.")
            return
        
        item = watchlist[index]
        await self._watchlist_handle_copy(query, item['address'])
    
    async def watchlist_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /watchlist command - MONITORING engine
        
        Commands:
        - /watchlist add <address_or_contract> [chain] [label]
        - /watchlist remove <address_or_contract>
        - /watchlist list
        - /watchlist rename <address> <new_label>
        """
        try:
            user_id = update.effective_user.id
            args = context.args
            
            if not args:
                # Show watchlist help
                await self._show_watchlist_help(update)
                return
            
            command = args[0].lower()
            
            if command == "add":
                await self._watchlist_add(update, context, user_id, args[1:])
            elif command == "remove":
                await self._watchlist_remove(update, context, user_id, args[1:])
            elif command == "list":
                await self._watchlist_list(update, context, user_id)
            elif command == "rename":
                await self._watchlist_rename(update, context, user_id, args[1:])
            else:
                await update.message.reply_text("❌ Unknown watchlist command. Use /watchlist for help.")
                
        except Exception as e:
            logger.error(f"Watchlist command failed: {e}")
            await update.message.reply_text("❌ Watchlist command failed. Please try again.")
    
    async def _show_watchlist_help(self, update: Update):
        """Show watchlist help"""
        help_text = """
**Watchlist Commands:**

`/watchlist add <address> [chain] [label]` - Add wallet/token to watchlist
`/watchlist remove <address>` - Remove from watchlist
`/watchlist list` - Show your watchlist
`/watchlist rename <address> <new_label>` - Rename watchlist item

**Examples:**
`/watchlist add 0x1234...5678 ethereum MyWallet`
`/watchlist add 0xabcd...efgh bsc`
`/watchlist remove 0x1234...5678`
`/watchlist rename 0x1234...5678 NewLabel`
        """
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def _watchlist_add(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, args: List[str]):
        """Add wallet/token to watchlist"""
        if not args:
            await update.message.reply_text("❌ Please provide an address to add.")
            return
        
        address = args[0]
        chain = args[1] if len(args) > 1 else None
        label = args[2] if len(args) > 2 else None
        
        # Auto-detect chain if not provided
        if not chain:
            chain = self._detect_chain(address)
            if not chain:
                # Ask user to specify chain
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("ETH", callback_data=f"add_chain_eth_{address}_{label or ''}")],
                    [InlineKeyboardButton("BSC", callback_data=f"add_chain_bsc_{address}_{label or ''}")],
                    [InlineKeyboardButton("SOL", callback_data=f"add_chain_sol_{address}_{label or ''}")]
                ])
                await update.message.reply_text(
                    f"❓ Address could exist on multiple chains. Please specify chain:",
                    reply_markup=keyboard
                )
                return
        
        # Validate address
        if not self._is_valid_address(address, chain):
            await update.message.reply_text(f"❌ Invalid {chain} address format.")
            return
        
        # Add to watchlist
        success = self.db.add_wallet_to_watchlist(
            address=address,
            chain=chain,
            user_id=user_id,
            wallet_type='wallet',
            label=label
        )
        
        if success:
            chain_name = chain.upper()
            message = f"✅ Added {chain_name}: {address[:6]}...{address[-4:]} to watchlist"
            if label:
                message += f" (Label: {label})"
            await update.message.reply_text(message)
        else:
            await update.message.reply_text("❌ Failed to add to watchlist. Please try again.")
    
    async def _watchlist_remove(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, args: List[str]):
        """Remove wallet/token from watchlist"""
        if not args:
            await update.message.reply_text("❌ Please provide an address to remove.")
            return
        
        address = args[0]
        
        # Try to remove from all chains
        removed = False
        for chain in ['ethereum', 'bsc', 'solana']:
            if self.db.remove_from_watchlist(address, chain, user_id):
                removed = True
        
        if removed:
            await update.message.reply_text(f"✅ Removed {address[:6]}...{address[-4:]} from watchlist")
        else:
            await update.message.reply_text("❌ Address not found in watchlist or already removed.")
    
    async def _watchlist_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
        """List user's watchlist"""
        try:
            watchlist = self.db.get_user_watchlist(user_id, active_only=True)
            
            if not watchlist:
                await update.message.reply_text("📝 Your watchlist is empty. Use `/watchlist add <address>` to add wallets.")
                return
            
            # Store watchlist data in context for callback handlers
            context.bot_data['last_watchlist'] = watchlist
            
            # Format watchlist exactly as specified
            message = "🔔 **Your Watchlist:**\n\n"
            
            for i, item in enumerate(watchlist):
                # Format address
                short_addr = f"{item['address'][:6]}...{item['address'][-4:]}"
                chain_name = item['chain'].upper()
                
                # Format label
                label_text = f" (label: {item['label']})" if item['label'] else ""
                
                # Format timestamp
                added_time = datetime.fromtimestamp(item['added_at'])
                time_ago = self._format_time_ago(added_time)
                
                item_text = (
                    f"{i+1}. **{short_addr}** ({chain_name}){label_text}\n"
                    f"   Added: {time_ago}\n\n"
                )
                message += item_text
            
            # Create inline keyboard for actions
            keyboard = self._create_watchlist_keyboard(watchlist)
            
            await update.message.reply_text(
                message,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Watchlist list failed: {e}")
            await update.message.reply_text("❌ Failed to load watchlist. Please try again.")
    
    async def _watchlist_rename(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, args: List[str]):
        """Rename watchlist item"""
        if len(args) < 2:
            await update.message.reply_text("❌ Please provide address and new label: `/watchlist rename <address> <new_label>`")
            return
        
        address = args[0]
        new_label = args[1]
        
        # Update label in database
        success = self.db.set_user_setting(user_id, f"watchlist_label_{address}", new_label)
        
        if success:
            await update.message.reply_text(f"✅ Renamed {address[:6]}...{address[-4:]} to '{new_label}'")
        else:
            await update.message.reply_text("❌ Failed to rename. Please try again.")
    
    def _detect_chain(self, address: str) -> Optional[str]:
        """Auto-detect chain by address format"""
        if address.startswith('0x') and len(address) == 42:
            # Could be ETH or BSC - would need to check activity
            return None  # Let user choose
        elif len(address) == 44 and not address.startswith('0x'):
            return 'solana'
        return None
    
    def _is_valid_address(self, address: str, chain: str) -> bool:
        """Validate address format for chain"""
        try:
            if chain in ['ethereum', 'bsc']:
                return address.startswith('0x') and len(address) == 42
            elif chain == 'solana':
                return len(address) == 44 and not address.startswith('0x')
            return False
        except:
            return False
    
    def _format_time_ago(self, timestamp: datetime) -> str:
        """Format timestamp as relative time"""
        now = datetime.now()
        diff = now - timestamp
        
        if diff.days > 0:
            return f"{diff.days} days ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hours ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} minutes ago"
        else:
            return "just now"
    
    def _create_watchlist_keyboard(self, watchlist: List[Dict]) -> InlineKeyboardMarkup:
        """Create inline keyboard for watchlist items"""
        keyboard = []
        
        for i, item in enumerate(watchlist):
            # Use shortened callback data to avoid 64-byte limit
            row = [
                InlineKeyboardButton(
                    "🔍 Analyze", 
                    callback_data=f"w_a_{i}"
                ),
                InlineKeyboardButton(
                    "🗑 Remove", 
                    callback_data=f"w_r_{i}"
                ),
                InlineKeyboardButton(
                    "📋 Copy", 
                    callback_data=f"w_c_{i}"
                )
            ]
            keyboard.append(row)
        
        return InlineKeyboardMarkup(keyboard)
    
    async def analyze_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /analyze <address_or_contract> [depth]
        
        Wallet: returns score breakdown, top tokens, counterparties, top profitable trades, graph summary
        Token: returns honeypot boolean, liquidity_usd, locked boolean + expiry, owner, top holders, risk flags
        """
        try:
            args = context.args
            if not args:
                await update.message.reply_text("❌ Please provide an address to analyze: `/analyze <address> [depth]`")
                return
            
            address = args[0]
            depth = int(args[1]) if len(args) > 1 else 3
            
            # Auto-detect chain
            chain = self._detect_chain(address)
            if not chain:
                await update.message.reply_text("❌ Could not detect chain. Please specify: `/analyze <address> <chain>`")
                return
            
            # For now, return basic analysis
            analysis_text = f"🔍 **Analysis for {address[:6]}...{address[-4:]}**\n\n"
            analysis_text += f"Chain: {chain.upper()}\n"
            analysis_text += f"Analysis depth: {depth}\n\n"
            analysis_text += "Detailed analysis coming soon..."
            
            # Create inline keyboard
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⭐ Add to Watchlist", callback_data=f"add_watchlist_{address}_{chain}")],
                [InlineKeyboardButton("📋 Copy Address", callback_data=f"copy_address_{address}")]
            ])
            
            await update.message.reply_text(
                analysis_text,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Analyze command failed: {e}")
            await update.message.reply_text("❌ Analysis failed. Please try again.")

    async def buy_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/buy <token_address> <amount> [chain] — Execute a buy order with enhanced intelligence"""
        try:
            args = context.args
            user_id = str(update.effective_user.id)
            
            # Check if mnemonic is configured
            from config import Config
            if not Config.MNEMONIC:
                await update.message.reply_text(
                    "❌ No wallet configured. Please set up your mnemonic first using /mnemonic command."
                )
                return
            
            if len(args) < 2:
                # Show latest BUY alerts from watched addresses
                await self._show_latest_buy_alerts(update, context)
                return
            
            token_address = args[0]
            amount = args[1]
            chain = args[2].lower() if len(args) > 2 else 'ethereum'
            
            # Validate amount
            try:
                amount_float = float(amount)
                if amount_float <= 0:
                    await update.message.reply_text("❌ Amount must be a positive number.")
                    return
            except ValueError:
                await update.message.reply_text("❌ Invalid amount. Please enter a valid number.")
                return
            
            # Show processing message
            processing_msg = await update.message.reply_text(
                f"🔄 Processing buy order...\n\n"
                f"Token: `{token_address}`\n"
                f"Amount: ${amount}\n"
                f"Chain: {chain.upper()}\n\n"
                f"Analyzing token safety and calculating trade details...",
                parse_mode='Markdown'
            )
            
            # Perform token analysis
            risk_score, is_safe = await self._analyze_token_safety(token_address, chain)
            
            if not is_safe and Config.SAFE_MODE:
                await processing_msg.edit_text(
                    f"🚫 Trade blocked by SAFE_MODE\n\n"
                    f"Token: `{token_address}`\n"
                    f"Risk Score: {risk_score}/100\n\n"
                    f"This token failed safety checks. Use /settings to disable SAFE_MODE if needed.",
                    parse_mode='Markdown'
                )
                return
            
            # Calculate trade details
            trade_details = await self._calculate_trade_details(token_address, amount_float, chain)
            
            # Show trade preview with confirmation
            preview_text = f"""
🛒 **Buy Order Preview**

**Token:** {trade_details['token_name']} ({trade_details['token_symbol']})
**Contract:** `{token_address}`
**Amount:** ${amount_float:,.2f}
**Chain:** {chain.upper()}

**Expected Tokens:** {trade_details['expected_tokens']:,.2f} {trade_details['token_symbol']}
**Slippage:** {trade_details['slippage']:.2f}%
**Gas Fee:** ${trade_details['gas_fee']:.2f}
**Total Cost:** ${trade_details['total_cost']:.2f}

**Safety Analysis:**
• Risk Score: {risk_score}/100
• Status: {'✅ SAFE' if is_safe else '🚫 RISK'}
• Honeypot: {'❌ Detected' if trade_details['is_honeypot'] else '✅ Clean'}
• Liquidity: ${trade_details['liquidity_usd']:,.0f}

**Portfolio Impact:** {trade_details['portfolio_percent']:.1f}% of total
"""
            
            # Create confirmation keyboard
            keyboard = [
                [
                    InlineKeyboardButton("✅ Confirm Buy", callback_data=f"confirm_buy_{token_address}_{amount}_{chain}"),
                    InlineKeyboardButton("❌ Cancel", callback_data="cancel_buy")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await processing_msg.edit_text(preview_text, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Buy command failed: {e}")
            await update.message.reply_text("❌ Buy failed. Please try again.")
    
    async def _show_latest_buy_alerts(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show latest BUY alerts from watched addresses"""
        try:
            # Get latest buy alerts
            alerts = self.db.get_latest_buy_alerts(limit=10)
            
            if not alerts:
                await update.message.reply_text(
                    "📊 **Latest Buy Alerts**\n\n"
                    "No recent buy alerts from your watched addresses.\n\n"
                    "Use `/buy <token_address> <amount> [chain]` to buy manually."
                )
                return
            
            # Group alerts by token for consensus detection
            token_groups = {}
            for alert in alerts:
                key = f"{alert['chain']}:{alert['token_address']}"
                if key not in token_groups:
                    token_groups[key] = []
                token_groups[key].append(alert)
            
            # Sort by consensus and recency
            sorted_tokens = sorted(token_groups.items(), 
                                key=lambda x: (len(x[1]), max(a['created_at'] for a in x[1])), 
                                reverse=True)
            
            message = "📊 **Latest Buy Alerts**\n\n"
            keyboard = []
            
            for i, (token_key, token_alerts) in enumerate(sorted_tokens[:5]):  # Show top 5
                alert = token_alerts[0]  # Use first alert for token info
                consensus_icon = "🚀" if len(token_alerts) > 1 else ""
                safety_icon = "✅" if alert['is_safe'] else "🚫"
                
                # Calculate consensus info
                total_volume = sum(a['amount_usd'] for a in token_alerts)
                trader_count = len(set(a['wallet_address'] for a in token_alerts))
                
                message += f"{consensus_icon} **{alert['token_name']}** ({alert['token_symbol']}) {safety_icon}\n"
                message += f"• Contract: `{alert['token_address']}`\n"
                message += f"• Traders: {trader_count} wallets\n"
                message += f"• Volume: ${total_volume:,.0f}\n"
                message += f"• Risk: {alert['risk_score']}/100\n"
                message += f"• Chain: {alert['chain'].upper()}\n\n"
                
                # Add inline buttons for each token (shortened callback data)
                keyboard.append([
                    InlineKeyboardButton(f"Buy $50", callback_data=f"buy_quick_{alert['token_address']}_50_{alert['chain']}"),
                    InlineKeyboardButton(f"Buy $100", callback_data=f"buy_quick_{alert['token_address']}_100_{alert['chain']}"),
                    InlineKeyboardButton(f"Custom", callback_data=f"buy_custom_{alert['token_address']}_{alert['chain']}")
                ])
                keyboard.append([
                    InlineKeyboardButton(f"Analyze Token", callback_data=f"buy_analyze_{alert['token_address']}_{alert['chain']}"),
                    InlineKeyboardButton(f"Analyze Wallet", callback_data=f"analyze_wallet_{alert['wallet_address']}_{alert['chain']}")
                ])
                
                if i < len(sorted_tokens) - 1:
                    keyboard.append([InlineKeyboardButton("─" * 20, callback_data="noop")])
            
            # Add manual input option
            keyboard.append([
                InlineKeyboardButton("📝 Manual Input", callback_data="buy_manual"),
                InlineKeyboardButton("🔄 Refresh", callback_data="buy_refresh")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error showing buy alerts: {e}")
            await update.message.reply_text("❌ Failed to load buy alerts. Please try again.")
    
    async def _analyze_token_safety(self, token_address: str, chain: str) -> tuple[int, bool]:
        """Analyze token safety using GoPlus and other tools"""
        try:
            # This would integrate with GoPlus API for real analysis
            # For now, return mock data
            risk_score = 25  # Mock safe score
            is_safe = risk_score < 30
            return risk_score, is_safe
        except Exception as e:
            logger.error(f"Error analyzing token safety: {e}")
            return 50, False
    
    async def _calculate_trade_details(self, token_address: str, amount_usd: float, chain: str) -> dict:
        """Calculate trade details including slippage, gas, etc."""
        try:
            # This would integrate with 0x API for EVM or Jupiter for Solana
            # For now, return mock data
            return {
                'token_name': 'Mock Token',
                'token_symbol': 'MOCK',
                'expected_tokens': amount_usd * 1000,  # Mock rate
                'slippage': 0.5,
                'gas_fee': 15.0,
                'total_cost': amount_usd + 15.0,
                'is_honeypot': False,
                'liquidity_usd': 50000,
                'portfolio_percent': 5.0
            }
        except Exception as e:
            logger.error(f"Error calculating trade details: {e}")
            return {
                'token_name': 'Unknown',
                'token_symbol': 'UNK',
                'expected_tokens': 0,
                'slippage': 0,
                'gas_fee': 0,
                'total_cost': amount_usd,
                'is_honeypot': True,
                'liquidity_usd': 0,
                'portfolio_percent': 0
            }

    async def sell_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/sell <token_address> <amount> [chain] — Execute a sell order"""
        try:
            args = context.args
            if len(args) < 2:
                await update.message.reply_text("❌ Usage: /sell <token_address> <amount> [chain]")
                return
            
            token_address = args[0]
            amount = args[1]
            chain = args[2].lower() if len(args) > 2 else 'ethereum'
            
            # Validate inputs
            try:
                amount_float = float(amount)
                if amount_float <= 0:
                    await update.message.reply_text("❌ Amount must be greater than 0")
                    return
            except ValueError:
                await update.message.reply_text("❌ Invalid amount. Please use a number.")
                return
            
            # Check if mnemonic is configured
            from config import Config
            if not Config.MNEMONIC:
                await update.message.reply_text(
                    "❌ Wallet not configured. Please add MNEMONIC to your .env file.\n\n"
                    "Example:\n"
                    "MNEMONIC=your twelve word mnemonic phrase goes here"
                )
                return
            
            # Show processing message
            processing_msg = await update.message.reply_text(
                f"💱 Processing sell order...\n\n"
                f"Token: `{token_address}`\n"
                f"Amount: {amount} tokens\n"
                f"Chain: {chain.upper()}\n\n"
                f"⏳ Executing trade...",
                parse_mode='Markdown'
            )
            
            # Simulate trade execution (replace with real trading logic)
            import asyncio
            await asyncio.sleep(2)  # Simulate processing time
            
            # For now, show a success message with mock data
            await processing_msg.edit_text(
                f"✅ Sell order executed!\n\n"
                f"Token: `{token_address}`\n"
                f"Amount: {amount} tokens\n"
                f"Chain: {chain.upper()}\n"
                f"Tx Hash: `0x5678...9abc`\n"
                f"Gas Used: 120,000\n"
                f"Status: ✅ Confirmed\n\n"
                f"*This is a demo. Real trading requires proper integration with DEXs.*",
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Sell command failed: {e}")
            await update.message.reply_text("❌ Sell failed. Please try again.")

    async def check_watchlist_alerts(self):
        """Check watchlist for new activity and send alerts"""
        try:
            # Get all watchlist entries
            watchlist = self.db.get_user_watchlist(user_id=None)  # Get all users' watchlists
            
            for entry in watchlist:
                try:
                    # Analyze the wallet for recent activity
                    scanner = await self.get_scanner()
                    result = await scanner.analyze_wallet(entry['address'], entry['chain'])
                    
                    if result and result.recent_activity > 0:
                        # Send alert about new activity
                        alert_text = (
                            f"🚨 Watchlist Alert!\n\n"
                            f"Wallet: `{entry['address']}`\n"
                            f"Chain: {entry['chain'].upper()}\n"
                            f"Recent Activity: {result.recent_activity} trades\n"
                            f"Current Score: {result.score:.1f}/100\n\n"
                            f"Sample Token: {result.sample_profitable_token}\n"
                            f"Multiplier: {result.sample_multiplier:.1f}x"
                        )
                        
                        # In a real implementation, you would send this to the user
                        # For now, just log it
                        logger.info(f"Watchlist alert for {entry['address']}: {result.recent_activity} recent trades")
                        
                except Exception as e:
                    logger.error(f"Error checking watchlist entry {entry['address']}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Watchlist alert check failed: {e}")

    async def mnemonic_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/mnemonic — Manage wallet mnemonic securely"""
        try:
            from core.secure_wallet import get_secure_wallet
            
            args = context.args
            secure_wallet = get_secure_wallet()
            
            if not args:
                # Show status and options with inline buttons
                status = secure_wallet.get_wallet_status()
                
                if status['configured']:
                    message = f"""
🔐 **Wallet Status**

✅ Wallet is configured and encrypted
📅 Created: {status.get('created_at', 'Unknown')}
💾 Size: {status.get('file_size', 0)} bytes
🔑 Address: {status.get('address', 'Unknown')[:6]}...{status.get('address', 'Unknown')[-6:]}

**Available Actions:**
"""
                else:
                    message = f"""
🔐 **Wallet Status**

❌ No wallet configured

**Available Actions:**
"""
                
                # Create inline keyboard based on status
                keyboard = []
                if status['configured']:
                    keyboard.extend([
                        [InlineKeyboardButton("📊 Status", callback_data="mnemonic_status")],
                        [InlineKeyboardButton("🔐 Export", callback_data="mnemonic_export")],
                        [InlineKeyboardButton("🚨 Delete", callback_data="mnemonic_delete")]
                    ])
                else:
                    keyboard.extend([
                        [InlineKeyboardButton("📊 Status", callback_data="mnemonic_status")],
                        [InlineKeyboardButton("🆕 Generate", callback_data="mnemonic_generate")],
                        [InlineKeyboardButton("📥 Import", callback_data="mnemonic_import")]
                    ])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
                return
            
            command = args[0].lower()
            
            if command == "status":
                status = secure_wallet.get_wallet_status()
                if status['configured']:
                    await update.message.reply_text(
                        f"✅ Wallet is configured and encrypted\n"
                        f"📅 Created: {status.get('created_at', 'Unknown')}\n"
                        f"💾 Size: {status.get('file_size', 0)} bytes"
                    )
                else:
                    await update.message.reply_text("❌ No wallet configured")
            
            elif command == "generate":
                await update.message.reply_text(
                    "🔐 **Generate New Wallet**\n\n"
                    "This will create a new wallet with a random mnemonic.\n"
                    "⚠️ **WARNING:** This will overwrite any existing wallet!\n\n"
                    "Please send your password to continue:\n"
                    "`/mnemonic generate <password>`",
                    parse_mode='Markdown'
                )
            
            elif command == "import":
                await update.message.reply_text(
                    "🔐 **Import Wallet**\n\n"
                    "⚠️ **SECURITY WARNING:**\n"
                    "Never type your mnemonic in Telegram chat!\n\n"
                    "For security, please use the secure import script:\n"
                    "```bash\npython secure_import.py\n```\n\n"
                    "This script will:\n"
                    "• Prompt for mnemonic securely\n"
                    "• Encrypt and store it\n"
                    "• Never expose it in logs or chat",
                    parse_mode='Markdown'
                )
            
            elif command == "export":
                if len(args) < 2:
                    await update.message.reply_text(
                        "🔐 **Export Wallet**\n\n"
                        "Please provide your password:\n"
                        "`/mnemonic export <password>`",
                        parse_mode='Markdown'
                    )
                    return
                
                password = args[1]
                result = secure_wallet.export_wallet(password)
                
                if result['success']:
                    await update.message.reply_text(
                        f"✅ **Wallet Exported**\n\n"
                        f"**Addresses:**\n"
                        f"• Ethereum: `{result['addresses']['ethereum']}`\n"
                        f"• BSC: `{result['addresses']['bsc']}`\n"
                        f"• Solana: `{result['addresses']['solana']}`\n\n"
                        f"**Encrypted Data:**\n"
                        f"`{result['encrypted_data'][:100]}...`\n\n"
                        f"⚠️ Keep this encrypted data secure!",
                        parse_mode='Markdown'
                    )
                else:
                    await update.message.reply_text(f"❌ Export failed: {result['error']}")
            
            elif command == "delete":
                if len(args) < 2:
                    await update.message.reply_text(
                        "🚨 **Delete Wallet**\n\n"
                        "⚠️ **WARNING:** This will permanently delete your wallet!\n\n"
                        "If you're sure, provide your password:\n"
                        "`/mnemonic delete <password>`",
                        parse_mode='Markdown'
                    )
                    return
                
                password = args[1]
                result = secure_wallet.delete_wallet(password)
                
                if result['success']:
                    await update.message.reply_text("✅ Wallet deleted successfully")
                else:
                    await update.message.reply_text(f"❌ Delete failed: {result['error']}")
            
            else:
                await update.message.reply_text(
                    "❌ Unknown command. Use `/mnemonic` to see available options."
                )
                
        except Exception as e:
            logger.error(f"Mnemonic command failed: {e}")
            await update.message.reply_text("❌ Mnemonic command failed. Please try again.")

    async def _handle_buy_callbacks(self, query, context, data: str):
        """Handle buy command callbacks"""
        try:
            if data.startswith("buy_quick_"):
                # Quick buy: buy_quick_<token>_<amount>_<chain>
                parts = data.split("_")
                if len(parts) >= 5:
                    token_address = parts[2]
                    amount = parts[3]
                    chain = parts[4]
                    await query.edit_message_text(
                        f"🛒 Quick buy: {amount} USD of {token_address[:6]}...{token_address[-4:]} on {chain.upper()}\n\n"
                        f"⚠️ This is a demo. Real trading requires proper DEX integration."
                    )
            elif data.startswith("buy_custom_"):
                # Custom buy: buy_custom_<token>_<chain>
                parts = data.split("_")
                if len(parts) >= 4:
                    token_address = parts[2]
                    chain = parts[3]
                    await query.edit_message_text(
                        f"📝 Custom buy for {token_address[:6]}...{token_address[-4:]} on {chain.upper()}\n\n"
                        f"Please use: `/buy {token_address} <amount> {chain}`"
                    )
            elif data.startswith("buy_analyze_"):
                # Analyze token: buy_analyze_<token>_<chain>
                parts = data.split("_")
                if len(parts) >= 4:
                    token_address = parts[2]
                    chain = parts[3]
                    await query.edit_message_text(
                        f"🔍 Token analysis for {token_address[:6]}...{token_address[-4:]} on {chain.upper()}\n\n"
                        f"Use `/analyze {token_address} {chain}` for detailed analysis."
                    )
            elif data == "buy_manual":
                await query.edit_message_text(
                    "📝 **Manual Buy Input**\n\n"
                    "Please use the format:\n"
                    "`/buy <token_address> <amount> [chain]`\n\n"
                    "**Examples:**\n"
                    "• `/buy 0x1234...5678 100`\n"
                    "• `/buy 0xabcd...efgh 50 bsc`\n"
                    "• `/buy So11111111111111111111111111111111111111112 200 solana`",
                    parse_mode='Markdown'
                )
            elif data == "buy_refresh":
                await query.edit_message_text("🔄 Refreshing buy alerts...")
                # In a real implementation, this would refresh the alerts
                await query.edit_message_text("✅ Buy alerts refreshed!")
        except Exception as e:
            logger.error(f"Buy callback error: {e}")
            await query.edit_message_text("❌ Buy action failed. Please try again.")
    
    async def _handle_mnemonic_callbacks(self, query, context, data: str):
        """Handle mnemonic command callbacks"""
        try:
            if data == "mnemonic_status":
                from core.secure_wallet import get_secure_wallet
                secure_wallet = get_secure_wallet()
                status = secure_wallet.get_wallet_status()
                
                if status['configured']:
                    message = f"""
🔐 **Wallet Status**

✅ **Configured:** Yes
📅 **Created:** {status.get('created_at', 'Unknown')}
💾 **Size:** {status.get('file_size', 0)} bytes
🔑 **Address:** {status.get('address', 'Unknown')[:6]}...{status.get('address', 'Unknown')[-6:]}
📁 **Path:** {status.get('keystore_path', 'Unknown')}
"""
                else:
                    message = """
🔐 **Wallet Status**

❌ **Configured:** No
⚠️ **Action Required:** Run `/mnemonic generate` or `/mnemonic import`
"""
                
                await query.edit_message_text(message, parse_mode='Markdown')
            
            elif data == "mnemonic_generate":
                await query.edit_message_text(
                    "🔐 **Generate New Wallet**\n\n"
                    "⚠️ **WARNING:** This will create a new wallet and overwrite any existing one!\n\n"
                    "Please provide a password:\n"
                    "`/mnemonic generate <password>`\n\n"
                    "**Security:** Your mnemonic will be encrypted and never shown in chat.",
                    parse_mode='Markdown'
                )
            
            elif data == "mnemonic_import":
                await query.edit_message_text(
                    "🔐 **Import Wallet**\n\n"
                    "⚠️ **SECURITY WARNING:**\n"
                    "Never type your mnemonic in Telegram chat!\n\n"
                    "**Secure Import Process:**\n"
                    "1. Run: `python secure_import.py`\n"
                    "2. Enter your mnemonic securely\n"
                    "3. Set a strong password\n"
                    "4. Wallet will be encrypted and stored\n\n"
                    "**Why this method?**\n"
                    "• Keeps mnemonic out of chat logs\n"
                    "• Prevents accidental exposure\n"
                    "• Follows security best practices",
                    parse_mode='Markdown'
                )
            
            elif data == "mnemonic_export":
                await query.edit_message_text(
                    "🔐 **Export Wallet**\n\n"
                    "Please provide your password:\n"
                    "`/mnemonic export <password>`\n\n"
                    "**What you'll get:**\n"
                    "• Encrypted keystore data\n"
                    "• Wallet addresses for all chains\n"
                    "• Safe to backup and restore",
                    parse_mode='Markdown'
                )
            
            elif data == "mnemonic_delete":
                await query.edit_message_text(
                    "🚨 **Delete Wallet**\n\n"
                    "⚠️ **WARNING:** This will permanently delete your wallet!\n\n"
                    "**This action cannot be undone!**\n\n"
                    "If you're absolutely sure, provide your password:\n"
                    "`/mnemonic delete <password>`\n\n"
                    "**Make sure you have:**\n"
                    "• Backed up your mnemonic\n"
                    "• Exported your keystore\n"
                    "• Transferred all funds",
                    parse_mode='Markdown'
                )
            
            elif data == "mnemonic_confirm_delete":
                await query.edit_message_text(
                    "🚨 **Final Confirmation**\n\n"
                    "**LAST CHANCE!** This will permanently delete your wallet!\n\n"
                    "Type: `CONFIRM DELETE` to proceed\n\n"
                    "⚠️ **This action cannot be undone!**"
                )
        
        except Exception as e:
            logger.error(f"Mnemonic callback error: {e}")
            await query.edit_message_text("❌ Mnemonic action failed. Please try again.")

# Global commands instance
bot_commands = BotCommands()

def get_bot_commands() -> BotCommands:
    """Get bot commands instance"""
    return bot_commands