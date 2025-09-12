"""
Test suite for portfolio summary in Meme Trader V4 Pro
"""
import pytest
from core.trading_engine import trading_engine
import asyncio

@pytest.mark.asyncio
async def test_portfolio_summary():
    user_id = "test_user"
    result = await trading_engine.get_portfolio_summary(user_id)
    assert "portfolio_value_usd" in result
    assert "positions" in result
    assert isinstance(result["positions"], list)
