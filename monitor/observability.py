"""
Core observability module for Meme Trader V4 Pro
Handles logging, monitoring, metrics, and alerting
"""
import logging
import time
import json
from typing import Any, Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field
import asyncio
from contextlib import contextmanager
import structlog
from prometheus_client import Counter, Gauge, Histogram
import psutil
import redis

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.BoundLogger,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Metrics
SCAN_TIME = Histogram(
    'memetrader_scan_duration_seconds',
    'Time spent scanning for opportunities'
)

ALERT_LATENCY = Histogram(
    'memetrader_alert_latency_seconds',
    'Time between event detection and alert delivery'
)

TRADE_DURATION = Histogram(
    'memetrader_trade_duration_seconds',
    'Time to execute a trade',
    ['chain', 'type']
)

API_HEALTH = Gauge(
    'memetrader_api_health',
    'API health status (1=healthy, 0=unhealthy)',
    ['api_name']
)

ERROR_COUNT = Counter(
    'memetrader_errors_total',
    'Total error count by type',
    ['module', 'error_type']
)

@dataclass
class HealthStatus:
    """Health check status for a component"""
    name: str
    status: str  # healthy, degraded, failed
    details: Dict[str, Any]
    last_check: datetime
    error: Optional[str] = None

@dataclass
class ModuleMetrics:
    """Performance metrics for a module"""
    module_name: str
    start_time: datetime
    operation_times: List[float] = field(default_factory=list)
    error_count: int = 0
    success_count: int = 0
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None

class ObservabilityManager:
    """Central manager for all observability features"""
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        metrics_ttl: int = 86400  # 24 hours
    ):
        self.redis = redis.Redis.from_url(
            redis_url,
            decode_responses=True
        )
        self.metrics_ttl = metrics_ttl
        self.module_metrics: Dict[str, ModuleMetrics] = {}
        self.health_checks: Dict[str, HealthStatus] = {}
        
    def log_action(
        self,
        action: str,
        module: str,
        status: str,
        **kwargs
    ):
        """Log an action with structured data"""
        # Remove sensitive data
        safe_kwargs = self._sanitize_data(kwargs)
        
        # Add standard fields
        log_data = {
            'action': action,
            'module': module,
            'status': status,
            'timestamp': datetime.utcnow().isoformat(),
            **safe_kwargs
        }
        
        logger.info(action, **log_data)
        
    def _sanitize_data(
        self,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Remove sensitive data before logging"""
        sensitive_keys = {
            'mnemonic', 'private_key', 'api_key', 'secret',
            'password', 'token', 'auth', 'key'
        }
        
        return {
            k: '[REDACTED]' if any(s in k.lower() for s in sensitive_keys)
            else v for k, v in data.items()
        }
        
    @contextmanager
    def measure_operation(
        self,
        module_name: str,
        operation: str
    ):
        """Measure operation duration"""
        start_time = time.time()
        try:
            yield
            duration = time.time() - start_time
            
            # Update module metrics
            if module_name not in self.module_metrics:
                self.module_metrics[module_name] = ModuleMetrics(
                    module_name=module_name,
                    start_time=datetime.utcnow()
                )
            
            metrics = self.module_metrics[module_name]
            metrics.operation_times.append(duration)
            metrics.success_count += 1
            
            # Store in Redis for persistence
            self.redis.lpush(
                f"metrics:{module_name}:times",
                duration
            )
            self.redis.expire(
                f"metrics:{module_name}:times",
                self.metrics_ttl
            )
            
            # Update Prometheus metrics
            if operation == 'scan':
                SCAN_TIME.observe(duration)
            elif operation == 'alert':
                ALERT_LATENCY.observe(duration)
            elif operation == 'trade':
                TRADE_DURATION.labels(
                    chain='unknown',
                    type='unknown'
                ).observe(duration)
                
        except Exception as e:
            duration = time.time() - start_time
            if module_name in self.module_metrics:
                metrics = self.module_metrics[module_name]
                metrics.error_count += 1
                metrics.last_error = str(e)
                metrics.last_error_time = datetime.utcnow()
            
            ERROR_COUNT.labels(
                module=module_name,
                error_type=type(e).__name__
            ).inc()
            
            raise
            
    async def update_health_check(
        self,
        component: str,
        check_fn: callable
    ):
        """Update health status for a component"""
        try:
            details = await check_fn()
            status = 'healthy'
            error = None
        except Exception as e:
            details = {}
            status = 'failed'
            error = str(e)
            
        self.health_checks[component] = HealthStatus(
            name=component,
            status=status,
            details=details,
            last_check=datetime.utcnow(),
            error=error
        )
        
        # Update Prometheus metric
        API_HEALTH.labels(
            api_name=component
        ).set(1 if status == 'healthy' else 0)
        
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get system-level metrics"""
        return {
            'cpu_percent': psutil.cpu_percent(),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_usage': psutil.disk_usage('/').percent,
            'open_files': len(psutil.Process().open_files()),
            'connections': len(psutil.Process().connections())
        }
        
    def get_module_metrics(
        self,
        module_name: str
    ) -> Dict[str, Any]:
        """Get metrics for a specific module"""
        if module_name not in self.module_metrics:
            return {}
            
        metrics = self.module_metrics[module_name]
        times = metrics.operation_times[-100:]  # Last 100 operations
        
        return {
            'uptime': (
                datetime.utcnow() - metrics.start_time
            ).total_seconds(),
            'success_rate': (
                metrics.success_count /
                (metrics.success_count + metrics.error_count)
                if (metrics.success_count + metrics.error_count) > 0
                else 0
            ),
            'avg_operation_time': (
                sum(times) / len(times)
                if times else 0
            ),
            'error_count': metrics.error_count,
            'last_error': metrics.last_error,
            'last_error_time': (
                metrics.last_error_time.isoformat()
                if metrics.last_error_time
                else None
            )
        }
        
    def get_health_status(self) -> Dict[str, Any]:
        """Get overall health status"""
        status = {
            'overall': 'healthy',
            'components': {},
            'system': self.get_system_metrics(),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        for component, health in self.health_checks.items():
            status['components'][component] = {
                'status': health.status,
                'details': health.details,
                'last_check': health.last_check.isoformat(),
                'error': health.error
            }
            
            if health.status != 'healthy':
                status['overall'] = 'degraded'
                
        return status
        
    async def run_all_health_checks(self):
        """Run all registered health checks"""
        tasks = []
        for component, check_fn in self.health_checks.items():
            tasks.append(
                self.update_health_check(component, check_fn)
            )
        await asyncio.gather(*tasks)
        
    def format_diagnostics(self) -> str:
        """Format diagnostics for admin command"""
        health = self.get_health_status()
        
        # Build message
        lines = [
            "🔍 System Diagnostics",
            "===================",
            f"Overall Status: {'✅' if health['overall'] == 'healthy' else '⚠️'} {health['overall'].upper()}",
            "",
            "System Metrics:",
            f"- CPU: {health['system']['cpu_percent']}%",
            f"- Memory: {health['system']['memory_percent']}%",
            f"- Disk: {health['system']['disk_usage']}%",
            "",
            "Component Status:"
        ]
        
        for name, component in health['components'].items():
            status_icon = '✅' if component['status'] == 'healthy' else '⚠️'
            lines.append(f"{status_icon} {name}: {component['status']}")
            if component['error']:
                lines.append(f"   Error: {component['error']}")
                
        lines.extend([
            "",
            "Module Performance:",
        ])
        
        for module_name in self.module_metrics:
            metrics = self.get_module_metrics(module_name)
            lines.extend([
                f"📊 {module_name}:",
                f"- Success Rate: {metrics['success_rate']:.1%}",
                f"- Avg Time: {metrics['avg_operation_time']:.2f}s",
                f"- Errors: {metrics['error_count']}"
            ])
            
        return "\n".join(lines)
        
    async def monitor_health(
        self,
        check_interval: int = 60
    ):
        """Continuous health monitoring"""
        while True:
            try:
                await self.run_all_health_checks()
                
                # Check for degraded status
                health = self.get_health_status()
                if health['overall'] != 'healthy':
                    self.log_action(
                        'system_health_degraded',
                        'monitor',
                        'warning',
                        health=health
                    )
                    
            except Exception as e:
                logger.error(
                    "Health monitor error",
                    error=str(e)
                )
                
            await asyncio.sleep(check_interval)
