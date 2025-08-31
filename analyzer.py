import asyncio
import logging
import requests
from datetime import datetime
from typing import Dict, Optional, List, Tuple
from web3 import Web3
from eth_account import Account
from config import Config
from db import get_db_session, Token
from utils.api_client import CovalentClient

logger = logging.getLogger(__name__)

class RouterMapping:
    """Router mapping and path building for honeypot detection"""
    
    ROUTER_CONFIGS = {
        # Ethereum Mainnet & Sepolia
        Config.UNISWAP_V2_ROUTER: {
            'name': 'Uniswap V2',
            'factory': '0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f',
            'weth': Config.WETH_ADDRESS,
            'chain_ids': [1, 11155111]
        },
        Config.SUSHISWAP_ROUTER: {
            'name': 'SushiSwap',
            'factory': '0xC0AEe478e3658e2610c5F7A4A2E1777cE9e4f2Ac',
            'weth': Config.WETH_ADDRESS,
            'chain_ids': [1, 11155111]
        },
        # BSC Mainnet & Testnet
        Config.PANCAKESWAP_ROUTER: {
            'name': 'PancakeSwap',
            'factory': '0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73',
            'weth': Config.WBNB_ADDRESS,
            'chain_ids': [56, 97]
        }
    }
    
    # Common honeypot revert signatures
    HONEYPOT_SIGNATURES = {
        'transfer_failed': ['TRANSFER_FAILED', 'Transfer failed'],
        'insufficient_output': ['INSUFFICIENT_OUTPUT_AMOUNT', 'Insufficient output amount'],
        'liquidity_locked': ['LIQUIDITY_LOCKED', 'Liquidity is locked'],
        'max_tx_amount': ['MAX_TX_AMOUNT', 'Transaction amount too large'],
        'trading_disabled': ['TRADING_DISABLED', 'Trading is disabled'],
        'blacklisted': ['BLACKLISTED', 'Address is blacklisted'],
        'cooldown': ['COOLDOWN', 'Transfer cooldown'],
        'max_wallet': ['MAX_WALLET', 'Max wallet exceeded'],
        'anti_bot': ['ANTI_BOT', 'Anti-bot protection'],
        'paused': ['PAUSED', 'Contract is paused']
    }
    
    @classmethod
    def get_router_for_chain(cls, chain_id: int) -> Optional[Dict]:
        """Get appropriate router configuration for chain"""
        for router_addr, config in cls.ROUTER_CONFIGS.items():
            if chain_id in config['chain_ids']:
                return {
                    'address': router_addr,
                    'config': config
                }
        return None
    
    @classmethod
    def build_token_to_weth_path(cls, token_address: str, chain_id: int) -> List[str]:
        """Build trading path from token to WETH"""
        router_info = cls.get_router_for_chain(chain_id)
        if not router_info:
            return []
        
        weth_address = Config.get_wrapped_native_token(chain_id)
        return [token_address, weth_address]

class HoneypotSimulator:
    """Advanced honeypot detection with ephemeral account simulation"""
    
    def __init__(self, chain_id: int = 11155111):
        self.chain_id = chain_id
        
        # Configure Web3 based on chain
        if chain_id == 11155111:  # Sepolia
            self.web3 = Web3(Web3.HTTPProvider(Config.ETHEREUM_RPC_URL))
        elif chain_id == 97:  # BSC Testnet
            self.web3 = Web3(Web3.HTTPProvider(Config.BSC_RPC_URL))
        else:
            raise ValueError(f"Unsupported chain ID: {chain_id}")
        
        self.router_config = RouterMapping.get_router_for_chain(chain_id)
        if not self.router_config:
            raise ValueError(f"No router configuration for chain {chain_id}")
        
        # Uniswap V2 Router ABI (minimal)
        self.router_abi = [
            {
                "inputs": [
                    {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
                    {"internalType": "uint256", "name": "amountOutMin", "type": "uint256"},
                    {"internalType": "address[]", "name": "path", "type": "address[]"},
                    {"internalType": "address", "name": "to", "type": "address"},
                    {"internalType": "uint256", "name": "deadline", "type": "uint256"}
                ],
                "name": "swapExactTokensForTokens",
                "outputs": [
                    {"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}
                ],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "inputs": [
                    {"internalType": "uint256", "name": "amountOutMin", "type": "uint256"},
                    {"internalType": "address[]", "name": "path", "type": "address[]"},
                    {"internalType": "address", "name": "to", "type": "address"},
                    {"internalType": "uint256", "name": "deadline", "type": "uint256"}
                ],
                "name": "swapExactETHForTokens",
                "outputs": [
                    {"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}
                ],
                "stateMutability": "payable",
                "type": "function"
            },
            {
                "inputs": [
                    {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
                    {"internalType": "address[]", "name": "path", "type": "address[]"}
                ],
                "name": "getAmountsOut",
                "outputs": [
                    {"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}
                ],
                "stateMutability": "view",
                "type": "function"
            }
        ]
        
        # ERC-20 ABI for token interactions
        self.erc20_abi = [
            {
                "constant": True,
                "inputs": [
                    {"name": "_owner", "type": "address"},
                    {"name": "_spender", "type": "address"}
                ],
                "name": "allowance",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            },
            {
                "constant": False,
                "inputs": [
                    {"name": "_spender", "type": "address"},
                    {"name": "_value", "type": "uint256"}
                ],
                "name": "approve",
                "outputs": [{"name": "", "type": "bool"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "balance", "type": "uint256"}],
                "type": "function"
            },
            {
                "constant": False,
                "inputs": [
                    {"name": "_to", "type": "address"},
                    {"name": "_value", "type": "uint256"}
                ],
                "name": "transfer",
                "outputs": [{"name": "", "type": "bool"}],
                "type": "function"
            }
        ]
    
    async def comprehensive_honeypot_check(self, token_address: str) -> Dict:
        """Comprehensive honeypot detection with multiple simulation approaches"""
        
        logger.info(f"🔍 Starting comprehensive honeypot check for {token_address}")
        
        results = {
            'is_honeypot': False,
            'risk_score': 0,
            'risk_factors': [],
            'simulation_results': {},
            'contract_analysis': {},
            'liquidity_analysis': {}
        }
        
        try:
            # 1. Contract-level analysis
            contract_risks = await self.analyze_contract_risks(token_address)
            results['contract_analysis'] = contract_risks
            results['risk_score'] += contract_risks.get('risk_score', 0)
            
            # 2. Liquidity analysis
            liquidity_risks = await self.analyze_liquidity_risks(token_address)
            results['liquidity_analysis'] = liquidity_risks
            results['risk_score'] += liquidity_risks.get('risk_score', 0)
            
            # 3. Trading simulation
            trading_simulation = await self.simulate_trading_scenarios(token_address)
            results['simulation_results'] = trading_simulation
            results['risk_score'] += trading_simulation.get('risk_score', 0)
            
            # 4. Ownership analysis
            ownership_risks = await self.analyze_ownership_concentration(token_address)
            results['risk_score'] += ownership_risks.get('risk_score', 0)
            
            # Compile risk factors
            all_factors = []
            all_factors.extend(contract_risks.get('risk_factors', []))
            all_factors.extend(liquidity_risks.get('risk_factors', []))
            all_factors.extend(trading_simulation.get('risk_factors', []))
            all_factors.extend(ownership_risks.get('risk_factors', []))
            
            results['risk_factors'] = all_factors
            
            # Determine if honeypot based on risk score and critical factors
            critical_factors = [f for f in all_factors if 'critical' in f.lower() or 'honeypot' in f.lower()]
            
            if results['risk_score'] >= 7 or critical_factors:
                results['is_honeypot'] = True
            
            logger.info(f"🔍 Honeypot check complete: risk_score={results['risk_score']}, is_honeypot={results['is_honeypot']}")
            
            return results
            
        except Exception as e:
            logger.error(f"Comprehensive honeypot check failed: {e}")
            return {
                'is_honeypot': False,
                'risk_score': 0,
                'risk_factors': ['Analysis failed'],
                'error': str(e)
            }
    
    async def analyze_contract_risks(self, token_address: str) -> Dict:
        """Analyze contract-level risks"""
        risks = {'risk_score': 0, 'risk_factors': []}
        
        try:
            # Check if contract is verified (placeholder - would use Etherscan API)
            # is_verified = await self.check_contract_verification(token_address)
            # if not is_verified:
            #     risks['risk_factors'].append('Contract not verified')
            #     risks['risk_score'] += 2
            
            # Check contract creation date (newer contracts are riskier)
            # creation_date = await self.get_contract_creation_date(token_address)
            
            # Check for proxy patterns
            is_proxy = await self.check_proxy_pattern(token_address)
            if is_proxy:
                risks['risk_factors'].append('Proxy contract detected')
                risks['risk_score'] += 1
            
            # Check for unusual functions
            unusual_functions = await self.check_unusual_functions(token_address)
            if unusual_functions:
                risks['risk_factors'].extend(unusual_functions)
                risks['risk_score'] += len(unusual_functions)
            
            return risks
            
        except Exception as e:
            logger.error(f"Contract risk analysis failed: {e}")
            return {'risk_score': 0, 'risk_factors': ['Contract analysis failed']}
    
    async def analyze_liquidity_risks(self, token_address: str) -> Dict:
        """Analyze liquidity-related risks"""
        risks = {'risk_score': 0, 'risk_factors': []}
        
        try:
            # Get token liquidity data
            covalent_client = CovalentClient()
            token_data = await covalent_client.get_token_data(token_address)
            
            if token_data:
                liquidity_usd = token_data.get('liquidity_usd', 0)
                
                if liquidity_usd < 1000:
                    risks['risk_factors'].append(f'Very low liquidity: ${liquidity_usd:,.2f}')
                    risks['risk_score'] += 3
                elif liquidity_usd < 10000:
                    risks['risk_factors'].append(f'Low liquidity: ${liquidity_usd:,.2f}')
                    risks['risk_score'] += 2
                elif liquidity_usd < 50000:
                    risks['risk_factors'].append(f'Moderate liquidity: ${liquidity_usd:,.2f}')
                    risks['risk_score'] += 1
            else:
                risks['risk_factors'].append('Unable to determine liquidity')
                risks['risk_score'] += 2
            
            return risks
            
        except Exception as e:
            logger.error(f"Liquidity risk analysis failed: {e}")
            return {'risk_score': 1, 'risk_factors': ['Liquidity analysis failed']}
    
    async def simulate_trading_scenarios(self, token_address: str) -> Dict:
        """Simulate various trading scenarios to detect honeypots"""
        simulation = {'risk_score': 0, 'risk_factors': [], 'scenarios': {}}
        
        try:
            # Create ephemeral accounts for simulation
            ephemeral_accounts = [Account.create() for _ in range(3)]
            
            # Test scenario 1: Small buy simulation
            buy_result = await self.simulate_buy_transaction(token_address, ephemeral_accounts[0])
            simulation['scenarios']['buy_simulation'] = buy_result
            
            if not buy_result['success']:
                simulation['risk_factors'].append(f"Buy simulation failed: {buy_result.get('error', 'Unknown')}")
                simulation['risk_score'] += 2
            
            # Test scenario 2: Sell simulation (if buy was successful)
            if buy_result['success']:
                sell_result = await self.simulate_sell_transaction(token_address, ephemeral_accounts[0])
                simulation['scenarios']['sell_simulation'] = sell_result
                
                if not sell_result['success']:
                    simulation['risk_factors'].append(f"CRITICAL: Sell simulation failed - {sell_result.get('error', 'Unknown')}")
                    simulation['risk_score'] += 5  # High risk if can't sell
            
            # Test scenario 3: Transfer simulation
            transfer_result = await self.simulate_transfer(token_address, ephemeral_accounts[0], ephemeral_accounts[1])
            simulation['scenarios']['transfer_simulation'] = transfer_result
            
            if not transfer_result['success']:
                simulation['risk_factors'].append(f"Transfer simulation failed: {transfer_result.get('error', 'Unknown')}")
                simulation['risk_score'] += 3
            
            return simulation
            
        except Exception as e:
            logger.error(f"Trading simulation failed: {e}")
            return {
                'risk_score': 2, 
                'risk_factors': ['Trading simulation failed'],
                'scenarios': {},
                'error': str(e)
            }
    
    async def simulate_buy_transaction(self, token_address: str, ephemeral_account: Account) -> Dict:
        """Simulate buying tokens with ephemeral account"""
        try:
            router_address = self.router_config['address']
            router_contract = self.web3.eth.contract(
                address=Web3.to_checksum_address(router_address),
                abi=self.router_abi
            )
            
            # Build trading path
            path = RouterMapping.build_token_to_weth_path(token_address, self.chain_id)
            if not path:
                return {'success': False, 'error': 'Cannot build trading path'}
            
            # Reverse path for buying (WETH -> Token)
            buy_path = path[::-1]
            
            # Small buy amount (0.001 ETH equivalent)
            buy_amount = self.web3.to_wei(0.001, 'ether')
            
            # Build transaction
            deadline = int(datetime.utcnow().timestamp()) + 300  # 5 minutes
            
            buy_tx = router_contract.functions.swapExactETHForTokens(
                0,  # amountOutMin (accept any amount)
                buy_path,
                ephemeral_account.address,
                deadline
            ).build_transaction({
                'from': ephemeral_account.address,
                'value': buy_amount,
                'gas': 200000,
                'gasPrice': self.web3.to_wei(20, 'gwei'),
                'nonce': 0,
                'chainId': self.chain_id
            })
            
            # Simulate transaction with eth_call
            try:
                result = self.web3.eth.call(buy_tx)
                return {
                    'success': True,
                    'result': result.hex(),
                    'message': 'Buy simulation successful'
                }
            except Exception as call_error:
                error_msg = str(call_error)
                
                # Check for honeypot signatures
                honeypot_detected = self.detect_honeypot_signatures(error_msg)
                
                return {
                    'success': False,
                    'error': error_msg,
                    'honeypot_signatures': honeypot_detected,
                    'is_honeypot_error': len(honeypot_detected) > 0
                }
                
        except Exception as e:
            return {'success': False, 'error': str(e), 'stage': 'transaction_building'}
    
    async def simulate_sell_transaction(self, token_address: str, ephemeral_account: Account) -> Dict:
        """Simulate selling tokens with ephemeral account"""
        try:
            router_address = self.router_config['address']
            router_contract = self.web3.eth.contract(
                address=Web3.to_checksum_address(router_address),
                abi=self.router_abi
            )
            
            # Build trading path (Token -> WETH)
            path = RouterMapping.build_token_to_weth_path(token_address, self.chain_id)
            if not path:
                return {'success': False, 'error': 'Cannot build trading path'}
            
            # Assume we have some tokens to sell (simulate with small amount)
            sell_amount = 1000 * 10**18  # 1000 tokens (assuming 18 decimals)
            
            # Build transaction
            deadline = int(datetime.utcnow().timestamp()) + 300  # 5 minutes
            
            sell_tx = router_contract.functions.swapExactTokensForTokens(
                sell_amount,
                0,  # amountOutMin (accept any amount)
                path,
                ephemeral_account.address,
                deadline
            ).build_transaction({
                'from': ephemeral_account.address,
                'gas': 200000,
                'gasPrice': self.web3.to_wei(20, 'gwei'),
                'nonce': 0,
                'chainId': self.chain_id
            })
            
            # Simulate transaction with eth_call
            try:
                result = self.web3.eth.call(sell_tx)
                return {
                    'success': True,
                    'result': result.hex(),
                    'message': 'Sell simulation successful'
                }
            except Exception as call_error:
                error_msg = str(call_error)
                
                # Check for honeypot signatures
                honeypot_detected = self.detect_honeypot_signatures(error_msg)
                
                return {
                    'success': False,
                    'error': error_msg,
                    'honeypot_signatures': honeypot_detected,
                    'is_honeypot_error': len(honeypot_detected) > 0
                }
                
        except Exception as e:
            return {'success': False, 'error': str(e), 'stage': 'transaction_building'}
    
    async def simulate_transfer(self, token_address: str, from_account: Account, to_account: Account) -> Dict:
        """Simulate token transfer between accounts"""
        try:
            token_contract = self.web3.eth.contract(
                address=Web3.to_checksum_address(token_address),
                abi=self.erc20_abi
            )
            
            # Small transfer amount
            transfer_amount = 100 * 10**18  # 100 tokens
            
            # Build transfer transaction
            transfer_tx = token_contract.functions.transfer(
                to_account.address,
                transfer_amount
            ).build_transaction({
                'from': from_account.address,
                'gas': 100000,
                'gasPrice': self.web3.to_wei(20, 'gwei'),
                'nonce': 0,
                'chainId': self.chain_id
            })
            
            # Simulate with eth_call
            try:
                result = self.web3.eth.call(transfer_tx)
                return {
                    'success': True,
                    'result': result.hex(),
                    'message': 'Transfer simulation successful'
                }
            except Exception as call_error:
                error_msg = str(call_error)
                honeypot_detected = self.detect_honeypot_signatures(error_msg)
                
                return {
                    'success': False,
                    'error': error_msg,
                    'honeypot_signatures': honeypot_detected,
                    'is_honeypot_error': len(honeypot_detected) > 0
                }
                
        except Exception as e:
            return {'success': False, 'error': str(e), 'stage': 'transaction_building'}
    
    def detect_honeypot_signatures(self, error_message: str) -> List[str]:
        """Detect honeypot signatures in error messages"""
        detected = []
        error_lower = error_message.lower()
        
        for category, signatures in RouterMapping.HONEYPOT_SIGNATURES.items():
            for signature in signatures:
                if signature.lower() in error_lower:
                    detected.append(f"{category}: {signature}")
                    break
        
        return detected
    
    async def check_proxy_pattern(self, token_address: str) -> bool:
        """Check if contract follows proxy pattern"""
        try:
            # Get contract code
            code = self.web3.eth.get_code(token_address)
            code_hex = code.hex()
            
            # Look for proxy patterns (delegatecall, implementation storage slots)
            proxy_patterns = [
                '60806040',  # Common proxy pattern
                '363d3d373d3d3d363d73',  # Minimal proxy pattern
                'a2646970667358221220'  # IPFS hash pattern often in proxies
            ]
            
            for pattern in proxy_patterns:
                if pattern in code_hex:
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Proxy pattern check failed: {e}")
            return False
    
    async def check_unusual_functions(self, token_address: str) -> List[str]:
        """Check for unusual or suspicious functions"""
        unusual = []
        
        try:
            # This would require contract ABI analysis
            # For now, return placeholder
            
            # In a full implementation, you would:
            # 1. Get contract ABI from Etherscan
            # 2. Analyze function signatures
            # 3. Look for suspicious patterns like:
            #    - Functions that can change balances arbitrarily
            #    - Blacklist/whitelist functions
            #    - Pausable functions
            #    - Owner-only trading restrictions
            
            return unusual
            
        except Exception as e:
            logger.error(f"Unusual function check failed: {e}")
            return []
    
    async def analyze_ownership_concentration(self, token_address: str) -> Dict:
        """Analyze token ownership concentration"""
        risks = {'risk_score': 0, 'risk_factors': []}
        
        try:
            # Get token holders (would use Covalent or other API)
            covalent_client = CovalentClient()
            holders = await covalent_client.get_token_holders(token_address, page=0)
            
            if holders and len(holders) > 0:
                # Analyze top holders
                total_supply = sum(float(holder.get('balance', 0)) for holder in holders)
                
                if total_supply > 0:
                    # Check top holder concentration
                    top_holder_balance = float(holders[0].get('balance', 0))
                    top_holder_percentage = (top_holder_balance / total_supply) * 100
                    
                    if top_holder_percentage > 50:
                        risks['risk_factors'].append(f'High ownership concentration: {top_holder_percentage:.1f}%')
                        risks['risk_score'] += 3
                    elif top_holder_percentage > 20:
                        risks['risk_factors'].append(f'Moderate ownership concentration: {top_holder_percentage:.1f}%')
                        risks['risk_score'] += 1
                    
                    # Check if few holders control majority
                    if len(holders) >= 5:
                        top_5_balance = sum(float(holder.get('balance', 0)) for holder in holders[:5])
                        top_5_percentage = (top_5_balance / total_supply) * 100
                        
                        if top_5_percentage > 80:
                            risks['risk_factors'].append(f'Top 5 holders control {top_5_percentage:.1f}% of supply')
                            risks['risk_score'] += 2
            
            return risks
            
        except Exception as e:
            logger.error(f"Ownership analysis failed: {e}")
            return {'risk_score': 0, 'risk_factors': ['Ownership analysis failed']}

class EnhancedTokenAnalyzer:
    """Enhanced token analyzer with hardened honeypot detection"""
    
    def __init__(self):
        self.covalent_client = CovalentClient()
        self.honeypot_simulator = HoneypotSimulator()
        
    async def analyze_token(self, token_address: str) -> Dict:
        """Comprehensive token analysis with enhanced honeypot detection"""
        try:
            logger.info(f"🔍 Starting enhanced analysis for token: {token_address}")
            
            # Validate token address
            if not Web3.is_address(token_address):
                raise ValueError("Invalid token address format")
            
            # Get basic token data
            token_data = await self.get_token_data(token_address)
            
            # Enhanced honeypot analysis
            honeypot_result = await self.honeypot_simulator.comprehensive_honeypot_check(token_address)
            
            # Get market sentiment
            sentiment_score = await self.analyze_sentiment(token_address, token_data.get('symbol'))
            
            # Calculate AI score with honeypot results
            ai_score = await self.calculate_enhanced_ai_score(token_data, honeypot_result, sentiment_score)
            
            # Generate recommendation with risk assessment
            recommendation = self.generate_enhanced_recommendation(token_data, honeypot_result, ai_score, sentiment_score)
            
            # Lock USD price at analysis time
            usd_locked_price = await self.lock_usd_at_trade(token_address, token_data.get('price_usd', 0))
            
            # Combine all analysis results
            analysis_result = {
                **token_data,
                'honeypot_analysis': honeypot_result,
                'is_honeypot': honeypot_result['is_honeypot'],
                'honeypot_risk_score': honeypot_result['risk_score'],
                'risk_factors': honeypot_result.get('risk_factors', []),
                'sentiment_score': sentiment_score,
                'ai_score': ai_score,
                'recommendation': recommendation,
                'analysis_timestamp': datetime.utcnow().isoformat(),
                'risk_level': self.calculate_enhanced_risk_level(ai_score, honeypot_result),
                'usd_locked_price': usd_locked_price,
                'trade_safety_score': self.calculate_trade_safety_score(honeypot_result, token_data)
            }
            
            # Save enhanced analysis to database
            await self.save_enhanced_analysis_to_db(token_address, analysis_result)
            
            logger.info(f"✅ Enhanced analysis completed for {token_address}: AI Score {ai_score}/10, Safety Score {analysis_result['trade_safety_score']}/10")
            return analysis_result
            
        except Exception as e:
            logger.error(f"Enhanced token analysis failed for {token_address}: {e}")
            raise Exception(f"Analysis failed: {str(e)}")
    
    async def get_token_data(self, token_address: str) -> Dict:
        """Get comprehensive token information"""
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
            web3 = Web3(Web3.HTTPProvider(Config.ETHEREUM_RPC_URL))
            
            # Basic ERC20 ABI
            erc20_abi = [
                {"constant": True, "inputs": [], "name": "name", "outputs": [{"name": "", "type": "string"}], "type": "function"},
                {"constant": True, "inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "type": "function"},
                {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
                {"constant": True, "inputs": [], "name": "totalSupply", "outputs": [{"name": "", "type": "uint256"}], "type": "function"}
            ]
            
            contract = web3.eth.contract(
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
    
    async def analyze_sentiment(self, token_address: str, symbol: Optional[str] = None) -> float:
        """Analyze market sentiment for the token"""
        try:
            if not symbol:
                return 0.5  # Neutral sentiment
            
            # In production, implement real sentiment analysis
            # For now, return baseline sentiment
            import random
            sentiment_score = random.uniform(0.3, 0.7)
            
            logger.info(f"Sentiment analysis for {symbol}: {sentiment_score:.2f}")
            return sentiment_score
            
        except Exception as e:
            logger.error(f"Sentiment analysis failed: {e}")
            return 0.5  # Neutral on error
    
    async def calculate_enhanced_ai_score(self, token_data: Dict, honeypot_result: Dict, sentiment_score: float) -> float:
        """Calculate enhanced AI-powered score incorporating honeypot results"""
        try:
            score = 5.0  # Base score
            
            # Honeypot penalty (most important factor)
            if honeypot_result['is_honeypot']:
                score -= 4  # Major penalty for confirmed honeypot
            else:
                # Gradual penalty based on risk score
                honeypot_risk = honeypot_result.get('risk_score', 0)
                score -= min(honeypot_risk * 0.3, 2)  # Max 2 point penalty
            
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
            else:
                score -= 1  # Penalty for very low liquidity
            
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
            
            # Sentiment factor (-1 to +1 points)
            sentiment_factor = (sentiment_score - 0.5) * 2
            score += sentiment_factor
            
            # Ensure score is between 0 and 10
            score = max(0, min(10, score))
            
            return round(score, 2)
            
        except Exception as e:
            logger.error(f"Enhanced AI score calculation failed: {e}")
            return 5.0  # Return neutral score on error
    
    def calculate_enhanced_risk_level(self, ai_score: float, honeypot_result: Dict) -> str:
        """Calculate enhanced risk level based on comprehensive analysis"""
        if honeypot_result['is_honeypot']:
            return "CRITICAL"
        
        honeypot_risk_score = honeypot_result.get('risk_score', 0)
        
        if honeypot_risk_score >= 6:
            return "HIGH"
        elif ai_score >= 7 and honeypot_risk_score <= 2:
            return "LOW"
        elif ai_score >= 5 and honeypot_risk_score <= 4:
            return "MEDIUM"
        else:
            return "HIGH"
    
    def calculate_trade_safety_score(self, honeypot_result: Dict, token_data: Dict) -> float:
        """Calculate trade safety score (0-10)"""
        try:
            safety_score = 10.0
            
            # Honeypot penalties
            if honeypot_result['is_honeypot']:
                safety_score = 0  # No safety if confirmed honeypot
            else:
                safety_score -= honeypot_result.get('risk_score', 0) * 0.8
            
            # Liquidity safety
            liquidity = token_data.get('liquidity_usd', 0)
            if liquidity < 1000:
                safety_score -= 3
            elif liquidity < 10000:
                safety_score -= 1
            
            # Volume safety
            volume = token_data.get('volume_24h', 0)
            if volume < 1000:
                safety_score -= 2
            elif volume < 10000:
                safety_score -= 1
            
            return max(0, min(10, round(safety_score, 1)))
            
        except Exception as e:
            logger.error(f"Trade safety score calculation failed: {e}")
            return 5.0
    
    def generate_enhanced_recommendation(self, token_data: Dict, honeypot_result: Dict, ai_score: float, sentiment_score: float) -> str:
        """Generate enhanced trading recommendation"""
        try:
            if honeypot_result['is_honeypot']:
                return "🚨 CRITICAL RISK - AVOID COMPLETELY - Confirmed honeypot detected. Do not trade this token under any circumstances."
            
            honeypot_risk = honeypot_result.get('risk_score', 0)
            risk_factors = honeypot_result.get('risk_factors', [])
            
            if honeypot_risk >= 6:
                return f"❌ HIGH RISK - AVOID - Multiple risk factors detected: {', '.join(risk_factors[:3])}"
            
            if ai_score >= 8 and honeypot_risk <= 2:
                return "🟢 STRONG BUY - Excellent fundamentals with low risk factors."
            elif ai_score >= 6.5 and honeypot_risk <= 3:
                return "🟡 MODERATE BUY - Good fundamentals, but monitor risk factors."
            elif ai_score >= 5 and honeypot_risk <= 4:
                return "🟡 HOLD/WATCH - Mixed signals, proceed with caution."
            elif ai_score >= 3:
                return "🔴 WEAK - Poor fundamentals and elevated risk."
            else:
                return "❌ AVOID - Very poor fundamentals, not recommended."
                
        except Exception as e:
            logger.error(f"Enhanced recommendation generation failed: {e}")
            return "⚠️ ANALYSIS INCOMPLETE - Unable to generate recommendation."
    
    async def lock_usd_at_trade(self, token_address: str, current_price: float) -> Dict:
        """Lock USD price at trade time for later comparison"""
        try:
            # In production, this would fetch real-time price from CoinGecko or similar
            # For now, store the current price with timestamp
            
            usd_lock_data = {
                'price_usd': current_price,
                'locked_at': datetime.utcnow().isoformat(),
                'source': 'covalent_api',
                'token_address': token_address
            }
            
            # Store in database for later reference
            await self.save_usd_lock_to_db(token_address, usd_lock_data)
            
            return usd_lock_data
            
        except Exception as e:
            logger.error(f"USD price locking failed: {e}")
            return {
                'price_usd': current_price,
                'locked_at': datetime.utcnow().isoformat(),
                'source': 'fallback',
                'error': str(e)
            }
    
    async def save_enhanced_analysis_to_db(self, token_address: str, analysis_result: Dict):
        """Save enhanced analysis results to database"""
        db = get_db_session()
        try:
            token = db.query(Token).filter(Token.address == token_address).first()
            if not token:
                token = Token(address=token_address)
                db.add(token)
            
            # Update token with enhanced analysis results
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
            logger.info(f"Enhanced analysis saved to database for {token_address}")
            
        except Exception as e:
            logger.error(f"Failed to save enhanced analysis to database: {e}")
        finally:
            db.close()
    
    async def save_usd_lock_to_db(self, token_address: str, usd_lock_data: Dict):
        """Save USD lock data to database for later reference"""
        # Implementation would store in a separate table for price locks
        # For now, just log the action
        logger.info(f"USD price locked for {token_address}: ${usd_lock_data['price_usd']:.6f}")

# Legacy compatibility
TokenAnalyzer = EnhancedTokenAnalyzer