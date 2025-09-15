"""
Multi-chain management service for BSC and Solana monitoring
"""

import logging
from typing import Dict, List, Optional, Any
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal

from services.helius import HeliusClient
from integrations.covalent import CovalentClient
from handlers.key_management import KeyManager

logger = logging.getLogger(__name__)

class ChainManager:
    """
    Multi-chain monitoring and coordination service.
    Handles parallel monitoring of BSC and Solana chains.
    """
    
    def __init__(self, key_manager: KeyManager):
        self.key_manager = key_manager
        self.helius = HeliusClient()
        self.covalent = CovalentClient()
        
        # Configuration
        self.solana_confirmations = 1  # Required confirmations for Solana
        self.bsc_confirmations = 3     # Required confirmations for BSC
        
        # Cache settings
        self.cache_ttl = 300  # 5 minutes
        self._cache = {}
        self._last_update = {}
    
    async def monitor_wallets(
        self,
        solana_wallets: List[str],
        bsc_wallets: List[str]
    ) -> Dict[str, List[Dict]]:
        """
        Monitor multiple wallets across chains simultaneously
        """
        tasks = []
        
        # Monitor Solana wallets
        for wallet in solana_wallets:
            tasks.append(self.helius.get_wallet_transactions(wallet))
            
        # Monitor BSC wallets 
        for wallet in bsc_wallets:
            tasks.append(self.covalent.get_transactions(
                chain_id="bsc",
                address=wallet
            ))
            
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process and combine results
        combined = {
            'solana': [],
            'bsc': []
        }
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error monitoring wallet: {result}")
                continue
                
            if i < len(solana_wallets):
                combined['solana'].extend(result)
            else:
                combined['bsc'].extend(result)
        
        return combined
    
    async def get_token_info(
        self,
        chain: str,
        token_address: str
    ) -> Optional[Dict]:
        """
        Get token information from either chain
        """
        cache_key = f"{chain}:token:{token_address}"
        
        # Check cache
        if (cache_key in self._cache and
            cache_key in self._last_update and
            datetime.now() - self._last_update[cache_key] < 
            timedelta(seconds=self.cache_ttl)):
            return self._cache[cache_key]
        
        result = None
        if chain == "solana":
            result = await self.helius.get_token_metadata(token_address)
        elif chain == "bsc":
            result = await self.covalent.get_token_data(
                chain_id="bsc",
                token_address=token_address
            )
            
        if result:
            self._cache[cache_key] = result
            self._last_update[cache_key] = datetime.now()
            
        return result
    
    async def check_transaction_confirmation(
        self,
        chain: str,
        tx_hash: str
    ) -> Dict[str, Any]:
        """
        Check transaction confirmation status on either chain
        """
        if chain == "solana":
            status = await self.helius.get_transaction_status(tx_hash)
            return {
                'confirmed': status['confirmations'] >= self.solana_confirmations,
                'confirmations': status['confirmations']
            }
        elif chain == "bsc":
            status = await self.covalent.get_transaction_status(
                chain_id="bsc",
                tx_hash=tx_hash
            )
            return {
                'confirmed': status['block_height'] >= self.bsc_confirmations,
                'confirmations': status['block_height']
            }
        else:
            raise ValueError(f"Unsupported chain: {chain}")
    
    async def analyze_wallet_activity(
        self,
        chain: str,
        wallet: str,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Analyze wallet activity and patterns
        """
        if chain == "solana":
            transfers = await self.helius.get_token_transfers(wallet, days)
            return {
                'transfer_count': len(transfers),
                'unique_tokens': len({t['token'] for t in transfers}),
                'total_usd_value': sum(t['usd_value'] for t in transfers),
                'risk_factors': {
                    'new_wallet_interactions': sum(
                        1 for t in transfers if t['from_new_wallet']
                    ),
                    'mixed_funds': sum(
                        1 for t in transfers if t['mixed_funds']
                    ),
                    'tornado_cash_proximity': any(
                        t['tornado_cash_proximity'] for t in transfers
                    )
                }
            }
        elif chain == "bsc":
            txns = await self.covalent.get_transactions(
                chain_id="bsc",
                address=wallet,
                days=days
            )
            return {
                'transaction_count': len(txns),
                'unique_tokens': len({t['contract_address'] for t in txns}),
                'total_value': sum(Decimal(t['value']) for t in txns),
                'risk_factors': {
                    'contract_interactions': sum(
                        1 for t in txns if t['to_address_label'] == 'contract'
                    ),
                    'high_value_txns': sum(
                        1 for t in txns 
                        if Decimal(t['value']) > Decimal('10000')
                    )
                }
            }
        else:
            raise ValueError(f"Unsupported chain: {chain}")
    
    async def find_related_wallets(
        self,
        chain: str,
        wallet: str,
        max_depth: int = 2
    ) -> List[str]:
        """
        Find wallets related through transactions
        """
        if chain == "solana":
            # Use Helius connection path API
            related = set()
            transfers = await self.helius.get_token_transfers(wallet)
            
            for transfer in transfers:
                related.add(transfer['from_address'])
                related.add(transfer['to_address'])
                
                if max_depth > 1:
                    for addr in list(related):
                        path = await self.helius.find_wallet_path(wallet, addr)
                        if path:
                            related.update(path)
                            
            related.discard(wallet)
            return list(related)
            
        elif chain == "bsc":
            # Use Covalent transaction history
            related = set()
            txns = await self.covalent.get_transactions(
                chain_id="bsc",
                address=wallet
            )
            
            for tx in txns:
                related.add(tx['from_address'])
                related.add(tx['to_address'])
                
                if max_depth > 1:
                    for addr in list(related):
                        addr_txns = await self.covalent.get_transactions(
                            chain_id="bsc",
                            address=addr
                        )
                        for atx in addr_txns:
                            related.add(atx['from_address'])
                            related.add(atx['to_address'])
                            
            related.discard(wallet)
            return list(related)
            
        else:
            raise ValueError(f"Unsupported chain: {chain}")
    
    async def get_token_deployments(
        self,
        chain: str,
        days: int = 7
    ) -> List[Dict]:
        """
        Get recent token deployments on either chain
        """
        if chain == "solana":
            return await self.helius.get_token_deployments(days)
            
        elif chain == "bsc":
            return await self.covalent.get_token_deployments(
                chain_id="bsc",
                days=days
            )
            
        else:
            raise ValueError(f"Unsupported chain: {chain}")
            
    async def simulate_transaction(
        self,
        chain: str,
        transaction: Dict
    ) -> Dict[str, Any]:
        """
        Simulate transaction before execution
        """
        if chain == "solana":
            return await self.helius.simulate_transaction(transaction)
            
        elif chain == "bsc":
            return await self.covalent.simulate_transaction(
                chain_id="bsc",
                transaction=transaction
            )
            
        else:
            raise ValueError(f"Unsupported chain: {chain}")
