#!/usr/bin/env python3
"""
Secure Wallet Import Script for Meme Trader V4 Pro
Safely imports mnemonic without exposing it in logs or chat
"""

import getpass
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.secure_wallet import get_secure_wallet

def main():
    """Main import function"""
    print("🔐 Secure Wallet Import")
    print("=" * 40)
    print()
    print("⚠️  SECURITY WARNING:")
    print("   Never share your mnemonic with anyone!")
    print("   This script will encrypt and store it securely.")
    print()
    
    # Get mnemonic securely
    print("Enter your 12-word mnemonic phrase:")
    print("(Words will be hidden as you type)")
    mnemonic = getpass.getpass("Mnemonic: ").strip()
    
    if not mnemonic:
        print("❌ No mnemonic provided. Exiting.")
        return
    
    # Validate mnemonic format
    words = mnemonic.split()
    if len(words) != 12:
        print(f"❌ Invalid mnemonic: Expected 12 words, got {len(words)}")
        return
    
    # Get password for encryption
    print()
    print("Enter a password to encrypt your wallet:")
    password = getpass.getpass("Password: ")
    
    if not password:
        print("❌ No password provided. Exiting.")
        return
    
    # Confirm password
    password_confirm = getpass.getpass("Confirm password: ")
    
    if password != password_confirm:
        print("❌ Passwords don't match. Exiting.")
        return
    
    print()
    print("🔄 Importing wallet...")
    
    # Import wallet
    secure_wallet = get_secure_wallet()
    result = secure_wallet.import_wallet(mnemonic, password)
    
    if result['success']:
        print("✅ Wallet imported successfully!")
        print()
        print("📋 Your wallet addresses:")
        for chain, address in result['addresses'].items():
            print(f"   {chain.upper()}: {address}")
        print()
        print("🔒 Your mnemonic has been encrypted and stored securely.")
        print("   You can now use the bot's trading commands.")
    else:
        print(f"❌ Import failed: {result['error']}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n❌ Import cancelled by user.")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)