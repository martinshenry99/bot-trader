"""
Multi-chain monitoring service for both Solana and BSC chains
"""

import logging
import asyncio
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta
from decimal import Decimal

from services.helius import HeliusClient
from services.covalent import CovalentClient
from services.chain_manager import ChainManager
from handlers.key_management import KeyManager
from db.models import Transaction, WalletActivity, TokenInfo

logger = logging.getLogger(__name__)

class ChainMonitor:
    """
    Real-time monitoring service for both Solana and BSC chains.
    Handles parallel monitoring, data normalization, and alerting.
    """
    
    def __init__(self, chain_manager: ChainManager):
        self.chain_manager = chain_manager
        
        # Monitoring state
        self.monitored_wallets = {
            'solana': set(),
            'bsc': set()
        }
        self.monitored_tokens = {
            'solana': set(),
            'bsc': set()
        }
        
        # Alert thresholds
        self.value_threshold = Decimal('10000')  # $10k USD
        self.transaction_interval = 60  # 1 minute
        self.whale_threshold = Decimal('100000')  # $100k USD
        
        # Cache settings
        self.cache_ttl = 300  # 5 minutes
        self._last_token_update = {}
        self._token_cache = {}
        
    async def add_wallet_monitor(
        self,
        chain: str,
        wallet: str
    ) -> None:
        """Add wallet to monitoring list"""
        if chain not in ('solana', 'bsc'):
            raise ValueError(f"Unsupported chain: {chain}")
            
        self.monitored_wallets[chain].add(wallet)
        logger.info(f"Added {wallet} to {chain} monitoring")
        
    async def remove_wallet_monitor(
        self,
        chain: str,
        wallet: str
    ) -> None:
        """Remove wallet from monitoring"""
        if chain in self.monitored_wallets:
            self.monitored_wallets[chain].discard(wallet)
            logger.info(f"Removed {wallet} from {chain} monitoring")
            
    async def add_token_monitor(
        self,
        chain: str,
        token: str
    ) -> None:
        """Add token to monitoring list"""
        if chain not in ('solana', 'bsc'):
            raise ValueError(f"Unsupported chain: {chain}")
            
        self.monitored_tokens[chain].add(token)
        
        # Get initial token info
        token_info = await self.chain_manager.get_token_info(chain, token)
        if token_info:
            self._token_cache[f"{chain}:{token}"] = token_info
            self._last_token_update[f"{chain}:{token}"] = datetime.now()
            
        logger.info(f"Added {token} to {chain} monitoring")
        
    async def remove_token_monitor(
        self,
        chain: str,
        token: str
    ) -> None:
        """Remove token from monitoring"""
        if chain in self.monitored_tokens:
            self.monitored_tokens[chain].discard(token)
            logger.info(f"Removed {token} from {chain} monitoring")
            
    async def start_monitoring(self) -> None:
        """Start monitoring all tracked wallets and tokens"""
        while True:
            try:
                await self._monitor_cycle()
                await asyncio.sleep(self.transaction_interval)
            except Exception as e:
                logger.error(f"Error in monitoring cycle: {str(e)}")
                await asyncio.sleep(5)  # Brief pause on error
                
    async def _monitor_cycle(self) -> None:
        """Single monitoring cycle"""
        # Monitor wallets in parallel
        results = await self.chain_manager.monitor_wallets(
            solana_wallets=list(self.monitored_wallets['solana']),
            bsc_wallets=list(self.monitored_wallets['bsc'])
        )
        
        # Process new transactions
        for chain, transactions in results.items():
            for tx in transactions:
                await self._process_transaction(chain, tx)
                
        # Update token info
        await self._update_token_info()
        
    async def _process_transaction(
        self,
        chain: str,
        transaction: Dict
    ) -> None:
        """Process and analyze new transaction"""
        # Check transaction status
        status = await self.chain_manager.check_transaction_confirmation(
            chain,
            transaction['hash']
        )
        
        if not status['confirmed']:
            return  # Skip unconfirmed transactions
            
        # Extract transaction details
        if chain == 'solana':
            value = Decimal(str(transaction.get('usd_value', 0)))
            from_addr = transaction['sourceAddress']
            to_addr = transaction['destinationAddress']
            token = transaction.get('tokenAddress')
        else:  # BSC
            value = Decimal(str(transaction.get('value', 0)))
            from_addr = transaction['from_address']
            to_addr = transaction['to_address']
            token = transaction.get('contract_address')
            
        # Check if transaction involves monitored tokens
        if token in self.monitored_tokens[chain]:
            await self._analyze_token_transaction(
                chain,
                token,
                transaction
            )
            
        # Check for high value transfers
        if value >= self.value_threshold:
            await self._handle_high_value_transfer(
                chain,
                transaction,
                value
            )
            
        # Check for whale activity
        if value >= self.whale_threshold:
            await self._handle_whale_activity(
                chain,
                transaction,
                value
            )
            
        # Update wallet activity metrics
        if from_addr in self.monitored_wallets[chain]:
            await self._update_wallet_metrics(
                chain,
                from_addr,
                transaction,
                'out'
            )
            
        if to_addr in self.monitored_wallets[chain]:
            await self._update_wallet_metrics(
                chain,
                to_addr,
                transaction,
                'in'
            )
            
    async def _analyze_token_transaction(
        self,
        chain: str,
        token: str,
        transaction: Dict
    ) -> None:
        """Analyze token transaction for patterns"""
        # Get token info
        token_info = await self._get_token_info(chain, token)
        if not token_info:
            return
            
        # Check for large moves relative to supply
        if chain == 'solana':
            amount = Decimal(str(transaction.get('amount', 0)))
            decimals = token_info.get('decimals', 0)
            total_supply = Decimal(str(token_info.get('total_supply', 0)))
        else:  # BSC
            amount = Decimal(str(transaction.get('value', 0)))
            decimals = token_info.get('decimals', 18)
            total_supply = Decimal(str(token_info.get('total_supply', 0)))
            
        if total_supply > 0:
            move_percentage = (amount / Decimal(10**decimals)) / total_supply * 100
            if move_percentage >= 1:  # 1% or more of supply
                logger.warning(
                    f"Large token movement detected on {chain}: "
                    f"{move_percentage:.2f}% of {token_info['symbol']}"
                )
                
    async def _handle_high_value_transfer(
        self,
        chain: str,
        transaction: Dict,
        value: Decimal
    ) -> None:
        """Handle high value transfer detection"""
        logger.warning(
            f"High value transfer detected on {chain}: "
            f"${value:,.2f} USD"
        )
        
        # Check for suspicious patterns
        from_addr = (
            transaction['sourceAddress']
            if chain == 'solana'
            else transaction['from_address']
        )
        
        # Analyze source wallet
        analysis = await self.chain_manager.analyze_wallet_activity(
            chain,
            from_addr
        )
        
        risk_factors = analysis.get('risk_factors', {})
        if chain == 'solana':
            if (risk_factors.get('mixed_funds') or
                risk_factors.get('tornado_cash_proximity')):
                logger.warning(
                    f"High risk transfer detected from {from_addr} "
                    f"on {chain}"
                )
        else:  # BSC
            if risk_factors.get('contract_interactions', 0) > 10:
                logger.warning(
                    f"High contract interaction wallet {from_addr} "
                    f"detected on {chain}"
                )
                
    async def _handle_whale_activity(
        self,
        chain: str,
        transaction: Dict,
        value: Decimal
    ) -> None:
        """Handle whale activity detection"""
        logger.warning(
            f"Whale activity detected on {chain}: "
            f"${value:,.2f} USD"
        )
        
        # Find related wallets
        from_addr = (
            transaction['sourceAddress']
            if chain == 'solana'
            else transaction['from_address']
        )
        
        related = await self.chain_manager.find_related_wallets(
            chain,
            from_addr
        )
        
        # Check if any related wallets are monitored
        monitored_related = set(related) & self.monitored_wallets[chain]
        if monitored_related:
            logger.warning(
                f"Whale wallet {from_addr} related to monitored "
                f"wallets: {monitored_related}"
            )
            
    async def _update_wallet_metrics(
        self,
        chain: str,
        wallet: str,
        transaction: Dict,
        direction: str
    ) -> None:
        """Update wallet activity metrics"""
        # Get recent activity analysis
        analysis = await self.chain_manager.analyze_wallet_activity(
            chain,
            wallet,
            days=7
        )
        
        # Store metrics
        await WalletActivity.create(
            wallet_address=wallet,
            chain=chain,
            transaction_count=analysis['transaction_count'],
            unique_tokens=analysis['unique_tokens'],
            total_value=analysis['total_value'],
            risk_score=sum(
                1 for v in analysis['risk_factors'].values()
                if v in (True, 1)
            ),
            last_active=datetime.now()
        )
        
    async def _get_token_info(
        self,
        chain: str,
        token: str
    ) -> Optional[Dict]:
        """Get cached or fresh token info"""
        cache_key = f"{chain}:{token}"
        
        # Check cache
        if (cache_key in self._token_cache and
            cache_key in self._last_token_update and
            datetime.now() - self._last_token_update[cache_key] <
            timedelta(seconds=self.cache_ttl)):
            return self._token_cache[cache_key]
            
        # Get fresh info
        token_info = await self.chain_manager.get_token_info(chain, token)
        if token_info:
            self._token_cache[cache_key] = token_info
            self._last_token_update[cache_key] = datetime.now()
            
        return token_info
        
    async def _update_token_info(self) -> None:
        """Update info for all monitored tokens"""
        for chain, tokens in self.monitored_tokens.items():
            for token in tokens:
                await self._get_token_info(chain, token)
