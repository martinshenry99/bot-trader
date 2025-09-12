"""
Bot helper functions for database operations and utilities
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from web3 import Web3
import secrets

from db import get_db_session, WalletWatch, ExecutorWallet, User
from integrations.covalent import CovalentClient
from core.wallet_manager import wallet_manager

logger = logging.getLogger(__name__)

# Rate limiting storage
rate_limits = {}


async def check_rate_limit(user_id: str, action: str, window_minutes: int = 10, max_requests: int = 5) -> bool:
    """Check if user is within rate limits"""
    try:
        now = datetime.utcnow()
        key = f"{user_id}_{action}"
        
        if key not in rate_limits:
            rate_limits[key] = []
        
        # Clean old requests
        rate_limits[key] = [
            timestamp for timestamp in rate_limits[key]
            if now - timestamp < timedelta(minutes=window_minutes)
        ]
        
        # Check if under limit
        if len(rate_limits[key]) >= max_requests:
            return False
        
        # Add current request
        rate_limits[key].append(now)
        return True
        
    except Exception as e:
        logger.error(f"Rate limit check failed: {e}")
        return True  # Allow on error


async def is_token_contract(address: str, chain: str) -> bool:
    """Check if address is a token contract"""
    try:
        # Simple heuristic: check if it has contract code
        # In production, would check for ERC-20 functions
        covalent_client = CovalentClient()
        chain_id = get_chain_id(chain)
        
        code = await covalent_client.get_code(chain_id, address)
        if len(code) <= 2:  # Just "0x"
            return False
        
        # Additional check: try to get token metadata
        try:
            token_data = await covalent_client.get_token_metadata(chain_id, address)
            return token_data.get('name') is not None
        except:
            return True  # Assume it's a contract if it has code
            
    except Exception as e:
        logger.error(f"Token contract check failed: {e}")
        return False


async def add_to_watchlist(user_id: int, address: str, label: str, chain: str = 'ethereum') -> bool:
    """Add address to user's watchlist"""
    try:
        db = get_db_session()
        try:
            # Check if already exists
            existing = db.query(WalletWatch).filter(
                WalletWatch.user_id == user_id,
                WalletWatch.wallet_address == address.lower()
            ).first()
            
            if existing:
                existing.label = label
                existing.is_active = True
                existing.updated_at = datetime.utcnow()
            else:
                watch_item = WalletWatch(
                    user_id=user_id,
                    wallet_address=address.lower(),
                    label=label,
                    chain=chain,
                    is_active=True,
                    added_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.add(watch_item)
            
            db.commit()
            
            # Notify scanner of new watchlist item
            from services.wallet_scanner import wallet_scanner
            await wallet_scanner.add_wallet_to_watchlist(address.lower(), user_id, [chain])
            
            return True
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Failed to add to watchlist: {e}")
        return False


async def remove_from_watchlist(user_id: int, address: str) -> bool:
    """Remove address from user's watchlist"""
    try:
        db = get_db_session()
        try:
            watch_item = db.query(WalletWatch).filter(
                WalletWatch.user_id == user_id,
                WalletWatch.wallet_address == address.lower()
            ).first()
            
            if watch_item:
                watch_item.is_active = False
                watch_item.updated_at = datetime.utcnow()
                db.commit()
                return True
            
            return False
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Failed to remove from watchlist: {e}")
        return False


async def get_user_watchlist(user_id: int) -> List[Dict]:
    """Get user's active watchlist"""
    try:
        db = get_db_session()
        try:
            watchlist = db.query(WalletWatch).filter(
                WalletWatch.user_id == user_id,
                WalletWatch.is_active == True
            ).order_by(WalletWatch.added_at.desc()).all()
            
            return [
                {
                    'address': item.wallet_address,
                    'label': item.label,
                    'chain': item.chain,
                    'added_at': item.added_at.strftime('%Y-%m-%d'),
                    'updated_at': item.updated_at.strftime('%Y-%m-%d') if item.updated_at else None
                }
                for item in watchlist
            ]
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Failed to get watchlist: {e}")
        return []


async def rename_watchlist_item(user_id: int, address: str, new_label: str) -> bool:
    """Rename watchlist item"""
    try:
        db = get_db_session()
        try:
            watch_item = db.query(WalletWatch).filter(
                WalletWatch.user_id == user_id,
                WalletWatch.wallet_address == address.lower(),
                WalletWatch.is_active == True
            ).first()
            
            if watch_item:
                watch_item.label = new_label
                watch_item.updated_at = datetime.utcnow()
                db.commit()
                return True
            
            return False
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Failed to rename watchlist item: {e}")
        return False


async def get_user_executor_wallets(user_id: int) -> List[Dict]:
    """Get user's executor wallets"""
    try:
        db = get_db_session()
        try:
            # For now, return all executor wallets (in production, would filter by user)
            wallets = db.query(ExecutorWallet).filter(
                ExecutorWallet.is_active == True
            ).all()
            
            return [
                {
                    'id': wallet.id,
                    'address': wallet.address,
                    'chain': wallet.chain,
                    'created_at': wallet.created_at.strftime('%Y-%m-%d'),
                    'label': wallet.label or f"Wallet {wallet.id}"
                }
                for wallet in wallets
            ]
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Failed to get executor wallets: {e}")
        return []


async def get_wallet_balance(address: str, chain: str) -> Dict:
    """Get wallet balance and token holdings with multicall batching for EVM chains"""
    try:
        if chain in ["ethereum", "bsc"]:
            from web3 import Web3
            from web3.middleware import geth_poa_middleware
            from eth_abi import decode_single
            # Example RPC endpoints (should be replaced with config/env)
            rpc_map = {
                "ethereum": "https://rpc.ankr.com/eth",
                "bsc": "https://rpc.ankr.com/bsc"
            }
            w3 = Web3(Web3.HTTPProvider(rpc_map[chain]))
            if chain == "bsc":
                w3.middleware_onion.inject(geth_poa_middleware, layer=0)
            # Multicall contract address (mainnet)
            multicall_address = {
                "ethereum": "0x5ba1e12693dc8f9c48aad8770482f4739beed696",
                "bsc": "0x1Ee38d535d541c55C9dae27B12edf090C608E6Fb"
            }[chain]
            multicall_abi = [
                {
                    "constant": True,
                    "inputs": [
                        {"components": [
                            {"name": "target", "type": "address"},
                            {"name": "callData", "type": "bytes"}
                        ], "name": "calls", "type": "tuple[]"}
                    ],
                    "name": "aggregate",
                    "outputs": [
                        {"name": "blockNumber", "type": "uint256"},
                        {"name": "returnData", "type": "bytes[]"}
                    ],
                    "payable": False,
                    "stateMutability": "view",
                    "type": "function"
                }
            ]
            multicall = w3.eth.contract(address=multicall_address, abi=multicall_abi)
            # Example: batch ERC20 balanceOf calls for top tokens
            # For demo, use static token list
            tokens = [
                {"address": "0x6B175474E89094C44Da98b954EedeAC495271d0F", "symbol": "DAI", "decimals": 18},
                {"address": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", "symbol": "USDC", "decimals": 6},
                {"address": "0xdAC17F958D2ee523a2206206994597C13D831ec7", "symbol": "USDT", "decimals": 6}
            ]
            calls = []
            for token in tokens:
                erc20_abi = ["function balanceOf(address) view returns (uint256)"]
                contract = w3.eth.contract(address=token["address"], abi=erc20_abi)
                call_data = contract.encodeABI(fn_name="balanceOf", args=[address])
                calls.append((token["address"], call_data))
            # Prepare multicall input
            multicall_input = [{"target": c[0], "callData": bytes.fromhex(c[1][2:])} for c in calls]
            result = multicall.functions.aggregate(multicall_input).call()
            balances = []
            for i, token in enumerate(tokens):
                raw = result[1][i]
                value = int.from_bytes(raw, "big") / (10 ** token["decimals"])
                balances.append({"symbol": token["symbol"], "balance": value, "contract": token["address"]})
            # Native balance
            native_balance = w3.eth.get_balance(address) / 1e18
            native_symbol = get_native_symbol(chain)
            usd_value = native_balance * 2000  # Placeholder
            return {
                "native_balance": native_balance,
                "native_symbol": native_symbol,
                "usd_value": usd_value,
                "tokens": balances
            }
        # ...existing code for non-EVM chains...
        # ...existing code...
    except Exception as e:
        logger.error(f"Failed to get wallet balance: {e}")
        return {
            "native_balance": 0,
            "native_symbol": get_native_symbol(chain),
            "usd_value": 0,
            "tokens": []
        }


async def get_executor_wallet(wallet_id: str) -> Optional[Dict]:
    """Get executor wallet by ID"""
    try:
        db = get_db_session()
        try:
            wallet = db.query(ExecutorWallet).filter(
                ExecutorWallet.id == int(wallet_id),
                ExecutorWallet.is_active == True
            ).first()
            
            if wallet:
                return {
                    'id': wallet.id,
                    'address': wallet.address,
                    'chain': wallet.chain,
                    'created_at': wallet.created_at.strftime('%Y-%m-%d'),
                    'label': wallet.label or f"Wallet {wallet.id}"
                }
            
            return None
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Failed to get executor wallet: {e}")
        return None


def get_explorer_url(address: str, chain: str) -> str:
    """Get block explorer URL for address"""
    explorers = {
        'ethereum': f"https://etherscan.io/address/{address}",
        'bsc': f"https://bscscan.com/address/{address}",
        'polygon': f"https://polygonscan.com/address/{address}",
        'arbitrum': f"https://arbiscan.io/address/{address}",
        'optimism': f"https://optimistic.etherscan.io/address/{address}"
    }
    return explorers.get(chain.lower(), f"https://etherscan.io/address/{address}")


def get_chain_id(chain: str) -> int:
    """Get chain ID for chain name"""
    chain_ids = {
        'ethereum': 1,
        'bsc': 56,
        'polygon': 137,
        'arbitrum': 42161,
        'optimism': 10
    }
    return chain_ids.get(chain.lower(), 1)


def get_native_symbol(chain: str) -> str:
    """Get native token symbol for chain"""
    symbols = {
        'ethereum': 'ETH',
        'bsc': 'BNB',
        'polygon': 'MATIC',
        'arbitrum': 'ETH',
        'optimism': 'ETH'
    }
    return symbols.get(chain.lower(), 'ETH')


async def generate_executor_wallet(force_show: bool = False) -> Dict[str, Any]:
    """Generate new executor wallet with encrypted keystore"""
    try:
        logger.info("🔑 Generating new executor wallet...")
        
        # Generate wallet using wallet manager
        wallet_info = wallet_manager.create_wallet(
            wallet_name="executor_wallet",
            blockchain="ethereum"
        )
        
        # Store in database
        db = get_db_session()
        try:
            executor_wallet = ExecutorWallet(
                address=wallet_info['address'],
                keystore_path=wallet_info['keystore_path'],
                chain='ethereum',
                label=f"Executor {wallet_info['address'][-6:]}",
                is_active=True,
                created_at=datetime.utcnow()
            )
            db.add(executor_wallet)
            db.commit()
            
            wallet_id = executor_wallet.id
            
        finally:
            db.close()
        
        # Show mnemonic in console (NOT in Telegram)
        mnemonic = wallet_info.get('private_key', '')  # This would be the mnemonic in production
        
        print("\n" + "="*80)
        print("🔑 NEW EXECUTOR WALLET GENERATED")
        print("="*80)
        print(f"WALLET ID: {wallet_id}")
        print(f"ADDRESS: {wallet_info['address']}")
        print(f"KEYSTORE: {wallet_info['keystore_path']}")
        print("\n⚠️  CRITICAL: SAVE THIS MNEMONIC IMMEDIATELY!")
        print("This will NEVER be shown again!")
        print("-"*80)
        print(f"MNEMONIC: {mnemonic}")
        print("-"*80)
        print("✅ Mnemonic saved to secure backup? (y/n): ", end="", flush=True)
        print("="*80)
        
        # Create verification hash
        import hashlib
        mnemonic_hash = hashlib.sha256(mnemonic.encode()).hexdigest()
        
        # Save hash for verification
        with open('/app/keystores/last_mnemonic_hash.txt', 'w') as f:
            f.write(f"{mnemonic_hash}\n{datetime.utcnow().isoformat()}\n{wallet_id}")
        
        return {
            'success': True,
            'wallet_id': wallet_id,
            'address': wallet_info['address'],
            'keystore_path': wallet_info['keystore_path'],
            'mnemonic_shown_in_console': True
        }
        
    except Exception as e:
        logger.error(f"Failed to generate executor wallet: {e}")
        return {
            'success': False,
            'error': str(e)
        }
