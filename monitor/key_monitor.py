"""
API key management and alerts system
"""

import asyncio
from typing import Dict, List, Optional, Set
import time
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass
import os
from telegram import Bot
from handlers.key_management import KeyManager
from monitor.metrics import metrics_manager

logger = logging.getLogger(__name__)

@dataclass
class KeyStatus:
    """API key status information"""
    service: str
    total_keys: int
    available_keys: int
    cooldown_keys: int
    exhausted_keys: int
    next_available: Optional[datetime]

class KeyMonitor:
    """API key monitoring and alerting system"""
    
    def __init__(self, key_manager: KeyManager):
        self.key_manager = key_manager
        self.telegram_bot = Bot(os.getenv('TELEGRAM_BOT_TOKEN'))
        self.admin_id = int(os.getenv('ADMIN_TELEGRAM_ID'))
        
        # Alert settings
        self.alert_threshold = 0.2  # Alert when 20% keys remain
        self.alert_cooldown = 3600  # 1 hour between alerts
        self.last_alerts: Dict[str, float] = {}
        
        # Start monitoring
        self._start_monitor()
    
    def _start_monitor(self):
        """Start background monitoring task"""
        asyncio.create_task(self._monitor_loop())
    
    async def _monitor_loop(self):
        """Continuous monitoring loop"""
        while True:
            try:
                await self._check_all_services()
                await asyncio.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Error in key monitor loop: {str(e)}")
                await asyncio.sleep(60)  # Wait before retrying
    
    async def _check_all_services(self):
        """Check all services for key exhaustion"""
        for service in self.key_manager.list_services():
            status = await self.get_service_status(service)
            
            # Record metrics
            metrics_manager.record_api_key_status(
                service,
                status.available_keys,
                status.total_keys
            )
            
            # Check for alerts
            await self._check_alerts(status)
    
    async def get_service_status(self, service: str) -> KeyStatus:
        """Get current key status for a service"""
        keys = self.key_manager.get_service_keys(service)
        if not keys:
            return KeyStatus(
                service=service,
                total_keys=0,
                available_keys=0,
                cooldown_keys=0,
                exhausted_keys=0,
                next_available=None
            )
        
        now = datetime.now()
        available = 0
        cooldown = 0
        exhausted = 0
        next_time = None
        
        for key in keys:
            if key.is_available():
                available += 1
            elif key.cooldown_until and key.cooldown_until > now:
                cooldown += 1
                if not next_time or key.cooldown_until < next_time:
                    next_time = key.cooldown_until
            else:
                exhausted += 1
        
        return KeyStatus(
            service=service,
            total_keys=len(keys),
            available_keys=available,
            cooldown_keys=cooldown,
            exhausted_keys=exhausted,
            next_available=next_time
        )
    
    async def _check_alerts(self, status: KeyStatus):
        """Check if alerts need to be sent"""
        service = status.service
        now = time.time()
        
        # Skip if on cooldown
        if service in self.last_alerts:
            if now - self.last_alerts[service] < self.alert_cooldown:
                return
        
        # Calculate available percentage
        if status.total_keys == 0:
            return
            
        available_pct = status.available_keys / status.total_keys
        
        # Check for low availability
        if available_pct <= self.alert_threshold:
            await self._send_alert(status)
            self.last_alerts[service] = now
        
        # Check for complete exhaustion
        if status.available_keys == 0:
            await self._send_exhaustion_alert(status)
            self.last_alerts[service] = now
    
    async def _send_alert(self, status: KeyStatus):
        """Send low key availability alert"""
        message = (
            f"⚠️ Low API key availability for {status.service}\n\n"
            f"Available keys: {status.available_keys}/{status.total_keys}\n"
            f"Keys in cooldown: {status.cooldown_keys}\n"
            f"Exhausted keys: {status.exhausted_keys}\n"
        )
        
        if status.next_available:
            message += f"\nNext key available: {status.next_available.strftime('%H:%M:%S')}"
        
        try:
            await self.telegram_bot.send_message(
                chat_id=self.admin_id,
                text=message
            )
        except Exception as e:
            logger.error(f"Error sending key alert: {str(e)}")
    
    async def _send_exhaustion_alert(self, status: KeyStatus):
        """Send complete key exhaustion alert"""
        message = (
            f"🚨 CRITICAL: All API keys exhausted for {status.service}\n\n"
            f"Total keys: {status.total_keys}\n"
            f"Keys in cooldown: {status.cooldown_keys}\n"
        )
        
        if status.next_available:
            message += (
                f"\nNext key available: {status.next_available.strftime('%H:%M:%S')}\n"
                f"Time until available: {(status.next_available - datetime.now()).seconds // 60} minutes"
            )
        
        message += "\n\nRemediation steps:"
        message += "\n1. Check rate limits and adjust if needed"
        message += "\n2. Consider adding more API keys"
        message += "\n3. Review usage patterns for optimization"
        
        try:
            await self.telegram_bot.send_message(
                chat_id=self.admin_id,
                text=message,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Error sending exhaustion alert: {str(e)}")
    
    async def get_rotation_status(self) -> Dict[str, Dict]:
        """Get key rotation status for all services"""
        status = {}
        
        for service in self.key_manager.list_services():
            service_status = await self.get_service_status(service)
            
            # Calculate health metrics
            total = service_status.total_keys or 1  # Prevent div by zero
            health = (service_status.available_keys / total) * 100
            
            status[service] = {
                'health': f"{health:.1f}%",
                'available': service_status.available_keys,
                'total': service_status.total_keys,
                'cooldown': service_status.cooldown_keys,
                'exhausted': service_status.exhausted_keys,
                'next_available': (
                    service_status.next_available.strftime('%H:%M:%S')
                    if service_status.next_available else 'N/A'
                )
            }
        
        return status
