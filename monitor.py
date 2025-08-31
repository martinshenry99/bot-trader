import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from web3 import Web3
from config import Config
from db import get_db_session, Token, Wallet, Transaction, MonitoringAlert
from utils.api_client import CovalentClient

logger = logging.getLogger(__name__)

class TokenMonitor:
    """Monitor tokens for price changes and trading opportunities"""
    
    def __init__(self):
        self.covalent_client = CovalentClient()
        self.monitoring_tokens = {}
        self.is_running = False
        
    async def start_monitoring(self, token_addresses: List[str], user_id: str):
        """Start monitoring specified tokens"""
        self.is_running = True
        logger.info(f"Starting token monitoring for {len(token_addresses)} tokens")
        
        for address in token_addresses:
            self.monitoring_tokens[address] = {
                'user_id': user_id,
                'last_price': None,
                'last_check': datetime.utcnow(),
                'alerts_sent': 0
            }
        
        # Start monitoring loop
        asyncio.create_task(self.monitoring_loop())
        
    async def stop_monitoring(self):
        """Stop token monitoring"""
        self.is_running = False
        self.monitoring_tokens.clear()
        logger.info("Token monitoring stopped")
        
    async def monitoring_loop(self):
        """Main monitoring loop"""
        while self.is_running:
            try:
                await self.check_all_tokens()
                await asyncio.sleep(30)  # Check every 30 seconds
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")
                await asyncio.sleep(60)  # Wait longer on error
                
    async def check_all_tokens(self):
        """Check all monitored tokens for changes"""
        for token_address, data in self.monitoring_tokens.items():
            try:
                await self.check_token(token_address, data)
            except Exception as e:
                logger.error(f"Error checking token {token_address}: {e}")
                
    async def check_token(self, token_address: str, monitor_data: Dict):
        """Check individual token for price changes"""
        try:
            # Get current token data
            token_data = await self.covalent_client.get_token_data(token_address)
            
            if not token_data:
                return
                
            current_price = token_data.get('price_usd', 0)
            last_price = monitor_data['last_price']
            
            # Update database
            await self.update_token_in_db(token_address, token_data)
            
            # Check for significant price changes
            if last_price and current_price > 0:
                price_change = ((current_price - last_price) / last_price) * 100
                
                # Alert on significant changes (>5% up or down)
                if abs(price_change) >= 5:
                    await self.create_price_alert(
                        token_address, 
                        monitor_data['user_id'],
                        price_change,
                        current_price,
                        last_price
                    )
            
            # Update monitoring data
            monitor_data['last_price'] = current_price
            monitor_data['last_check'] = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"Token check error for {token_address}: {e}")
            
    async def update_token_in_db(self, token_address: str, token_data: Dict):
        """Update token data in database"""
        db = get_db_session()
        try:
            token = db.query(Token).filter(Token.address == token_address).first()
            if not token:
                token = Token(address=token_address)
                db.add(token)
            
            # Update token data
            token.name = token_data.get('name')
            token.symbol = token_data.get('symbol')
            token.decimals = token_data.get('decimals')
            token.price_usd = token_data.get('price_usd')
            token.market_cap = token_data.get('market_cap')
            token.liquidity_usd = token_data.get('liquidity_usd')
            token.volume_24h = token_data.get('volume_24h')
            token.last_analyzed = datetime.utcnow()
            token.updated_at = datetime.utcnow()
            
            db.commit()
        finally:
            db.close()
            
    async def create_price_alert(self, token_address: str, user_id: str, price_change: float, current_price: float, last_price: float):
        """Create price change alert"""
        db = get_db_session()
        try:
            # Get token info
            token = db.query(Token).filter(Token.address == token_address).first()
            token_symbol = token.symbol if token else token_address[:8]
            
            # Create alert
            alert = MonitoringAlert(
                user_id=int(user_id),
                alert_type='price_change',
                title=f'Price Alert: {token_symbol}',
                message=f'{token_symbol} price changed by {price_change:.2f}%\nFrom ${last_price:.6f} to ${current_price:.6f}',
                token_address=token_address,
                trigger_value=price_change
            )
            db.add(alert)
            db.commit()
            
            logger.info(f"Price alert created for {token_symbol}: {price_change:.2f}%")
            
        finally:
            db.close()

class WalletMonitor:
    """Monitor wallet addresses for new transactions"""
    
    def __init__(self):
        self.covalent_client = CovalentClient()
        self.monitoring_wallets = {}
        self.is_running = False
        
    async def start_monitoring(self, wallet_addresses: List[str], user_id: str):
        """Start monitoring specified wallets"""
        self.is_running = True
        logger.info(f"Starting wallet monitoring for {len(wallet_addresses)} wallets")
        
        for address in wallet_addresses:
            self.monitoring_wallets[address] = {
                'user_id': user_id,
                'last_block_checked': 0,
                'last_check': datetime.utcnow()
            }
        
        # Start monitoring loop
        asyncio.create_task(self.monitoring_loop())
        
    async def stop_monitoring(self):
        """Stop wallet monitoring"""
        self.is_running = False
        self.monitoring_wallets.clear()
        logger.info("Wallet monitoring stopped")
        
    async def monitoring_loop(self):
        """Main monitoring loop"""
        while self.is_running:
            try:
                await self.check_all_wallets()
                await asyncio.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Wallet monitoring loop error: {e}")
                await asyncio.sleep(120)  # Wait longer on error
                
    async def check_all_wallets(self):
        """Check all monitored wallets for new transactions"""
        for wallet_address, data in self.monitoring_wallets.items():
            try:
                await self.check_wallet(wallet_address, data)
            except Exception as e:
                logger.error(f"Error checking wallet {wallet_address}: {e}")
                
    async def check_wallet(self, wallet_address: str, monitor_data: Dict):
        """Check individual wallet for new transactions"""
        try:
            # Get recent transactions
            transactions = await self.covalent_client.get_wallet_transactions(
                wallet_address, 
                from_block=monitor_data['last_block_checked']
            )
            
            if not transactions:
                return
                
            # Process new transactions
            new_transactions = 0
            for tx in transactions:
                if await self.process_transaction(wallet_address, tx, monitor_data['user_id']):
                    new_transactions += 1
                    
            if new_transactions > 0:
                await self.create_transaction_alert(
                    wallet_address,
                    monitor_data['user_id'], 
                    new_transactions
                )
                
            # Update last checked block
            if transactions:
                monitor_data['last_block_checked'] = max(tx.get('block_number', 0) for tx in transactions)
            monitor_data['last_check'] = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"Wallet check error for {wallet_address}: {e}")
            
    async def process_transaction(self, wallet_address: str, tx_data: Dict, user_id: str) -> bool:
        """Process and store a new transaction"""
        db = get_db_session()
        try:
            # Check if transaction already exists
            existing_tx = db.query(Transaction).filter(
                Transaction.tx_hash == tx_data.get('tx_hash')
            ).first()
            
            if existing_tx:
                return False
                
            # Get wallet from database
            wallet = db.query(Wallet).filter(Wallet.address == wallet_address).first()
            if not wallet:
                return False
                
            # Create transaction record
            transaction = Transaction(
                wallet_id=wallet.id,
                tx_hash=tx_data.get('tx_hash'),
                from_address=tx_data.get('from_address'),
                to_address=tx_data.get('to_address'),
                value=float(tx_data.get('value', 0)),
                token_address=tx_data.get('token_address'),
                token_symbol=tx_data.get('token_symbol'),
                gas_used=tx_data.get('gas_used'),
                gas_price=float(tx_data.get('gas_price', 0)),
                block_number=tx_data.get('block_number'),
                timestamp=datetime.fromisoformat(tx_data.get('timestamp', datetime.utcnow().isoformat())),
                transaction_type=self.determine_transaction_type(tx_data, wallet_address)
            )
            
            db.add(transaction)
            db.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error processing transaction: {e}")
            return False
        finally:
            db.close()
            
    def determine_transaction_type(self, tx_data: Dict, wallet_address: str) -> str:
        """Determine the type of transaction"""
        from_addr = tx_data.get('from_address', '').lower()
        to_addr = tx_data.get('to_address', '').lower()
        wallet_addr = wallet_address.lower()
        
        if from_addr == wallet_addr:
            return 'send'
        elif to_addr == wallet_addr:
            return 'receive'
        else:
            return 'interaction'
            
    async def create_transaction_alert(self, wallet_address: str, user_id: str, tx_count: int):
        """Create new transaction alert"""
        db = get_db_session()
        try:
            alert = MonitoringAlert(
                user_id=int(user_id),
                alert_type='new_transaction',
                title='New Transaction Alert',
                message=f'{tx_count} new transaction(s) detected in wallet {wallet_address[:8]}...{wallet_address[-8:]}',
                wallet_address=wallet_address,
                trigger_value=tx_count
            )
            db.add(alert)
            db.commit()
            
            logger.info(f"Transaction alert created for wallet {wallet_address}: {tx_count} new transactions")
            
        finally:
            db.close()

class MonitoringManager:
    """Centralized monitoring management"""
    
    def __init__(self):
        self.token_monitor = TokenMonitor()
        self.wallet_monitor = WalletMonitor()
        
    async def start_token_monitoring(self, token_addresses: List[str], user_id: str):
        """Start monitoring tokens for a user"""
        await self.token_monitor.start_monitoring(token_addresses, user_id)
        
    async def start_wallet_monitoring(self, wallet_addresses: List[str], user_id: str):
        """Start monitoring wallets for a user"""
        await self.wallet_monitor.start_monitoring(wallet_addresses, user_id)
        
    async def stop_all_monitoring(self):
        """Stop all monitoring"""
        await self.token_monitor.stop_monitoring()
        await self.wallet_monitor.stop_monitoring()
        
    async def get_monitoring_status(self) -> Dict:
        """Get current monitoring status"""
        return {
            'token_monitor_running': self.token_monitor.is_running,
            'wallet_monitor_running': self.wallet_monitor.is_running,
            'monitored_tokens': len(self.token_monitor.monitoring_tokens),
            'monitored_wallets': len(self.wallet_monitor.monitoring_wallets)
        }