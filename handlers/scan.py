"""
Scan implementation for Meme Trader V4 Pro with settings integration
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from db.models import get_db_manager
from settings.constants import SettingKeys
from monitor.scanner import DiscoveryScanner
from utils.formatters import format_scan_result
from services.insider_detector import InsiderDetector

logger = logging.getLogger(__name__)

class EnhancedDiscoveryScanner(DiscoveryScanner):
    """Enhanced scanner with settings integration"""
    
    def __init__(self):
        super().__init__()
        self.insider_detector = InsiderDetector()
        
    async def scan_with_settings(self, user_id: int) -> List[Dict]:
        """
        Run scan with user settings
        """
        db = get_db_manager()
        
        # Get user settings
        min_score = int(db.get_user_setting(user_id, SettingKeys.SCAN_MIN_SCORE.value, "70"))
        max_results = int(db.get_user_setting(user_id, SettingKeys.SCAN_MAX_RESULTS.value, "50"))
        chains = db.get_user_setting(user_id, SettingKeys.SCAN_CHAINS.value, "eth,bsc,sol").split(",")
        insider_min_score = int(db.get_user_setting(user_id, SettingKeys.INSIDER_MIN_SCORE.value, "70"))
        
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
