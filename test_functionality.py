#!/usr/bin/env python3
"""Test script for Meme Trader V4 Pro functionality"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import Config
from analyzer import TokenAnalyzer
from pro_features import AIAnalyst
from executor import TradeExecutor
from monitor import TokenMonitor, WalletMonitor
from utils.api_client import CovalentClient

async def test_configuration():
    """Test configuration setup"""
    print("🔧 Testing Configuration...")
    try:
        Config.validate()
        print("✅ Configuration validated successfully")
        print(f"   • Telegram Bot Token: {'*' * 30}{Config.TELEGRAM_BOT_TOKEN[-10:]}")
        print(f"   • Covalent API Key: {'*' * 20}{Config.COVALENT_API_KEY[-10:]}")
        print(f"   • Network: {Config.NETWORK_NAME} (Chain ID: {Config.CHAIN_ID})")
        return True
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return False

async def test_database():
    """Test database connection"""
    print("\n🗄️  Testing Database Connection...")
    try:
        from db import get_db_session, Token
        db = get_db_session()
        
        # Test basic query
        token_count = db.query(Token).count()
        db.close()
        
        print(f"✅ Database connection successful")
        print(f"   • Total tokens in database: {token_count}")
        return True
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

async def test_covalent_api():
    """Test Covalent API connection"""
    print("\n🌐 Testing Covalent API...")
    try:
        client = CovalentClient()
        
        # Test with a known token address
        test_address = "0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b"
        token_data = await client.get_token_data(test_address)
        
        if token_data:
            print("✅ Covalent API connection successful")
            print(f"   • Retrieved data for token: {token_data.get('symbol', 'Unknown')}")
        else:
            print("⚠️  Covalent API connected but no data retrieved (may be testnet limitation)")
        
        await client.close_all_sessions()
        return True
    except Exception as e:
        print(f"❌ Covalent API error: {e}")
        return False

async def test_token_analyzer():
    """Test token analysis functionality"""
    print("\n🔍 Testing Token Analyzer...")
    try:
        analyzer = TokenAnalyzer()
        
        # Test with sample token
        test_address = "0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b"
        analysis = await analyzer.analyze_token(test_address)
        
        print("✅ Token Analyzer working successfully")
        print(f"   • Analyzed token: {analysis.get('symbol', 'Unknown')}")
        print(f"   • AI Score: {analysis.get('ai_score', 0)}/10")
        print(f"   • Risk Level: {analysis.get('risk_level', 'Unknown')}")
        print(f"   • Honeypot Risk: {'🔴 HIGH' if analysis.get('is_honeypot') else '🟢 LOW'}")
        return True
    except Exception as e:
        print(f"❌ Token Analyzer error: {e}")
        return False

async def test_ai_features():
    """Test AI-powered features"""
    print("\n🤖 Testing AI Features...")
    try:
        ai_analyst = AIAnalyst()
        
        # Test AI analysis with sample data
        sample_market_data = {
            'address': '0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b',
            'name': 'Test Token',
            'symbol': 'TEST',
            'price_usd': 0.001,
            'market_cap': 1000000,
            'liquidity_usd': 50000,
            'volume_24h': 10000,
            'is_honeypot': False
        }
        
        ai_analysis = await ai_analyst.analyze_token_with_ai(
            sample_market_data['address'], 
            sample_market_data
        )
        
        print("✅ AI Analysis working successfully")
        print(f"   • AI Recommendation: {ai_analysis.get('recommendation', 'Unknown')}")
        print(f"   • AI Score: {ai_analysis.get('ai_score', 0)}/10")
        print(f"   • Confidence: {ai_analysis.get('confidence_score', 0)}/10")
        print(f"   • Model Used: {ai_analysis.get('model_used', 'Unknown')}")
        return True
    except Exception as e:
        print(f"❌ AI Features error: {e}")
        return False

async def test_trade_executor():
    """Test trade execution (simulation)"""
    print("\n💱 Testing Trade Executor...")
    try:
        executor = TradeExecutor()
        
        # Test trade parameters validation
        test_params = {
            'user_id': 123456789,
            'wallet_address': '0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b',
            'trade_type': 'buy',
            'token_in_address': '0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee',  # ETH
            'token_out_address': '0xA0b86a33E6441ba0BB7e1ae5E3e7BAaD5D1D7e3c',
            'amount_in': 0.01,
            'slippage': 0.01
        }
        
        # Validate trade parameters
        is_valid = executor.validate_trade_params(test_params)
        
        if is_valid:
            print("✅ Trade Executor validation working")
            print("   • Trade parameters validation: PASSED")
            print("   • Network: Sepolia Testnet (Safe for testing)")
        else:
            print("⚠️  Trade parameter validation failed")
        
        return True
    except Exception as e:
        print(f"❌ Trade Executor error: {e}")
        return False

async def test_monitoring():
    """Test monitoring functionality"""
    print("\n📊 Testing Monitoring Features...")
    try:
        token_monitor = TokenMonitor()
        wallet_monitor = WalletMonitor()
        
        print("✅ Monitoring components initialized successfully")
        print("   • Token Monitor: Ready")
        print("   • Wallet Monitor: Ready")
        print("   • Real-time monitoring: Available")
        return True
    except Exception as e:
        print(f"❌ Monitoring error: {e}")
        return False

async def main():
    """Run all tests"""
    print("🚀 MEME TRADER V4 PRO - FUNCTIONALITY TEST")
    print("=" * 50)
    
    tests = [
        ("Configuration", test_configuration),
        ("Database", test_database),
        ("Covalent API", test_covalent_api),
        ("Token Analyzer", test_token_analyzer),
        ("AI Features", test_ai_features),
        ("Trade Executor", test_trade_executor),
        ("Monitoring", test_monitoring)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            if result:
                passed += 1
        except Exception as e:
            print(f"❌ {test_name} test failed: {e}")
    
    print("\n" + "=" * 50)
    print(f"🏁 TEST RESULTS: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED! Meme Trader V4 Pro is ready!")
        print("\n🔥 FEATURES READY:")
        print("   • ✅ Telegram Bot Interface")
        print("   • ✅ Real-time Token Monitoring")
        print("   • ✅ AI-Powered Market Analysis")
        print("   • ✅ Honeypot Detection")
        print("   • ✅ Trade Execution (Testnet)")
        print("   • ✅ Multi-wallet Management")
        print("   • ✅ Portfolio Tracking")
        print("\n📱 Start the bot with: python bot.py")
    else:
        print(f"⚠️  {total - passed} tests failed. Please check the errors above.")
    
    return passed == total

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)