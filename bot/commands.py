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
            
            # Format watchlist exactly as specified
            message = "🔔 **Your Watchlist:**\n\n"
            
            for item in watchlist:
                # Format address
                short_addr = f"{item['address'][:6]}...{item['address'][-4:]}"
                chain_name = item['chain'].upper()
                
                # Format label
                label_text = f" (label: {item['label']})" if item['label'] else ""
                
                # Format timestamp
                added_time = datetime.fromtimestamp(item['added_at'])
                time_ago = self._format_time_ago(added_time)
                
                item_text = (
                    f"🔔 **{short_addr}** ({chain_name}){label_text}\n"
                    f"Added: {time_ago}\n\n"
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
        
        for item in watchlist:
            # Row for each item with action buttons
            row = [
                InlineKeyboardButton(
                    "🔍 Analyze", 
                    callback_data=f"analyze_wallet_{item['address']}_{item['chain']}"
                ),
                InlineKeyboardButton(
                    "🗑 Remove", 
                    callback_data=f"remove_watchlist_{item['address']}_{item['chain']}"
                ),
                InlineKeyboardButton(
                    "📋 Copy", 
                    callback_data=f"copy_address_{item['address']}"
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

# Global commands instance
bot_commands = BotCommands()

def get_bot_commands() -> BotCommands:
    """Get bot commands instance"""
    return bot_commands