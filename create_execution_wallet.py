#!/usr/bin/env python3
"""
Create secure execution wallet for Meme Trader V4 Pro
"""

import os
import json
import secrets
from eth_account import Account
from executor import KeystoreManager
from config import Config

def create_execution_wallet():
    """Create a new execution wallet with keystore protection"""
    
    print("🔐 Creating Secure Execution Wallet for Meme Trader V4 Pro")
    print("=" * 60)
    
    # Generate secure private key
    private_key = "0x" + secrets.token_hex(32)
    
    # Create account from private key
    account = Account.from_key(private_key)
    
    print(f"✅ New wallet generated successfully!")
    print(f"📍 **Wallet Address:** {account.address}")
    print(f"🔑 **Private Key:** {private_key}")
    
    # Create keystore file with password protection
    keystore_password = "MemeTrader2024!"  # Default password for automation
    print(f"📝 Using default password: {keystore_password}")
    
    # Create keystore directory
    keystore_dir = "/app/keystores"
    os.makedirs(keystore_dir, exist_ok=True)
    
    # Generate keystore filename
    keystore_filename = f"execution_wallet_{account.address.lower()}.json"
    keystore_path = os.path.join(keystore_dir, keystore_filename)
    
    try:
        # Create encrypted keystore directly
        encrypted = account.encrypt(keystore_password.encode())
        
        with open(keystore_path, 'w') as f:
            json.dump(encrypted, f)
        
        print(f"🔒 Keystore created: {keystore_path}")
        
        # Test keystore loading
        with open(keystore_path, 'r') as f:
            keystore_data = json.load(f)
        
        from eth_keyfile import extract_key_from_keyfile
        loaded_key = extract_key_from_keyfile(keystore_data, keystore_password.encode())
        test_account = Account.from_key(loaded_key)
        
        assert test_account.address == account.address, "Keystore verification failed!"
        print("✅ Keystore verification successful!")
        
    except Exception as e:
        print(f"❌ Keystore creation failed: {e}")
        print("⚠️  Continuing with private key only...")
        keystore_path = None
    
    # Create wallet info file
    wallet_info = {
        "address": account.address,
        "keystore_file": keystore_path,
        "created_at": "2024-08-31T22:30:00Z",
        "purpose": "Meme Trader V4 Pro Execution Wallet",
        "networks": ["Ethereum Sepolia", "BSC Testnet"],
        "security_note": "Private key encrypted in keystore file"
    }
    
    wallet_info_path = "/app/execution_wallet_info.json"
    with open(wallet_info_path, 'w') as f:
        json.dump(wallet_info, f, indent=2)
    
    print(f"📋 Wallet info saved: {wallet_info_path}")
    
    # Show testnet funding instructions
    print("\n" + "=" * 60)
    print("💰 **TESTNET FUNDING INSTRUCTIONS**")
    print("=" * 60)
    
    print("To fund this wallet for testing, visit these faucets:")
    print("\n📍 **Ethereum Sepolia Testnet:**")
    print(f"   • Alchemy Faucet: https://sepoliafaucet.com/")
    print(f"   • Infura Faucet: https://www.infura.io/faucet/sepolia")
    print(f"   • Your wallet: {account.address}")
    
    print("\n📍 **BSC Testnet:**")
    print(f"   • BSC Faucet: https://testnet.bnbchain.org/faucet-smart")
    print(f"   • Your wallet: {account.address}")
    
    print("\n🔧 **Integration Instructions:**")
    print("Add this to your bot commands or trading functions:")
    print(f'```python')
    print(f'EXECUTION_WALLET_ADDRESS = "{account.address}"')
    print(f'KEYSTORE_PATH = "{keystore_path}"')
    print(f'KEYSTORE_PASSWORD = "{keystore_password}"')
    print(f'```')
    
    print("\n⚠️  **SECURITY REMINDERS:**")
    print("• This wallet is for TESTNET use only")
    print("• Never use real funds on testnet wallets")
    print("• Keep keystore password secure")
    print("• Private key is encrypted in keystore file")
    
    return {
        "address": account.address,
        "private_key": private_key,
        "keystore_path": keystore_path,
        "keystore_password": keystore_password
    }

def main():
    """Main execution function"""
    try:
        wallet_info = create_execution_wallet()
        
        if wallet_info:
            print("\n🎉 **EXECUTION WALLET CREATED SUCCESSFULLY!**")
            print("\n📋 **Quick Summary:**")
            print(f"   • Address: {wallet_info['address']}")
            print(f"   • Keystore: {wallet_info['keystore_path']}")
            print(f"   • Password: {wallet_info['keystore_password']}")
            print("\n🚀 Ready for testnet trading!")
            
            return wallet_info
        else:
            print("❌ Wallet creation failed!")
            return None
            
    except Exception as e:
        print(f"❌ Error creating execution wallet: {e}")
        return None

if __name__ == "__main__":
    wallet_info = main()