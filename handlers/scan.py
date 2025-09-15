"""
Scan command handler implementation with settings integration
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.base_command import BaseCommand
from bot.callback_data import CallbackAction, create_callback_data
from monitor.scanner import DiscoveryScanner
from services.insider_detector import InsiderDetector
from services.wallet_analyzer import wallet_analyzer
from db.models import get_db_manager
from utils.formatting import format_scan_result, format_wallet_analysis, format_error_message

logger = logging.getLogger(__name__)

class ScanCommand(BaseCommand):
    """Handler for /scan command and callbacks"""
    
    def __init__(self):
        super().__init__()
        self.db = get_db_manager()
        self.scanner = DiscoveryScanner()
        self.insider_detector = InsiderDetector()
        self.items_per_page = 5
        
    async def __call__(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /scan command"""
        try:
            # Ensure user exists
            if not await self.ensure_user_exists(update):
                return
                
            user_id = str(update.effective_user.id)
            page = 0  # Start with first page
            
            await self.show_scan_menu(update, user_id, page)
            
        except Exception as e:
            logger.error(f"Error in scan command: {e}", exc_info=True)
            error_msg = format_error_message("Failed to load scan menu")
            if update.message:
                await update.message.reply_text(error_msg)
            elif update.callback_query:
                await update.callback_query.edit_message_text(error_msg)
                
    async def show_scan_menu(self, update: Update, user_id: str, page: int):
        """Show scan menu with options"""
        try:
            # Get settings
            settings = await self.get_user_settings(user_id)
            
            # Build keyboard
            keyboard = [
                [
                    InlineKeyboardButton(
                        "📊 Active Scans",
                        callback_data=create_callback_data(
                            CallbackAction.SELECT,
                            "scan_active"
                        )
                    ),
                    InlineKeyboardButton(
                        "➕ New Scan",
                        callback_data=create_callback_data(
                            CallbackAction.SELECT,
                            "scan_new"
                        )
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🔍 Discovery Mode",
                        callback_data=create_callback_data(
                            CallbackAction.SELECT,
                            "scan_discovery"
                        )
                    ),
                    InlineKeyboardButton(
                        "⚙️ Scan Settings",
                        callback_data=create_callback_data(
                            CallbackAction.SETTINGS,
                            "scan_settings"
                        )
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🔙 Back to Menu",
                        callback_data=create_callback_data(
                            CallbackAction.SELECT,
                            "main_menu"
                        )
                    )
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            text = (
                "🔍 **SCANNER MENU**\n\n"
                "Choose scan type:\n\n"
                "📊 Active Scans - View current scan results\n"
                "➕ New Scan - Start wallet or token scan\n"
                "🔍 Discovery - Find trending tokens\n"
                "⚙️ Settings - Configure scan parameters\n\n"
                f"Current Settings:\n"
                f"• Min Score: {settings.get('scan_min_score', 70)}%\n"
                f"• Min Trades: {settings.get('scan_min_trades', 10)}\n"
                f"• Alert Min USD: ${settings.get('alert_min_usd', 1000)}\n"
                f"• Alert Frequency: {settings.get('alert_frequency', 300)}s"
            )
            
            if update.message:
                await update.message.reply_text(
                    text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            else:
                await update.callback_query.edit_message_text(
                    text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                
        except Exception as e:
            logger.error(f"Error showing scan menu: {e}", exc_info=True)
            error_msg = format_error_message("Failed to load scan menu")
            if update.message:
                await update.message.reply_text(error_msg)
            elif update.callback_query:
                await update.callback_query.edit_message_text(error_msg)
                
    async def show_active_scans(self, update: Update, user_id: str, page: int):
        """Show active scans and results"""
        try:
            # Get user's watched wallets
            watched_wallets = await self.db.get_user_watchlist(user_id)
            
            # Get wallet data and analysis
            scan_results = []
            for wallet in watched_wallets:
                try:
                    analysis = await wallet_analyzer.analyze_wallet(
                        wallet.address,
                        wallet.chain,
                        time_window=timedelta(hours=24)
                    )
                    
                    scan_results.append({
                        'wallet': wallet,
                        'analysis': analysis
                    })
                except Exception as e:
                    logger.error(f"Error analyzing wallet {wallet.address}: {e}")
                    continue
                    
            # Sort by trade volume
            scan_results.sort(
                key=lambda x: x['analysis'].get('total_volume_usd', 0),
                reverse=True
            )
            
            # Paginate results
            start_idx = page * self.items_per_page
            end_idx = start_idx + self.items_per_page
            page_results = scan_results[start_idx:end_idx]
            total_pages = (len(scan_results) + self.items_per_page - 1) // self.items_per_page
            
            # Format text
            text = "📊 **ACTIVE SCANS**\n\n"
            
            if not watched_wallets:
                text += "No active scans.\nStart a new scan to begin monitoring!"
            else:
                text += f"Monitoring {len(watched_wallets)} targets:\n\n"
                
                for result in page_results:
                    wallet = result['wallet']
                    analysis = result['analysis']
                    
                    text += format_wallet_analysis(
                        wallet.address,
                        wallet.chain,
                        analysis,
                        include_trades=False
                    ) + "\n"
                    
                if total_pages > 1:
                    text += f"\nPage {page + 1}/{total_pages}"
            
            # Build keyboard
            keyboard = []
            
            if total_pages > 1:
                nav_buttons = []
                if page > 0:
                    nav_buttons.append(
                        InlineKeyboardButton(
                            "⬅️ Previous",
                            callback_data=create_callback_data(
                                CallbackAction.PREV_PAGE,
                                "scan_active",
                                page=page
                            )
                        )
                    )
                if page < total_pages - 1:
                    nav_buttons.append(
                        InlineKeyboardButton(
                            "Next ➡️",
                            callback_data=create_callback_data(
                                CallbackAction.NEXT_PAGE,
                                "scan_active",
                                page=page
                            )
                        )
                    )
                keyboard.append(nav_buttons)
                
            keyboard.append([
                InlineKeyboardButton(
                    "🔄 Refresh",
                    callback_data=create_callback_data(
                        CallbackAction.REFRESH,
                        "scan_active",
                        page=page
                    )
                ),
                InlineKeyboardButton(
                    "🔙 Back",
                    callback_data=create_callback_data(
                        CallbackAction.SELECT,
                        "scan_menu"
                    )
                )
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if update.message:
                await update.message.reply_text(
                    text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            else:
                await update.callback_query.edit_message_text(
                    text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                
        except Exception as e:
            logger.error(f"Error showing active scans: {e}", exc_info=True)
            error_msg = format_error_message("Failed to load active scans")
            if update.message:
                await update.message.reply_text(error_msg)
            elif update.callback_query:
                await update.callback_query.edit_message_text(error_msg)
                
    async def start_new_scan(self, update: Update, user_id: str, scan_type: str):
        """Start a new wallet or token scan"""
        try:
            # Get user settings
            settings = await self.get_user_settings(user_id)
            
            # Validate settings
            setting_errors = validate_settings(settings)
            if setting_errors:
                error_text = "Please fix the following settings:\n"
                for field, error in setting_errors.items():
                    error_text += f"• {field}: {error}\n"
                    
                keyboard = [[
                    InlineKeyboardButton(
                        "⚙️ Fix Settings",
                        callback_data=create_callback_data(
                            CallbackAction.SETTINGS,
                            "scan_settings"
                        )
                    ),
                    InlineKeyboardButton(
                        "🔙 Back",
                        callback_data=create_callback_data(
                            CallbackAction.SELECT,
                            "scan_menu"
                        )
                    )
                ]]
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.callback_query.edit_message_text(
                    error_text,
                    reply_markup=reply_markup
                )
                return
                
            # Show scan options
            keyboard = [[
                InlineKeyboardButton(
                    "👛 Wallet",
                    callback_data=create_callback_data(
                        CallbackAction.SELECT,
                        "scan_wallet"
                    )
                ),
                InlineKeyboardButton(
                    "🪙 Token",
                    callback_data=create_callback_data(
                        CallbackAction.SELECT,
                        "scan_token"
                    )
                )
            ], [
                InlineKeyboardButton(
                    "🔙 Back",
                    callback_data=create_callback_data(
                        CallbackAction.SELECT,
                        "scan_menu"
                    )
                )
            ]]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            text = (
                "🔍 **NEW SCAN**\n\n"
                "Choose what to scan:\n\n"
                "👛 Wallet - Monitor specific wallets\n"
                "🪙 Token - Track token metrics & trades"
            )
            
            await update.callback_query.edit_message_text(
                text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error starting new scan: {e}", exc_info=True)
            error_msg = format_error_message("Failed to start new scan")
            await update.callback_query.edit_message_text(error_msg)
            
    async def discovery_scan(self, update: Update, user_id: str, page: int):
        """Run token discovery scan"""
        try:
            # Get settings
            settings = await self.get_user_settings(user_id)
            
            # Validate scan parameters
            valid, error = self.validate_scan_inputs(
                min_score=settings.get('scan_min_score'),
                min_trades=settings.get('scan_min_trades'),
                min_volume=settings.get('alert_min_usd')
            )
            
            if not valid:
                keyboard = [[
                    InlineKeyboardButton(
                        "⚙️ Fix Settings",
                        callback_data=create_callback_data(
                            CallbackAction.SETTINGS,
                            "scan_settings"
                        )
                    ),
                    InlineKeyboardButton(
                        "🔙 Back",
                        callback_data=create_callback_data(
                            CallbackAction.SELECT,
                            "scan_menu"
                        )
                    )
                ]]
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.callback_query.edit_message_text(
                    f"❌ {error}\n\nPlease adjust your scan settings.",
                    reply_markup=reply_markup
                )
                return
            
            # Run scan with validated settings
            discoveries = await self.scanner.scan_with_settings(
                min_score=settings.get('scan_min_score', 70),
                min_trades=settings.get('scan_min_trades', 10),
                chains=settings.get('scan_chains', ['eth', 'bsc', 'sol']).split(','),
                page=page,
                limit=self.items_per_page
            )
            
            # Format text
            text = "🔍 **DISCOVERY SCAN**\n\n"
            
            if not discoveries:
                text += "No tokens found matching criteria."
            else:
                for token in discoveries:
                    text += format_scan_result(token) + "\n\n"
                    
            # Build keyboard
            keyboard = []
            
            if len(discoveries) == self.items_per_page:
                keyboard.append([
                    InlineKeyboardButton(
                        "Next Page ➡️",
                        callback_data=create_callback_data(
                            CallbackAction.NEXT_PAGE,
                            "scan_discovery",
                            page=page
                        )
                    )
                ])
                
            keyboard.append([
                InlineKeyboardButton(
                    "🔄 Refresh",
                    callback_data=create_callback_data(
                        CallbackAction.REFRESH,
                        "scan_discovery",
                        page=page
                    )
                ),
                InlineKeyboardButton(
                    "🔙 Back",
                    callback_data=create_callback_data(
                        CallbackAction.SELECT,
                        "scan_menu"
                    )
                )
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.callback_query.edit_message_text(
                text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error in discovery scan: {e}", exc_info=True)
            error_msg = format_error_message("Failed to run discovery scan")
            await update.callback_query.edit_message_text(error_msg)
        
        # Track stats
        total_scanned = 0
        passed_filters = 0
        results = []
        
        # Scan each chain
        for chain in chains:
            # Get initial candidates with pagination
            page = 1
            while len(results) < max_results:
                candidates = await self._get_candidates(chain, page=page, limit=50)
                if not candidates:
                    break
                    
                total_scanned += len(candidates)
                
                # Process candidates
                for candidate in candidates:
                    # Skip if we've reached max results
                    if len(results) >= max_results:
                        break
                        
                    # Apply score filter
                    if candidate.get('score', 0) < min_score:
                        continue
                        
                    # Check insider status
                    insider_data = await self.insider_detector.analyze(
                        candidate['address'],
                        chain,
                        lookback_minutes=int(db.get_user_setting(
                            user_id,
                            SettingKeys.INSIDER_EARLY_WINDOW.value,
                            "5"
                        ))
                    )
                    
                    if insider_data.get('score', 0) >= insider_min_score:
                        min_repeat = int(db.get_user_setting(
                            user_id,
                            SettingKeys.INSIDER_MIN_REPEAT.value,
                            "3"
                        ))
                        
                        if insider_data.get('repeat_count', 0) >= min_repeat:
                            candidate['insider_score'] = insider_data['score']
                            candidate['insider_label'] = insider_data['label']
                    
                    # Candidate passed all filters
                    passed_filters += 1
                    results.append(candidate)
                
                page += 1
        
        return {
            'results': results[:max_results],
            'stats': {
                'total_scanned': total_scanned,
                'passed_filters': passed_filters,
                'insider_detected': len([r for r in results if 'insider_score' in r])
            }
        }

async def handle_scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /scan command"""
    if not update.message:
        return
        
    user_id = update.message.from_user.id
    
    # Send initial status
    status_message = await update.message.reply_text(
        "🔍 Starting scan...\n"
        "This may take a few moments."
    )
    
    try:
        # Run scan
        scanner = EnhancedDiscoveryScanner()
        scan_results = await scanner.scan_with_settings(user_id)
        
        results = scan_results['results']
        stats = scan_results['stats']
        
        if not results:
            await status_message.edit_text(
                "❌ No results found matching your criteria.\n\n"
                f"Scanned: {stats['total_scanned']} wallets\n"
                "Try adjusting your settings with /settings."
            )
            return
            
        # Format results message
        msg = (
            "📊 Scan Results\n\n"
            f"Scanned: {stats['total_scanned']} candidates\n"
            f"Passed Filters: {stats['passed_filters']}\n"
            f"Insiders Detected: {stats['insider_detected']}\n\n"
        )
        
        # Add results
        for i, result in enumerate(results[:10], 1):
            msg += f"{i}. {format_scan_result(result)}\n\n"
            
        # Add note if more results available
        if len(results) > 10:
            msg += f"\n... and {len(results)-10} more results"
        
        # Add keyboard
        keyboard = []
        if len(results) > 10:
            keyboard.append([InlineKeyboardButton("📋 Show More", callback_data="scan:more:10")])
        
        keyboard.append([
            InlineKeyboardButton("⚙️ Settings", callback_data="settings:menu"),
            InlineKeyboardButton("🔄 Refresh", callback_data="scan:refresh")
        ])
        
        await status_message.edit_text(
            msg,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logger.error(f"Scan failed: {e}")
        await status_message.edit_text(
            "❌ Scan failed. Please try again later."
        )
