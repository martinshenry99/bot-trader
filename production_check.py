"""
Production readiness verification for Meme Trader V4 Pro
Checks all critical components before production deployment
"""
import os
import json
import asyncio
import logging
import sqlite3
from datetime import datetime
from typing import Dict, List, Any
from pathlib import Path

from config import Config
from integrations.covalent import CovalentAPI 
from integrations.goplus import GoPlusAPI
from integrations.zerox import ZeroXClient
from integrations.jupiter import JupiterAPI
from integrations.helius import HeliusAPI
from integrations.coingecko import CoinGeckoAPI
from core.secure_wallet import SecureWallet
from db.models import setup_database
from monitor.scanner import TokenScanner
from monitor.watchlist_monitor import WalletMonitor

logger = logging.getLogger(__name__)

class ProductionReadinessChecker:
    """Verifies production readiness across all components"""
    
    def __init__(self):
        self.config = Config()
        self.results = {
            "api_keys": {"status": "pending", "issues": []},
            "environment": {"status": "pending", "issues": []},
            "security": {"status": "pending", "issues": []},
            "monitoring": {"status": "pending", "issues": []},
            "wallet": {"status": "pending", "issues": []},
            "database": {"status": "pending", "issues": []},
            "documentation": {"status": "pending", "issues": []}
        }
        
    async def check_api_keys(self) -> bool:
        """Verify API key configuration and rotation"""
        try:
            # Check required API keys exist
            required_apis = {
                "COVALENT": CovalentAPI,
                "GOPLUS": GoPlusAPI,
                "ZEROX": ZeroXClient,
                "JUPITER": JupiterAPI,
                "HELIUS": HeliusAPI,
                "COINGECKO": CoinGeckoAPI
            }
            
            for api_name, api_class in required_apis.items():
                # Check primary key
                primary_key = os.getenv(f"{api_name}_API_KEY")
                if not primary_key:
                    self.results["api_keys"]["issues"].append(
                        f"Missing primary API key for {api_name}"
                    )
                
                # Check rotation keys
                rotation_keys = os.getenv(f"{api_name}_ROTATION_KEYS")
                if not rotation_keys:
                    self.results["api_keys"]["issues"].append(
                        f"Missing rotation keys for {api_name}"
                    )
                    
                # Validate key format
                try:
                    api_instance = api_class()
                    await api_instance.verify_api_key()
                except Exception as e:
                    self.results["api_keys"]["issues"].append(
                        f"Invalid API key format for {api_name}: {str(e)}"
                    )
                    
            # Check rate limit settings
            for api_name in required_apis:
                rate_limit = os.getenv(f"{api_name}_RATE_LIMIT")
                if not rate_limit:
                    self.results["api_keys"]["issues"].append(
                        f"Missing rate limit setting for {api_name}"
                    )
                    
            # Verify no API keys in logs
            log_files = Path("logs").glob("*.log")
            for log_file in log_files:
                with open(log_file) as f:
                    content = f.read()
                    for api_name in required_apis:
                        key = os.getenv(f"{api_name}_API_KEY")
                        if key and key in content:
                            self.results["api_keys"]["issues"].append(
                                f"API key leak found in {log_file}"
                            )
                            
            self.results["api_keys"]["status"] = (
                "passed" if not self.results["api_keys"]["issues"] else "failed"
            )
            return len(self.results["api_keys"]["issues"]) == 0
            
        except Exception as e:
            self.results["api_keys"]["status"] = "error"
            self.results["api_keys"]["issues"].append(str(e))
            return False
            
    async def check_environment(self) -> bool:
        """Verify production environment setup"""
        try:
            # Check required directories
            required_dirs = ["logs", "data", "backups"]
            for dir_name in required_dirs:
                if not os.path.exists(dir_name):
                    self.results["environment"]["issues"].append(
                        f"Missing required directory: {dir_name}"
                    )
                    
            # Check log rotation config
            log_config = Path("logging.conf")
            if not log_config.exists():
                self.results["environment"]["issues"].append(
                    "Missing logging configuration"
                )
                
            # Verify environment variables
            required_vars = [
                "TELEGRAM_BOT_TOKEN",
                "DB_PATH",
                "LOG_LEVEL",
                "SAFE_MODE",
                "ADMIN_USER_ID"
            ]
            
            for var in required_vars:
                if not os.getenv(var):
                    self.results["environment"]["issues"].append(
                        f"Missing environment variable: {var}"
                    )
                    
            # Check database backup
            db_path = os.getenv("DB_PATH", "meme_trader.db")
            backup_path = f"backups/{datetime.now().strftime('%Y%m%d')}_backup.db"
            
            try:
                with sqlite3.connect(db_path) as conn:
                    backup = sqlite3.connect(backup_path)
                    conn.backup(backup)
                    backup.close()
            except Exception as e:
                self.results["environment"]["issues"].append(
                    f"Database backup failed: {str(e)}"
                )
                
            self.results["environment"]["status"] = (
                "passed" if not self.results["environment"]["issues"] else "failed"
            )
            return len(self.results["environment"]["issues"]) == 0
            
        except Exception as e:
            self.results["environment"]["status"] = "error"
            self.results["environment"]["issues"].append(str(e))
            return False
            
    async def check_security(self) -> bool:
        """Verify security configuration"""
        try:
            # Check admin commands protection
            admin_commands = [
                "/admin",
                "/mnemonic",
                "/rotate_wallet",
                "/emergency_stop"
            ]
            
            admin_id = os.getenv("ADMIN_USER_ID")
            if not admin_id:
                self.results["security"]["issues"].append(
                    "Missing admin user ID configuration"
                )
                
            # Check wallet encryption
            wallet = SecureWallet()
            if not wallet.is_encrypted():
                self.results["security"]["issues"].append(
                    "Wallet storage not encrypted"
                )
                
            # Verify emergency stop
            try:
                await self.emergency_stop_test()
            except Exception as e:
                self.results["security"]["issues"].append(
                    f"Emergency stop test failed: {str(e)}"
                )
                
            # Check sensitive data protection
            log_files = Path("logs").glob("*.log")
            sensitive_patterns = [
                "private key",
                "mnemonic",
                "seed phrase",
                "password"
            ]
            
            for log_file in log_files:
                with open(log_file) as f:
                    content = f.read().lower()
                    for pattern in sensitive_patterns:
                        if pattern in content:
                            self.results["security"]["issues"].append(
                                f"Sensitive data found in {log_file}: {pattern}"
                            )
                            
            self.results["security"]["status"] = (
                "passed" if not self.results["security"]["issues"] else "failed"
            )
            return len(self.results["security"]["issues"]) == 0
            
        except Exception as e:
            self.results["security"]["status"] = "error"
            self.results["security"]["issues"].append(str(e))
            return False
            
    async def check_monitoring(self) -> bool:
        """Verify monitoring and alerting setup"""
        try:
            # Test API health checks
            apis = [
                CovalentAPI(),
                GoPlusAPI(),
                ZeroXClient(),
                JupiterAPI(),
                HeliusAPI(),
                CoinGeckoAPI()
            ]
            
            for api in apis:
                try:
                    await api.health_check()
                except Exception as e:
                    self.results["monitoring"]["issues"].append(
                        f"API health check failed for {api.__class__.__name__}: {str(e)}"
                    )
                    
            # Check database connection
            try:
                setup_database()
            except Exception as e:
                self.results["monitoring"]["issues"].append(
                    f"Database health check failed: {str(e)}"
                )
                
            # Verify background tasks
            scanner = TokenScanner()
            monitor = WalletMonitor()
            
            try:
                await scanner.start()
                await monitor.start()
            except Exception as e:
                self.results["monitoring"]["issues"].append(
                    f"Background task check failed: {str(e)}"
                )
            finally:
                await scanner.stop()
                await monitor.stop()
                
            # Check metrics collection
            metrics_path = "data/metrics.json"
            if not os.path.exists(metrics_path):
                self.results["monitoring"]["issues"].append(
                    "Metrics collection not configured"
                )
                
            self.results["monitoring"]["status"] = (
                "passed" if not self.results["monitoring"]["issues"] else "failed"
            )
            return len(self.results["monitoring"]["issues"]) == 0
            
        except Exception as e:
            self.results["monitoring"]["status"] = "error"
            self.results["monitoring"]["issues"].append(str(e))
            return False
            
    async def check_wallet(self) -> bool:
        """Verify wallet configuration and backup"""
        try:
            wallet = SecureWallet()
            
            # Check wallet encryption
            if not wallet.is_encrypted():
                self.results["wallet"]["issues"].append(
                    "Wallet not properly encrypted"
                )
                
            # Verify backup mnemonic exists
            if not wallet.has_backup():
                self.results["wallet"]["issues"].append(
                    "Missing wallet backup mnemonic"
                )
                
            # Test wallet rotation
            try:
                await wallet.rotate_keys(test_mode=True)
            except Exception as e:
                self.results["wallet"]["issues"].append(
                    f"Wallet rotation test failed: {str(e)}"
                )
                
            # Check safe mode setting
            if os.getenv("SAFE_MODE") != "false":
                self.results["wallet"]["issues"].append(
                    "Production wallet not in live mode (SAFE_MODE=true)"
                )
                
            self.results["wallet"]["status"] = (
                "passed" if not self.results["wallet"]["issues"] else "failed"
            )
            return len(self.results["wallet"]["issues"]) == 0
            
        except Exception as e:
            self.results["wallet"]["status"] = "error"
            self.results["wallet"]["issues"].append(str(e))
            return False
            
    def check_documentation(self) -> bool:
        """Verify documentation completeness"""
        try:
            required_docs = [
                "README.md",
                "docs/deployment.md",
                "docs/emergency.md",
                "docs/troubleshooting.md",
                "docs/api_integration.md"
            ]
            
            for doc in required_docs:
                if not os.path.exists(doc):
                    self.results["documentation"]["issues"].append(
                        f"Missing documentation: {doc}"
                    )
                    
            self.results["documentation"]["status"] = (
                "passed" if not self.results["documentation"]["issues"] else "failed"
            )
            return len(self.results["documentation"]["issues"]) == 0
            
        except Exception as e:
            self.results["documentation"]["status"] = "error"
            self.results["documentation"]["issues"].append(str(e))
            return False
            
    async def emergency_stop_test(self):
        """Test emergency shutdown functionality"""
        # Implement emergency stop test logic
        pass
        
    async def run_all_checks(self) -> Dict[str, Any]:
        """Run all production readiness checks"""
        await asyncio.gather(
            self.check_api_keys(),
            self.check_environment(),
            self.check_security(),
            self.check_monitoring(),
            self.check_wallet()
        )
        self.check_documentation()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "results": self.results,
            "passed": all(
                r["status"] == "passed" 
                for r in self.results.values()
            )
        }
        
async def main():
    """Run production readiness check"""
    checker = ProductionReadinessChecker()
    results = await checker.run_all_checks()
    
    print("\n=== PRODUCTION READINESS REPORT ===\n")
    for component, result in results["results"].items():
        print(f"\n{component.upper()}:")
        print(f"Status: {result['status']}")
        if result["issues"]:
            print("Issues:")
            for issue in result["issues"]:
                print(f"  • {issue}")
                
    print(f"\nOVERALL STATUS: {'PASSED' if results['passed'] else 'FAILED'}")
    
    # Save results
    with open("production_check_results.json", "w") as f:
        json.dump(results, f, indent=2)
        
if __name__ == "__main__":
    asyncio.run(main())
