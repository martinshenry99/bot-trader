"""Tests for enhanced security features"""
import pytest
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime

from core.secure_wallet import SecureWallet

@pytest.fixture
def test_config_dir(tmp_path):
    return str(tmp_path / "test_config")

@pytest.fixture
def secure_wallet(test_config_dir):
    return SecureWallet(test_config_dir)

def test_init_encryption(secure_wallet, test_config_dir):
    """Test encryption initialization"""
    salt_file = Path(test_config_dir) / "salt"
    
    # Check salt file creation
    assert salt_file.exists()
    assert len(secure_wallet.salt) == 16

def test_generate_mnemonic(secure_wallet):
    """Test mnemonic generation"""
    name = "test_wallet"
    password = "test_password"
    
    mnemonic = secure_wallet.generate_mnemonic(name, password)
    
    # Check mnemonic format
    assert isinstance(mnemonic, str)
    assert len(mnemonic.split()) == 24  # BIP39 standard
    
    # Check storage
    wallets = secure_wallet._load_wallets(password)
    assert name in wallets
    assert 'encrypted_mnemonic' in wallets[name]
    assert 'created_at' in wallets[name]

def test_import_mnemonic(secure_wallet):
    """Test mnemonic import"""
    name = "imported_wallet"
    password = "test_password"
    test_mnemonic = "test abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"
    
    with pytest.raises(ValueError):
        # Should fail validation
        secure_wallet.import_mnemonic(name, test_mnemonic, password)

@patch('eth_account.Account.from_mnemonic')
def test_import_valid_mnemonic(mock_from_mnemonic, secure_wallet):
    """Test importing valid mnemonic"""
    name = "valid_wallet"
    password = "test_password"
    valid_mnemonic = "valid mnemonic phrase"
    
    mock_from_mnemonic.return_value = MagicMock()
    
    result = secure_wallet.import_mnemonic(name, valid_mnemonic, password)
    assert result is True
    
    wallets = secure_wallet._load_wallets(password)
    assert name in wallets

def test_export_mnemonic(secure_wallet):
    """Test mnemonic export"""
    name = "export_wallet"
    password = "test_password"
    
    # Generate wallet first
    original_mnemonic = secure_wallet.generate_mnemonic(name, password)
    
    # Export and verify
    exported_mnemonic = secure_wallet.export_mnemonic(name, password)
    assert exported_mnemonic == original_mnemonic

def test_delete_mnemonic(secure_wallet):
    """Test secure mnemonic deletion"""
    name = "delete_wallet"
    password = "test_password"
    
    # Create wallet first
    secure_wallet.generate_mnemonic(name, password)
    
    # Test invalid confirmation
    with pytest.raises(ValueError):
        secure_wallet.delete_mnemonic(name, password, "WRONG")
    
    # Test valid deletion
    assert secure_wallet.delete_mnemonic(name, password, f"DELETE {name}") is True
    
    # Verify deletion
    wallets = secure_wallet._load_wallets(password)
    assert name not in wallets

def test_get_addresses(secure_wallet):
    """Test address retrieval"""
    name = "address_wallet"
    password = "test_password"
    
    # Generate wallet first
    secure_wallet.generate_mnemonic(name, password)
    
    # Get addresses
    addresses = secure_wallet.get_addresses(password)
    assert name in addresses
    assert addresses[name].startswith("0x")
    assert len(addresses[name]) == 42  # Standard Ethereum address length
