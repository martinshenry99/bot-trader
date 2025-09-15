"""
Alert management system for Meme Trader V4 Pro
"""
import os
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from telegram import Update, Bot
from telegram.ext import CallbackContext

logger = logging.getLogger(__name__)

class AlertManager:
    """Manage system alerts and notifications"""
    
    def __init__(self):
        self.config = {
            "critical": {
                "timeout": 0,  # Send immediately
                "retry": 300,  # Retry every 5 minutes
                "channels": ["telegram", "log"]
            },
            "warning": {
                "timeout": 300,  # 5 minute cooldown
                "retry": 3600,  # Retry every hour
                "channels": ["telegram", "log"]
            },
            "info": {
                "timeout": 3600,  # 1 hour cooldown
                "retry": None,  # No retry
                "channels": ["log"]
            }
        }
        
        self.alert_history = {}
        self.last_notification = {}
        self.bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
        self.admin_id = os.getenv("ADMIN_USER_ID")
        
    async def send_alert(
        self,
        level: str,
        title: str,
        message: str,
        metadata: Optional[Dict] = None
    ):
        """Send an alert"""
        timestamp = datetime.utcnow()
        alert_id = f"{level}_{title}_{timestamp.strftime('%Y%m%d%H%M%S')}"
        
        alert = {
            "id": alert_id,
            "level": level,
            "title": title,
            "message": message,
            "metadata": metadata or {},
            "timestamp": timestamp.isoformat(),
            "status": "new"
        }
        
        # Check cooldown
        if title in self.last_notification:
            last_time = self.last_notification[title]
            cooldown = self.config[level]["timeout"]
            
            if cooldown and (timestamp - last_time) < timedelta(seconds=cooldown):
                logger.debug(f"Alert '{title}' is on cooldown")
                return
                
        # Record alert
        self.alert_history[alert_id] = alert
        self.last_notification[title] = timestamp
        
        # Send notifications
        channels = self.config[level]["channels"]
        
        if "telegram" in channels:
            await self._send_telegram_alert(alert)
            
        if "log" in channels:
            self._log_alert(alert)
            
        # Save alert history
        self._save_history()
        
    async def _send_telegram_alert(self, alert: Dict[str, Any]):
        """Send alert via Telegram"""
        try:
            if not self.admin_id:
                logger.error("No admin Telegram ID configured")
                return
                
            # Format message
            emoji = {
                "critical": "🚨",
                "warning": "⚠️",
                "info": "ℹ️"
            }
            
            message = (
                f"{emoji[alert['level']]} *{alert['title']}*\n\n"
                f"{alert['message']}\n\n"
                f"Time: {alert['timestamp']}"
            )
            
            if alert['metadata']:
                message += "\n\nDetails:"
                for key, value in alert['metadata'].items():
                    message += f"\n• {key}: {value}"
                    
            await self.bot.send_message(
                chat_id=self.admin_id,
                text=message,
                parse_mode='Markdown'
            )
            
            alert['status'] = "sent"
            
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")
            alert['status'] = "failed"
            
    def _log_alert(self, alert: Dict[str, Any]):
        """Log alert to file"""
        try:
            log_level = {
                "critical": logging.ERROR,
                "warning": logging.WARNING,
                "info": logging.INFO
            }[alert['level']]
            
            logger.log(
                log_level,
                f"ALERT: {alert['title']} - {alert['message']}"
            )
            
        except Exception as e:
            logger.error(f"Failed to log alert: {e}")
            
    def _save_history(self):
        """Save alert history to file"""
        try:
            os.makedirs("data", exist_ok=True)
            with open("data/alert_history.json", "w") as f:
                json.dump(
                    {k: v for k, v in self.alert_history.items()},
                    f,
                    indent=2
                )
        except Exception as e:
            logger.error(f"Failed to save alert history: {e}")
            
    def _load_history(self):
        """Load alert history from file"""
        try:
            if os.path.exists("data/alert_history.json"):
                with open("data/alert_history.json", "r") as f:
                    self.alert_history = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load alert history: {e}")
            
    async def retry_failed_alerts(self):
        """Retry failed critical/warning alerts"""
        now = datetime.utcnow()
        
        for alert_id, alert in self.alert_history.items():
            if alert['status'] != "failed":
                continue
                
            level = alert['level']
            if level not in ["critical", "warning"]:
                continue
                
            timestamp = datetime.fromisoformat(alert['timestamp'])
            retry_after = self.config[level]["retry"]
            
            if retry_after and (now - timestamp).total_seconds() >= retry_after:
                await self.send_alert(
                    level,
                    f"Retry: {alert['title']}",
                    alert['message'],
                    alert['metadata']
                )
                
    def get_recent_alerts(
        self,
        hours: int = 24,
        level: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get recent alerts"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        alerts = []
        for alert in self.alert_history.values():
            timestamp = datetime.fromisoformat(alert['timestamp'])
            if timestamp < cutoff:
                continue
                
            if level and alert['level'] != level:
                continue
                
            alerts.append(alert)
            
        return sorted(
            alerts,
            key=lambda x: x['timestamp'],
            reverse=True
        )
        
    async def start_alert_manager(self):
        """Start alert management system"""
        self._load_history()
        
        while True:
            try:
                await self.retry_failed_alerts()
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"Alert manager error: {e}")
                await asyncio.sleep(5)
                
async def main():
    """Run alert manager"""
    manager = AlertManager()
    await manager.start_alert_manager()
    
if __name__ == "__main__":
    asyncio.run(main())
