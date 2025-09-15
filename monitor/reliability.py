"""
Monitoring and metrics collection for API reliability
"""
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import logging
import asyncio
from dataclasses import dataclass, field
import statistics
from prometheus_client import (
    Counter,
    Histogram,
    Gauge
)

logger = logging.getLogger(__name__)

@dataclass
class APIMetrics:
    """Container for API call metrics"""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    rate_limit_hits: int = 0
    retry_count: int = 0
    response_times: list[float] = field(default_factory=list)
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None

class MetricsCollector:
    """Collects and exposes reliability metrics"""
    
    def __init__(self):
        # Prometheus metrics
        self.api_calls_total = Counter(
            'api_calls_total',
            'Total number of API calls',
            ['api_name', 'status']
        )
        
        self.api_response_time = Histogram(
            'api_response_time_seconds',
            'API response time in seconds',
            ['api_name']
        )
        
        self.cache_ops = Counter(
            'cache_operations_total',
            'Total cache operations',
            ['operation', 'status']
        )
        
        self.rate_limits = Counter(
            'rate_limit_hits_total',
            'Number of rate limit hits',
            ['api_name']
        )
        
        self.retry_attempts = Counter(
            'retry_attempts_total',
            'Number of retry attempts',
            ['api_name']
        )
        
        self.active_requests = Gauge(
            'active_requests',
            'Number of active requests',
            ['api_name']
        )
        
        # In-memory metrics
        self.api_metrics: Dict[str, APIMetrics] = {}
        
    def record_api_call(
        self,
        api_name: str,
        success: bool,
        response_time: float,
        error: Optional[str] = None
    ):
        """Record API call metrics"""
        # Update Prometheus metrics
        status = 'success' if success else 'failure'
        self.api_calls_total.labels(
            api_name=api_name,
            status=status
        ).inc()
        
        self.api_response_time.labels(
            api_name=api_name
        ).observe(response_time)
        
        # Update in-memory metrics
        if api_name not in self.api_metrics:
            self.api_metrics[api_name] = APIMetrics()
            
        metrics = self.api_metrics[api_name]
        metrics.total_calls += 1
        metrics.response_times.append(response_time)
        
        if success:
            metrics.successful_calls += 1
        else:
            metrics.failed_calls += 1
            metrics.last_error = error
            metrics.last_error_time = datetime.now()
            
        # Keep only last 1000 response times
        if len(metrics.response_times) > 1000:
            metrics.response_times = metrics.response_times[-1000:]
            
    def record_cache_operation(
        self,
        operation: str,
        success: bool
    ):
        """Record cache operation metrics"""
        status = 'success' if success else 'failure'
        self.cache_ops.labels(
            operation=operation,
            status=status
        ).inc()
        
    def record_rate_limit(self, api_name: str):
        """Record rate limit hit"""
        self.rate_limits.labels(
            api_name=api_name
        ).inc()
        
        if api_name in self.api_metrics:
            self.api_metrics[api_name].rate_limit_hits += 1
            
    def record_retry(self, api_name: str):
        """Record retry attempt"""
        self.retry_attempts.labels(
            api_name=api_name
        ).inc()
        
        if api_name in self.api_metrics:
            self.api_metrics[api_name].retry_count += 1
            
    def get_api_stats(self, api_name: str) -> Dict[str, Any]:
        """Get detailed stats for an API"""
        if api_name not in self.api_metrics:
            return {}
            
        metrics = self.api_metrics[api_name]
        response_times = metrics.response_times
        
        return {
            'total_calls': metrics.total_calls,
            'success_rate': (
                metrics.successful_calls / metrics.total_calls
                if metrics.total_calls > 0
                else 0
            ),
            'avg_response_time': (
                statistics.mean(response_times)
                if response_times
                else 0
            ),
            'p95_response_time': (
                statistics.quantiles(response_times, n=20)[18]
                if len(response_times) >= 20
                else None
            ),
            'rate_limit_hits': metrics.rate_limit_hits,
            'retry_count': metrics.retry_count,
            'last_error': metrics.last_error,
            'last_error_time': metrics.last_error_time
        }
        
    def get_health_check(self) -> Dict[str, Any]:
        """Get system health check"""
        health = {
            'status': 'healthy',
            'apis': {}
        }
        
        for api_name, metrics in self.api_metrics.items():
            # Check if API had recent errors
            recent_error = False
            if metrics.last_error_time:
                if datetime.now() - metrics.last_error_time < timedelta(minutes=5):
                    recent_error = True
                    
            # Calculate error rate
            error_rate = (
                metrics.failed_calls / metrics.total_calls
                if metrics.total_calls > 0
                else 0
            )
            
            # Calculate average response time
            avg_response_time = (
                statistics.mean(metrics.response_times)
                if metrics.response_times
                else 0
            )
            
            api_health = 'degraded' if any([
                recent_error,
                error_rate > 0.1,  # >10% error rate
                avg_response_time > 2.0,  # >2s average response
                metrics.rate_limit_hits > 10  # >10 rate limits
            ]) else 'healthy'
            
            health['apis'][api_name] = {
                'status': api_health,
                'error_rate': error_rate,
                'avg_response_time': avg_response_time,
                'rate_limit_hits': metrics.rate_limit_hits,
                'last_error': metrics.last_error,
                'last_error_time': metrics.last_error_time
            }
            
            if api_health == 'degraded':
                health['status'] = 'degraded'
                
        return health

class HealthMonitor:
    """Monitors system health and alerts on issues"""
    
    def __init__(
        self,
        metrics_collector: MetricsCollector,
        alert_threshold: float = 0.1,
        check_interval: int = 60
    ):
        self.metrics = metrics_collector
        self.alert_threshold = alert_threshold
        self.check_interval = check_interval
        self.running = False
        self._task: Optional[asyncio.Task] = None
        
    async def start(self):
        """Start health monitoring"""
        if not self.running:
            self.running = True
            self._task = asyncio.create_task(self._monitor_health())
            
    async def stop(self):
        """Stop health monitoring"""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
                
    async def _monitor_health(self):
        """Monitor system health and alert on issues"""
        while self.running:
            try:
                health = self.metrics.get_health_check()
                
                if health['status'] == 'degraded':
                    # Log degraded APIs
                    for api_name, api_health in health['apis'].items():
                        if api_health['status'] == 'degraded':
                            logger.warning(
                                f"{api_name} API health degraded: "
                                f"Error rate: {api_health['error_rate']:.2%}, "
                                f"Avg response time: {api_health['avg_response_time']:.2f}s"
                            )
                            
                            # Add additional alerting here (e.g., Telegram, Discord)
                            
            except Exception as e:
                logger.error(f"Health monitor error: {e}")
                
            await asyncio.sleep(self.check_interval)
