"""
System-wide metrics collection and monitoring
"""

import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from collections import defaultdict

logger = logging.getLogger(__name__)

@dataclass
class APIMetrics:
    """API performance metrics"""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_latency: float = 0.0
    rate_limits_hit: int = 0
    quota_exceeded: int = 0
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None

@dataclass
class AlertMetrics:
    """Alert system metrics"""
    total_alerts: int = 0
    successful_sends: int = 0
    failed_sends: int = 0
    avg_latency: float = 0.0
    consensus_alerts: int = 0
    duplicate_prevented: int = 0

@dataclass
class TradeMetrics:
    """Trading system metrics"""
    total_trades: int = 0
    successful_buys: int = 0
    successful_sells: int = 0
    failed_trades: int = 0
    avg_execution_time: float = 0.0
    slippage_total: float = 0.0
    preflight_blocks: int = 0

class MetricsManager:
    """Central metrics collection and monitoring"""
    
    def __init__(self):
        self.api_metrics: Dict[str, APIMetrics] = defaultdict(APIMetrics)
        self.alert_metrics = AlertMetrics()
        self.trade_metrics = TradeMetrics()
        self.start_time = datetime.now()
        
        # Time-series data (last 24h in 5-min buckets)
        self.time_series = {
            'api_calls': defaultdict(list),
            'alerts': [],
            'trades': []
        }
        
        # Performance thresholds
        self.thresholds = {
            'api_error_rate': 0.1,  # 10% error rate
            'alert_latency': 2.0,   # 2 seconds
            'trade_latency': 5.0    # 5 seconds
        }
    
    def record_api_call(self, service: str, success: bool, latency: float, error: Optional[str] = None):
        """Record API call metrics"""
        metrics = self.api_metrics[service]
        metrics.total_calls += 1
        
        if success:
            metrics.successful_calls += 1
        else:
            metrics.failed_calls += 1
            metrics.last_error = error
            metrics.last_error_time = datetime.now()
            
            if error and 'rate limit' in error.lower():
                metrics.rate_limits_hit += 1
            elif error and 'quota' in error.lower():
                metrics.quota_exceeded += 1
        
        metrics.total_latency += latency
        
        # Record time-series data
        self.time_series['api_calls'][service].append({
            'timestamp': datetime.now(),
            'success': success,
            'latency': latency
        })
        
        # Clean old time-series data
        self._clean_time_series()
        
        # Check thresholds
        self._check_api_thresholds(service)
    
    def record_alert(self, success: bool, latency: float):
        """Record alert metrics"""
        self.alert_metrics.total_alerts += 1
        
        if success:
            self.alert_metrics.successful_sends += 1
        else:
            self.alert_metrics.failed_sends += 1
            
        # Update moving average
        if self.alert_metrics.avg_latency == 0:
            self.alert_metrics.avg_latency = latency
        else:
            self.alert_metrics.avg_latency = (
                0.9 * self.alert_metrics.avg_latency + 
                0.1 * latency
            )
            
        # Record time-series
        self.time_series['alerts'].append({
            'timestamp': datetime.now(),
            'success': success,
            'latency': latency
        })
        
        # Check thresholds
        if latency > self.thresholds['alert_latency']:
            logger.warning(f"Alert latency ({latency:.2f}s) exceeded threshold")
    
    def record_trade(self, success: bool, trade_type: str, execution_time: float, slippage: Optional[float] = None):
        """Record trade metrics"""
        self.trade_metrics.total_trades += 1
        
        if success:
            if trade_type.lower() == 'buy':
                self.trade_metrics.successful_buys += 1
            else:
                self.trade_metrics.successful_sells += 1
        else:
            self.trade_metrics.failed_trades += 1
            
        # Update moving average execution time
        if self.trade_metrics.avg_execution_time == 0:
            self.trade_metrics.avg_execution_time = execution_time
        else:
            self.trade_metrics.avg_execution_time = (
                0.9 * self.trade_metrics.avg_execution_time +
                0.1 * execution_time
            )
            
        if slippage is not None:
            self.trade_metrics.slippage_total += slippage
            
        # Record time-series
        self.time_series['trades'].append({
            'timestamp': datetime.now(),
            'success': success,
            'type': trade_type,
            'execution_time': execution_time,
            'slippage': slippage
        })
        
        # Check thresholds
        if execution_time > self.thresholds['trade_latency']:
            logger.warning(f"Trade execution time ({execution_time:.2f}s) exceeded threshold")
    
    def record_preflight_block(self, reason: str):
        """Record trade blocked by preflight checks"""
        self.trade_metrics.preflight_blocks += 1
        logger.info(f"Trade blocked by preflight check: {reason}")
    
    def record_consensus(self):
        """Record consensus alert"""
        self.alert_metrics.consensus_alerts += 1
    
    def record_duplicate_prevented(self):
        """Record prevented duplicate alert"""
        self.alert_metrics.duplicate_prevented += 1
    
    def get_api_health(self, service: str) -> Dict[str, Any]:
        """Get health metrics for API service"""
        metrics = self.api_metrics[service]
        total = metrics.total_calls or 1  # Prevent div by zero
        
        return {
            'error_rate': metrics.failed_calls / total,
            'avg_latency': metrics.total_latency / total,
            'rate_limits': metrics.rate_limits_hit,
            'quota_exceeded': metrics.quota_exceeded,
            'last_error': metrics.last_error,
            'last_error_time': metrics.last_error_time
        }
    
    def get_alert_health(self) -> Dict[str, Any]:
        """Get alert system health metrics"""
        total = self.alert_metrics.total_alerts or 1
        
        return {
            'success_rate': self.alert_metrics.successful_sends / total,
            'avg_latency': self.alert_metrics.avg_latency,
            'consensus_alerts': self.alert_metrics.consensus_alerts,
            'duplicates_prevented': self.alert_metrics.duplicate_prevented
        }
    
    def get_trade_health(self) -> Dict[str, Any]:
        """Get trading system health metrics"""
        total = self.trade_metrics.total_trades or 1
        
        return {
            'success_rate': (self.trade_metrics.successful_buys + 
                           self.trade_metrics.successful_sells) / total,
            'avg_execution_time': self.trade_metrics.avg_execution_time,
            'avg_slippage': self.trade_metrics.slippage_total / total,
            'preflight_blocks': self.trade_metrics.preflight_blocks
        }
    
    def get_system_summary(self) -> Dict[str, Any]:
        """Get overall system health summary"""
        uptime = datetime.now() - self.start_time
        
        return {
            'uptime': str(uptime),
            'total_alerts': self.alert_metrics.total_alerts,
            'total_trades': self.trade_metrics.total_trades,
            'api_calls': {
                service: metrics.total_calls
                for service, metrics in self.api_metrics.items()
            }
        }
    
    def _clean_time_series(self):
        """Clean time series data older than 24h"""
        cutoff = datetime.now() - timedelta(hours=24)
        
        # Clean API calls
        for service in self.time_series['api_calls']:
            self.time_series['api_calls'][service] = [
                data for data in self.time_series['api_calls'][service]
                if data['timestamp'] > cutoff
            ]
            
        # Clean alerts
        self.time_series['alerts'] = [
            data for data in self.time_series['alerts']
            if data['timestamp'] > cutoff
        ]
        
        # Clean trades
        self.time_series['trades'] = [
            data for data in self.time_series['trades']
            if data['timestamp'] > cutoff
        ]
    
    def _check_api_thresholds(self, service: str):
        """Check API metrics against thresholds"""
        metrics = self.api_metrics[service]
        total = metrics.total_calls
        
        if total > 100:  # Only check after sufficient samples
            error_rate = metrics.failed_calls / total
            if error_rate > self.thresholds['api_error_rate']:
                logger.warning(
                    f"API {service} error rate ({error_rate:.1%}) "
                    f"exceeded threshold ({self.thresholds['api_error_rate']:.1%})"
                )

# Global metrics manager instance
metrics_manager = MetricsManager()
