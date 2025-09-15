"""
Tests for API key monitoring system
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, timedelta
import os
from monitor.key_monitor import KeyMonitor, KeyStatus
from handlers.key_management import KeyManager, APIKey

@pytest.fixture
def mock_key_manager():
    """Mock key manager"""
    return Mock(spec=KeyManager)

@pytest.fixture
def mock_telegram_bot():
    """Mock Telegram bot"""
    return AsyncMock()

@pytest.fixture
def key_monitor(mock_key_manager):
    """Create key monitor with mocked dependencies"""
    with patch('monitor.key_monitor.Bot') as mock_bot:
        mock_bot.return_value = AsyncMock()
        monitor = KeyMonitor(mock_key_manager)
        return monitor

def create_mock_key(is_available: bool, cooldown_time: Optional[datetime] = None) -> Mock:
    """Create a mock API key"""
    key = Mock(spec=APIKey)
    key.is_available.return_value = is_available
    key.cooldown_until = cooldown_time
    return key

async def test_service_status_calculation(key_monitor, mock_key_manager):
    """Test service status calculation"""
    service = "test_api"
    now = datetime.now()
    future = now + timedelta(minutes=30)
    
    # Create mock keys
    keys = [
        create_mock_key(True),  # Available
        create_mock_key(False, future),  # In cooldown
        create_mock_key(False, None)  # Exhausted
    ]
    
    mock_key_manager.get_service_keys.return_value = keys
    
    status = await key_monitor.get_service_status(service)
    
    assert isinstance(status, KeyStatus)
    assert status.service == service
    assert status.total_keys == 3
    assert status.available_keys == 1
    assert status.cooldown_keys == 1
    assert status.exhausted_keys == 1
    assert status.next_available == future

async def test_alert_generation(key_monitor, mock_key_manager):
    """Test alert generation logic"""
    service = "test_api"
    now = datetime.now()
    
    # Create mostly exhausted key set
    keys = [
        create_mock_key(False, now + timedelta(minutes=30)),  # Cooldown
        create_mock_key(False, now + timedelta(minutes=60)),  # Cooldown
        create_mock_key(False, None),  # Exhausted
        create_mock_key(True)  # Single available key
    ]
    
    mock_key_manager.get_service_keys.return_value = keys
    mock_key_manager.list_services.return_value = [service]
    
    # Should trigger alert (only 25% keys available)
    await key_monitor._check_all_services()
    
    # Verify alert was sent
    assert key_monitor.telegram_bot.send_message.called
    call_args = key_monitor.telegram_bot.send_message.call_args[1]
    assert "Low API key availability" in call_args['text']
    assert "1/4" in call_args['text']

async def test_exhaustion_alert(key_monitor, mock_key_manager):
    """Test complete exhaustion alert"""
    service = "test_api"
    now = datetime.now()
    
    # All keys exhausted or in cooldown
    keys = [
        create_mock_key(False, now + timedelta(minutes=30)),
        create_mock_key(False, now + timedelta(minutes=45)),
        create_mock_key(False, None)
    ]
    
    mock_key_manager.get_service_keys.return_value = keys
    mock_key_manager.list_services.return_value = [service]
    
    await key_monitor._check_all_services()
    
    # Verify critical alert was sent
    assert key_monitor.telegram_bot.send_message.called
    call_args = key_monitor.telegram_bot.send_message.call_args[1]
    assert "CRITICAL: All API keys exhausted" in call_args['text']
    assert "Remediation steps" in call_args['text']

async def test_alert_cooldown(key_monitor, mock_key_manager):
    """Test alert cooldown period"""
    service = "test_api"
    
    # Create low availability situation
    keys = [create_mock_key(False)] * 4 + [create_mock_key(True)]
    mock_key_manager.get_service_keys.return_value = keys
    mock_key_manager.list_services.return_value = [service]
    
    # First alert
    await key_monitor._check_all_services()
    assert key_monitor.telegram_bot.send_message.called
    
    # Reset mock
    key_monitor.telegram_bot.send_message.reset_mock()
    
    # Immediate second check
    await key_monitor._check_all_services()
    
    # Should not alert again (cooldown)
    assert not key_monitor.telegram_bot.send_message.called

async def test_rotation_status(key_monitor, mock_key_manager):
    """Test key rotation status report"""
    services = ["api1", "api2"]
    mock_key_manager.list_services.return_value = services
    
    # Setup different states for each service
    service_keys = {
        "api1": [
            create_mock_key(True),
            create_mock_key(True),
            create_mock_key(False, None)
        ],
        "api2": [
            create_mock_key(False, datetime.now() + timedelta(minutes=30)),
            create_mock_key(False, None)
        ]
    }
    
    def get_service_keys(service):
        return service_keys[service]
    
    mock_key_manager.get_service_keys.side_effect = get_service_keys
    
    status = await key_monitor.get_rotation_status()
    
    assert len(status) == 2
    
    # Check api1 status
    assert status["api1"]["total"] == 3
    assert status["api1"]["available"] == 2
    assert status["api1"]["exhausted"] == 1
    assert float(status["api1"]["health"].rstrip("%")) > 60
    
    # Check api2 status
    assert status["api2"]["total"] == 2
    assert status["api2"]["available"] == 0
    assert status["api2"]["cooldown"] == 1
    assert status["api2"]["exhausted"] == 1
    assert float(status["api2"]["health"].rstrip("%")) == 0

async def test_metrics_recording(key_monitor, mock_key_manager):
    """Test metrics recording for key status"""
    service = "test_api"
    mock_key_manager.list_services.return_value = [service]
    
    keys = [
        create_mock_key(True),
        create_mock_key(True),
        create_mock_key(False)
    ]
    mock_key_manager.get_service_keys.return_value = keys
    
    with patch('monitor.key_monitor.metrics_manager') as mock_metrics:
        await key_monitor._check_all_services()
        
        # Verify metrics were recorded
        mock_metrics.record_api_key_status.assert_called_with(
            service,
            available_keys=2,
            total_keys=3
        )

async def test_empty_service(key_monitor, mock_key_manager):
    """Test handling of service with no keys"""
    service = "empty_api"
    mock_key_manager.get_service_keys.return_value = []
    
    status = await key_monitor.get_service_status(service)
    
    assert status.total_keys == 0
    assert status.available_keys == 0
    assert status.cooldown_keys == 0
    assert status.exhausted_keys == 0
    assert status.next_available is None

@pytest.mark.parametrize("available,total,should_alert", [
    (2, 10, True),   # 20% - should alert
    (3, 10, False),  # 30% - should not alert
    (1, 10, True),   # 10% - should alert
    (0, 10, True),   # 0% - should alert (exhaustion)
])
async def test_alert_thresholds(key_monitor, mock_key_manager, available, total, should_alert):
    """Test alert threshold behavior"""
    service = "test_api"
    
    # Create keys with specified availability
    keys = (
        [create_mock_key(True)] * available +
        [create_mock_key(False)] * (total - available)
    )
    
    mock_key_manager.get_service_keys.return_value = keys
    mock_key_manager.list_services.return_value = [service]
    
    # Reset alert cooldown
    key_monitor.last_alerts = {}
    
    await key_monitor._check_all_services()
    
    if should_alert:
        assert key_monitor.telegram_bot.send_message.called
    else:
        assert not key_monitor.telegram_bot.send_message.called
