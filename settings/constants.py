"""
Settings keys and default values for Meme Trader V4 Pro
"""

from enum import Enum
from typing import Any, Dict

class SettingKeys(Enum):
    """All available setting keys with their default values"""
    # Scan settings
    SCAN_MIN_SCORE = 'scan_min_score'
    SCAN_MAX_RESULTS = 'scan_max_results'
    SCAN_CHAINS = 'scan_chains'
    
    # Insider detection settings
    INSIDER_MIN_SCORE = 'insider_min_score'
    INSIDER_EARLY_WINDOW = 'insider_early_window_minutes'
    INSIDER_MIN_REPEAT = 'insider_min_repeat'

DEFAULT_SETTINGS: Dict[str, Any] = {
    # Scan defaults
    SettingKeys.SCAN_MIN_SCORE.value: 70,
    SettingKeys.SCAN_MAX_RESULTS.value: 50,
    SettingKeys.SCAN_CHAINS.value: 'eth,bsc,sol',
    
    # Insider defaults
    SettingKeys.INSIDER_MIN_SCORE.value: 70,
    SettingKeys.INSIDER_EARLY_WINDOW.value: 5,
    SettingKeys.INSIDER_MIN_REPEAT.value: 3
}

def validate_setting(key: str, value: str) -> bool:
    """Validate setting value based on key"""
    try:
        if key in [SettingKeys.SCAN_MIN_SCORE.value, SettingKeys.INSIDER_MIN_SCORE.value]:
            score = int(value)
            return 0 <= score <= 100
            
        elif key == SettingKeys.SCAN_MAX_RESULTS.value:
            results = int(value)
            return 1 <= results <= 200
            
        elif key == SettingKeys.SCAN_CHAINS.value:
            chains = value.lower().split(',')
            valid_chains = {'eth', 'bsc', 'sol'}
            return all(chain in valid_chains for chain in chains)
            
        elif key == SettingKeys.INSIDER_EARLY_WINDOW.value:
            minutes = int(value)
            return 1 <= minutes <= 60
            
        elif key == SettingKeys.INSIDER_MIN_REPEAT.value:
            repeats = int(value)
            return 1 <= repeats <= 10
            
        return False
        
    except ValueError:
        return False
