"""
API usage monitoring for Meme Trader V4 Pro
"""
import os
import json
import asyncio
import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)

class APIUsageMonitor:
    """Monitor API usage and rate limits"""
    
    def __init__(self):
        self.usage_file = "data/api_usage.json"
        self.usage_data = defaultdict(dict)
        self.rate_limits = {
            "covalent": int(os.getenv("COVALENT_RATE_LIMIT", "60")),
            "goplus": int(os.getenv("GOPLUS_RATE_LIMIT", "60")),
            "zerox": int(os.getenv("ZEROX_RATE_LIMIT", "60")),
            "jupiter": int(os.getenv("JUPITER_RATE_LIMIT", "60")),
            "helius": int(os.getenv("HELIUS_RATE_LIMIT", "60")),
            "coingecko": int(os.getenv("COINGECKO_RATE_LIMIT", "60"))
        }
        self._load_usage_data()
        
    def _load_usage_data(self):
        """Load API usage data from file"""
        try:
            if os.path.exists(self.usage_file):
                with open(self.usage_file, 'r') as f:
                    self.usage_data = defaultdict(dict, json.load(f))
        except Exception as e:
            logger.error(f"Error loading API usage data: {e}")
            
    def _save_usage_data(self):
        """Save API usage data to file"""
        try:
            os.makedirs(os.path.dirname(self.usage_file), exist_ok=True)
            with open(self.usage_file, 'w') as f:
                json.dump(dict(self.usage_data), f, indent=2)
        except Exception as e:
            logger.error(f"Error saving API usage data: {e}")
            
    def track_request(
        self,
        api: str,
        endpoint: str,
        status_code: int,
        latency: float
    ):
        """Track an API request"""
        timestamp = datetime.utcnow().isoformat()
        
        if api not in self.usage_data:
            self.usage_data[api] = {
                "requests": 0,
                "errors": 0,
                "rate_limited": 0,
                "total_latency": 0,
                "endpoints": defaultdict(int),
                "last_request": None,
                "history": []
            }
            
        self.usage_data[api]["requests"] += 1
        
        if status_code >= 400:
            self.usage_data[api]["errors"] += 1
            
        if status_code == 429:
            self.usage_data[api]["rate_limited"] += 1
            
        self.usage_data[api]["total_latency"] += latency
        self.usage_data[api]["endpoints"][endpoint] += 1
        self.usage_data[api]["last_request"] = timestamp
        
        # Keep last 1000 requests in history
        self.usage_data[api]["history"].append({
            "timestamp": timestamp,
            "endpoint": endpoint,
            "status_code": status_code,
            "latency": latency
        })
        self.usage_data[api]["history"] = \
            self.usage_data[api]["history"][-1000:]
            
        self._save_usage_data()
        
    def check_rate_limits(self, api: str, window: int = 60) -> Dict[str, Any]:
        """Check if API is approaching rate limits"""
        try:
            if api not in self.usage_data:
                return {
                    "status": "unknown",
                    "current_rate": 0,
                    "limit": self.rate_limits.get(api, 0),
                    "usage_percent": 0
                }
                
            now = datetime.utcnow()
            cutoff = now - timedelta(seconds=window)
            
            # Count requests in window
            recent_requests = sum(
                1 for req in self.usage_data[api]["history"]
                if datetime.fromisoformat(req["timestamp"]) > cutoff
            )
            
            limit = self.rate_limits.get(api, 0)
            usage_percent = (recent_requests / limit * 100) if limit > 0 else 0
            
            return {
                "status": "warning" if usage_percent > 80 else "healthy",
                "current_rate": recent_requests,
                "limit": limit,
                "usage_percent": usage_percent
            }
            
        except Exception as e:
            logger.error(f"Error checking rate limits for {api}: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
            
    def get_api_metrics(self, api: str) -> Dict[str, Any]:
        """Get metrics for specific API"""
        if api not in self.usage_data:
            return {}
            
        data = self.usage_data[api]
        total_requests = data["requests"]
        
        return {
            "total_requests": total_requests,
            "error_rate": (data["errors"] / total_requests * 100) if total_requests > 0 else 0,
            "rate_limited": data["rate_limited"],
            "avg_latency": (data["total_latency"] / total_requests) if total_requests > 0 else 0,
            "endpoints": dict(data["endpoints"]),
            "last_request": data["last_request"],
            "rate_limits": self.check_rate_limits(api)
        }
        
    def get_usage_summary(self) -> Dict[str, Any]:
        """Get overall API usage summary"""
        summary = {}
        
        for api in self.usage_data.keys():
            metrics = self.get_api_metrics(api)
            rate_limits = self.check_rate_limits(api)
            
            summary[api] = {
                "status": rate_limits["status"],
                "usage_percent": rate_limits["usage_percent"],
                "error_rate": metrics.get("error_rate", 0),
                "rate_limited_count": metrics.get("rate_limited", 0),
                "total_requests": metrics.get("total_requests", 0)
            }
            
        return summary
        
    def get_usage_report(self) -> str:
        """Get human readable usage report"""
        try:
            lines = ["=== API Usage Report ==="]
            
            for api, metrics in self.get_usage_summary().items():
                status_emoji = {
                    "healthy": "✅",
                    "warning": "⚠️",
                    "error": "❌",
                    "unknown": "❓"
                }[metrics["status"]]
                
                lines.extend([
                    f"\n{status_emoji} {api.upper()}:",
                    f"  Usage: {metrics['usage_percent']:.1f}%",
                    f"  Requests: {metrics['total_requests']}",
                    f"  Error Rate: {metrics['error_rate']:.1f}%",
                    f"  Rate Limited: {metrics['rate_limited_count']} times"
                ])
                
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"Error generating usage report: {e}")
            return f"Error: {str(e)}"
            
    def analyze_usage_patterns(
        self,
        api: str,
        hours: int = 24
    ) -> Dict[str, Any]:
        """Analyze API usage patterns"""
        try:
            if api not in self.usage_data:
                return {}
                
            now = datetime.utcnow()
            cutoff = now - timedelta(hours=hours)
            
            # Filter recent requests
            recent_requests = [
                req for req in self.usage_data[api]["history"]
                if datetime.fromisoformat(req["timestamp"]) > cutoff
            ]
            
            if not recent_requests:
                return {}
                
            # Analyze patterns
            hourly_counts = defaultdict(int)
            endpoint_counts = defaultdict(int)
            error_counts = defaultdict(int)
            latencies = []
            
            for req in recent_requests:
                hour = datetime.fromisoformat(req["timestamp"]).strftime("%H")
                hourly_counts[hour] += 1
                endpoint_counts[req["endpoint"]] += 1
                if req["status_code"] >= 400:
                    error_counts[req["status_code"]] += 1
                latencies.append(req["latency"])
                
            return {
                "total_requests": len(recent_requests),
                "hourly_distribution": dict(hourly_counts),
                "top_endpoints": dict(sorted(
                    endpoint_counts.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:5]),
                "error_distribution": dict(error_counts),
                "avg_latency": sum(latencies) / len(latencies) if latencies else 0,
                "max_latency": max(latencies) if latencies else 0
            }
            
        except Exception as e:
            logger.error(f"Error analyzing usage patterns for {api}: {e}")
            return {}
            
    async def monitor_rate_limits(self):
        """Continuously monitor rate limits"""
        while True:
            try:
                summary = self.get_usage_summary()
                
                for api, metrics in summary.items():
                    if metrics["status"] == "warning":
                        logger.warning(
                            f"High API usage for {api}: "
                            f"{metrics['usage_percent']:.1f}%"
                        )
                    elif metrics["status"] == "error":
                        logger.error(
                            f"API {api} is in error state: "
                            f"{metrics.get('error', 'Unknown error')}"
                        )
                        
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Rate limit monitoring error: {e}")
                await asyncio.sleep(5)
                
async def main():
    """Run API usage monitoring"""
    monitor = APIUsageMonitor()
    await monitor.monitor_rate_limits()
    
if __name__ == "__main__":
    asyncio.run(main())
