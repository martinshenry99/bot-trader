"""
Multicall implementation for batching EVM chain calls
"""
from typing import List, Dict, Any, Optional
from eth_abi import decode_abi, encode_single
from web3 import Web3
from web3.contract import Contract

# Standard Multicall ABI
MULTICALL_ABI = [
    {
        "inputs": [
            {
                "components": [
                    {
                        "name": "target",
                        "type": "address"
                    },
                    {
                        "name": "callData",
                        "type": "bytes"
                    }
                ],
                "name": "calls",
                "type": "tuple[]"
            }
        ],
        "name": "aggregate",
        "outputs": [
            {
                "name": "blockNumber",
                "type": "uint256"
            },
            {
                "name": "returnData",
                "type": "bytes[]"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    }
]

# Multicall contract addresses per chain
MULTICALL_ADDRESSES = {
    1: "0xcA11bde05977b3631167028862bE2a173976CA11",  # Ethereum
    56: "0xcA11bde05977b3631167028862bE2a173976CA11",  # BSC
    137: "0xcA11bde05977b3631167028862bE2a173976CA11", # Polygon
    42161: "0xcA11bde05977b3631167028862bE2a173976CA11" # Arbitrum
}

class MulticallHelper:
    """Helper class for batching EVM chain calls"""
    
    def __init__(self, w3: Web3, chain_id: int):
        self.w3 = w3
        self.chain_id = chain_id
        self.multicall_address = MULTICALL_ADDRESSES.get(chain_id)
        if not self.multicall_address:
            raise ValueError(f"No Multicall address for chain {chain_id}")
            
        self.multicall = self.w3.eth.contract(
            address=self.multicall_address,
            abi=MULTICALL_ABI
        )
    
    async def batch_balances(
        self,
        token_addresses: List[str],
        wallet_address: str
    ) -> Dict[str, float]:
        """Batch ERC20 token balance checks"""
        # ERC20 balanceOf function selector
        balance_selector = self.w3.keccak(
            text="balanceOf(address)"
        )[:4].hex()
        
        calls = []
        for token in token_addresses:
            # Encode function call data
            call_data = balance_selector + encode_single(
                "(address)",
                [wallet_address]
            ).hex()
            
            calls.append({
                "target": self.w3.to_checksum_address(token),
                "callData": call_data
            })
        
        # Make multicall
        try:
            block, results = await self.multicall.functions.aggregate(
                calls
            ).call()
            
            # Process results
            balances = {}
            for i, token in enumerate(token_addresses):
                try:
                    balance = int(decode_abi(["uint256"], results[i])[0])
                    balances[token] = balance
                except Exception as e:
                    balances[token] = 0
                    
            return balances
            
        except Exception as e:
            return {token: 0 for token in token_addresses}
    
    async def batch_allowances(
        self,
        token_addresses: List[str],
        owner_address: str,
        spender_address: str
    ) -> Dict[str, int]:
        """Batch ERC20 token allowance checks"""
        # ERC20 allowance function selector
        allowance_selector = self.w3.keccak(
            text="allowance(address,address)"
        )[:4].hex()
        
        calls = []
        for token in token_addresses:
            # Encode function call data
            call_data = allowance_selector + encode_single(
                "(address,address)",
                [owner_address, spender_address]
            ).hex()
            
            calls.append({
                "target": self.w3.to_checksum_address(token),
                "callData": call_data
            })
        
        # Make multicall
        try:
            block, results = await self.multicall.functions.aggregate(
                calls
            ).call()
            
            # Process results
            allowances = {}
            for i, token in enumerate(token_addresses):
                try:
                    allowance = int(decode_abi(["uint256"], results[i])[0])
                    allowances[token] = allowance
                except Exception as e:
                    allowances[token] = 0
                    
            return allowances
            
        except Exception as e:
            return {token: 0 for token in token_addresses}
    
    async def batch_metadata(
        self,
        token_addresses: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """Batch ERC20 token metadata checks (name, symbol, decimals)"""
        # Function selectors
        name_selector = self.w3.keccak(text="name()")[:4].hex()
        symbol_selector = self.w3.keccak(text="symbol()")[:4].hex()
        decimals_selector = self.w3.keccak(text="decimals()")[:4].hex()
        
        calls = []
        for token in token_addresses:
            token_addr = self.w3.to_checksum_address(token)
            calls.extend([
                {
                    "target": token_addr,
                    "callData": name_selector
                },
                {
                    "target": token_addr,
                    "callData": symbol_selector
                },
                {
                    "target": token_addr,
                    "callData": decimals_selector
                }
            ])
        
        # Make multicall
        try:
            block, results = await self.multicall.functions.aggregate(
                calls
            ).call()
            
            # Process results
            metadata = {}
            for i in range(0, len(results), 3):
                token = token_addresses[i // 3]
                try:
                    name = decode_abi(["string"], results[i])[0]
                    symbol = decode_abi(["string"], results[i + 1])[0]
                    decimals = decode_abi(["uint8"], results[i + 2])[0]
                    
                    metadata[token] = {
                        "name": name,
                        "symbol": symbol,
                        "decimals": decimals
                    }
                except Exception as e:
                    metadata[token] = {
                        "name": "Unknown",
                        "symbol": "???",
                        "decimals": 18
                    }
            
            return metadata
            
        except Exception as e:
            return {
                token: {
                    "name": "Unknown",
                    "symbol": "???",
                    "decimals": 18
                }
                for token in token_addresses
            }
    
    async def batch_token_info(
        self,
        token_addresses: List[str],
        wallet_address: str
    ) -> Dict[str, Dict[str, Any]]:
        """
        Batch all token info (balances, metadata, allowances) in one call
        """
        # Get token metadata
        metadata = await self.batch_metadata(token_addresses)
        
        # Get balances
        balances = await self.batch_balances(token_addresses, wallet_address)
        
        # Get allowances for common DEX routers
        dex_routers = {
            # Uniswap V2-style routers
            1: "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",  # Uniswap
            56: "0x10ED43C718714eb63d5aA57B78B54704E256024E",  # PancakeSwap
            137: "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506"  # SushiSwap
        }
        
        router = dex_routers.get(self.chain_id)
        allowances = {}
        if router:
            allowances = await self.batch_allowances(
                token_addresses,
                wallet_address,
                router
            )
        
        # Combine all info
        token_info = {}
        for token in token_addresses:
            token_info[token] = {
                **metadata.get(token, {}),
                "balance": balances.get(token, 0),
                "allowance": allowances.get(token, 0)
            }
        
        return token_info
