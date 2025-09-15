"""
Test suite for metrics collection and monitoring
"""

import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import Mock
from monitor.metrics import metrics_manager, APIMetrics, AlertMetrics, TradeMetrics

@pytest.fixture
def reset_metrics():
    """Reset metrics before each test"""
    metrics_manager.api_metrics.clear()
    metrics_manager.alert_metrics = AlertMetrics()
    metrics_manager.trade_metrics = TradeMetrics()
    metrics_manager.start_time = datetime.now()
    metrics_manager.time_series = {
        'api_calls': {},
        'alerts': [],
        'trades': []
    }
    yield

def test_api_metrics(reset_metrics):
    """Test API metrics collection"""
    # Record successful call
    metrics_manager.record_api_call(
        service="test_api",
        success=True,
        latency=0.5
    )
    
    # Record failed call
    metrics_manager.record_api_call(
        service="test_api",
        success=False,
        latency=1.0,
        error="Test error"
    )
    
    # Get metrics
    metrics = metrics_manager.api_metrics["test_api"]
    
    assert metrics.total_calls == 2
    assert metrics.successful_calls == 1
    assert metrics.failed_calls == 1
    assert metrics.total_latency == 1.5
    assert metrics.last_error == "Test error"

def test_alert_metrics(reset_metrics):
    """Test alert metrics collection"""
    # Record successful alert
    metrics_manager.record_alert(success=True, latency=0.1)
    
    # Record failed alert
    metrics_manager.record_alert(success=False, latency=0.2)
    
    # Record consensus
    metrics_manager.record_consensus()
    
    # Record duplicate prevention
    metrics_manager.record_duplicate_prevented()
    
    metrics = metrics_manager.alert_metrics
    
    assert metrics.total_alerts == 2
    assert metrics.successful_sends == 1
    assert metrics.failed_sends == 1
    assert 0.1 <= metrics.avg_latency <= 0.2
    assert metrics.consensus_alerts == 1
    assert metrics.duplicate_prevented == 1

def test_trade_metrics(reset_metrics):
    """Test trade metrics collection"""
    # Record successful buy
    metrics_manager.record_trade(
        success=True,
        trade_type="buy",
        execution_time=2.0,
        slippage=0.01
    )
    
    # Record successful sell
    metrics_manager.record_trade(
        success=True,
        trade_type="sell",
        execution_time=1.5,
        slippage=0.005
    )
    
    # Record failed trade
    metrics_manager.record_trade(
        success=False,
        trade_type="buy",
        execution_time=3.0
    )
    
    metrics = metrics_manager.trade_metrics
    
    assert metrics.total_trades == 3
    assert metrics.successful_buys == 1
    assert metrics.successful_sells == 1
    assert metrics.failed_trades == 1
    assert 1.5 <= metrics.avg_execution_time <= 3.0
    assert metrics.slippage_total == 0.015

def test_time_series_data(reset_metrics):
    """Test time series data collection"""
    # Add API calls over time
    for i in range(3):
        metrics_manager.record_api_call(
            service="test_api",
            success=True,
            latency=0.1 * i
        )
        time.sleep(0.1)
    
    # Add alerts
    for i in range(2):
        metrics_manager.record_alert(
            success=True,
            latency=0.2 * i
        )
        time.sleep(0.1)
    
    # Add trades
    for i in range(2):
        metrics_manager.record_trade(
            success=True,
            trade_type="buy",
            execution_time=1.0 * i
        )
        time.sleep(0.1)
    
    # Check time series data
    assert len(metrics_manager.time_series['api_calls']['test_api']) == 3
    assert len(metrics_manager.time_series['alerts']) == 2
    assert len(metrics_manager.time_series['trades']) == 2

def test_data_cleanup(reset_metrics):
    """Test old data cleanup"""
    # Add old data
    old_time = datetime.now() - timedelta(hours=25)
    
    # Old API call
    metrics_manager.time_series['api_calls']['test_api'] = [
        {'timestamp': old_time, 'success': True, 'latency': 0.1}
    ]
    
    # Old alert
    metrics_manager.time_series['alerts'] = [
        {'timestamp': old_time, 'success': True, 'latency': 0.1}
    ]
    
    # Old trade
    metrics_manager.time_series['trades'] = [
        {'timestamp': old_time, 'success': True, 'execution_time': 1.0}
    ]
    
    # Add new data
    metrics_manager.record_api_call("test_api", True, 0.1)
    metrics_manager.record_alert(True, 0.1)
    metrics_manager.record_trade(True, "buy", 1.0)
    
    # Clean old data
    metrics_manager._clean_time_series()
    
    # Check only new data remains
    assert len(metrics_manager.time_series['api_calls']['test_api']) == 1
    assert len(metrics_manager.time_series['alerts']) == 1
    assert len(metrics_manager.time_series['trades']) == 1

def test_threshold_monitoring(reset_metrics):
    """Test threshold monitoring"""
    # Override thresholds for testing
    metrics_manager.thresholds.update({
        'api_error_rate': 0.2,  # 20% error rate threshold
        'alert_latency': 1.0,   # 1 second alert latency threshold
        'trade_latency': 2.0    # 2 second trade latency threshold
    })
    
    # Create high error rate
    for _ in range(8):
        metrics_manager.record_api_call("test_api", True, 0.1)
    for _ in range(2):
        metrics_manager.record_api_call("test_api", False, 0.1, "Error")
    
    # Add slow alert
    metrics_manager.record_alert(True, 1.5)  # Above threshold
    
    # Add slow trade
    metrics_manager.record_trade(True, "buy", 2.5)  # Above threshold
    
    # Check metrics
    api_health = metrics_manager.get_api_health("test_api")
    assert api_health['error_rate'] == 0.2  # At threshold
    
    alert_health = metrics_manager.get_alert_health()
    assert alert_health['avg_latency'] > metrics_manager.thresholds['alert_latency']
    
    trade_health = metrics_manager.get_trade_health()
    assert trade_health['avg_execution_time'] > metrics_manager.thresholds['trade_latency']

def test_api_rate_limit_metrics(reset_metrics):
    """Test API rate limit and quota metrics"""
    # Record rate limit hits
    metrics_manager.record_api_call(
        service="test_api",
        success=False,
        latency=0.1,
        error="Rate limit exceeded"
    )
    metrics_manager.record_api_call(
        service="test_api",
        success=False,
        latency=0.1,
        error="Rate limit hit"
    )
    
    # Record quota exceeded
    metrics_manager.record_api_call(
        service="test_api",
        success=False,
        latency=0.1,
        error="Quota exceeded for today"
    )
    
    metrics = metrics_manager.api_metrics["test_api"]
    assert metrics.rate_limits_hit == 2
    assert metrics.quota_exceeded == 1
    assert metrics.total_calls == 3
    assert metrics.failed_calls == 3
    
def test_preflight_blocks(reset_metrics):
    """Test trade preflight blocks"""
    # Record different preflight blocks
    metrics_manager.record_preflight_block("insufficient_funds")
    metrics_manager.record_preflight_block("high_slippage")
    metrics_manager.record_preflight_block("market_closed")
    
    metrics = metrics_manager.trade_metrics
    assert metrics.preflight_blocks == 3
    
def test_system_summary(reset_metrics):
    """Test system summary metrics"""
    # Add API calls
    metrics_manager.record_api_call("api1", True, 0.1)
    metrics_manager.record_api_call("api2", True, 0.2)
    metrics_manager.record_api_call("api2", False, 0.3, "Error")
    
    # Add alerts
    metrics_manager.record_alert(True, 0.1)
    metrics_manager.record_alert(False, 0.2)
    
    # Add trades
    metrics_manager.record_trade(True, "buy", 1.0)
    metrics_manager.record_trade(True, "sell", 1.5)
    
    # Get summary
    summary = metrics_manager.get_system_summary()
    
    assert isinstance(summary['uptime'], str)
    assert summary['total_alerts'] == 2
    assert summary['total_trades'] == 2
    assert len(summary['api_calls']) == 2
    assert summary['api_calls']['api1'] == 1
    assert summary['api_calls']['api2'] == 2
    
def test_alert_moving_average(reset_metrics):
    """Test alert latency moving average calculation"""
    # Record series of alerts with increasing latency
    latencies = [0.1, 0.2, 0.3, 0.4, 0.5]
    for latency in latencies:
        metrics_manager.record_alert(True, latency)
        
    # Get latest metrics
    alert_health = metrics_manager.get_alert_health()
    
    # Verify moving average calculation
    # The moving average should be weighted towards more recent values
    assert alert_health['avg_latency'] > statistics.mean(latencies[:-2])  # Should be weighted towards recent values
    assert alert_health['avg_latency'] < latencies[-1]  # But not as high as the latest value

def test_trade_execution_time_tracking(reset_metrics):
    """Test trade execution time tracking"""
    # Record trades with varying execution times
    metrics_manager.record_trade(True, "buy", 1.0, 0.01)  # Fast trade
    metrics_manager.record_trade(True, "buy", 3.0, 0.02)  # Slow trade
    metrics_manager.record_trade(True, "sell", 1.5, 0.01)  # Medium trade
    
    # Get trade health
    trade_health = metrics_manager.get_trade_health()
    
    # Check execution time metrics
    assert 1.0 < trade_health['avg_execution_time'] < 3.0  # Should be somewhere in between
    assert abs(trade_health['avg_slippage'] - 0.013) < 0.001  # Average slippage should be close to 0.013
