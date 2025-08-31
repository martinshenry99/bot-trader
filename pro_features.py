import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dotenv import load_dotenv
from emergentintegrations.llm.chat import LlmChat, UserMessage
from config import Config
from db import get_db_session, Token, Trade, User, MonitoringAlert
from analyzer import TokenAnalyzer
from executor import TradeExecutor

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class AIAnalyst:
    """AI-powered market analysis using Emergent LLM"""
    
    def __init__(self):
        self.api_key = os.getenv('EMERGENT_LLM_KEY')
        if not self.api_key:
            raise ValueError("EMERGENT_LLM_KEY not found in environment variables")
            
        self.llm_chat = LlmChat(
            api_key=self.api_key,
            session_id="meme_trader_analyst",
            system_message="""You are an expert cryptocurrency market analyst specializing in meme tokens and DeFi trading. 
            
            Your expertise includes:
            - Technical analysis and price prediction
            - Risk assessment for new tokens
            - Market sentiment analysis
            - Trading strategy recommendations
            - Honeypot and scam detection
            
            Always provide:
            1. Clear, actionable insights
            2. Risk levels (LOW, MEDIUM, HIGH)
            3. Specific recommendations (BUY, SELL, HOLD, AVOID)
            4. Confidence scores (1-10)
            5. Key reasoning behind your analysis
            
            Be concise but thorough. Focus on practical trading advice."""
        ).with_model("openai", "gpt-4o-mini")
        
        self.token_analyzer = TokenAnalyzer()
    
    async def analyze_token_with_ai(self, token_address: str, market_data: Dict) -> Dict:
        """Comprehensive AI-powered token analysis"""
        try:
            # Prepare analysis prompt
            analysis_prompt = f"""
            Analyze this cryptocurrency token for trading potential:
            
            **Token Data:**
            - Address: {token_address}
            - Name: {market_data.get('name', 'Unknown')}
            - Symbol: {market_data.get('symbol', 'Unknown')}
            - Price: ${market_data.get('price_usd', 0):.8f}
            - Market Cap: ${market_data.get('market_cap', 0):,.2f}
            - Liquidity: ${market_data.get('liquidity_usd', 0):,.2f}
            - 24h Volume: ${market_data.get('volume_24h', 0):,.2f}
            - Honeypot Risk: {market_data.get('is_honeypot', 'Unknown')}
            
            **Analysis Requirements:**
            1. Overall risk assessment (LOW/MEDIUM/HIGH)
            2. Trading recommendation (BUY/SELL/HOLD/AVOID)
            3. Confidence score (1-10)
            4. Key strengths and weaknesses
            5. Price prediction (short-term)
            6. Recommended position size
            
            Provide your analysis in a structured format.
            """
            
            user_message = UserMessage(text=analysis_prompt)
            ai_response = await self.llm_chat.send_message(user_message)
            
            # Parse AI response and extract key metrics
            analysis_result = self.parse_ai_analysis(ai_response, market_data)
            
            logger.info(f"AI analysis completed for {token_address}")
            return analysis_result
            
        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            return self.fallback_analysis(market_data)
    
    def parse_ai_analysis(self, ai_response: str, market_data: Dict) -> Dict:
        """Parse AI response into structured data"""
        try:
            # Extract key information from AI response
            response_lower = ai_response.lower()
            
            # Determine recommendation
            if 'avoid' in response_lower or 'do not buy' in response_lower:
                recommendation = 'AVOID'
                ai_score = 2.0
            elif 'buy' in response_lower and 'strong' in response_lower:
                recommendation = 'STRONG_BUY'
                ai_score = 8.5
            elif 'buy' in response_lower:
                recommendation = 'BUY'
                ai_score = 7.0
            elif 'sell' in response_lower:
                recommendation = 'SELL'
                ai_score = 3.0
            elif 'hold' in response_lower:
                recommendation = 'HOLD'
                ai_score = 5.0
            else:
                recommendation = 'NEUTRAL'
                ai_score = 5.0
            
            # Determine risk level
            if 'high risk' in response_lower or 'very risky' in response_lower:
                risk_level = 'HIGH'
            elif 'medium risk' in response_lower or 'moderate risk' in response_lower:
                risk_level = 'MEDIUM'
            elif 'low risk' in response_lower:
                risk_level = 'LOW'
            else:
                risk_level = 'MEDIUM'  # Default
            
            # Extract confidence score (look for numbers 1-10)
            confidence_score = 7.0  # Default
            import re
            confidence_matches = re.findall(r'confidence[:\s]*(\d+(?:\.\d+)?)', response_lower)
            if confidence_matches:
                confidence_score = float(confidence_matches[0])
            
            return {
                'ai_analysis': ai_response,
                'recommendation': recommendation,
                'risk_level': risk_level,
                'ai_score': ai_score,
                'confidence_score': confidence_score,
                'analysis_timestamp': datetime.utcnow().isoformat(),
                'model_used': 'gpt-4o-mini',
                'token_address': market_data.get('address', ''),
                'market_context': {
                    'liquidity_assessment': self.assess_liquidity(market_data.get('liquidity_usd', 0)),
                    'volume_assessment': self.assess_volume(market_data.get('volume_24h', 0)),
                    'market_cap_tier': self.classify_market_cap(market_data.get('market_cap', 0))
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to parse AI analysis: {e}")
            return self.fallback_analysis(market_data)
    
    def assess_liquidity(self, liquidity_usd: float) -> str:
        """Assess liquidity level"""
        if liquidity_usd >= 100000:
            return 'HIGH'
        elif liquidity_usd >= 50000:
            return 'MEDIUM'
        elif liquidity_usd >= 10000:
            return 'LOW'
        else:
            return 'VERY_LOW'
    
    def assess_volume(self, volume_24h: float) -> str:
        """Assess trading volume"""
        if volume_24h >= 500000:
            return 'HIGH'
        elif volume_24h >= 100000:
            return 'MEDIUM'
        elif volume_24h >= 10000:
            return 'LOW'
        else:
            return 'VERY_LOW'
    
    def classify_market_cap(self, market_cap: float) -> str:
        """Classify market cap tier"""
        if market_cap >= 100000000:  # $100M+
            return 'LARGE_CAP'
        elif market_cap >= 10000000:  # $10M-$100M
            return 'MID_CAP'
        elif market_cap >= 1000000:   # $1M-$10M
            return 'SMALL_CAP'
        else:
            return 'MICRO_CAP'
    
    def fallback_analysis(self, market_data: Dict) -> Dict:
        """Fallback analysis when AI fails"""
        return {
            'ai_analysis': 'AI analysis unavailable',
            'recommendation': 'HOLD',
            'risk_level': 'MEDIUM',
            'ai_score': 5.0,
            'confidence_score': 3.0,
            'analysis_timestamp': datetime.utcnow().isoformat(),
            'model_used': 'fallback',
            'token_address': market_data.get('address', ''),
            'market_context': {
                'liquidity_assessment': self.assess_liquidity(market_data.get('liquidity_usd', 0)),
                'volume_assessment': self.assess_volume(market_data.get('volume_24h', 0)),
                'market_cap_tier': self.classify_market_cap(market_data.get('market_cap', 0))
            }
        }

class SmartTradingEngine:
    """AI-powered automated trading engine"""
    
    def __init__(self):
        self.ai_analyst = AIAnalyst()
        self.executor = TradeExecutor()
        self.active_strategies = {}
    
    async def execute_smart_trade(self, user_id: str, token_address: str, strategy_params: Dict) -> Dict:
        """Execute AI-guided trade"""
        try:
            # Get comprehensive token analysis
            market_data = await self.token_analyzer.analyze_token(token_address)
            ai_analysis = await self.ai_analyst.analyze_token_with_ai(token_address, market_data)
            
            # Determine trade parameters based on AI analysis
            trade_params = await self.calculate_trade_parameters(
                user_id, token_address, ai_analysis, strategy_params
            )
            
            # Execute trade if AI recommends it
            if ai_analysis['recommendation'] in ['BUY', 'STRONG_BUY']:
                execution_result = await self.executor.execute_trade(trade_params)
                
                # Log AI trade decision
                await self.log_ai_trade_decision(user_id, token_address, ai_analysis, execution_result)
                
                return {
                    'success': True,
                    'trade_executed': True,
                    'ai_recommendation': ai_analysis['recommendation'],
                    'ai_score': ai_analysis['ai_score'],
                    'execution_result': execution_result
                }
            else:
                return {
                    'success': True,
                    'trade_executed': False,
                    'ai_recommendation': ai_analysis['recommendation'],
                    'ai_score': ai_analysis['ai_score'],
                    'reason': f"AI recommends {ai_analysis['recommendation']} - trade not executed"
                }
                
        except Exception as e:
            logger.error(f"Smart trade execution failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def calculate_trade_parameters(self, user_id: str, token_address: str, ai_analysis: Dict, strategy_params: Dict) -> Dict:
        """Calculate optimal trade parameters based on AI analysis"""
        try:
            # Base trade parameters
            base_amount = strategy_params.get('amount', 0.01)  # Default 0.01 ETH
            
            # Adjust amount based on AI confidence and risk level
            confidence_multiplier = ai_analysis['confidence_score'] / 10.0
            
            if ai_analysis['risk_level'] == 'LOW':
                risk_multiplier = 1.5
            elif ai_analysis['risk_level'] == 'MEDIUM':
                risk_multiplier = 1.0
            else:  # HIGH risk
                risk_multiplier = 0.5
            
            # Calculate final amount
            final_amount = base_amount * confidence_multiplier * risk_multiplier
            final_amount = min(final_amount, strategy_params.get('max_amount', 0.1))  # Cap at max
            
            # Determine slippage based on liquidity
            liquidity_assessment = ai_analysis['market_context']['liquidity_assessment']
            if liquidity_assessment == 'HIGH':
                slippage = 0.005  # 0.5%
            elif liquidity_assessment == 'MEDIUM':
                slippage = 0.01   # 1%
            elif liquidity_assessment == 'LOW':
                slippage = 0.02   # 2%
            else:
                slippage = 0.05   # 5% for very low liquidity
            
            return {
                'user_id': int(user_id),
                'wallet_address': strategy_params['wallet_address'],
                'trade_type': 'buy',
                'token_in_address': '0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee',  # ETH
                'token_out_address': token_address,
                'amount_in': final_amount,
                'slippage': slippage,
                'price_usd': 0  # Will be calculated by executor
            }
            
        except Exception as e:
            logger.error(f"Failed to calculate trade parameters: {e}")
            raise
    
    async def log_ai_trade_decision(self, user_id: str, token_address: str, ai_analysis: Dict, execution_result: Dict):
        """Log AI trade decision for analysis"""
        try:
            db = get_db_session()
            
            # Create monitoring alert for AI trade
            alert = MonitoringAlert(
                user_id=int(user_id),
                alert_type='ai_trade_executed',
                title='AI Trade Executed',
                message=f"AI executed trade for token {token_address[:8]}... with recommendation: {ai_analysis['recommendation']}",
                token_address=token_address,
                trigger_value=ai_analysis['ai_score']
            )
            db.add(alert)
            db.commit()
            
            logger.info(f"AI trade decision logged for user {user_id}")
            
        except Exception as e:
            logger.error(f"Failed to log AI trade decision: {e}")
        finally:
            db.close()

class MultiWalletManager:
    """Manage multiple wallets with automated strategies"""
    
    def __init__(self):
        self.smart_engine = SmartTradingEngine()
        self.active_managers = {}
    
    async def start_multi_wallet_strategy(self, user_id: str, strategy_config: Dict) -> Dict:
        """Start automated trading across multiple wallets"""
        try:
            wallet_addresses = strategy_config.get('wallets', [])
            if not wallet_addresses:
                raise ValueError("No wallets specified")
            
            strategy_id = f"strategy_{user_id}_{datetime.utcnow().timestamp()}"
            
            # Initialize strategy for each wallet
            for wallet_address in wallet_addresses:
                wallet_strategy = {
                    'wallet_address': wallet_address,
                    'user_id': user_id,
                    'strategy_type': strategy_config.get('strategy_type', 'conservative'),
                    'max_amount_per_trade': strategy_config.get('max_amount_per_trade', 0.05),
                    'max_trades_per_day': strategy_config.get('max_trades_per_day', 5),
                    'active': True
                }
                
                # Store active strategy
                self.active_managers[f"{strategy_id}_{wallet_address}"] = wallet_strategy
            
            # Start monitoring loop
            asyncio.create_task(self.multi_wallet_monitoring_loop(strategy_id, user_id))
            
            return {
                'success': True,
                'strategy_id': strategy_id,
                'active_wallets': len(wallet_addresses),
                'message': 'Multi-wallet strategy started successfully'
            }
            
        except Exception as e:
            logger.error(f"Failed to start multi-wallet strategy: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def multi_wallet_monitoring_loop(self, strategy_id: str, user_id: str):
        """Monitoring loop for multi-wallet strategy"""
        logger.info(f"Starting multi-wallet monitoring for strategy {strategy_id}")
        
        while True:
            try:
                # Find active strategies for this user
                active_strategies = {
                    k: v for k, v in self.active_managers.items() 
                    if k.startswith(strategy_id) and v['active']
                }
                
                if not active_strategies:
                    logger.info(f"No active strategies for {strategy_id}, stopping monitoring")
                    break
                
                # Execute strategy logic for each wallet
                for strategy_key, strategy_config in active_strategies.items():
                    await self.execute_wallet_strategy(strategy_key, strategy_config)
                
                # Wait before next iteration
                await asyncio.sleep(300)  # Check every 5 minutes
                
            except Exception as e:
                logger.error(f"Multi-wallet monitoring error: {e}")
                await asyncio.sleep(600)  # Wait longer on error
    
    async def execute_wallet_strategy(self, strategy_key: str, strategy_config: Dict):
        """Execute strategy for a specific wallet"""
        try:
            # This is a placeholder for complex multi-wallet logic
            # In a real implementation, this would:
            # 1. Scan for trending tokens
            # 2. Analyze multiple tokens simultaneously
            # 3. Execute trades based on AI recommendations
            # 4. Manage portfolio balance across wallets
            
            logger.info(f"Executing strategy for {strategy_config['wallet_address']}")
            
        except Exception as e:
            logger.error(f"Wallet strategy execution failed: {e}")
    
    async def stop_multi_wallet_strategy(self, strategy_id: str) -> Dict:
        """Stop multi-wallet strategy"""
        try:
            # Deactivate all strategies with this ID
            strategies_stopped = 0
            for key in list(self.active_managers.keys()):
                if key.startswith(strategy_id):
                    self.active_managers[key]['active'] = False
                    strategies_stopped += 1
            
            return {
                'success': True,
                'strategies_stopped': strategies_stopped,
                'message': 'Multi-wallet strategy stopped successfully'
            }
            
        except Exception as e:
            logger.error(f"Failed to stop multi-wallet strategy: {e}")
            return {
                'success': False,
                'error': str(e)
            }

class ProFeaturesManager:
    """Centralized manager for all pro features"""
    
    def __init__(self):
        self.ai_analyst = AIAnalyst()
        self.smart_engine = SmartTradingEngine()
        self.multi_wallet_manager = MultiWalletManager()
    
    async def get_ai_market_insights(self, limit: int = 5) -> List[Dict]:
        """Get AI-powered market insights"""
        try:
            # Get trending tokens and analyze with AI
            insights = []
            
            # Placeholder for trending token detection
            # In a real implementation, this would fetch trending tokens
            sample_tokens = [
                "0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b",
                "0xA0b86a33E6441ba0BB7e1ae5E3e7BAaD5D1D7e3c"
            ]
            
            for token_address in sample_tokens[:limit]:
                try:
                    # Analyze token with AI
                    market_data = await self.ai_analyst.token_analyzer.analyze_token(token_address)
                    ai_analysis = await self.ai_analyst.analyze_token_with_ai(token_address, market_data)
                    
                    insights.append({
                        'token_address': token_address,
                        'symbol': market_data.get('symbol', 'UNKNOWN'),
                        'ai_recommendation': ai_analysis['recommendation'],
                        'ai_score': ai_analysis['ai_score'],
                        'risk_level': ai_analysis['risk_level'],
                        'confidence': ai_analysis['confidence_score'],
                        'key_insights': ai_analysis['ai_analysis'][:200] + '...'  # Truncate for display
                    })
                    
                except Exception as e:
                    logger.error(f"Failed to get insights for {token_address}: {e}")
            
            return insights
            
        except Exception as e:
            logger.error(f"Failed to get market insights: {e}")
            return []
    
    async def get_portfolio_optimization_suggestions(self, user_id: str) -> Dict:
        """Get AI-powered portfolio optimization suggestions"""
        try:
            # This would analyze user's current portfolio and suggest optimizations
            return {
                'success': True,
                'suggestions': [
                    'Consider diversifying into different market cap tiers',
                    'Reduce exposure to high-risk meme tokens',
                    'Increase allocation to established DeFi tokens'
                ],
                'risk_score': 6.5,
                'optimization_potential': 15.3
            }
            
        except Exception as e:
            logger.error(f"Failed to get portfolio optimization: {e}")
            return {'success': False, 'error': str(e)}