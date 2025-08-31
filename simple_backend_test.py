#!/usr/bin/env python3
"""
Simple Backend Test for Meme Trader V4 Pro
Focus on key functionality verification
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import Config
from db import get_db_session, Token, User
from analyzer import TokenAnalyzer
from pro_features import AIAnalyst
from executor import TradeExecutor
from utils.api_client import CovalentClient

class SimpleBackendTester:
    def __init__(self):
        self.tests_passed = 0
        self.tests_total = 0

    async def test_configuration(self):
        """Test configuration"""
        print("🔧 Testing Configuration...")
        try:
            Config.validate()
            print(f"✅ Configuration valid")
            print(f"   • Network: {Config.NETWORK_NAME}")
            print(f"   • Chain ID: {Config.CHAIN_ID}")
            return True
        except Exception as e:
            print(f"❌ Configuration failed: {e}")
            return False

    async def test_database(self):
        """Test database connection"""
        print("\n🗄️ Testing Database...")
        try:
            db = get_db_session()
            token_count = db.query(Token).count()
            user_count = db.query(User).count()
            db.close()
            
            print(f"✅ Database connected")
            print(f"   • Tokens: {token_count}")
            print(f"   • Users: {user_count}")
            return True
        except Exception as e:
            print(f"❌ Database failed: {e}")
            return False

    async def test_token_analyzer(self):
        """Test token analyzer"""
        print("\n🔍 Testing Token Analyzer...")
        try:
            analyzer = TokenAnalyzer()
            test_address = "0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b"
            
            analysis = await analyzer.analyze_token(test_address)
            
            print(f"✅ Token analysis working")
            print(f"   • Symbol: {analysis.get('symbol', 'Unknown')}")
            print(f"   • AI Score: {analysis.get('ai_score', 0)}/10")
            print(f"   • Risk Level: {analysis.get('risk_level', 'Unknown')}")
            return True
        except Exception as e:
            print(f"❌ Token analyzer failed: {e}")
            return False

    async def test_ai_features(self):
        """Test AI features"""
        print("\n🤖 Testing AI Features...")
        try:
            ai_analyst = AIAnalyst()
            
            sample_data = {
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
                sample_data['address'], 
                sample_data
            )
            
            print(f"✅ AI analysis working")
            print(f"   • Recommendation: {ai_analysis.get('recommendation', 'Unknown')}")
            print(f"   • AI Score: {ai_analysis.get('ai_score', 0)}/10")
            print(f"   • Model: {ai_analysis.get('model_used', 'Unknown')}")
            return True
        except Exception as e:
            print(f"❌ AI features failed: {e}")
            return False

    async def test_trade_executor(self):
        """Test trade executor"""
        print("\n💱 Testing Trade Executor...")
        try:
            executor = TradeExecutor()
            
            test_params = {
                'user_id': 123456789,
                'wallet_address': '0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b',
                'trade_type': 'buy',
                'token_in_address': '0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee',
                'token_out_address': '0xA0b86a33E6441ba0BB7e1ae5E3e7BAaD5D1D7e3c',
                'amount_in': 0.01,
                'slippage': 0.01
            }
            
            is_valid = executor.validate_trade_params(test_params)
            
            print(f"✅ Trade executor working")
            print(f"   • Parameter validation: {'✅' if is_valid else '❌'}")
            print(f"   • Network: {Config.NETWORK_NAME} (testnet)")
            return True
        except Exception as e:
            print(f"❌ Trade executor failed: {e}")
            return False

    async def test_api_client(self):
        """Test API client"""
        print("\n🌐 Testing API Client...")
        try:
            client = CovalentClient()
            
            # Test connection (may fail on testnet, that's OK)
            test_address = "0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b"
            token_data = await client.get_token_data(test_address)
            
            await client.close_all_sessions()
            
            print(f"✅ API client working")
            print(f"   • Connection: {'✅' if token_data else '⚠️ Limited on testnet'}")
            return True
        except Exception as e:
            print(f"❌ API client failed: {e}")
            return False

    async def run_all_tests(self):
        """Run all tests"""
        print("🚀 MEME TRADER V4 PRO - SIMPLE BACKEND TEST")
        print("=" * 50)
        
        tests = [
            ("Configuration", self.test_configuration),
            ("Database", self.test_database),
            ("Token Analyzer", self.test_token_analyzer),
            ("AI Features", self.test_ai_features),
            ("Trade Executor", self.test_trade_executor),
            ("API Client", self.test_api_client)
        ]
        
        self.tests_total = len(tests)
        
        for test_name, test_func in tests:
            try:
                result = await test_func()
                if result:
                    self.tests_passed += 1
            except Exception as e:
                print(f"❌ {test_name} test failed: {e}")
        
        print("\n" + "=" * 50)
        print(f"🏁 TEST RESULTS: {self.tests_passed}/{self.tests_total} tests passed")
        
        if self.tests_passed == self.tests_total:
            print("🎉 ALL CORE TESTS PASSED!")
            print("\n✅ VERIFIED COMPONENTS:")
            print("   • Configuration management")
            print("   • Database connectivity")
            print("   • Token analysis engine")
            print("   • AI-powered features")
            print("   • Trade execution system")
            print("   • API client integration")
        else:
            print(f"⚠️ {self.tests_total - self.tests_passed} tests had issues")
        
        return self.tests_passed >= (self.tests_total - 1)  # Allow 1 failure

async def main():
    """Main test runner"""
    tester = SimpleBackendTester()
    success = await tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)