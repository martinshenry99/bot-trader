"""Risk scoring command handler"""
import logging
from typing import Optional

from bot.commands import command_handler
from services.risk_scorer import RiskScorer
from utils.formatting import format_table, format_percentage

logger = logging.getLogger(__name__)

class RiskScoringHandler:
    """Handler for risk scoring commands"""
    
    def __init__(self, risk_scorer: RiskScorer):
        self.risk_scorer = risk_scorer
    
    @command_handler("risk analyze")
    async def analyze_token(self, token_address: str, chain: str = "ethereum") -> str:
        """Analyze risk metrics for a token"""
        try:
            metrics = await self.risk_scorer.calculate_risk_score(token_address, chain)
            
            # Format response
            response = [
                "🔍 Risk Analysis Results",
                "----------------------",
                f"Overall Risk Score: {self._format_risk_level(metrics.overall_risk)}",
                "",
                "Component Scores:",
                f"• Token Risk: {format_percentage(metrics.token_score)}",
                f"• Liquidity Risk: {format_percentage(metrics.liquidity_score)}",
                f"• Volatility Risk: {format_percentage(metrics.volatility_score)}",
                f"• Market Risk: {format_percentage(metrics.market_score)}",
                f"• Security Risk: {format_percentage(metrics.security_score)}",
            ]
            
            if metrics.risk_factors:
                response.extend([
                    "",
                    "⚠️ Risk Factors Identified:",
                    *[f"• {factor}" for factor in metrics.risk_factors]
                ])
                
            return "\n".join(response)
            
        except Exception as e:
            logger.error(f"Error analyzing token risk: {str(e)}")
            return f"❌ Error analyzing token: {str(e)}"
            
    def _format_risk_level(self, risk_score: float) -> str:
        """Format risk score with color indicator"""
        if risk_score >= 0.7:
            return f"🔴 HIGH ({risk_score:.1%})"
        elif risk_score >= 0.4:
            return f"🟡 MEDIUM ({risk_score:.1%})"
        else:
            return f"🟢 LOW ({risk_score:.1%})"
