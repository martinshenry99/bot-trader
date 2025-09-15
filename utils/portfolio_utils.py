"""
Portfolio visualization and analysis utilities
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import numpy as np
from decimal import Decimal

logger = logging.getLogger(__name__)

def generate_portfolio_chart(portfolio: Dict) -> Optional[str]:
    """Generate portfolio visualization chart"""
    try:
        # Create figure with subplots
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 12))
        fig.suptitle('Portfolio Analysis', fontsize=16)
        
        # Plot 1: Chain Distribution (Pie Chart)
        chain_values = [
            float(data['value_usd'])
            for data in portfolio['chains'].values()
        ]
        chain_labels = [
            f"{chain.upper()}\n{data['percentage']:.1f}%"
            for chain, data in portfolio['chains'].items()
        ]
        
        ax1.pie(
            chain_values,
            labels=chain_labels,
            autopct='%1.1f%%',
            startangle=90
        )
        ax1.set_title('Chain Distribution')
        
        # Plot 2: Top Positions (Bar Chart)
        positions = portfolio['top_positions']
        tokens = [pos['token'] for pos in positions]
        values = [float(pos['value_usd']) for pos in positions]
        changes = [float(pos['24h_change']) for pos in positions]
        
        x = np.arange(len(tokens))
        width = 0.35
        
        bars = ax2.bar(x, values, width, label='Value (USD)')
        
        # Color bars based on 24h change
        for bar, change in zip(bars, changes):
            color = 'g' if change >= 0 else 'r'
            bar.set_color(color)
            
        ax2.set_ylabel('USD Value')
        ax2.set_title('Top Positions')
        ax2.set_xticks(x)
        ax2.set_xticklabels(tokens, rotation=45)
        
        # Add value labels on bars
        for bar in bars:
            height = bar.get_height()
            ax2.text(
                bar.get_x() + bar.get_width()/2.,
                height,
                f'${height:,.0f}',
                ha='center',
                va='bottom'
            )
            
        # Adjust layout and save
        plt.tight_layout()
        chart_path = 'portfolio_chart.png'
        plt.savefig(chart_path)
        plt.close()
        
        return chart_path
        
    except Exception as e:
        logger.error(f"Error generating portfolio chart: {str(e)}")
        return None

def generate_performance_chart(
    snapshots: List[Dict],
    days: int = 30
) -> Optional[str]:
    """Generate performance history chart"""
    try:
        # Create figure
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 12))
        fig.suptitle('Portfolio Performance History', fontsize=16)
        
        # Prepare data
        dates = [s['timestamp'] for s in snapshots]
        values = [float(s['total_value_usd']) for s in snapshots]
        
        # Calculate daily returns
        returns = []
        for i in range(1, len(values)):
            daily_return = (values[i] - values[i-1]) / values[i-1] * 100
            returns.append(daily_return)
            
        # Plot 1: Portfolio Value Over Time
        ax1.plot(dates, values, 'b-')
        ax1.set_title('Portfolio Value (USD)')
        ax1.set_xlabel('Date')
        ax1.set_ylabel('USD Value')
        ax1.grid(True)
        
        # Format x-axis dates
        ax1.tick_params(axis='x', rotation=45)
        
        # Plot 2: Daily Returns
        ax2.bar(dates[1:], returns)
        ax2.set_title('Daily Returns (%)')
        ax2.set_xlabel('Date')
        ax2.set_ylabel('Return (%)')
        ax2.grid(True)
        
        # Color bars based on return
        bars = ax2.patches
        for bar in bars:
            if bar.get_height() >= 0:
                bar.set_color('g')
            else:
                bar.set_color('r')
                
        # Format x-axis dates
        ax2.tick_params(axis='x', rotation=45)
        
        # Adjust layout and save
        plt.tight_layout()
        chart_path = 'performance_chart.png'
        plt.savefig(chart_path)
        plt.close()
        
        return chart_path
        
    except Exception as e:
        logger.error(f"Error generating performance chart: {str(e)}")
        return None

def calculate_portfolio_metrics(
    portfolio: Dict,
    snapshots: List[Dict]
) -> Dict:
    """Calculate advanced portfolio metrics"""
    try:
        metrics = {}
        
        # Calculate returns
        if len(snapshots) >= 2:
            initial_value = float(snapshots[0]['total_value_usd'])
            final_value = float(portfolio['total_value_usd'])
            
            # Total return
            total_return = (final_value - initial_value) / initial_value * 100
            metrics['total_return'] = total_return
            
            # Calculate daily returns
            daily_returns = []
            values = [float(s['total_value_usd']) for s in snapshots]
            for i in range(1, len(values)):
                daily_return = (values[i] - values[i-1]) / values[i-1]
                daily_returns.append(daily_return)
                
            # Volatility (annualized)
            daily_volatility = np.std(daily_returns)
            annual_volatility = daily_volatility * np.sqrt(252)
            metrics['volatility'] = annual_volatility * 100
            
            # Sharpe ratio (assuming risk-free rate of 2%)
            risk_free_rate = 0.02
            excess_returns = [r - risk_free_rate/252 for r in daily_returns]
            sharpe_ratio = (
                np.mean(excess_returns) /
                np.std(excess_returns) *
                np.sqrt(252)
            )
            metrics['sharpe_ratio'] = sharpe_ratio
            
            # Maximum drawdown
            running_max = np.maximum.accumulate(values)
            drawdowns = (running_max - values) / running_max * 100
            max_drawdown = np.max(drawdowns)
            metrics['max_drawdown'] = max_drawdown
            
        # Diversification metrics
        total_value = float(portfolio['total_value_usd'])
        
        # Herfindahl-Hirschman Index (HHI) for concentration
        position_weights = [
            float(pos['value_usd']) / total_value
            for pos in portfolio['top_positions']
        ]
        hhi = sum(w * w for w in position_weights)
        metrics['concentration_index'] = hhi * 100
        
        # Chain diversification score
        chain_weights = [
            float(data['value_usd']) / total_value
            for data in portfolio['chains'].values()
        ]
        chain_hhi = sum(w * w for w in chain_weights)
        metrics['chain_diversification'] = (1 - chain_hhi) * 100
        
        # Risk-adjusted metrics
        if 'volatility' in metrics:
            # Sortino ratio (downside risk only)
            negative_returns = [r for r in daily_returns if r < 0]
            downside_vol = (
                np.std(negative_returns) * np.sqrt(252)
                if negative_returns
                else 0
            )
            
            excess_return = total_return - risk_free_rate
            sortino_ratio = (
                excess_return / downside_vol
                if downside_vol > 0
                else 0
            )
            metrics['sortino_ratio'] = sortino_ratio
            
            # Calmar ratio (return / max drawdown)
            calmar_ratio = (
                total_return / max_drawdown
                if max_drawdown > 0
                else 0
            )
            metrics['calmar_ratio'] = calmar_ratio
            
        return metrics
        
    except Exception as e:
        logger.error(f"Error calculating portfolio metrics: {str(e)}")
        return {}
