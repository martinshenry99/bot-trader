"""
Test suite for user settings CRUD in Meme Trader V4 Pro
"""
import pytest
from db.models import get_db_manager

def test_user_settings_crud():
    db = get_db_manager()
    user_id = 12345
    key = "test_setting"
    value = "test_value"
    # Set user setting
    assert db.set_user_setting(user_id, key, value)
    # Get user setting
    assert db.get_user_setting(user_id, key) == value
    # Update user setting
    new_value = "new_value"
    assert db.set_user_setting(user_id, key, new_value)
    assert db.get_user_setting(user_id, key) == new_value
    # Delete user setting
    assert db.set_user_setting(user_id, key, "")
    assert db.get_user_setting(user_id, key) == ""
