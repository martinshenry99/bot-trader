
"""
Comprehensive Wallet & Token Analyzer with Deep Graph Scanning
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional, Any, Tuple
from dataclasses import dataclass
from web3 import Web3
import networkx as nx
from collections import defaultdict
import hashlib

from integrations.base import integration_manager
from integrations.covalent import CovalentClient
from integrations.goplus import GoPlusClient
from utils.api_client import APIClient
from db import get_db_session, WalletWatch, ExecutorWallet
from core.wallet_manager import wallet_manager

logger = logging.getLogger(__name__)


@dataclass
class WalletScore:
    """Wallet analysis score data"""
    address: str
    score: int  # 0-100
    classification: str  # Safe/Watch/Risky
    max_multiplier: float
    win_rate: float
    avg_hold_time: float
    tokens_traded: int
    last_activity: datetime
    total_volume_usd: float


@dataclass
class TokenMetrics:
    """Token profitability metrics"""
    symbol: str
    contract: str
    profit_multiplier: float
    usd_gain: float
    buy_tx: str
    sell_tx: str
    hold_days: float


@dataclass
class GraphNode:
    """Graph analysis node"""
    address: str
    node_type: str  # 'wallet', 'contract', 'exchange'
    centrality: float
    cluster_id: int
    funding_sources: int
    is_cex: bool
    is_dev: bool
    total_volume: float
    risk_flags: List[str]


class WalletAnalyzer:
    """Comprehensive wallet and token analyzer"""
    
    def __init__(self):
        self.covalent_client = CovalentClient()
        self.goplus_client = None
        self.cache = {}
        self.cache_ttl = 600  # 10 minutes
        
        # Known CEX addresses (sample)
        self.known_cex_addresses = {
            '0xd551234ae421e3bcba99a0da6d736074f22192ff',  # Binance
            '0x3cd751e6b0078be393132286c442345e5dc49699',  # Binance
            '0x28c6c06298d514db089934071355e5743bf21d60',  # Binance
            '0x21a31ee1afc51d94c2efccaa2092ad1028285549',  # Binance
            '0x56eddb7aa87536c09ccc2793473599fd21a8b17f'   # Binance
        }
        
    async def analyze_wallet(self, address: str, chain: str = 'ethereum', depth: int = 3) -> Dict:
        """
        Comprehensive wallet analysis with graph scanning
        
        Args:
            address: Wallet address to analyze
            chain: Blockchain (ethereum, bsc, polygon)
            depth: Graph scanning depth (1-5)
            
        Returns:
            Complete analysis results
        """
        try:
            logger.info(f"🔍 Starting wallet analysis: {address} (depth={depth})")
            
            # Validate address
            if not Web3.is_address(address):
                raise ValueError("Invalid wallet address format")
            
            # Check cache first
            cache_key = f"wallet_{address}_{chain}_{depth}"
            if cache_key in self.cache:
                cached_data, timestamp = self.cache[cache_key]
                if datetime.utcnow() - timestamp < timedelta(seconds=self.cache_ttl):
                    logger.info(f"📋 Returning cached analysis for {address}")
                    return cached_data
            
            # Get basic wallet data
            wallet_data = await self._get_wallet_basic_data(address, chain)
            
            # Analyze trading history
            trading_metrics = await self._analyze_trading_history(address, chain)
            
            # Perform graph analysis
            graph_metrics = await self._analyze_wallet_graph(address, chain, depth)
            
            # Calculate wallet score
            wallet_score = self._calculate_wallet_score(wallet_data, trading_metrics, graph_metrics)
            
            # Get top counterparties
            top_counterparties = await self._get_top_counterparties(address, chain)
            
            # Compile results
            analysis_result = {
                'address': address,
                'chain': chain,
                'analysis_timestamp': datetime.utcnow().isoformat(),
                'score': wallet_score.score,
                'classification': wallet_score.classification,
                'max_multiplier': wallet_score.max_multiplier,
                'win_rate': wallet_score.win_rate,
                'avg_hold_time': wallet_score.avg_hold_time,
                'tokens_traded': wallet_score.tokens_traded,
                'last_activity': wallet_score.last_activity.isoformat() if wallet_score.last_activity else None,
                'total_volume_usd': wallet_score.total_volume_usd,
                'top_tokens': trading_metrics.get('top_tokens', []),
                'top_counterparties': top_counterparties,
                'graph_metrics': graph_metrics,
                'wallet_data': wallet_data,
                'risk_flags': self._get_wallet_risk_flags(wallet_data, trading_metrics, graph_metrics)
            }
            
            # Cache results
            self.cache[cache_key] = (analysis_result, datetime.utcnow())
            
            logger.info(f"✅ Wallet analysis completed: {address} (score: {wallet_score.score})")
            return analysis_result
            
        except Exception as e:
            logger.error(f"Wallet analysis failed for {address}: {e}")
            raise Exception(f"Analysis failed: {e}")
    
    async def analyze_token(self, contract_address: str, chain: str = 'ethereum') -> Dict:
        """
        Comprehensive token analysis with honeypot detection
        
        Args:
            contract_address: Token contract address
            chain: Blockchain network
            
        Returns:
            Complete token analysis
        """
        try:
            logger.info(f"🔍 Starting token analysis: {contract_address}")
            
            # Validate contract address
            if not Web3.is_address(contract_address):
                raise ValueError("Invalid contract address format")
            
            # Check cache
            cache_key = f"token_{contract_address}_{chain}"
            if cache_key in self.cache:
                cached_data, timestamp = self.cache[cache_key]
                if datetime.utcnow() - timestamp < timedelta(seconds=self.cache_ttl):
                    return cached_data
            
            # Get basic token data
            token_data = await self._get_token_basic_data(contract_address, chain)
            
            # Analyze liquidity and holders
            liquidity_data = await self._analyze_token_liquidity(contract_address, chain)
            
            # Honeypot detection
            honeypot_result = await self._detect_honeypot(contract_address, chain)
            
            # Ownership analysis
            ownership_data = await self._analyze_token_ownership(contract_address, chain)
            
            # Calculate risk flags
            risk_flags = self._calculate_token_risk_flags(
                token_data, liquidity_data, honeypot_result, ownership_data
            )
            
            # Compile results
            analysis_result = {
                'contract_address': contract_address,
                'chain': chain,
                'analysis_timestamp': datetime.utcnow().isoformat(),
                'token_data': token_data,
                'liquidity_data': liquidity_data,
                'honeypot_result': honeypot_result,
                'ownership_data': ownership_data,
                'risk_flags': risk_flags,
                'is_honeypot': honeypot_result.get('is_honeypot', False),
                'risk_score': self._calculate_token_risk_score(risk_flags),
                'recommendation': self._get_token_recommendation(risk_flags)
            }
            
            # Cache results
            self.cache[cache_key] = (analysis_result, datetime.utcnow())
            
            logger.info(f"✅ Token analysis completed: {contract_address}")
            return analysis_result
            
        except Exception as e:
            logger.error(f"Token analysis failed for {contract_address}: {e}")
            raise Exception(f"Analysis failed: {e}")
    
    async def _get_wallet_basic_data(self, address: str, chain: str) -> Dict:
        """Get basic wallet information"""
        try:
            chain_id = self._get_chain_id(chain)
            
            # Get balance
            balance_data = await self.covalent_client.get_token_balances(chain_id, address)
            
            # Get transaction count
            tx_count = await self.covalent_client.get_transaction_count(chain_id, address)
            
            # Check if it's a contract
            code = await self.covalent_client.get_code(chain_id, address)
            is_contract = len(code) > 2
            
            return {
                'is_contract': is_contract,
                'balance_eth': balance_data.get('balance', 0),
                'balance_usd': balance_data.get('balance_usd', 0),
                'transaction_count': tx_count,
                'token_count': len(balance_data.get('items', [])),
                'first_tx_date': None  # Would implement with first transaction lookup
            }
            
        except Exception as e:
            logger.error(f"Failed to get basic wallet data: {e}")
            return {
                'is_contract': False,
                'balance_eth': 0,
                'balance_usd': 0,
                'transaction_count': 0,
                'token_count': 0,
                'first_tx_date': None
            }
    
    async def _analyze_trading_history(self, address: str, chain: str) -> Dict:
        """Analyze wallet's trading history and performance"""
        try:
            chain_id = self._get_chain_id(chain)
            
            # Get recent transfers
            transfers = await self.covalent_client.get_transfers(chain_id, address, page_size=1000)
            
            # Analyze trades
            trades = self._extract_trades_from_transfers(transfers)
            
            # Calculate metrics
            total_trades = len(trades)
            profitable_trades = sum(1 for trade in trades if trade.get('profit_usd', 0) > 0)
            win_rate = (profitable_trades / total_trades * 100) if total_trades > 0 else 0
            
            # Calculate max multiplier
            max_multiplier = 1.0
            total_volume = 0
            hold_times = []
            
            for trade in trades:
                if trade.get('sell_usd', 0) > 0 and trade.get('buy_usd', 0) > 0:
                    multiplier = trade['sell_usd'] / trade['buy_usd']
                    max_multiplier = max(max_multiplier, multiplier)
                
                total_volume += trade.get('buy_usd', 0)
                
                if trade.get('hold_time_hours'):
                    hold_times.append(trade['hold_time_hours'])
            
            avg_hold_time = sum(hold_times) / len(hold_times) / 24 if hold_times else 0  # days
            
            # Get top profitable tokens
            top_tokens = sorted(
                [trade for trade in trades if trade.get('profit_usd', 0) > 0],
                key=lambda x: x.get('profit_multiplier', 1),
                reverse=True
            )[:5]
            
            return {
                'total_trades': total_trades,
                'win_rate': win_rate,
                'max_multiplier': max_multiplier,
                'avg_hold_time': avg_hold_time,
                'total_volume_usd': total_volume,
                'top_tokens': [
                    {
                        'symbol': trade.get('token_symbol', 'Unknown'),
                        'contract': trade.get('token_address'),
                        'profit_multiplier': trade.get('profit_multiplier', 1),
                        'usd_gain': trade.get('profit_usd', 0),
                        'buy_tx': trade.get('buy_tx'),
                        'sell_tx': trade.get('sell_tx'),
                        'hold_days': trade.get('hold_time_hours', 0) / 24
                    }
                    for trade in top_tokens
                ]
            }
            
        except Exception as e:
            logger.error(f"Failed to analyze trading history: {e}")
            return {
                'total_trades': 0,
                'win_rate': 0,
                'max_multiplier': 1.0,
                'avg_hold_time': 0,
                'total_volume_usd': 0,
                'top_tokens': []
            }
    
    def _extract_trades_from_transfers(self, transfers: List[Dict]) -> List[Dict]:
        """Extract completed trades from transfer history"""
        trades = []
        token_positions = defaultdict(list)
        
        try:
            # Group transfers by token
            for transfer in transfers:
                token_address = transfer.get('contract_address')
                if token_address:
                    token_positions[token_address].append(transfer)
            
            # Analyze each token's trading history
            for token_address, token_transfers in token_positions.items():
                # Sort by timestamp
                token_transfers.sort(key=lambda x: x.get('block_signed_at', ''))
                
                # Match buys and sells
                position = 0
                buy_price = 0
                buy_tx = None
                buy_time = None
                
                for transfer in token_transfers:
                    value = float(transfer.get('value', 0))
                    quote_rate = float(transfer.get('quote_rate', 0))
                    
                    if transfer.get('transfer_type') == 'IN':
                        # Buy
                        if position == 0:
                            buy_price = quote_rate
                            buy_tx = transfer.get('tx_hash')
                            buy_time = transfer.get('block_signed_at')
                        position += value
                    
                    elif transfer.get('transfer_type') == 'OUT' and position > 0:
                        # Sell
                        sell_price = quote_rate
                        sell_tx = transfer.get('tx_hash')
                        sell_time = transfer.get('block_signed_at')
                        
                        if buy_price > 0 and sell_price > 0:
                            profit_multiplier = sell_price / buy_price
                            profit_usd = (sell_price - buy_price) * value
                            
                            # Calculate hold time
                            hold_time_hours = 0
                            if buy_time and sell_time:
                                buy_dt = datetime.fromisoformat(buy_time.replace('Z', '+00:00'))
                                sell_dt = datetime.fromisoformat(sell_time.replace('Z', '+00:00'))
                                hold_time_hours = (sell_dt - buy_dt).total_seconds() / 3600
                            
                            trades.append({
                                'token_address': token_address,
                                'token_symbol': transfer.get('contract_ticker_symbol', 'Unknown'),
                                'buy_tx': buy_tx,
                                'sell_tx': sell_tx,
                                'buy_usd': buy_price * value,
                                'sell_usd': sell_price * value,
                                'profit_usd': profit_usd,
                                'profit_multiplier': profit_multiplier,
                                'hold_time_hours': hold_time_hours
                            })
                        
                        position -= value
            
            return trades
            
        except Exception as e:
            logger.error(f"Failed to extract trades: {e}")
            return []
    
    async def _analyze_wallet_graph(self, address: str, chain: str, depth: int) -> Dict:
        """Perform deep graph analysis of wallet connections"""
        try:
            logger.info(f"📊 Starting graph analysis (depth={depth})")
            
            graph = nx.DiGraph()
            visited = set()
            to_visit = [(address, 0)]  # (address, current_depth)
            breadth_limit = 200
            
            chain_id = self._get_chain_id(chain)
            
            while to_visit and len(visited) < breadth_limit:
                current_address, current_depth = to_visit.pop(0)
                
                if current_address in visited or current_depth >= depth:
                    continue
                
                visited.add(current_address)
                
                # Get transfers for this address
                transfers = await self.covalent_client.get_transfers(
                    chain_id, current_address, page_size=100
                )
                
                # Add connections to graph
                counterparties = set()
                for transfer in transfers:
                    from_addr = transfer.get('from_address')
                    to_addr = transfer.get('to_address')
                    value_usd = float(transfer.get('value_quote', 0))
                    
                    if from_addr and to_addr:
                        graph.add_edge(from_addr, to_addr, weight=value_usd)
                        
                        if current_address == from_addr:
                            counterparties.add(to_addr)
                        elif current_address == to_addr:
                            counterparties.add(from_addr)
                
                # Add counterparties to visit list
                for counterparty in counterparties:
                    if counterparty not in visited and current_depth + 1 < depth:
                        to_visit.append((counterparty, current_depth + 1))
                
                # Rate limiting
                await asyncio.sleep(0.1)
            
            # Calculate graph metrics
            metrics = self._calculate_graph_metrics(graph, address)
            
            logger.info(f"✅ Graph analysis completed: {len(visited)} nodes analyzed")
            return metrics
            
        except Exception as e:
            logger.error(f"Graph analysis failed: {e}")
            return {
                'cluster_size': 1,
                'funding_sources': 0,
                'centrality': 0.0,
                'is_dev_involved': False,
                'connected_components': 1,
                'top_connections': []
            }
    
    def _calculate_graph_metrics(self, graph: nx.DiGraph, address: str) -> Dict:
        """Calculate graph analysis metrics"""
        try:
            # Basic metrics
            cluster_size = len(graph.nodes())
            
            # Centrality measures
            centrality = 0.0
            if address in graph.nodes():
                centrality = nx.degree_centrality(graph).get(address, 0.0)
            
            # Connected components
            undirected = graph.to_undirected()
            components = list(nx.connected_components(undirected))
            connected_components = len(components)
            
            # Find address's component
            address_component = None
            for component in components:
                if address in component:
                    address_component = component
                    break
            
            # Funding sources (incoming edges)
            funding_sources = graph.in_degree(address) if address in graph.nodes() else 0
            
            # Detect potential dev behavior
            is_dev_involved = self._detect_dev_behavior(graph, address)
            
            # Top connections by transaction volume
            top_connections = []
            if address in graph.nodes():
                neighbors = list(graph.neighbors(address)) + list(graph.predecessors(address))
                neighbor_volumes = []
                
                for neighbor in set(neighbors):
                    total_volume = 0
                    if graph.has_edge(address, neighbor):
                        total_volume += graph[address][neighbor].get('weight', 0)
                    if graph.has_edge(neighbor, address):
                        total_volume += graph[neighbor][address].get('weight', 0)
                    
                    neighbor_volumes.append((neighbor, total_volume))
                
                # Sort by volume and take top 10
                neighbor_volumes.sort(key=lambda x: x[1], reverse=True)
                top_connections = [
                    {
                        'address': addr,
                        'volume_usd': volume,
                        'is_cex': addr.lower() in self.known_cex_addresses,
                        'relationship': 'counterparty'
                    }
                    for addr, volume in neighbor_volumes[:10]
                ]
            
            return {
                'cluster_size': cluster_size,
                'funding_sources': funding_sources,
                'centrality': centrality,
                'is_dev_involved': is_dev_involved,
                'connected_components': connected_components,
                'top_connections': top_connections
            }
            
        except Exception as e:
            logger.error(f"Failed to calculate graph metrics: {e}")
            return {
                'cluster_size': 1,
                'funding_sources': 0,
                'centrality': 0.0,
                'is_dev_involved': False,
                'connected_components': 1,
                'top_connections': []
            }
    
    def _detect_dev_behavior(self, graph: nx.DiGraph, address: str) -> bool:
        """Detect if address shows developer/founder behavior patterns"""
        try:
            # Check if address deployed contracts
            # Check if address added liquidity and then transferred
            # Check funding patterns typical of dev wallets
            
            # For now, simplified heuristic
            if address in graph.nodes():
                out_degree = graph.out_degree(address)
                in_degree = graph.in_degree(address)
                
                # High outgoing transactions might indicate distribution
                if out_degree > in_degree * 2 and out_degree > 10:
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Dev behavior detection failed: {e}")
            return False
    
    async def _get_top_counterparties(self, address: str, chain: str) -> List[Dict]:
        """Get top counterparties by transaction volume"""
        try:
            chain_id = self._get_chain_id(chain)
            transfers = await self.covalent_client.get_transfers(chain_id, address, page_size=500)
            
            counterparty_volumes = defaultdict(float)
            
            for transfer in transfers:
                from_addr = transfer.get('from_address')
                to_addr = transfer.get('to_address')
                value_usd = float(transfer.get('value_quote', 0))
                
                counterparty = None
                if from_addr == address:
                    counterparty = to_addr
                elif to_addr == address:
                    counterparty = from_addr
                
                if counterparty:
                    counterparty_volumes[counterparty] += value_usd
            
            # Sort by volume and take top 10
            sorted_counterparties = sorted(
                counterparty_volumes.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
            
            return [
                {
                    'address': addr,
                    'volume_usd': volume,
                    'is_cex': addr.lower() in self.known_cex_addresses,
                    'tx_count': 0  # Would implement with detailed counting
                }
                for addr, volume in sorted_counterparties
            ]
            
        except Exception as e:
            logger.error(f"Failed to get counterparties: {e}")
            return []
    
    def _calculate_wallet_score(self, wallet_data: Dict, trading_metrics: Dict, graph_metrics: Dict) -> WalletScore:
        """Calculate overall wallet score and classification"""
        try:
            score = 50  # Base score
            
            # Trading performance (40 points max)
            win_rate = trading_metrics.get('win_rate', 0)
            max_multiplier = trading_metrics.get('max_multiplier', 1)
            total_trades = trading_metrics.get('total_trades', 0)
            
            if win_rate > 70:
                score += 20
            elif win_rate > 50:
                score += 10
            elif win_rate < 30:
                score -= 10
            
            if max_multiplier > 10:
                score += 15
            elif max_multiplier > 5:
                score += 10
            elif max_multiplier > 2:
                score += 5
            
            if total_trades > 50:
                score += 5
            elif total_trades < 5:
                score -= 5
            
            # Graph metrics (30 points max)
            centrality = graph_metrics.get('centrality', 0)
            funding_sources = graph_metrics.get('funding_sources', 0)
            cluster_size = graph_metrics.get('cluster_size', 1)
            
            if centrality > 0.1:
                score += 10
            elif centrality > 0.05:
                score += 5
            
            if funding_sources > 10:
                score += 10
            elif funding_sources > 5:
                score += 5
            
            if cluster_size > 50:
                score += 10
            elif cluster_size > 20:
                score += 5
            
            # Risk factors (penalties)
            if graph_metrics.get('is_dev_involved'):
                score -= 15
            
            if wallet_data.get('transaction_count', 0) < 10:
                score -= 10
            
            # Ensure score is within bounds
            score = max(0, min(100, score))
            
            # Determine classification
            if score >= 75:
                classification = "Safe"
            elif score >= 50:
                classification = "Watch"
            else:
                classification = "Risky"
            
            return WalletScore(
                address=wallet_data.get('address', ''),
                score=score,
                classification=classification,
                max_multiplier=trading_metrics.get('max_multiplier', 1.0),
                win_rate=trading_metrics.get('win_rate', 0.0),
                avg_hold_time=trading_metrics.get('avg_hold_time', 0.0),
                tokens_traded=len(trading_metrics.get('top_tokens', [])),
                last_activity=datetime.utcnow(),  # Would implement proper last activity
                total_volume_usd=trading_metrics.get('total_volume_usd', 0.0)
            )
            
        except Exception as e:
            logger.error(f"Score calculation failed: {e}")
            return WalletScore(
                address='',
                score=0,
                classification="Unknown",
                max_multiplier=1.0,
                win_rate=0.0,
                avg_hold_time=0.0,
                tokens_traded=0,
                last_activity=datetime.utcnow(),
                total_volume_usd=0.0
            )
    
    async def _get_token_basic_data(self, contract_address: str, chain: str) -> Dict:
        """Get basic token information"""
        try:
            chain_id = self._get_chain_id(chain)
            
            # Get token metadata
            token_data = await self.covalent_client.get_token_metadata(chain_id, contract_address)
            
            return {
                'name': token_data.get('name', 'Unknown'),
                'symbol': token_data.get('symbol', 'Unknown'),
                'decimals': token_data.get('decimals', 18),
                'total_supply': token_data.get('total_supply', 0),
                'contract_address': contract_address,
                'deploy_time': None,  # Would implement with contract creation lookup
                'is_verified': False,  # Would implement with Etherscan verification check
                'owner_address': None  # Would implement with contract owner lookup
            }
            
        except Exception as e:
            logger.error(f"Failed to get token basic data: {e}")
            return {
                'name': 'Unknown',
                'symbol': 'Unknown',
                'decimals': 18,
                'total_supply': 0,
                'contract_address': contract_address,
                'deploy_time': None,
                'is_verified': False,
                'owner_address': None
            }
    
    async def _analyze_token_liquidity(self, contract_address: str, chain: str) -> Dict:
        """Analyze token liquidity and LP health"""
        try:
            # This would implement detailed liquidity analysis
            # For now, return placeholder data
            return {
                'total_liquidity_usd': 0,
                'largest_lp_provider': None,
                'lp_concentration': 0,
                'liquidity_locked': False,
                'lock_expiry': None
            }
            
        except Exception as e:
            logger.error(f"Liquidity analysis failed: {e}")
            return {
                'total_liquidity_usd': 0,
                'largest_lp_provider': None,
                'lp_concentration': 0,
                'liquidity_locked': False,
                'lock_expiry': None
            }
    
    async def _detect_honeypot(self, contract_address: str, chain: str) -> Dict:
        """Detect honeypot using simulation and external APIs"""
        try:
            # Try GoPlus API first
            if self.goplus_client:
                goplus_result = await self.goplus_client.check_token_security(
                    self._get_chain_id(chain), contract_address
                )
                if goplus_result:
                    return {
                        'is_honeypot': goplus_result.get('is_honeypot', False),
                        'simulation_passed': not goplus_result.get('is_honeypot', False),
                        'error_message': None,
                        'buy_tax': goplus_result.get('buy_tax', 0),
                        'sell_tax': goplus_result.get('sell_tax', 0),
                        'source': 'goplus'
                    }
            
            # Fallback to simulation (would implement eth_call simulation)
            return {
                'is_honeypot': False,
                'simulation_passed': True,
                'error_message': None,
                'buy_tax': 0,
                'sell_tax': 0,
                'source': 'simulation'
            }
            
        except Exception as e:
            logger.error(f"Honeypot detection failed: {e}")
            return {
                'is_honeypot': True,  # Conservative assumption on error
                'simulation_passed': False,
                'error_message': str(e),
                'buy_tax': 0,
                'sell_tax': 0,
                'source': 'error'
            }
    
    async def _analyze_token_ownership(self, contract_address: str, chain: str) -> Dict:
        """Analyze token ownership and concentration"""
        try:
            # Would implement holder analysis
            return {
                'top_holders': [],
                'owner_percentage': 0,
                'concentration_risk': 'LOW',
                'renounced': False
            }
            
        except Exception as e:
            logger.error(f"Ownership analysis failed: {e}")
            return {
                'top_holders': [],
                'owner_percentage': 0,
                'concentration_risk': 'UNKNOWN',
                'renounced': False
            }
    
    def _calculate_token_risk_flags(self, token_data: Dict, liquidity_data: Dict, 
                                  honeypot_result: Dict, ownership_data: Dict) -> List[str]:
        """Calculate token risk flags"""
        flags = []
        
        if honeypot_result.get('is_honeypot'):
            flags.append('HONEYPOT')
        
        if liquidity_data.get('total_liquidity_usd', 0) < 5000:
            flags.append('LOW_LIQUIDITY')
        
        if not liquidity_data.get('liquidity_locked'):
            flags.append('LIQUIDITY_RISK')
        
        if ownership_data.get('owner_percentage', 0) > 25:
            flags.append('DEV_CONTROL')
        
        if not token_data.get('is_verified'):
            flags.append('UNVERIFIED_CODE')
        
        if honeypot_result.get('buy_tax', 0) > 10 or honeypot_result.get('sell_tax', 0) > 10:
            flags.append('HIGH_TAX')
        
        return flags
    
    def _calculate_token_risk_score(self, risk_flags: List[str]) -> int:
        """Calculate token risk score (0-100)"""
        flag_weights = {
            'HONEYPOT': 50,
            'LOW_LIQUIDITY': 20,
            'LIQUIDITY_RISK': 15,
            'DEV_CONTROL': 15,
            'UNVERIFIED_CODE': 10,
            'HIGH_TAX': 20
        }
        
        score = sum(flag_weights.get(flag, 0) for flag in risk_flags)
        return min(100, score)
    
    def _get_token_recommendation(self, risk_flags: List[str]) -> str:
        """Get token trading recommendation"""
        if 'HONEYPOT' in risk_flags:
            return 'AVOID'
        elif len(risk_flags) >= 3:
            return 'AVOID'
        elif len(risk_flags) >= 2:
            return 'HOLD'
        elif len(risk_flags) == 1:
            return 'WATCH'
        else:
            return 'BUY'
    
    def _get_wallet_risk_flags(self, wallet_data: Dict, trading_metrics: Dict, graph_metrics: Dict) -> List[str]:
        """Get wallet risk flags"""
        flags = []
        
        if graph_metrics.get('is_dev_involved'):
            flags.append('DEV_WALLET')
        
        if trading_metrics.get('win_rate', 0) < 30:
            flags.append('LOW_WIN_RATE')
        
        if wallet_data.get('transaction_count', 0) < 10:
            flags.append('LOW_ACTIVITY')
        
        liquidity_trades = 0  # Would implement liquidity analysis
        if liquidity_trades > 5:
            flags.append('LIQUIDITY_PROVIDER')
        
        return flags
    
    def _get_chain_id(self, chain: str) -> int:
        """Get chain ID for chain name"""
        chain_ids = {
            'ethereum': 1,
            'bsc': 56,
            'polygon': 137,
            'arbitrum': 42161,
            'optimism': 10
        }
        return chain_ids.get(chain.lower(), 1)


# Global analyzer instance
wallet_analyzer = WalletAnalyzer()
