"""
Tests for wallet graph analysis
"""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, Mock
import networkx as nx
from datetime import datetime, timedelta
from services.graph_analyzer import GraphAnalyzer, GraphSummary

@pytest.fixture
def mock_services():
    """Mock external service dependencies"""
    return {
        'covalent': AsyncMock(),
        'helius': AsyncMock()
    }

@pytest.fixture
def graph_analyzer(mock_services):
    """Create graph analyzer with mocked services"""
    return GraphAnalyzer(
        mock_services['covalent'],
        mock_services['helius']
    )

@pytest.fixture
def sample_transactions():
    """Sample transaction history"""
    return [
        {
            'from_address': '0xwallet',
            'to_address': '0xtrader1',
            'usd_value': 5000,
            'timestamp': int((datetime.now() - timedelta(days=1)).timestamp())
        },
        {
            'from_address': '0xtrader1',
            'to_address': '0xwallet',
            'usd_value': 6000,
            'timestamp': int((datetime.now() - timedelta(days=2)).timestamp())
        },
        {
            'from_address': '0xwallet',
            'to_address': '0xtrader2',
            'usd_value': 3000,
            'timestamp': int((datetime.now() - timedelta(days=3)).timestamp())
        },
        {
            'from_address': '0xtrader2',
            'to_address': '0xtrader3',
            'usd_value': 2000,
            'timestamp': int((datetime.now() - timedelta(days=4)).timestamp())
        }
    ]

async def test_wallet_graph_summary(graph_analyzer, mock_services, sample_transactions):
    """Test wallet graph summary generation"""
    wallet = "0xwallet"
    chain = "ethereum"
    
    # Mock transaction history
    mock_services['covalent'].get_wallet_history.return_value = sample_transactions
    
    # Get summary
    summary = await graph_analyzer.get_wallet_graph_summary(wallet, chain)
    
    assert isinstance(summary, GraphSummary)
    assert summary.transaction_count == len(sample_transactions)
    assert summary.total_volume_usd == Decimal('16000')
    assert 0 <= summary.centrality_score <= 1
    assert summary.cluster_size > 0
    assert len(summary.influential_neighbors) <= graph_analyzer.top_neighbors

def test_transaction_graph_building(graph_analyzer, sample_transactions):
    """Test transaction graph construction"""
    wallet = "0xwallet"
    
    # Build graph
    G = graph_analyzer._build_transaction_graph(wallet, sample_transactions)
    
    assert isinstance(G, nx.Graph)
    assert G.has_node(wallet)
    assert G.has_node("0xtrader1")
    assert G.has_edge(wallet, "0xtrader1")
    
    # Check edge attributes
    edge = G[wallet]["0xtrader1"]
    assert 'volume' in edge
    assert 'count' in edge

def test_graph_pruning(graph_analyzer):
    """Test graph pruning logic"""
    # Create large test graph
    G = nx.Graph()
    main_wallet = "0xwallet"
    
    # Add many edges with different volumes
    for i in range(150):  # More than max_neighbors
        G.add_edge(
            main_wallet,
            f"0xtrader{i}",
            volume=1000 + i,  # Increasing volume
            count=1
        )
    
    # Prune graph
    H = graph_analyzer._prune_graph(G, main_wallet)
    
    assert len(H) <= graph_analyzer.max_neighbors + 1  # +1 for main wallet
    assert H.has_node(main_wallet)  # Main wallet must be retained

def test_centrality_calculation(graph_analyzer):
    """Test centrality score calculation"""
    # Create test graph
    G = nx.Graph()
    wallet = "0xwallet"
    
    # Add star topology centered on wallet
    for i in range(5):
        G.add_edge(wallet, f"0xtrader{i}", volume=1000, count=1)
    
    # Add some edges between traders
    G.add_edge("0xtrader0", "0xtrader1", volume=500, count=1)
    G.add_edge("0xtrader1", "0xtrader2", volume=500, count=1)
    
    centrality = graph_analyzer._calculate_centrality(G, wallet)
    assert centrality > 0.5  # Should be relatively central

def test_influential_neighbors(graph_analyzer):
    """Test influential neighbor identification"""
    # Create test graph
    G = nx.Graph()
    wallet = "0xwallet"
    
    # Add neighbors with different volumes
    neighbors = {
        "0xhigh": {"volume": 10000, "count": 5},
        "0xmedium": {"volume": 5000, "count": 3},
        "0xlow": {"volume": 1000, "count": 1}
    }
    
    for addr, data in neighbors.items():
        G.add_edge(
            wallet,
            addr,
            volume=data["volume"],
            count=data["count"]
        )
    
    influential = graph_analyzer._get_influential_neighbors(G, wallet)
    
    assert len(influential) == len(neighbors)
    assert influential[0]['address'] == "0xhigh"  # Highest volume should be first
    assert influential[-1]['address'] == "0xlow"  # Lowest volume should be last

def test_text_summary_generation(graph_analyzer):
    """Test human-readable summary generation"""
    summary = GraphSummary(
        centrality_score=0.75,
        cluster_size=10,
        influential_neighbors=[
            {
                'address': '0xtrader1',
                'volume_usd': Decimal('10000'),
                'tx_count': 5,
                'importance': 10500
            },
            {
                'address': '0xtrader2',
                'volume_usd': Decimal('5000'),
                'tx_count': 3,
                'importance': 5300
            }
        ],
        total_volume_usd=Decimal('15000'),
        transaction_count=8,
        timestamp=int(datetime.now().timestamp())
    )
    
    text = graph_analyzer.generate_text_summary(summary)
    
    assert isinstance(text, str)
    assert '75%' in text  # Centrality percentage
    assert '10 wallets' in text  # Cluster size
    assert '$15,000' in text  # Volume
    assert '8' in text  # Transaction count
    assert '0xtrader1' in text  # Top trader
    assert '5 trades' in text  # Trade count

async def test_solana_support(graph_analyzer, mock_services, sample_transactions):
    """Test Solana chain support"""
    wallet = "SolanaWallet"
    chain = "solana"
    
    # Mock Helius response
    mock_services['helius'].get_wallet_history.return_value = sample_transactions
    
    summary = await graph_analyzer.get_wallet_graph_summary(wallet, chain)
    
    assert isinstance(summary, GraphSummary)
    # Verify Helius was called instead of Covalent
    assert mock_services['helius'].get_wallet_history.called
    assert not mock_services['covalent'].get_wallet_history.called

def test_minimum_transaction_filtering(graph_analyzer, sample_transactions):
    """Test minimum transaction value filtering"""
    wallet = "0xwallet"
    
    # Add some small transactions
    small_txs = [
        {
            'from_address': wallet,
            'to_address': '0xsmall',
            'usd_value': 100,  # Below minimum
            'timestamp': int(datetime.now().timestamp())
        }
    ]
    
    all_txs = sample_transactions + small_txs
    
    # Build graph
    G = graph_analyzer._build_transaction_graph(wallet, all_txs)
    
    # Small transaction should be filtered out
    assert not G.has_node('0xsmall')
    
    # Calculate volume
    volume = graph_analyzer._calculate_total_volume(all_txs)
    assert volume == Decimal('16000')  # Only large transactions
