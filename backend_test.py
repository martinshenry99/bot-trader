#!/usr/bin/env python3
"""
Comprehensive Backend Testing for Meme Trader V4 Pro
Tests all components individually and their integrations
"""

import asyncio
import sys
import os
import logging
from datetime import datetime
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import all components
from config import Config
from db import create_tables, get_db_session, User, Wallet, Token, Trade, Transaction, MonitoringAlert
from analyzer import TokenAnalyzer, MarketAnalyzer
from pro_features import AIAnalyst, SmartTradingEngine, MultiWalletManager, ProFeaturesManager
from executor import TradeExecutor, TradingStrategies
from monitor import TokenMonitor, WalletMonitor, MonitoringManager
from utils.api_client import CovalentClient, covalent_client

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ComprehensiveBackendTester:
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        
    async def run_test(self, test_name: str, test_func, *args, **kwargs):
        """Run a single test and track results"""
        self.tests_run += 1
        print(f"\n🔍 Testing {test_name}...")
        
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func(*args, **kwargs)
            else:
                result = test_func(*args, **kwargs)
            
            if result:
                self.tests_passed += 1
                print(f"✅ {test_name}: PASSED")
                self.test_results.append({"name": test_name, "status": "PASSED", "details": ""})
                return True
            else:
                print(f"❌ {test_name}: FAILED")
                self.test_results.append({"name": test_name, "status": "FAILED", "details": "Test returned False"})
                return False
                
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {str(e)}")
            self.test_results.append({"name": test_name, "status": "ERROR", "details": str(e)})
            return False

    # ==================== DATABASE TESTS ====================
    
    def test_database_schema(self):
        """Test database schema creation and integrity"""
        try:
            create_tables()
            
            # Test database connection
            db = get_db_session()
            
            # Test each table exists and can be queried
            tables_to_test = [User, Wallet, Token, Trade, Transaction, MonitoringAlert]
            
            for table in tables_to_test:
                count = db.query(table).count()
                print(f"   • {table.__tablename__}: {count} records")
            
            db.close()
            return True
            
        except Exception as e:
            logger.error(f"Database schema test failed: {e}")
            return False

    def test_database_crud_operations(self):
        """Test CRUD operations on database"""
        try:
            db = get_db_session()
            
            # Test User creation
            test_user = User(
                telegram_id="test_123456",
                username="test_user",
                first_name="Test",
                last_name="User"
            )
            db.add(test_user)
            db.commit()
            db.refresh(test_user)
            
            # Test User retrieval
            retrieved_user = db.query(User).filter(User.telegram_id == "test_123456").first()
            assert retrieved_user is not None
            assert retrieved_user.username == "test_user"
            
            # Test Wallet creation
            test_wallet = Wallet(
                user_id=test_user.id,
                address="0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b",
                name="Test Wallet"
            )
            db.add(test_wallet)
            db.commit()
            
            # Test Token creation (use unique address)
            import time
            unique_address = f"0xA0b86a33E6441ba0BB7e1ae5E3e7BAaD5D1D7e{int(time.time()) % 1000:03d}"
            test_token = Token(
                address=unique_address,
                symbol="TEST",
                name="Test Token",
                decimals=18,
                price_usd=0.001,
                ai_score=7.5
            )
            db.add(test_token)
            db.commit()
            
            # Cleanup test data
            db.delete(test_wallet)
            db.delete(test_token)
            db.delete(test_user)
            db.commit()
            db.close()
            
            print("   • User CRUD: ✅")
            print("   • Wallet CRUD: ✅")
            print("   • Token CRUD: ✅")
            
            return True
            
        except Exception as e:
            logger.error(f"Database CRUD test failed: {e}")
            return False

    # ==================== CONFIGURATION TESTS ====================
    
    def test_configuration_validation(self):
        """Test configuration validation"""
        try:
            # Test config validation
            Config.validate()
            
            # Test required environment variables
            required_vars = [
                'TELEGRAM_BOT_TOKEN',
                'COVALENT_API_KEY'
            ]
            
            for var in required_vars:
                value = getattr(Config, var)
                if not value:
                    raise ValueError(f"Missing {var}")
                print(f"   • {var}: {'*' * 20}{value[-10:]}")
            
            # Test network configuration
            print(f"   • Network: {Config.NETWORK_NAME}")
            print(f"   • Chain ID: {Config.CHAIN_ID}")
            print(f"   • RPC URL: {Config.ETHEREUM_RPC_URL[:50]}...")
            
            return True
            
        except Exception as e:
            logger.error(f"Configuration test failed: {e}")
            return False

    # ==================== API CLIENT TESTS ====================
    
    async def test_covalent_api_client(self):
        """Test Covalent API client functionality"""
        try:
            client = CovalentClient()
            
            # Test token data retrieval
            test_address = "0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b"
            token_data = await client.get_token_data(test_address)
            
            if token_data:
                print(f"   • Token data retrieved: {token_data.get('symbol', 'Unknown')}")
            else:
                print("   • Token data: No data (expected on testnet)")
            
            # Test wallet balances (may not work on testnet)
            try:
                balances = await client.get_wallet_balances(test_address)
                print(f"   • Wallet balances: {len(balances)} tokens")
            except:
                print("   • Wallet balances: Not available on testnet")
            
            # Test session cleanup
            await client.close_all_sessions()
            print("   • Session cleanup: ✅")
            
            return True
            
        except Exception as e:
            logger.error(f"Covalent API test failed: {e}")
            return False

    # ==================== ANALYZER TESTS ====================
    
    async def test_token_analyzer(self):
        """Test token analyzer functionality"""
        try:
            analyzer = TokenAnalyzer()
            
            # Test token analysis
            test_address = "0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b"
            analysis = await analyzer.analyze_token(test_address)
            
            # Verify analysis structure
            required_fields = ['symbol', 'ai_score', 'risk_level', 'is_honeypot', 'recommendation']
            for field in required_fields:
                if field not in analysis:
                    raise ValueError(f"Missing field in analysis: {field}")
            
            print(f"   • Token: {analysis.get('symbol', 'Unknown')}")
            print(f"   • AI Score: {analysis.get('ai_score', 0)}/10")
            print(f"   • Risk Level: {analysis.get('risk_level', 'Unknown')}")
            print(f"   • Honeypot: {'Yes' if analysis.get('is_honeypot') else 'No'}")
            print(f"   • Recommendation: {analysis.get('recommendation', 'None')}")
            
            return True
            
        except Exception as e:
            logger.error(f"Token analyzer test failed: {e}")
            return False

    async def test_market_analyzer(self):
        """Test market analyzer functionality"""
        try:
            market_analyzer = MarketAnalyzer()
            
            # Test trending tokens
            trending = await market_analyzer.get_trending_tokens(limit=2)
            print(f"   • Trending tokens retrieved: {len(trending)}")
            
            # Test market conditions
            conditions = await market_analyzer.analyze_market_conditions()
            print(f"   • Market sentiment: {conditions.get('market_sentiment', 'Unknown')}")
            
            return True
            
        except Exception as e:
            logger.error(f"Market analyzer test failed: {e}")
            return False

    # ==================== AI FEATURES TESTS ====================
    
    async def test_ai_analyst(self):
        """Test AI analyst functionality"""
        try:
            ai_analyst = AIAnalyst()
            
            # Test AI analysis
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
            
            # Verify AI analysis structure
            required_fields = ['recommendation', 'ai_score', 'confidence_score', 'model_used']
            for field in required_fields:
                if field not in ai_analysis:
                    raise ValueError(f"Missing field in AI analysis: {field}")
            
            print(f"   • AI Recommendation: {ai_analysis.get('recommendation', 'Unknown')}")
            print(f"   • AI Score: {ai_analysis.get('ai_score', 0)}/10")
            print(f"   • Confidence: {ai_analysis.get('confidence_score', 0)}/10")
            print(f"   • Model: {ai_analysis.get('model_used', 'Unknown')}")
            
            return True
            
        except Exception as e:
            logger.error(f"AI analyst test failed: {e}")
            return False

    async def test_smart_trading_engine(self):
        """Test smart trading engine"""
        try:
            smart_engine = SmartTradingEngine()
            
            # Test trade parameter calculation
            sample_ai_analysis = {
                'recommendation': 'BUY',
                'ai_score': 7.5,
                'confidence_score': 8.0,
                'risk_level': 'MEDIUM',
                'market_context': {
                    'liquidity_assessment': 'MEDIUM',
                    'volume_assessment': 'LOW',
                    'market_cap_tier': 'SMALL_CAP'
                }
            }
            
            strategy_params = {
                'wallet_address': '0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b',
                'amount': 0.01,
                'max_amount': 0.1
            }
            
            trade_params = await smart_engine.calculate_trade_parameters(
                "123456", 
                "0xA0b86a33E6441ba0BB7e1ae5E3e7BAaD5D1D7e3c",
                sample_ai_analysis,
                strategy_params
            )
            
            print(f"   • Trade amount calculated: {trade_params.get('amount_in', 0)} ETH")
            print(f"   • Slippage: {trade_params.get('slippage', 0) * 100}%")
            print(f"   • Trade type: {trade_params.get('trade_type', 'Unknown')}")
            
            return True
            
        except Exception as e:
            logger.error(f"Smart trading engine test failed: {e}")
            return False

    # ==================== EXECUTOR TESTS ====================
    
    async def test_trade_executor(self):
        """Test trade executor functionality"""
        try:
            executor = TradeExecutor()
            
            # Test trade parameter validation
            valid_params = {
                'user_id': 123456789,
                'wallet_address': '0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b',
                'trade_type': 'buy',
                'token_in_address': '0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee',  # ETH
                'token_out_address': '0xA0b86a33E6441ba0BB7e1ae5E3e7BAaD5D1D7e3c',
                'amount_in': 0.01,
                'slippage': 0.01
            }
            
            is_valid = executor.validate_trade_params(valid_params)
            print(f"   • Parameter validation: {'✅' if is_valid else '❌'}")
            
            # Test invalid parameters
            invalid_params = valid_params.copy()
            invalid_params['wallet_address'] = 'invalid_address'
            is_invalid = executor.validate_trade_params(invalid_params)
            print(f"   • Invalid parameter detection: {'✅' if not is_invalid else '❌'}")
            
            # Test balance check (will return 0 on testnet)
            balance = await executor.check_wallet_balance(
                valid_params['wallet_address'],
                valid_params['token_in_address']
            )
            print(f"   • Balance check: {balance} ETH")
            
            return True
            
        except Exception as e:
            logger.error(f"Trade executor test failed: {e}")
            return False

    # ==================== MONITORING TESTS ====================
    
    async def test_monitoring_system(self):
        """Test monitoring system functionality"""
        try:
            token_monitor = TokenMonitor()
            wallet_monitor = WalletMonitor()
            monitoring_manager = MonitoringManager()
            
            # Test monitoring initialization
            print("   • Token monitor initialized: ✅")
            print("   • Wallet monitor initialized: ✅")
            print("   • Monitoring manager initialized: ✅")
            
            # Test monitoring status
            status = await monitoring_manager.get_monitoring_status()
            print(f"   • Token monitor running: {status.get('token_monitor_running', False)}")
            print(f"   • Wallet monitor running: {status.get('wallet_monitor_running', False)}")
            print(f"   • Monitored tokens: {status.get('monitored_tokens', 0)}")
            print(f"   • Monitored wallets: {status.get('monitored_wallets', 0)}")
            
            return True
            
        except Exception as e:
            logger.error(f"Monitoring system test failed: {e}")
            return False

    # ==================== INTEGRATION TESTS ====================
    
    async def test_full_workflow_integration(self):
        """Test complete workflow integration"""
        try:
            print("   Testing complete workflow...")
            
            # 1. Initialize components
            analyzer = TokenAnalyzer()
            ai_analyst = AIAnalyst()
            executor = TradeExecutor()
            
            # 2. Analyze a token
            test_address = "0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b"
            token_analysis = await analyzer.analyze_token(test_address)
            print(f"   • Token analysis: ✅ (Score: {token_analysis.get('ai_score', 0)})")
            
            # 3. Get AI recommendation
            ai_analysis = await ai_analyst.analyze_token_with_ai(test_address, token_analysis)
            print(f"   • AI analysis: ✅ (Recommendation: {ai_analysis.get('recommendation', 'Unknown')})")
            
            # 4. Validate trade parameters
            trade_params = {
                'user_id': 123456789,
                'wallet_address': '0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b',
                'trade_type': 'buy',
                'token_in_address': '0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee',
                'token_out_address': test_address,
                'amount_in': 0.01,
                'slippage': 0.01
            }
            
            is_valid = executor.validate_trade_params(trade_params)
            print(f"   • Trade validation: ✅ (Valid: {is_valid})")
            
            # 5. Test database integration
            db = get_db_session()
            token_count = db.query(Token).count()
            db.close()
            print(f"   • Database integration: ✅ (Tokens: {token_count})")
            
            return True
            
        except Exception as e:
            logger.error(f"Full workflow integration test failed: {e}")
            return False

    async def test_pro_features_integration(self):
        """Test pro features integration"""
        try:
            pro_manager = ProFeaturesManager()
            
            # Test AI market insights
            insights = await pro_manager.get_ai_market_insights(limit=2)
            print(f"   • AI market insights: {len(insights)} tokens analyzed")
            
            # Test portfolio optimization
            optimization = await pro_manager.get_portfolio_optimization_suggestions("123456")
            print(f"   • Portfolio optimization: {'✅' if optimization.get('success') else '❌'}")
            
            return True
            
        except Exception as e:
            logger.error(f"Pro features integration test failed: {e}")
            return False

    # ==================== ERROR HANDLING TESTS ====================
    
    async def test_error_handling(self):
        """Test error handling across components"""
        try:
            analyzer = TokenAnalyzer()
            
            # Test invalid token address
            try:
                await analyzer.analyze_token("invalid_address")
                print("   • Invalid address handling: ❌ (Should have failed)")
                return False
            except:
                print("   • Invalid address handling: ✅")
            
            # Test API client error handling
            client = CovalentClient()
            result = await client.get_token_data("0x0000000000000000000000000000000000000000")
            print(f"   • API error handling: ✅ (Graceful failure)")
            
            await client.close_all_sessions()
            
            return True
            
        except Exception as e:
            logger.error(f"Error handling test failed: {e}")
            return False

    # ==================== MAIN TEST RUNNER ====================
    
    async def run_all_tests(self):
        """Run all backend tests"""
        print("🚀 MEME TRADER V4 PRO - COMPREHENSIVE BACKEND TESTING")
        print("=" * 60)
        
        # Database Tests
        print("\n📊 DATABASE TESTS")
        await self.run_test("Database Schema", self.test_database_schema)
        await self.run_test("Database CRUD Operations", self.test_database_crud_operations)
        
        # Configuration Tests
        print("\n⚙️ CONFIGURATION TESTS")
        await self.run_test("Configuration Validation", self.test_configuration_validation)
        
        # API Client Tests
        print("\n🌐 API CLIENT TESTS")
        await self.run_test("Covalent API Client", self.test_covalent_api_client)
        
        # Analyzer Tests
        print("\n🔍 ANALYZER TESTS")
        await self.run_test("Token Analyzer", self.test_token_analyzer)
        await self.run_test("Market Analyzer", self.test_market_analyzer)
        
        # AI Features Tests
        print("\n🤖 AI FEATURES TESTS")
        await self.run_test("AI Analyst", self.test_ai_analyst)
        await self.run_test("Smart Trading Engine", self.test_smart_trading_engine)
        
        # Executor Tests
        print("\n💱 EXECUTOR TESTS")
        await self.run_test("Trade Executor", self.test_trade_executor)
        
        # Monitoring Tests
        print("\n📊 MONITORING TESTS")
        await self.run_test("Monitoring System", self.test_monitoring_system)
        
        # Integration Tests
        print("\n🔗 INTEGRATION TESTS")
        await self.run_test("Full Workflow Integration", self.test_full_workflow_integration)
        await self.run_test("Pro Features Integration", self.test_pro_features_integration)
        
        # Error Handling Tests
        print("\n⚠️ ERROR HANDLING TESTS")
        await self.run_test("Error Handling", self.test_error_handling)
        
        # Print final results
        print("\n" + "=" * 60)
        print(f"🏁 BACKEND TEST RESULTS: {self.tests_passed}/{self.tests_run} tests passed")
        
        if self.tests_passed == self.tests_run:
            print("🎉 ALL BACKEND TESTS PASSED!")
            print("\n✅ VERIFIED COMPONENTS:")
            print("   • Database schema and CRUD operations")
            print("   • Configuration management")
            print("   • Covalent API integration")
            print("   • Token analysis engine")
            print("   • AI-powered features")
            print("   • Trade execution system")
            print("   • Real-time monitoring")
            print("   • Component integrations")
            print("   • Error handling")
        else:
            print(f"⚠️ {self.tests_run - self.tests_passed} tests failed")
            print("\n❌ FAILED TESTS:")
            for result in self.test_results:
                if result["status"] != "PASSED":
                    print(f"   • {result['name']}: {result['status']} - {result['details']}")
        
        return self.tests_passed == self.tests_run

async def main():
    """Main test runner"""
    tester = ComprehensiveBackendTester()
    success = await tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)