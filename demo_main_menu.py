#!/usr/bin/env python3
"""
Demo script showing the enhanced main menu system
"""

import asyncio
from ui.main_menu import MainMenu

async def demo_main_menu():
    """Demo the main menu system"""
    print("🚀 **MEME TRADER V4 PRO - MAIN MENU SYSTEM DEMO**")
    print("=" * 60)
    
    # Demo main menu
    print("\n📱 **MAIN MENU INTERFACE:**")
    menu_text, menu_keyboard = await MainMenu.get_main_menu("123456789")
    print(menu_text)
    print("\n🔘 **Available Buttons:**")
    for i, row in enumerate(menu_keyboard.inline_keyboard, 1):
        for j, button in enumerate(row, 1):
            print(f"  {i}.{j} {button.text}")
    
    print("\n" + "="*60)
    
    # Demo portfolio menu
    print("\n📊 **PORTFOLIO MENU WITH SELL BUTTONS:**")
    try:
        portfolio_text, portfolio_keyboard = await MainMenu.get_portfolio_menu("123456789")
        print(portfolio_text[:500] + "..." if len(portfolio_text) > 500 else portfolio_text)
        print("\n🔘 **Portfolio Action Buttons:**")
        for i, row in enumerate(portfolio_keyboard.inline_keyboard[:8], 1):  # Show first 8 rows
            for j, button in enumerate(row, 1):
                if button.text != "─────────────":  # Skip separators
                    print(f"  • {button.text}")
    except Exception as e:
        print(f"Portfolio demo error: {e}")
    
    print("\n" + "="*60)
    
    # Demo settings menu
    print("\n⚙️ **SETTINGS MENU:**")
    try:
        settings_text, settings_keyboard = await MainMenu.get_settings_menu("123456789")
        print(settings_text)
        print("\n🔘 **Settings Buttons:**")
        for row in settings_keyboard.inline_keyboard:
            for button in row:
                print(f"  • {button.text}")
    except Exception as e:
        print(f"Settings demo error: {e}")
    
    print("\n" + "="*60)
    
    # Demo scan menu
    print("\n🔍 **SCAN MENU:**")
    scan_text, scan_keyboard = await MainMenu.get_scan_menu()
    print(scan_text)
    print("\n🔘 **Scan Buttons:**")
    for row in scan_keyboard.inline_keyboard:
        for button in row:
            print(f"  • {button.text}")
    
    print("\n" + "="*60)
    
    # Demo buy amount menu
    print("\n💵 **BUY AMOUNT SELECTION:**")
    buy_text, buy_keyboard = MainMenu.get_buy_amount_menu()
    print(buy_text)
    print("\n🔘 **Amount Options:**")
    for row in buy_keyboard.inline_keyboard:
        for button in row:
            print(f"  • {button.text}")
    
    print("\n" + "="*60)
    
    # Demo confirmation popups
    print("\n✅ **CONFIRMATION POPUPS:**")
    
    # Sell confirmation
    print("\n💸 **Sell Confirmation:**")
    sell_details = {
        'token_symbol': 'MEME',
        'token_id': '0x742d35Cc',
        'percentage': 50,
        'estimated_value': 1200.0,
        'token_amount': 1000.0
    }
    sell_confirm_text, sell_confirm_keyboard = MainMenu.create_confirmation_popup("sell", sell_details)
    print(sell_confirm_text)
    print("\n🔘 **Sell Confirmation Buttons:**")
    for row in sell_confirm_keyboard.inline_keyboard:
        for button in row:
            print(f"  • {button.text}")
    
    # Panic sell confirmation
    print("\n🚨 **Panic Sell Confirmation:**")
    panic_details = {
        'total_value': 5000.0,
        'position_count': 3
    }
    panic_confirm_text, panic_confirm_keyboard = MainMenu.create_confirmation_popup("panic_sell", panic_details)
    print(panic_confirm_text)
    print("\n🔘 **Panic Sell Confirmation Buttons:**")
    for row in panic_confirm_keyboard.inline_keyboard:
        for button in row:
            print(f"  • {button.text}")

def demo_user_flow():
    """Demo the complete user flow"""
    print("\n\n🎯 **COMPLETE USER FLOW EXAMPLE:**")
    print("="*60)
    
    flow_steps = [
        "1. 🚀 User sends /start",
        "   → Main Menu appears with portfolio value and quick actions",
        "",
        "2. 💸 User clicks 'Sell Token'",
        "   → Portfolio view with sell buttons for each token",
        "",
        "3. 📊 User clicks 'Sell 50% MEME'",
        "   → Confirmation popup: 'Sell 50% of MEME (≈$1,200)?'",
        "",
        "4. ✅ User clicks 'Confirm'",
        "   → Trade executes, result shown",
        "",
        "5. 🏠 Main Menu automatically reappears",
        "   → Updated portfolio value, ready for next action",
        "",
        "6. 📈 User clicks 'Moonshot Leaderboard'",
        "   → Shows top wallets with clickable addresses",
        "",
        "7. 🔍 User clicks 'Analyze Top Wallet'",
        "   → Shows wallet analysis with action buttons",
        "",
        "8. 🏠 Main Menu automatically reappears",
        "   → Seamless navigation, no typing needed!"
    ]
    
    for step in flow_steps:
        print(step)

def main():
    """Run all demos"""
    print("🎨 **MEME TRADER V4 PRO - ENHANCED UI SYSTEM**")
    print("Persistent Main Menu + Confirmation Popups + Action Buttons")
    print("="*60)
    
    # Run async demo
    try:
        asyncio.run(demo_main_menu())
    except Exception as e:
        print(f"Demo error: {e}")
    
    # Show user flow
    demo_user_flow()
    
    print("\n\n🎉 **ENHANCEMENT SUMMARY:**")
    print("="*60)
    print("✅ **Persistent Main Menu System**")
    print("  • Appears after every action automatically")
    print("  • /start or 'Main Menu' button refreshes anytime")
    print("  • Real-time portfolio value display")
    print("  • One-click access to all features")
    print("")
    print("✅ **Enhanced Portfolio View**")
    print("  • USD + token amount + contract links")
    print("  • Sell 25%/50%/100%/Custom buttons per token")
    print("  • View Contract (block explorer) buttons")
    print("  • Blacklist Token buttons")
    print("")
    print("✅ **Smart Confirmation Popups**")
    print("  • Every trade requires confirmation")
    print("  • Shows exact amounts and values")
    print("  • Clear ✅ Confirm / ❌ Cancel options")
    print("  • Returns to Main Menu after completion")
    print("")
    print("✅ **Comprehensive Settings Menu**")
    print("  • Toggle Mirror Sell/Buy with one click")
    print("  • Default buy amount dropdown ($10-$500)")
    print("  • Safe Mode toggle")
    print("  • Panic sell confirmation settings")
    print("")
    print("✅ **Seamless Navigation**")
    print("  • No typing required for basic operations")
    print("  • Clickable addresses with block explorer links")
    print("  • Quick action buttons on all addresses")
    print("  • Main Menu always accessible")
    print("")
    print("🚀 **The bot is now fully menu-driven and user-friendly!**")

if __name__ == "__main__":
    main()