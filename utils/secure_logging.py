"""Secure logging system with sensitive data masking"""
import logging
import json
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
import re
from pathlib import Path

class SecureLogger:
    """Secure logging with sensitive data masking"""
    
    def __init__(self, log_dir: str):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize loggers
        self.trade_logger = self._setup_logger(
            'trade_logger',
            self.log_dir / 'trades.log'
        )
        self.error_logger = self._setup_logger(
            'error_logger',
            self.log_dir / 'errors.log'
        )
        self.security_logger = self._setup_logger(
            'security_logger',
            self.log_dir / 'security.log'
        )
        
        # Patterns for masking
        self.patterns = {
            'private_key': re.compile(r'0x[a-fA-F0-9]{64}'),
            'mnemonic': re.compile(r'\b(\w+\s+){11,23}\w+\b'),
            'api_key': re.compile(r'[A-Za-z0-9-_]{20,}'),
            'wallet': re.compile(r'0x[a-fA-F0-9]{40}')
        }
    
    def _setup_logger(
        self,
        name: str,
        log_file: Path,
        level: int = logging.INFO
    ) -> logging.Logger:
        """Set up a logger instance"""
        logger = logging.getLogger(name)
        logger.setLevel(level)
        
        # File handler
        handler = logging.FileHandler(log_file)
        handler.setLevel(level)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        
        logger.addHandler(handler)
        return logger
    
    def mask_sensitive_data(self, text: str) -> str:
        """Mask sensitive information in text"""
        masked = text
        
        for pattern_name, pattern in self.patterns.items():
            if pattern_name == 'wallet':
                # Keep first 6 and last 4 characters of wallet addresses
                masked = pattern.sub(
                    lambda m: f"{m.group(0)[:6]}...{m.group(0)[-4:]}",
                    masked
                )
            else:
                # Completely mask other sensitive data
                masked = pattern.sub('[REDACTED]', masked)
        
        return masked
    
    def log_trade(
        self,
        trade_type: str,
        token_address: str,
        amount: Union[int, float, str],
        user_id: str,
        details: Optional[Dict] = None,
        success: bool = True
    ):
        """Log trade execution"""
        try:
            log_entry = {
                'timestamp': datetime.utcnow().isoformat(),
                'type': trade_type,
                'token': self.mask_sensitive_data(token_address),
                'amount': str(amount),
                'user': self.mask_sensitive_data(str(user_id)),
                'success': success
            }
            
            if details:
                # Mask sensitive data in details
                masked_details = {}
                for key, value in details.items():
                    if isinstance(value, str):
                        masked_details[key] = self.mask_sensitive_data(value)
                    else:
                        masked_details[key] = value
                log_entry['details'] = masked_details
            
            self.trade_logger.info(json.dumps(log_entry))
            
        except Exception as e:
            self.error_logger.error(
                f"Failed to log trade: {str(e)}"
            )
    
    def log_error(
        self,
        error: Exception,
        context: Dict[str, Any],
        user_id: Optional[str] = None
    ):
        """Log error with context"""
        try:
            log_entry = {
                'timestamp': datetime.utcnow().isoformat(),
                'error_type': error.__class__.__name__,
                'error_message': str(error),
                'user': self.mask_sensitive_data(str(user_id)) if user_id else None
            }
            
            # Mask sensitive data in context
            masked_context = {}
            for key, value in context.items():
                if isinstance(value, str):
                    masked_context[key] = self.mask_sensitive_data(value)
                else:
                    masked_context[key] = value
            
            log_entry['context'] = masked_context
            
            # Add stack trace if available
            if hasattr(error, '__traceback__'):
                import traceback
                trace = traceback.format_exception(
                    type(error),
                    error,
                    error.__traceback__
                )
                log_entry['stack_trace'] = self.mask_sensitive_data(
                    ''.join(trace)
                )
            
            self.error_logger.error(json.dumps(log_entry))
            
        except Exception as e:
            self.error_logger.error(
                f"Failed to log error: {str(e)}"
            )
    
    def log_security_event(
        self,
        event_type: str,
        details: Dict[str, Any],
        severity: str = 'info',
        user_id: Optional[str] = None
    ):
        """Log security-related events"""
        try:
            log_entry = {
                'timestamp': datetime.utcnow().isoformat(),
                'event_type': event_type,
                'severity': severity,
                'user': self.mask_sensitive_data(str(user_id)) if user_id else None
            }
            
            # Mask sensitive data in details
            masked_details = {}
            for key, value in details.items():
                if isinstance(value, str):
                    masked_details[key] = self.mask_sensitive_data(value)
                else:
                    masked_details[key] = value
            
            log_entry['details'] = masked_details
            
            if severity == 'critical':
                self.security_logger.critical(json.dumps(log_entry))
            elif severity == 'warning':
                self.security_logger.warning(json.dumps(log_entry))
            else:
                self.security_logger.info(json.dumps(log_entry))
            
        except Exception as e:
            self.error_logger.error(
                f"Failed to log security event: {str(e)}"
            )
    
    def get_recent_trades(
        self,
        hours: int = 24,
        user_id: Optional[str] = None
    ) -> List[Dict]:
        """Get recent trade logs"""
        try:
            cutoff_time = datetime.utcnow().timestamp() - (hours * 3600)
            trades = []
            
            with open(self.log_dir / 'trades.log', 'r') as f:
                for line in f:
                    try:
                        entry = json.loads(line.split('] ')[-1])
                        timestamp = datetime.fromisoformat(
                            entry['timestamp']
                        ).timestamp()
                        
                        if timestamp > cutoff_time:
                            if user_id is None or entry['user'] == str(user_id):
                                trades.append(entry)
                    except:
                        continue
            
            return trades
            
        except Exception as e:
            self.error_logger.error(
                f"Failed to get recent trades: {str(e)}"
            )
            return []
    
    def get_error_logs(
        self,
        hours: int = 24,
        min_severity: str = 'error'
    ) -> List[Dict]:
        """Get recent error logs"""
        try:
            cutoff_time = datetime.utcnow().timestamp() - (hours * 3600)
            errors = []
            
            with open(self.log_dir / 'errors.log', 'r') as f:
                for line in f:
                    try:
                        entry = json.loads(line.split('] ')[-1])
                        timestamp = datetime.fromisoformat(
                            entry['timestamp']
                        ).timestamp()
                        
                        if timestamp > cutoff_time:
                            errors.append(entry)
                    except:
                        continue
            
            return errors
            
        except Exception as e:
            self.error_logger.error(
                f"Failed to get error logs: {str(e)}"
            )
            return []
    
    def get_security_logs(
        self,
        hours: int = 24,
        min_severity: str = 'warning'
    ) -> List[Dict]:
        """Get recent security logs"""
        try:
            cutoff_time = datetime.utcnow().timestamp() - (hours * 3600)
            events = []
            
            severity_levels = {
                'info': 0,
                'warning': 1,
                'critical': 2
            }
            min_level = severity_levels.get(min_severity, 0)
            
            with open(self.log_dir / 'security.log', 'r') as f:
                for line in f:
                    try:
                        entry = json.loads(line.split('] ')[-1])
                        timestamp = datetime.fromisoformat(
                            entry['timestamp']
                        ).timestamp()
                        
                        if (timestamp > cutoff_time and
                            severity_levels.get(entry['severity'], 0) >= min_level):
                            events.append(entry)
                    except:
                        continue
            
            return events
            
        except Exception as e:
            self.error_logger.error(
                f"Failed to get security logs: {str(e)}"
            )
            return []
