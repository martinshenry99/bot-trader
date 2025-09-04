#!/usr/bin/env python3
"""
Create a test wallet for Meme Trader V4 Pro
"""

import os
from eth_account import Account
from mnemonic import Mnemonic

def create_test_wallet():
    """Create a new test wallet with mnemonic"""
    
    # Generate a new mnemonic
    mnemo = Mnemonic("english")
    mnemonic = mnemo.generate(strength=128)  # 12 words
    
    # Create account from mnemonic
    Account.enable_unaudited_hdwallet_features()
    account = Account.from_mnemonic(mnemonic)
    
    print("=" * 60)
    print("NEW TEST WALLET CREATED")
    print("=" * 60)
    print(f"Address: {account.address}")
    print(f"Mnemonic: {mnemonic}")
    print("=" * 60)
    print("IMPORTANT: Save this mnemonic securely!")
    print("Add it to your .env file as:")
    print(f"MNEMONIC={mnemonic}")
    print("=" * 60)
    
    # Create .env file if it doesn't exist
    env_content = f"""# Meme Trader V4 Pro Environment Configuration

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=8300046520:AAE6wdXTyK0w_-moczD33zSxjYkNsyp2cyY

# API Key Rotation (Add your actual keys here)
COVALENT_KEYS=your_covalent_key_1,your_covalent_key_2,your_covalent_key_3
HELIUS_KEYS=your_helius_key_1,your_helius_key_2
GOPLUS_KEYS=your_goplus_key_1,your_goplus_key_2

# RPC Endpoints
ETHEREUM_RPC_URL=https://eth.llamarpc.com
BSC_RPC_URL=https://bsc-dataseed1.binance.org
SOLANA_RPC_URL=https://api.mainnet-beta.solana.com

# Scanner Configuration
SCAN_INTERVAL_SECONDS=3600
WATCHLIST_POLL_SECONDS=60
CACHE_TTL_SECONDS=600
SCAN_MIN_SCORE=50

# Graph Analysis Configuration
GRAPH_BREADTH_LIMIT=50
GRAPH_DEPTH_LIMIT=3

# Mirror Trading Configuration
MIRROR_CONFIRM=false
MIRROR_CONFIRM_TIMEOUT=30

# Safety Configuration
SAFE_MODE=true
MIRROR_SELL=true
MIRROR_BUY=false

# Wallet Configuration
MNEMONIC={mnemonic}

# Database Configuration
DATABASE_URL=sqlite:///meme_trader.db

# Logging Configuration
LOG_LEVEL=INFO
LOG_FILE=bot.log

# Development Configuration
DEBUG=false
TEST_MODE=false
"""
    
    if not os.path.exists('.env'):
        with open('.env', 'w') as f:
            f.write(env_content)
        print("Created .env file with your wallet configuration!")
    else:
        print("Warning: .env file already exists. Please add the MNEMONIC manually.")
    
    return account.address, mnemonic

if __name__ == "__main__":
    create_test_wallet()