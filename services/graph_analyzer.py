"""
Graph analysis and summary generation for wallet analysis
"""

import networkx as nx
from typing import Dict, List, Set, Tuple
from dataclasses import dataclass
from decimal import Decimal
import logging
from functools import lru_cache
import time
from services.covalent import CovalentService
from services.helius import HeliusService
from utils.cache import cache_result

logger = logging.getLogger(__name__)

@dataclass
class GraphSummary:
    """Summary of wallet graph analysis"""
    centrality_score: float  # 0-1 scale
    cluster_size: int
    influential_neighbors: List[Dict]  # Top counterparties
    total_volume_usd: Decimal
    transaction_count: int
    timestamp: int

class GraphAnalyzer:
    """Wallet graph analysis service"""
    
    def __init__(self, covalent: CovalentService, helius: HeliusService):
        self.covalent = covalent
        self.helius = helius
        self.cache_ttl = 3600  # 1 hour cache
        
        # Analysis parameters
        self.min_tx_value = 1000  # Minimum USD value to consider
        self.max_neighbors = 100  # Limit graph size
        self.top_neighbors = 5  # Number of top counterparties to return
    
    @cache_result(ttl=3600)
    async def get_wallet_graph_summary(
        self,
        wallet_address: str,
        chain: str,
        days: int = 30
    ) -> GraphSummary:
        """Generate graph summary for a wallet"""
        try:
            # Get transaction history
            if chain == "solana":
                transactions = await self.helius.get_wallet_history(
                    wallet_address,
                    days=days
                )
            else:
                transactions = await self.covalent.get_wallet_history(
                    wallet_address,
                    chain,
                    days=days
                )
            
            # Build graph
            G = self._build_transaction_graph(wallet_address, transactions)
            
            # Calculate metrics
            centrality = self._calculate_centrality(G, wallet_address)
            cluster = self._get_wallet_cluster(G, wallet_address)
            neighbors = self._get_influential_neighbors(G, wallet_address)
            
            # Calculate volume
            volume = self._calculate_total_volume(transactions)
            
            return GraphSummary(
                centrality_score=centrality,
                cluster_size=len(cluster),
                influential_neighbors=neighbors,
                total_volume_usd=volume,
                transaction_count=len(transactions),
                timestamp=int(time.time())
            )
            
        except Exception as e:
            logger.error(f"Error generating graph summary: {str(e)}")
            raise
    
    def _build_transaction_graph(
        self,
        wallet: str,
        transactions: List[Dict]
    ) -> nx.Graph:
        """Build transaction graph from history"""
        G = nx.Graph()
        
        # Add edges for each transaction
        for tx in transactions:
            if tx['usd_value'] < self.min_tx_value:
                continue
                
            from_addr = tx['from_address']
            to_addr = tx['to_address']
            
            # Add edge with volume as weight
            if G.has_edge(from_addr, to_addr):
                G[from_addr][to_addr]['volume'] += tx['usd_value']
                G[from_addr][to_addr]['count'] += 1
            else:
                G.add_edge(
                    from_addr,
                    to_addr,
                    volume=tx['usd_value'],
                    count=1
                )
        
        # Prune to manage size
        if len(G) > self.max_neighbors:
            G = self._prune_graph(G, wallet)
            
        return G
    
    def _prune_graph(self, G: nx.Graph, wallet: str) -> nx.Graph:
        """Prune graph to include only important nodes"""
        # Get nodes sorted by volume
        volumes = {}
        for u, v, data in G.edges(data=True):
            volumes[u] = volumes.get(u, 0) + data['volume']
            volumes[v] = volumes.get(v, 0) + data['volume']
            
        # Sort nodes by volume
        sorted_nodes = sorted(
            volumes.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # Keep wallet and top nodes
        keep_nodes = {wallet}  # Always keep main wallet
        for node, _ in sorted_nodes[:self.max_neighbors]:
            keep_nodes.add(node)
            
        # Create new graph with only important nodes
        H = G.subgraph(keep_nodes).copy()
        return H
    
    def _calculate_centrality(self, G: nx.Graph, wallet: str) -> float:
        """Calculate degree centrality score"""
        if len(G) < 2:
            return 0.0
            
        centrality = nx.degree_centrality(G)
        return centrality.get(wallet, 0.0)
    
    def _get_wallet_cluster(self, G: nx.Graph, wallet: str) -> Set[str]:
        """Get connected component containing wallet"""
        if not G.has_node(wallet):
            return set()
            
        return nx.node_connected_component(G, wallet)
    
    def _get_influential_neighbors(
        self,
        G: nx.Graph,
        wallet: str
    ) -> List[Dict]:
        """Get most influential neighboring wallets"""
        if not G.has_node(wallet):
            return []
            
        # Calculate neighbor importance scores
        neighbors = []
        for neighbor in G.neighbors(wallet):
            edge_data = G[wallet][neighbor]
            
            # Score based on volume and frequency
            importance = edge_data['volume'] * (1 + edge_data['count'] / 100)
            
            neighbors.append({
                'address': neighbor,
                'volume_usd': edge_data['volume'],
                'tx_count': edge_data['count'],
                'importance': importance
            })
        
        # Sort by importance score
        neighbors.sort(key=lambda x: x['importance'], reverse=True)
        
        return neighbors[:self.top_neighbors]
    
    def _calculate_total_volume(self, transactions: List[Dict]) -> Decimal:
        """Calculate total transaction volume"""
        return sum(
            Decimal(str(tx['usd_value']))
            for tx in transactions
            if tx['usd_value'] >= self.min_tx_value
        )
    
    def generate_text_summary(self, summary: GraphSummary) -> str:
        """Generate human-readable summary"""
        lines = []
        
        # Activity stats
        lines.append(f"📊 Transaction Count: {summary.transaction_count}")
        lines.append(f"💰 Total Volume: ${summary.total_volume_usd:,.2f}")
        
        # Network metrics
        lines.append(f"🌐 Network Centrality: {summary.centrality_score:.2%}")
        lines.append(f"👥 Trading Cluster Size: {summary.cluster_size} wallets")
        
        # Top counterparties
        lines.append("\n🤝 Top Trading Partners:")
        for i, neighbor in enumerate(summary.influential_neighbors, 1):
            lines.append(
                f"{i}. {neighbor['address'][:8]}..."
                f" (${neighbor['volume_usd']:,.0f},"
                f" {neighbor['tx_count']} trades)"
            )
        
        return "\n".join(lines)
