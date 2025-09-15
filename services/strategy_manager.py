"""
Strategy templates and management system
"""

from typing import Dict, List, Optional, Any
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from services.chain_manager import ChainManager
from handlers.key_management import KeyManager
from db.models import UserStrategy, Transaction
from utils.cache import TTLCache

logger = logging.getLogger(__name__)

@dataclass
class StrategyConfig:
    """Strategy configuration parameters"""
    name: str
    description: str
    risk_level: int  # 1-5
    parameters: Dict[str, Any]
    chain_support: List[str]  # ['solana', 'bsc', 'eth']
    required_balance: Decimal
    max_position_size: Decimal
    stop_loss: Optional[Decimal]
    take_profit: Optional[Decimal]
    auto_compound: bool
    dry_run: bool = True

class StrategyTemplate:
    """Base class for strategy templates"""
    
    def __init__(
        self,
        chain_manager: ChainManager,
        key_manager: KeyManager,
        config: StrategyConfig
    ):
        self.chain_manager = chain_manager
        self.key_manager = key_manager
        self.config = config
        self.cache = TTLCache(ttl=300)  # 5 minute cache
        
    async def validate(self) -> bool:
        """Validate strategy configuration"""
        raise NotImplementedError
        
    async def execute(self, context: Dict) -> Dict:
        """Execute strategy logic"""
        raise NotImplementedError
        
    async def preview(self, context: Dict) -> Dict:
        """Preview strategy execution"""
        raise NotImplementedError
        
    async def get_stats(self) -> Dict:
        """Get strategy performance stats"""
        raise NotImplementedError

class MirrorSellStrategy(StrategyTemplate):
    """Auto-sell when watched wallet sells"""
    
    async def validate(self) -> bool:
        if not self.config.parameters.get('watched_wallets'):
            return False
            
        # Validate wallet addresses
        for wallet in self.config.parameters['watched_wallets']:
            if not await self.chain_manager.is_valid_address(
                self.config.parameters['chain'],
                wallet
            ):
                return False
                
        return True
        
    async def execute(self, context: Dict) -> Dict:
        """Execute mirror sell strategy"""
        results = {
            'trades': [],
            'errors': []
        }
        
        # Monitor watched wallets
        wallet_txs = await self.chain_manager.monitor_wallets(
            solana_wallets=(
                self.config.parameters['watched_wallets']
                if 'solana' in self.config.chain_support
                else []
            ),
            bsc_wallets=(
                self.config.parameters['watched_wallets']
                if 'bsc' in self.config.chain_support
                else []
            )
        )
        
        # Process transactions
        for chain, txs in wallet_txs.items():
            for tx in txs:
                # Check if it's a sell transaction
                if self._is_sell_transaction(chain, tx):
                    # Mirror the sell with configured parameters
                    try:
                        trade = await self._execute_mirror_sell(chain, tx)
                        results['trades'].append(trade)
                    except Exception as e:
                        results['errors'].append(str(e))
                        
        return results
        
    def _is_sell_transaction(self, chain: str, tx: Dict) -> bool:
        """Determine if transaction is a sell"""
        if chain == 'solana':
            # Check Solana DEX interactions
            return (
                tx.get('type') == 'SWAP' and
                tx.get('tokenIn') in self.config.parameters.get(
                    'monitored_tokens',
                    []
                )
            )
        else:  # BSC
            # Check BSC DEX interactions
            return (
                tx.get('to_address') in self.config.parameters.get(
                    'dex_addresses',
                    []
                ) and
                tx.get('contract_address') in self.config.parameters.get(
                    'monitored_tokens',
                    []
                )
            )
            
    async def _execute_mirror_sell(
        self,
        chain: str,
        tx: Dict
    ) -> Dict:
        """Execute mirrored sell order"""
        # Get token and amount to sell
        token = (
            tx['tokenAddress']
            if chain == 'solana'
            else tx['contract_address']
        )
        
        # Calculate sell amount based on portfolio
        balance = await self.chain_manager.get_token_balance(
            chain,
            self.config.parameters['wallet'],
            token
        )
        
        # Apply position size limits
        amount = min(
            balance,
            balance * self.config.max_position_size
        )
        
        # Execute sell order
        if not self.config.dry_run:
            return await self.chain_manager.execute_sell(
                chain=chain,
                token=token,
                amount=amount,
                slippage=self.config.parameters.get('slippage', 0.01)
            )
        else:
            return {
                'simulation': True,
                'chain': chain,
                'token': token,
                'amount': amount,
                'timestamp': datetime.now().isoformat()
            }

class ConservativeBuyStrategy(StrategyTemplate):
    """Only buy tokens with low risk score and locked liquidity"""
    
    async def validate(self) -> bool:
        required_params = [
            'max_risk_score',
            'min_liquidity_locked_days',
            'min_liquidity_amount'
        ]
        return all(
            p in self.config.parameters
            for p in required_params
        )
        
    async def execute(self, context: Dict) -> Dict:
        """Execute conservative buy strategy"""
        results = {
            'trades': [],
            'errors': []
        }
        
        # Get potential buy targets
        targets = await self._scan_for_targets()
        
        for target in targets:
            try:
                # Validate against conservative criteria
                if await self._validate_target(target):
                    # Execute buy with position sizing
                    trade = await self._execute_conservative_buy(target)
                    results['trades'].append(trade)
            except Exception as e:
                results['errors'].append(str(e))
                
        return results
        
    async def _scan_for_targets(self) -> List[Dict]:
        """Scan for potential buy targets"""
        targets = []
        
        # Get recent token deployments
        for chain in self.config.chain_support:
            deployments = await self.chain_manager.get_token_deployments(
                chain,
                days=1  # Look at last 24h
            )
            
            for deployment in deployments:
                # Get token info and initial analysis
                info = await self.chain_manager.get_token_info(
                    chain,
                    deployment['token']
                )
                
                if info:
                    targets.append({
                        'chain': chain,
                        'token': deployment['token'],
                        'info': info,
                        'deployment': deployment
                    })
                    
        return targets
        
    async def _validate_target(self, target: Dict) -> bool:
        """Validate target against conservative criteria"""
        # Check risk score
        risk_score = await self.chain_manager.get_token_risk_score(
            target['chain'],
            target['token']
        )
        
        if risk_score > self.config.parameters['max_risk_score']:
            return False
            
        # Check liquidity lock
        lock_info = await self.chain_manager.get_liquidity_lock_info(
            target['chain'],
            target['token']
        )
        
        if not lock_info:
            return False
            
        if (lock_info['days_locked'] <
            self.config.parameters['min_liquidity_locked_days']):
            return False
            
        if (lock_info['locked_amount'] <
            self.config.parameters['min_liquidity_amount']):
            return False
            
        return True
        
    async def _execute_conservative_buy(
        self,
        target: Dict
    ) -> Dict:
        """Execute conservative buy order"""
        # Calculate position size
        portfolio_value = await self.chain_manager.get_portfolio_value(
            target['chain'],
            self.config.parameters['wallet']
        )
        
        position_size = min(
            portfolio_value * self.config.max_position_size,
            self.config.parameters.get('max_position_usd', Decimal('1000'))
        )
        
        # Execute buy order
        if not self.config.dry_run:
            return await self.chain_manager.execute_buy(
                chain=target['chain'],
                token=target['token'],
                amount_usd=position_size,
                slippage=self.config.parameters.get('slippage', 0.01)
            )
        else:
            return {
                'simulation': True,
                'chain': target['chain'],
                'token': target['token'],
                'amount_usd': position_size,
                'timestamp': datetime.now().isoformat()
            }

class MomentumEntryStrategy(StrategyTemplate):
    """Buy based on multi-watcher consensus"""
    
    async def validate(self) -> bool:
        required_params = [
            'min_watchers',
            'consensus_threshold',
            'time_window'
        ]
        return all(
            p in self.config.parameters
            for p in required_params
        )
        
    async def execute(self, context: Dict) -> Dict:
        """Execute momentum entry strategy"""
        results = {
            'trades': [],
            'errors': []
        }
        
        # Get active watchers and their recent trades
        momentum_signals = await self._analyze_watcher_momentum()
        
        # Find tokens with consensus
        consensus_tokens = self._find_consensus_tokens(momentum_signals)
        
        # Execute trades for consensus tokens
        for token_data in consensus_tokens:
            try:
                trade = await self._execute_momentum_buy(token_data)
                results['trades'].append(trade)
            except Exception as e:
                results['errors'].append(str(e))
                
        return results
        
    async def _analyze_watcher_momentum(self) -> Dict:
        """Analyze watcher momentum signals"""
        signals = {}
        
        # Get configured watchers
        watchers = await self.chain_manager.get_top_wallets(
            min_trades=100,
            min_profit_rate=0.6
        )
        
        # Analyze recent trades
        for watcher in watchers[:self.config.parameters['min_watchers']]:
            recent_trades = await self.chain_manager.get_wallet_trades(
                watcher['address'],
                hours=self.config.parameters['time_window']
            )
            
            for trade in recent_trades:
                token = trade['token']
                if token not in signals:
                    signals[token] = {
                        'buys': 0,
                        'sells': 0,
                        'watchers': set()
                    }
                    
                if trade['type'] == 'BUY':
                    signals[token]['buys'] += 1
                    signals[token]['watchers'].add(watcher['address'])
                    
        return signals
        
    def _find_consensus_tokens(
        self,
        momentum_signals: Dict
    ) -> List[Dict]:
        """Find tokens with watcher consensus"""
        consensus_tokens = []
        
        for token, data in momentum_signals.items():
            # Calculate consensus metrics
            watcher_count = len(data['watchers'])
            buy_ratio = data['buys'] / (data['buys'] + data['sells'])
            
            if (watcher_count >= self.config.parameters['min_watchers'] and
                buy_ratio >= self.config.parameters['consensus_threshold']):
                consensus_tokens.append({
                    'token': token,
                    'watchers': watcher_count,
                    'buy_ratio': buy_ratio
                })
                
        return sorted(
            consensus_tokens,
            key=lambda x: (x['watchers'], x['buy_ratio']),
            reverse=True
        )
        
    async def _execute_momentum_buy(
        self,
        token_data: Dict
    ) -> Dict:
        """Execute momentum-based buy"""
        # Validate token first
        risk_score = await self.chain_manager.get_token_risk_score(
            self.config.parameters['chain'],
            token_data['token']
        )
        
        if risk_score > self.config.parameters.get('max_risk_score', 3):
            raise ValueError(f"Risk score too high: {risk_score}")
            
        # Calculate position size based on consensus strength
        base_size = self.config.max_position_size
        consensus_bonus = (
            token_data['watchers'] /
            self.config.parameters['min_watchers']
        )
        position_size = base_size * min(consensus_bonus, 2)  # Cap at 2x
        
        # Execute buy order
        if not self.config.dry_run:
            return await self.chain_manager.execute_buy(
                chain=self.config.parameters['chain'],
                token=token_data['token'],
                amount_usd=position_size,
                slippage=self.config.parameters.get('slippage', 0.01)
            )
        else:
            return {
                'simulation': True,
                'chain': self.config.parameters['chain'],
                'token': token_data['token'],
                'amount_usd': position_size,
                'consensus_strength': token_data['watchers'],
                'buy_ratio': token_data['buy_ratio'],
                'timestamp': datetime.now().isoformat()
            }

class StrategyManager:
    """Strategy management and execution system"""
    
    def __init__(
        self,
        chain_manager: ChainManager,
        key_manager: KeyManager
    ):
        self.chain_manager = chain_manager
        self.key_manager = key_manager
        
        # Register available strategies
        self.strategies = {
            'mirror_sell': MirrorSellStrategy,
            'conservative_buy': ConservativeBuyStrategy,
            'momentum_entry': MomentumEntryStrategy
        }
        
    async def list_strategies(self) -> List[Dict]:
        """List available strategy templates"""
        return [
            {
                'name': name,
                'description': strategy.__doc__,
                'parameters': self._get_strategy_parameters(name)
            }
            for name, strategy in self.strategies.items()
        ]
        
    def _get_strategy_parameters(self, strategy_name: str) -> Dict:
        """Get strategy parameter specifications"""
        if strategy_name == 'mirror_sell':
            return {
                'watched_wallets': 'List of wallet addresses to mirror',
                'monitored_tokens': 'List of tokens to monitor',
                'dex_addresses': 'List of DEX contract addresses',
                'slippage': 'Maximum slippage tolerance (default: 0.01)'
            }
        elif strategy_name == 'conservative_buy':
            return {
                'max_risk_score': 'Maximum allowed risk score (1-5)',
                'min_liquidity_locked_days': 'Minimum days liquidity must be locked',
                'min_liquidity_amount': 'Minimum locked liquidity in USD',
                'max_position_usd': 'Maximum position size in USD'
            }
        elif strategy_name == 'momentum_entry':
            return {
                'min_watchers': 'Minimum number of watchers required',
                'consensus_threshold': 'Minimum buy ratio for consensus',
                'time_window': 'Time window to analyze (hours)',
                'max_risk_score': 'Maximum allowed risk score (1-5)'
            }
            
    async def apply_strategy(
        self,
        user_id: int,
        strategy_name: str,
        config: Dict
    ) -> Dict:
        """Apply strategy template for user"""
        if strategy_name not in self.strategies:
            raise ValueError(f"Unknown strategy: {strategy_name}")
            
        # Create strategy configuration
        strategy_config = StrategyConfig(
            name=strategy_name,
            description=self.strategies[strategy_name].__doc__,
            risk_level=config.get('risk_level', 3),
            parameters=config,
            chain_support=config.get('chains', ['solana', 'bsc']),
            required_balance=Decimal(str(config.get('required_balance', '100'))),
            max_position_size=Decimal(str(config.get('max_position_size', '0.1'))),
            stop_loss=Decimal(str(config.get('stop_loss', '0.9'))),
            take_profit=Decimal(str(config.get('take_profit', '1.5'))),
            auto_compound=config.get('auto_compound', False),
            dry_run=config.get('dry_run', True)
        )
        
        # Create strategy instance
        strategy = self.strategies[strategy_name](
            self.chain_manager,
            self.key_manager,
            strategy_config
        )
        
        # Validate strategy configuration
        if not await strategy.validate():
            raise ValueError("Invalid strategy configuration")
            
        # Store user strategy
        await UserStrategy.create(
            user_id=user_id,
            strategy_name=strategy_name,
            config=json.dumps(config),
            created_at=datetime.now()
        )
        
        # Run preview if requested
        if config.get('preview', True):
            preview = await strategy.preview({'user_id': user_id})
            return {
                'status': 'applied',
                'preview': preview
            }
        
        return {'status': 'applied'}
