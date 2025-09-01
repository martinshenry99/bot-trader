#!/usr/bin/env python3
"""
Demo script showing enhanced address/contract formatting features
"""

from utils.formatting import AddressFormatter
from datetime import datetime

def demo_wallet_formatting():
    """Demo wallet address formatting"""
    print("🔗 **WALLET ADDRESS FORMATTING DEMO**")
    print("=" * 50)
    
    # Test wallet addresses
    eth_wallet = "0x8ba1f109551bD432803012645Hac136c22C501e3"
    bsc_wallet = "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984"
    sol_wallet = "DUSTawucrTsGU8hcqRdHDCbuYhCPADMLM2VcCb8VnFnQ"
    
    print("\n📍 **Ethereum Wallet:**")
    eth_formatted = AddressFormatter.format_wallet_address(eth_wallet, "ethereum", "DefiWhale")
    print(f"  Raw: {eth_wallet}")
    print(f"  Enhanced: {eth_formatted}")
    print(f"  Block Explorer: Etherscan link embedded")
    
    print("\n📍 **BSC Wallet:**")
    bsc_formatted = AddressFormatter.format_wallet_address(bsc_wallet, "bsc", "PancakeTrader")
    print(f"  Raw: {bsc_wallet}")
    print(f"  Enhanced: {bsc_formatted}")
    print(f"  Block Explorer: BscScan link embedded")
    
    print("\n📍 **Solana Wallet:**")
    sol_formatted = AddressFormatter.format_wallet_address(sol_wallet, "solana", "SolanaGem")
    print(f"  Raw: {sol_wallet}")
    print(f"  Enhanced: {sol_formatted}")
    print(f"  Block Explorer: Solscan link embedded")

def demo_token_formatting():
    """Demo token contract formatting"""
    print("\n\n🪙 **TOKEN CONTRACT FORMATTING DEMO**")
    print("=" * 50)
    
    # Test token addresses
    eth_token = "0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b"
    bsc_token = "0xA0b86a33E6441ba0BB7e1ae5E3e7BAaD5D1D7e3c"
    sol_token = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
    
    print("\n💎 **Ethereum Token:**")
    eth_token_formatted = AddressFormatter.format_token_address(eth_token, "ethereum", "MEME")
    print(f"  Raw: {eth_token}")
    print(f"  Enhanced: {eth_token_formatted}")
    print(f"  Block Explorer: Etherscan token page")
    
    print("\n💎 **BSC Token:**")
    bsc_token_formatted = AddressFormatter.format_token_address(bsc_token, "bsc", "CAKE")
    print(f"  Raw: {bsc_token}")
    print(f"  Enhanced: {bsc_token_formatted}")
    print(f"  Block Explorer: BscScan token page")
    
    print("\n💎 **Solana Token:**")
    sol_token_formatted = AddressFormatter.format_token_address(sol_token, "solana", "USDC")
    print(f"  Raw: {sol_token}")
    print(f"  Enhanced: {sol_token_formatted}")
    print(f"  Block Explorer: Solscan token page")

def demo_trading_alert():
    """Demo enhanced trading alert formatting"""
    print("\n\n🚨 **TRADING ALERT FORMATTING DEMO**")
    print("=" * 50)
    
    # Sample trading alert
    wallet_addr = "0x8ba1f109551bD432803012645Hac136c22C501e3"
    token_addr = "0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b"
    tx_hash = "0xabc123def456789012345678901234567890123456789012345678901234567890"
    
    message, buttons = AddressFormatter.format_trading_alert(
        wallet_address=wallet_addr,
        wallet_name="DefiWhale",
        action="buy",
        token_address=token_addr,
        token_symbol="MEME",
        amount_usd=25000.0,
        chain="ethereum",
        tx_hash=tx_hash,
        confidence=0.85
    )
    
    print("\n📱 **Enhanced Alert Message:**")
    print(message)
    print("\n🔘 **Action Buttons Available:**")
    for row in buttons.inline_keyboard:
        for button in row:
            print(f"  • {button.text}")

def demo_portfolio_position():
    """Demo portfolio position formatting"""
    print("\n\n📊 **PORTFOLIO POSITION FORMATTING DEMO**")
    print("=" * 50)
    
    token_addr = "0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b"
    
    position_text = AddressFormatter.format_portfolio_position(
        token_address=token_addr,
        token_symbol="MEME",
        chain="ethereum",
        current_value=15000.0,
        pnl_usd=5000.0,
        pnl_pct=50.0
    )
    
    print("\n💰 **Enhanced Portfolio Position:**")
    print(position_text)

def demo_leaderboard_entry():
    """Demo leaderboard entry formatting"""
    print("\n\n🏆 **LEADERBOARD ENTRY FORMATTING DEMO**")
    print("=" * 50)
    
    wallet_addr = "0x8ba1f109551bD432803012645Hac136c22C501e3"
    
    leaderboard_text = AddressFormatter.format_leaderboard_entry(
        rank=1,
        wallet_address=wallet_addr,
        multiplier=350.0,
        total_pnl=5000000.0,  # $5M
        win_rate=85.5,
        chains=["ethereum", "bsc"]
    )
    
    print("\n🥇 **Enhanced Leaderboard Entry:**")
    print(leaderboard_text)

def demo_action_buttons():
    """Demo action button creation"""
    print("\n\n🔘 **ACTION BUTTONS DEMO**")
    print("=" * 50)
    
    wallet_addr = "0x8ba1f109551bD432803012645Hac136c22C501e3"
    token_addr = "0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b"
    
    print("\n👤 **Wallet Action Buttons:**")
    wallet_buttons = AddressFormatter.create_wallet_action_buttons(wallet_addr, "ethereum")
    for row in wallet_buttons.inline_keyboard:
        for button in row:
            print(f"  • {button.text} (callback: {button.callback_data})")
    
    print("\n🪙 **Token Action Buttons:**")
    token_buttons = AddressFormatter.create_token_action_buttons(token_addr, "ethereum")
    for row in token_buttons.inline_keyboard:
        for button in row:
            print(f"  • {button.text} (callback: {button.callback_data})")
    
    print("\n🤝 **Combined Action Buttons:**")
    combined_buttons = AddressFormatter.create_combined_action_buttons(wallet_addr, token_addr, "ethereum")
    for row in combined_buttons.inline_keyboard:
        for button in row:
            print(f"  • {button.text} (callback: {button.callback_data})")

def demo_block_explorer_links():
    """Demo block explorer integration"""
    print("\n\n🔗 **BLOCK EXPLORER INTEGRATION DEMO**")
    print("=" * 50)
    
    sample_addr = "0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b"
    sample_tx = "0xabc123def456789012345678901234567890123456789012345678901234567890"
    
    print("\n🌐 **Block Explorer URLs Generated:**")
    
    # Ethereum
    print(f"  📍 Ethereum Wallet: https://etherscan.io/address/{sample_addr}")
    print(f"  🪙 Ethereum Token: https://etherscan.io/token/{sample_addr}")
    print(f"  📋 Ethereum TX: https://etherscan.io/tx/{sample_tx}")
    
    # BSC
    print(f"  📍 BSC Wallet: https://bscscan.com/address/{sample_addr}")
    print(f"  🪙 BSC Token: https://bscscan.com/token/{sample_addr}")
    print(f"  📋 BSC TX: https://bscscan.com/tx/{sample_tx}")
    
    # Solana
    sol_addr = "DUSTawucrTsGU8hcqRdHDCbuYhCPADMLM2VcCb8VnFnQ"
    sol_tx = "5VfHjQiqZKv8XYCvKrneJRg2vtxo3xDz7yHxxRrQQK6pqhWyZQTkDGxU7qTp6X5HcQsM5jUmYtJPZq1F3hKGjrUD"
    print(f"  📍 Solana Account: https://solscan.io/account/{sol_addr}")
    print(f"  🪙 Solana Token: https://solscan.io/token/{sol_addr}")
    print(f"  📋 Solana TX: https://solscan.io/tx/{sol_tx}")

def main():
    """Run all formatting demos"""
    print("🎨 **MEME TRADER V4 PRO - ENHANCED FORMATTING FEATURES**")
    print("=" * 60)
    print("✅ All wallet addresses and token contracts are now:")
    print("  • Clickable/copyable with Markdown formatting")
    print("  • Hyperlinked to appropriate block explorers")
    print("  • Enhanced with quick action buttons")
    print("  • Consistent across all features")
    print("=" * 60)
    
    # Run all demos
    demo_wallet_formatting()
    demo_token_formatting()
    demo_trading_alert()
    demo_portfolio_position()
    demo_leaderboard_entry()
    demo_action_buttons()
    demo_block_explorer_links()
    
    print("\n\n🎯 **ENHANCEMENT SUMMARY**")
    print("=" * 50)
    print("✅ **Features Enhanced:**")
    print("  • Trading alerts with wallet/token links")
    print("  • Portfolio positions with clickable tokens")
    print("  • Leaderboard entries with wallet links")
    print("  • Watchlist with enhanced wallet display")
    print("  • Blacklist with clickable addresses")
    print("  • All addresses link to block explorers")
    print("\n✅ **Action Buttons Added:**")
    print("  • 🔍 Analyze Wallet")
    print("  • 🔍 Analyze Token")
    print("  • 👁️ Add to Watchlist")
    print("  • 💰 Quick Buy")
    print("  • 🚫 Blacklist options")
    print("\n✅ **Supported Chains:**")
    print("  • Ethereum → Etherscan")
    print("  • BNB Chain → BscScan")
    print("  • Solana → Solscan")
    print("\n🚀 **All enhancements are now active in the bot!**")

if __name__ == "__main__":
    main()