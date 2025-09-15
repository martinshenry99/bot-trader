"""
Health monitoring system for Meme Trader V4 Pro
"""
import os
import psutil
import asyncio
import logging
from typing import Dict, Any
from datetime import datetime

from config import Config
from db.models import setup_database
from integrations.covalent import CovalentAPI
from integrations.goplus import GoPlusAPI
from integrations.zerox import ZeroXClient
from integrations.jupiter import JupiterAPI
from integrations.helius import HeliusAPI
from integrations.coingecko import CoinGeckoAPI

logger = logging.getLogger(__name__)

class HealthMonitor:
    """System health monitoring"""
    
    def __init__(self):
        self.config = Config()
        self.last_check = None
        self.health_data = {}
        
    async def check_system_health(self) -> Dict[str, Any]:
        """Check overall system health"""
        self.last_check = datetime.utcnow()
        
        self.health_data = {
            "timestamp": self.last_check.isoformat(),
            "system": await self._check_system_resources(),
            "api": await self._check_api_health(),
            "database": await self._check_database(),
            "memory": await self._check_memory_usage(),
            "status": "healthy"  # Will be updated based on checks
        }
        
        # Update overall status
        if any(
            component.get("status") == "error"
            for component in self.health_data.values()
            if isinstance(component, dict)
        ):
            self.health_data["status"] = "error"
        elif any(
            component.get("status") == "warning"
            for component in self.health_data.values()
            if isinstance(component, dict)
        ):
            self.health_data["status"] = "warning"
            
        return self.health_data
        
    async def _check_system_resources(self) -> Dict[str, Any]:
        """Check system resource usage"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            status = "healthy"
            warnings = []
            
            # Check thresholds
            if cpu_percent > 80:
                status = "warning"
                warnings.append("High CPU usage")
                
            if memory.percent > 85:
                status = "warning"
                warnings.append("High memory usage")
                
            if disk.percent > 90:
                status = "warning"
                warnings.append("Low disk space")
                
            return {
                "status": status,
                "cpu_usage": cpu_percent,
                "memory_usage": memory.percent,
                "disk_usage": disk.percent,
                "warnings": warnings
            }
            
        except Exception as e:
            logger.error(f"Error checking system resources: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
            
    async def _check_api_health(self) -> Dict[str, Any]:
        """Check API health status"""
        apis = {
            "covalent": CovalentAPI(),
            "goplus": GoPlusAPI(),
            "zerox": ZeroXClient(),
            "jupiter": JupiterAPI(),
            "helius": HeliusAPI(),
            "coingecko": CoinGeckoAPI()
        }
        
        results = {}
        overall_status = "healthy"
        
        for name, api in apis.items():
            try:
                await api.health_check()
                results[name] = {
                    "status": "healthy",
                    "latency": await self._measure_api_latency(api)
                }
            except Exception as e:
                results[name] = {
                    "status": "error",
                    "error": str(e)
                }
                overall_status = "error"
                
        return {
            "status": overall_status,
            "apis": results
        }
        
    async def _check_database(self) -> Dict[str, Any]:
        """Check database health"""
        try:
            # Test database connection and basic operations
            conn = setup_database()
            cursor = conn.cursor()
            
            # Check if tables exist
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table'
            """)
            tables = cursor.fetchall()
            
            # Check table sizes
            table_sizes = {}
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
                table_sizes[table[0]] = cursor.fetchone()[0]
                
            # Check database size
            db_path = os.getenv("DB_PATH", "meme_trader.db")
            db_size = os.path.getsize(db_path) / (1024 * 1024)  # Size in MB
            
            status = "healthy"
            warnings = []
            
            # Check thresholds
            if db_size > 1000:  # 1GB
                status = "warning"
                warnings.append("Database size exceeds 1GB")
                
            return {
                "status": status,
                "size_mb": round(db_size, 2),
                "tables": table_sizes,
                "warnings": warnings
            }
            
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
            
    async def _check_memory_usage(self) -> Dict[str, Any]:
        """Check application memory usage"""
        try:
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            
            # Convert to MB
            rss = memory_info.rss / (1024 * 1024)
            vms = memory_info.vms / (1024 * 1024)
            
            status = "healthy"
            warnings = []
            
            # Check thresholds
            if rss > 1000:  # 1GB RSS
                status = "warning"
                warnings.append("High RSS memory usage")
                
            return {
                "status": status,
                "rss_mb": round(rss, 2),
                "vms_mb": round(vms, 2),
                "warnings": warnings
            }
            
        except Exception as e:
            logger.error(f"Memory check failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
            
    async def _measure_api_latency(self, api) -> float:
        """Measure API response latency"""
        try:
            start = datetime.utcnow()
            await api.health_check()
            end = datetime.utcnow()
            
            return (end - start).total_seconds() * 1000  # Convert to ms
            
        except Exception:
            return -1  # Error measuring latency
            
    async def start_monitoring(self):
        """Start continuous health monitoring"""
        while True:
            try:
                await self.check_system_health()
                logger.info(f"Health Status: {self.health_data['status']}")
                
                if self.health_data["status"] != "healthy":
                    logger.warning("Health check warnings/errors detected")
                    
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Health monitoring error: {e}")
                await asyncio.sleep(5)  # Brief pause on error
                
async def main():
    """Run health monitoring"""
    monitor = HealthMonitor()
    await monitor.start_monitoring()
    
if __name__ == "__main__":
    asyncio.run(main())
