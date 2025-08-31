import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional, List
import requests
from web3 import Web3
from config import Config
from db import get_db_session, Token
from utils.api_client import CovalentClient

logger = logging.getLogger(__name__)

class TokenAnalyzer:
    """Advanced token analysis with AI scoring and honeypot detection"""
    
    def __init__(self):
        self.covalent_client = CovalentClient()
        self.web3 = Web3(Web3.HTTPProvider(Config.ETHEREUM_RPC_URL))
        
    async def analyze_token(self, token_address: str) -> Dict:
        """Comprehensive token analysis"""
        try:
            logger.info(f"Starting analysis for token: {token_address}")
            
            # Validate token address
            if not self.web3.is_address(token_address):
                raise ValueError("Invalid token address format")
            
            # Get basic token data
            token_data = await self.get_token_data(token_address)
            
            # Perform honeypot analysis
            honeypot_result = await self.check_honeypot(token_address)
            
            # Get market sentiment
            sentiment_score = await self.analyze_sentiment(token_address, token_data.get('symbol'))
            
            # Calculate AI score
            ai_score = await self.calculate_ai_score(token_data, honeypot_result, sentiment_score)
            
            # Generate recommendation
            recommendation = self.generate_recommendation(token_data, honeypot_result, ai_score, sentiment_score)
            
            # Combine all analysis results
            analysis_result = {
                **token_data,
                'is_honeypot': honeypot_result['is_honeypot'],
                'honeypot_reasons': honeypot_result.get('reasons', []),
                'sentiment_score': sentiment_score,
                'ai_score': ai_score,
                'recommendation': recommendation,
                'analysis_timestamp': datetime.utcnow().isoformat(),
                'risk_level': self.calculate_risk_level(ai_score, honeypot_result['is_honeypot'])
            }
            
            # Save analysis to database
            await self.save_analysis_to_db(token_address, analysis_result)
            
            logger.info(f"Analysis completed for {token_address}: AI Score {ai_score}/10")
            return analysis_result
            
        except Exception as e:
            logger.error(f"Token analysis failed for {token_address}: {e}")
            raise Exception(f"Analysis failed: {str(e)}")
    
    async def get_token_data(self, token_address: str) -> Dict:
        """Get basic token information"""
        try:
            # Get token data from Covalent
            token_data = await self.covalent_client.get_token_data(token_address)
            
            if not token_data:
                # Fallback: Get basic info from contract
                token_data = await self.get_token_data_from_contract(token_address)
            
            return token_data
            
        except Exception as e:
            logger.error(f"Failed to get token data for {token_address}: {e}")
            return {
                'address': token_address,
                'name': 'Unknown',
                'symbol': 'UNKNOWN',
                'decimals': 18,
                'price_usd': 0,
                'market_cap': 0,
                'liquidity_usd': 0,
                'volume_24h': 0
            }
    
    async def get_token_data_from_contract(self, token_address: str) -> Dict:
        """Get token data directly from smart contract"""
        try:
            # Basic ERC20 ABI for getting token info
            erc20_abi = [
                {
                    "constant": True,
                    "inputs": [],
                    "name": "name",
                    "outputs": [{"name": "", "type": "string"}],
                    "type": "function"
                },
                {
                    "constant": True,
                    "inputs": [],
                    "name": "symbol",
                    "outputs": [{"name": "", "type": "string"}],
                    "type": "function"
                },
                {
                    "constant": True,
                    "inputs": [],
                    "name": "decimals",
                    "outputs": [{"name": "", "type": "uint8"}],
                    "type": "function"
                },
                {
                    "constant": True,
                    "inputs": [],
                    "name": "totalSupply",
                    "outputs": [{"name": "", "type": "uint256"}],
                    "type": "function"
                }
            ]
            
            contract = self.web3.eth.contract(
                address=Web3.to_checksum_address(token_address),
                abi=erc20_abi
            )
            
            # Get token details
            name = contract.functions.name().call()
            symbol = contract.functions.symbol().call()
            decimals = contract.functions.decimals().call()
            total_supply = contract.functions.totalSupply().call()
            
            return {
                'address': token_address,
                'name': name,
                'symbol': symbol,
                'decimals': decimals,
                'total_supply': total_supply,
                'price_usd': 0,
                'market_cap': 0,
                'liquidity_usd': 0,
                'volume_24h': 0
            }
            
        except Exception as e:
            logger.error(f"Failed to get contract data: {e}")
            return {
                'address': token_address,
                'name': 'Unknown Token',
                'symbol': 'UNK',
                'decimals': 18,
                'price_usd': 0,
                'market_cap': 0,
                'liquidity_usd': 0,
                'volume_24h': 0
            }
    
    async def check_honeypot(self, token_address: str) -> Dict:
        """Check if token is a honeypot"""
        try:
            # Honeypot detection logic
            reasons = []
            is_honeypot = False
            
            # Check 1: Contract verification
            contract_verified = await self.is_contract_verified(token_address)
            if not contract_verified:
                reasons.append("Contract not verified")
            
            # Check 2: Liquidity check
            token_data = await self.covalent_client.get_token_data(token_address)
            liquidity = token_data.get('liquidity_usd', 0)
            
            if liquidity < Config.MIN_LIQUIDITY_USD:
                reasons.append(f"Low liquidity (${liquidity:,.2f})")
            
            # Check 3: Ownership concentration (placeholder)
            ownership_risk = await self.check_ownership_concentration(token_address)
            if ownership_risk:
                reasons.append("High ownership concentration")
            
            # Check 4: Trading simulation (basic check)
            trading_risk = await self.simulate_trading(token_address)
            if trading_risk:
                reasons.append("Trading restrictions detected")
                is_honeypot = True
            
            # Determine if it's a honeypot based on risk factors
            risk_score = len(reasons)
            if risk_score >= 3:
                is_honeypot = True
            
            return {
                'is_honeypot': is_honeypot,
                'risk_score': risk_score,
                'reasons': reasons,
                'liquidity_usd': liquidity
            }
            
        except Exception as e:
            logger.error(f"Honeypot check failed: {e}")
            return {
                'is_honeypot': False,
                'risk_score': 0,
                'reasons': ['Analysis failed'],
                'liquidity_usd': 0
            }
    
    async def is_contract_verified(self, token_address: str) -> bool:
        """Check if contract is verified (placeholder implementation)"""
        # In a real implementation, you'd check with Etherscan API
        return True
    
    async def check_ownership_concentration(self, token_address: str) -> bool:
        """Check for high ownership concentration (placeholder)"""
        # In a real implementation, you'd analyze top holders
        return False
    
    async def simulate_trading(self, token_address: str) -> bool:
        """Simulate trading to detect restrictions (placeholder)"""
        # In a real implementation, you'd simulate buy/sell transactions
        return False
    
    async def analyze_sentiment(self, token_address: str, symbol: Optional[str] = None) -> float:
        """Analyze market sentiment for the token"""
        try:
            if not symbol:
                return 0.5  # Neutral sentiment
            
            # For now, return a random sentiment score
            # In a real implementation, you'd analyze social media, news, etc.
            import random
            sentiment_score = random.uniform(0.2, 0.8)
            
            logger.info(f"Sentiment analysis for {symbol}: {sentiment_score:.2f}")
            return sentiment_score
            
        except Exception as e:
            logger.error(f"Sentiment analysis failed: {e}")
            return 0.5  # Neutral on error
    
    async def calculate_ai_score(self, token_data: Dict, honeypot_result: Dict, sentiment_score: float) -> float:
        """Calculate AI-powered score for the token"""
        try:
            score = 5.0  # Base score
            
            # Liquidity factor (0-2 points)
            liquidity = token_data.get('liquidity_usd', 0)
            if liquidity > 100000:
                score += 2
            elif liquidity > 50000:
                score += 1.5
            elif liquidity > 10000:
                score += 1
            elif liquidity > 1000:
                score += 0.5
            
            # Market cap factor (0-1 points)
            market_cap = token_data.get('market_cap', 0)
            if market_cap > 1000000:
                score += 1
            elif market_cap > 100000:
                score += 0.5
            
            # Volume factor (0-1 points)
            volume = token_data.get('volume_24h', 0)
            if volume > 50000:
                score += 1
            elif volume > 10000:
                score += 0.5
            
            # Honeypot penalty (-3 to 0 points)
            if honeypot_result['is_honeypot']:
                score -= 3
            else:
                score -= honeypot_result['risk_score'] * 0.5
            
            # Sentiment factor (-1 to +1 points)
            sentiment_factor = (sentiment_score - 0.5) * 2
            score += sentiment_factor
            
            # Ensure score is between 0 and 10
            score = max(0, min(10, score))
            
            return round(score, 2)
            
        except Exception as e:
            logger.error(f"AI score calculation failed: {e}")
            return 5.0  # Return neutral score on error
    
    def calculate_risk_level(self, ai_score: float, is_honeypot: bool) -> str:
        """Calculate risk level based on analysis"""
        if is_honeypot:
            return "HIGH"
        elif ai_score >= 7:
            return "LOW"
        elif ai_score >= 5:
            return "MEDIUM"
        else:
            return "HIGH"
    
    def generate_recommendation(self, token_data: Dict, honeypot_result: Dict, ai_score: float, sentiment_score: float) -> str:
        """Generate trading recommendation"""
        try:
            if honeypot_result['is_honeypot']:
                return "❌ AVOID - Potential honeypot detected. High risk of loss."
            
            if ai_score >= 8:
                return "🟢 STRONG BUY - Excellent fundamentals and high AI score."
            elif ai_score >= 6.5:
                return "🟡 BUY - Good fundamentals, consider entry with proper risk management."
            elif ai_score >= 5:
                return "🟡 HOLD/WATCH - Neutral signals, monitor for better entry."
            elif ai_score >= 3:
                return "🔴 WEAK - Poor fundamentals, high risk investment."
            else:
                return "❌ AVOID - Very poor fundamentals, not recommended."
                
        except Exception as e:
            logger.error(f"Recommendation generation failed: {e}")
            return "⚠️ ANALYSIS INCOMPLETE - Unable to generate recommendation."
    
    async def save_analysis_to_db(self, token_address: str, analysis_result: Dict):
        """Save analysis results to database"""
        db = get_db_session()
        try:
            token = db.query(Token).filter(Token.address == token_address).first()
            if not token:
                token = Token(address=token_address)
                db.add(token)
            
            # Update token with analysis results
            token.name = analysis_result.get('name')
            token.symbol = analysis_result.get('symbol')
            token.decimals = analysis_result.get('decimals')
            token.price_usd = analysis_result.get('price_usd')
            token.market_cap = analysis_result.get('market_cap')
            token.liquidity_usd = analysis_result.get('liquidity_usd')
            token.volume_24h = analysis_result.get('volume_24h')
            token.is_honeypot = analysis_result.get('is_honeypot')
            token.ai_score = analysis_result.get('ai_score')
            token.sentiment_score = analysis_result.get('sentiment_score')
            token.last_analyzed = datetime.utcnow()
            token.updated_at = datetime.utcnow()
            
            db.commit()
            logger.info(f"Analysis saved to database for {token_address}")
            
        except Exception as e:
            logger.error(f"Failed to save analysis to database: {e}")
        finally:
            db.close()

class MarketAnalyzer:
    """Market-wide analysis and trending tokens"""
    
    def __init__(self):
        self.covalent_client = CovalentClient()
        self.token_analyzer = TokenAnalyzer()
    
    async def get_trending_tokens(self, limit: int = 10) -> List[Dict]:
        """Get trending tokens based on volume and price changes"""
        try:
            # Placeholder implementation
            # In a real implementation, you'd fetch from DEX aggregators
            trending_tokens = []
            
            # Sample trending tokens (replace with real data)
            sample_tokens = [
                "0xA0b86a33E6441ba0BB7e1ae5E3e7BAaD5D1D7e3c",  # Placeholder addresses
                "0xB1c4d0F4C1A5E3D7B8a9A0C2E3F4A5B6C7D8E9F0"
            ]
            
            for token_address in sample_tokens[:limit]:
                try:
                    analysis = await self.token_analyzer.analyze_token(token_address)
                    trending_tokens.append(analysis)
                except Exception as e:
                    logger.error(f"Failed to analyze trending token {token_address}: {e}")
            
            return trending_tokens
            
        except Exception as e:
            logger.error(f"Failed to get trending tokens: {e}")
            return []
    
    async def analyze_market_conditions(self) -> Dict:
        """Analyze overall market conditions"""
        try:
            # Placeholder implementation
            return {
                'market_sentiment': 'neutral',
                'total_volume_24h': 0,
                'active_tokens': 0,
                'trending_up': 0,
                'trending_down': 0,
                'recommendation': 'Monitor market conditions'
            }
        except Exception as e:
            logger.error(f"Market analysis failed: {e}")
            return {}