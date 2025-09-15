"""
Enhanced error handling and user feedback system
"""
from typing import Dict, Optional, Any
import logging
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)

class ErrorCategory(Enum):
    """Categories of errors for better handling"""
    VALIDATION = "validation"
    EXECUTION = "execution"
    EXTERNAL = "external"
    SYSTEM = "system"
    SECURITY = "security"
    USER = "user"

@dataclass
class ErrorContext:
    """Context information for errors"""
    category: ErrorCategory
    code: str
    message: str
    details: Dict[str, Any]
    user_message: str
    suggestions: Optional[list] = None

class ErrorHandler:
    """Handles error processing and user feedback"""
    
    def __init__(self):
        # Error message templates
        self.templates = {
            # Validation errors
            'insufficient_balance': ErrorContext(
                category=ErrorCategory.VALIDATION,
                code='V001',
                message='Insufficient balance for transaction',
                details={},
                user_message=(
                    "You don't have enough {token} for this trade.\n"
                    "Required: {required}\n"
                    "Available: {available}"
                ),
                suggestions=[
                    "Try a smaller amount",
                    "Check your wallet balance"
                ]
            ),
            'high_price_impact': ErrorContext(
                category=ErrorCategory.VALIDATION,
                code='V002',
                message='Price impact too high',
                details={},
                user_message=(
                    "Transaction would cause high price impact of {impact}%.\n"
                    "Maximum allowed: {max_impact}%"
                ),
                suggestions=[
                    "Try a smaller amount",
                    "Split into multiple trades"
                ]
            ),
            
            # Execution errors
            'transaction_failed': ErrorContext(
                category=ErrorCategory.EXECUTION,
                code='E001',
                message='Transaction execution failed',
                details={},
                user_message=(
                    "Transaction failed: {reason}\n"
                    "Gas used: {gas_used}"
                ),
                suggestions=[
                    "Check transaction on explorer",
                    "Try increasing slippage",
                    "Contact support if issue persists"
                ]
            ),
            'api_error': ErrorContext(
                category=ErrorCategory.EXTERNAL,
                code='E002',
                message='External API error',
                details={},
                user_message=(
                    "Service temporarily unavailable: {service}\n"
                    "Error: {message}"
                ),
                suggestions=[
                    "Try again in a few minutes",
                    "Check service status"
                ]
            ),
            
            # Security errors
            'honeypot_detected': ErrorContext(
                category=ErrorCategory.SECURITY,
                code='S001',
                message='Token detected as honeypot',
                details={},
                user_message=(
                    "⚠️ SECURITY ALERT: Honeypot Detected!\n"
                    "This token has been flagged as potentially malicious.\n"
                    "Trading has been blocked for your safety."
                ),
                suggestions=[
                    "Do not trade this token",
                    "Report token to community"
                ]
            ),
            'high_risk': ErrorContext(
                category=ErrorCategory.SECURITY,
                code='S002',
                message='High risk token operation',
                details={},
                user_message=(
                    "⚠️ HIGH RISK OPERATION\n"
                    "Risk Factors:\n"
                    "{risk_factors}\n\n"
                    "Proceed with extreme caution."
                ),
                suggestions=[
                    "Review token on explorer",
                    "Check token security score",
                    "Use small test amount first"
                ]
            ),
            
            # System errors
            'rate_limit': ErrorContext(
                category=ErrorCategory.SYSTEM,
                code='SY001',
                message='Rate limit exceeded',
                details={},
                user_message=(
                    "Rate limit reached for {service}.\n"
                    "Please wait {wait_time} seconds."
                ),
                suggestions=[
                    "Try again later",
                    "Reduce request frequency"
                ]
            ),
            'system_overload': ErrorContext(
                category=ErrorCategory.SYSTEM,
                code='SY002',
                message='System under high load',
                details={},
                user_message=(
                    "System is currently experiencing high load.\n"
                    "Your request has been queued."
                ),
                suggestions=[
                    "Try again in a few minutes",
                    "Check system status"
                ]
            )
        }
    
    def handle_error(
        self,
        error_code: str,
        context: Dict[str, Any] = None
    ) -> ErrorContext:
        """Handle an error and generate appropriate response"""
        try:
            # Get error template
            error = self.templates.get(error_code)
            if not error:
                return self._create_generic_error()
            
            # Create new instance to avoid modifying template
            error = ErrorContext(
                category=error.category,
                code=error.code,
                message=error.message,
                details=context or {},
                user_message=error.user_message,
                suggestions=error.suggestions
            )
            
            # Format user message with context
            if context:
                error.user_message = error.user_message.format(**context)
            
            # Log error
            logger.error(
                f"Error {error.code}: {error.message}",
                extra={
                    'category': error.category.value,
                    'details': error.details
                }
            )
            
            return error
            
        except Exception as e:
            logger.error(f"Error handling error: {e}")
            return self._create_generic_error()
    
    def _create_generic_error(self) -> ErrorContext:
        """Create a generic error response"""
        return ErrorContext(
            category=ErrorCategory.SYSTEM,
            code='ERR000',
            message='An unexpected error occurred',
            details={},
            user_message=(
                "Sorry, something went wrong.\n"
                "Please try again or contact support."
            ),
            suggestions=[
                "Try again later",
                "Contact support if issue persists"
            ]
        )
    
    def is_retryable(self, error: ErrorContext) -> bool:
        """Check if an error is retryable"""
        retryable_categories = [
            ErrorCategory.EXTERNAL,
            ErrorCategory.SYSTEM
        ]
        return error.category in retryable_categories
    
    def get_retry_delay(self, error: ErrorContext) -> int:
        """Get recommended retry delay in seconds"""
        delays = {
            ErrorCategory.EXTERNAL: 5,
            ErrorCategory.SYSTEM: 30,
            ErrorCategory.VALIDATION: 0,
            ErrorCategory.EXECUTION: 15,
            ErrorCategory.SECURITY: 0,
            ErrorCategory.USER: 0
        }
        return delays.get(error.category, 30)

# Global instance
error_handler = ErrorHandler()

# Example usage:
"""
try:
    # Some operation
    pass
except Exception as e:
    error = error_handler.handle_error(
        'insufficient_balance',
        {
            'token': 'ETH',
            'required': '1.5',
            'available': '1.0'
        }
    )
    # Use error.user_message for user feedback
    # Use error.suggestions for helping user resolve the issue
"""
