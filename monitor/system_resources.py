"""
System resource monitoring for Meme Trader V4 Pro
"""
import os
import psutil
import asyncio
import logging
from typing import Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class SystemMonitor:
    """Monitor system resources"""
    
    def __init__(self):
        self.process = psutil.Process(os.getpid())
        self.start_time = datetime.utcnow()
        self.metrics = {}
        
    async def get_system_metrics(self) -> Dict[str, Any]:
        """Get current system metrics"""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            per_cpu = psutil.cpu_percent(interval=1, percpu=True)
            load_avg = psutil.getloadavg()
            
            # Memory metrics
            virtual_memory = psutil.virtual_memory()
            swap_memory = psutil.swap_memory()
            
            # Disk metrics
            disk_usage = psutil.disk_usage('/')
            disk_io = psutil.disk_io_counters()
            
            # Network metrics
            net_io = psutil.net_io_counters()
            
            # Process metrics
            process_info = self._get_process_metrics()
            
            self.metrics = {
                "timestamp": datetime.utcnow().isoformat(),
                "uptime": str(datetime.utcnow() - self.start_time),
                "cpu": {
                    "total_percent": cpu_percent,
                    "per_cpu_percent": per_cpu,
                    "load_average": load_avg
                },
                "memory": {
                    "total": virtual_memory.total,
                    "available": virtual_memory.available,
                    "used": virtual_memory.used,
                    "percent": virtual_memory.percent,
                    "swap_total": swap_memory.total,
                    "swap_used": swap_memory.used,
                    "swap_percent": swap_memory.percent
                },
                "disk": {
                    "total": disk_usage.total,
                    "used": disk_usage.used,
                    "free": disk_usage.free,
                    "percent": disk_usage.percent,
                    "read_bytes": disk_io.read_bytes,
                    "write_bytes": disk_io.write_bytes
                },
                "network": {
                    "bytes_sent": net_io.bytes_sent,
                    "bytes_recv": net_io.bytes_recv,
                    "packets_sent": net_io.packets_sent,
                    "packets_recv": net_io.packets_recv
                },
                "process": process_info
            }
            
            return self.metrics
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            return {}
            
    def _get_process_metrics(self) -> Dict[str, Any]:
        """Get process-specific metrics"""
        try:
            memory_info = self.process.memory_info()
            
            return {
                "cpu_percent": self.process.cpu_percent(),
                "memory_rss": memory_info.rss,
                "memory_vms": memory_info.vms,
                "threads": self.process.num_threads(),
                "fds": self.process.num_fds() if hasattr(self.process, 'num_fds') else None,
                "connections": len(self.process.connections()),
                "status": self.process.status()
            }
            
        except Exception as e:
            logger.error(f"Error collecting process metrics: {e}")
            return {}
            
    def check_resource_usage(self) -> Dict[str, Any]:
        """Check if resource usage exceeds thresholds"""
        warnings = []
        
        try:
            if not self.metrics:
                return {"status": "unknown", "warnings": ["No metrics available"]}
                
            # CPU thresholds
            if self.metrics["cpu"]["total_percent"] > 80:
                warnings.append(
                    f"High CPU usage: {self.metrics['cpu']['total_percent']}%"
                )
                
            # Memory thresholds
            if self.metrics["memory"]["percent"] > 85:
                warnings.append(
                    f"High memory usage: {self.metrics['memory']['percent']}%"
                )
                
            if self.metrics["memory"]["swap_percent"] > 60:
                warnings.append(
                    f"High swap usage: {self.metrics['memory']['swap_percent']}%"
                )
                
            # Disk thresholds
            if self.metrics["disk"]["percent"] > 90:
                warnings.append(
                    f"Low disk space: {self.metrics['disk']['percent']}% used"
                )
                
            # Process thresholds
            if self.metrics["process"]["cpu_percent"] > 50:
                warnings.append(
                    f"High process CPU: {self.metrics['process']['cpu_percent']}%"
                )
                
            if self.metrics["process"]["memory_rss"] > 1_000_000_000:  # 1GB
                warnings.append(
                    "High process memory usage: >1GB RSS"
                )
                
            return {
                "status": "warning" if warnings else "healthy",
                "warnings": warnings
            }
            
        except Exception as e:
            logger.error(f"Error checking resource usage: {e}")
            return {
                "status": "error",
                "warnings": [str(e)]
            }
            
    def _format_bytes(self, bytes: int) -> str:
        """Format bytes to human readable string"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes < 1024:
                return f"{bytes:.2f} {unit}"
            bytes /= 1024
        return f"{bytes:.2f} PB"
        
    def get_resource_summary(self) -> str:
        """Get human readable resource summary"""
        try:
            if not self.metrics:
                return "No metrics available"
                
            lines = [
                "=== System Resource Summary ===",
                f"Time: {self.metrics['timestamp']}",
                f"Uptime: {self.metrics['uptime']}",
                "",
                "CPU:",
                f"  Total: {self.metrics['cpu']['total_percent']}%",
                f"  Load Avg: {self.metrics['cpu']['load_average']}",
                "",
                "Memory:",
                f"  Used: {self._format_bytes(self.metrics['memory']['used'])}",
                f"  Available: {self._format_bytes(self.metrics['memory']['available'])}",
                f"  Percentage: {self.metrics['memory']['percent']}%",
                "",
                "Disk:",
                f"  Used: {self._format_bytes(self.metrics['disk']['used'])}",
                f"  Free: {self._format_bytes(self.metrics['disk']['free'])}",
                f"  Percentage: {self.metrics['disk']['percent']}%",
                "",
                "Network:",
                f"  Sent: {self._format_bytes(self.metrics['network']['bytes_sent'])}",
                f"  Received: {self._format_bytes(self.metrics['network']['bytes_recv'])}",
                "",
                "Process:",
                f"  CPU: {self.metrics['process']['cpu_percent']}%",
                f"  Memory RSS: {self._format_bytes(self.metrics['process']['memory_rss'])}",
                f"  Threads: {self.metrics['process']['threads']}",
                f"  Status: {self.metrics['process']['status']}"
            ]
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"Error generating resource summary: {e}")
            return f"Error: {str(e)}"
            
    async def start_monitoring(self, interval: int = 60):
        """Start continuous resource monitoring"""
        while True:
            try:
                metrics = await self.get_system_metrics()
                status = self.check_resource_usage()
                
                if status["status"] != "healthy":
                    logger.warning(
                        "Resource warnings:\n" +
                        "\n".join(f"- {w}" for w in status["warnings"])
                    )
                    
                await asyncio.sleep(interval)
                
            except Exception as e:
                logger.error(f"Resource monitoring error: {e}")
                await asyncio.sleep(5)
                
async def main():
    """Run system monitoring"""
    monitor = SystemMonitor()
    await monitor.start_monitoring()
    
if __name__ == "__main__":
    asyncio.run(main())
