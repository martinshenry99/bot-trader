"""
Multi-wallet keystore management for Meme Trader V4 Pro
"""

import os
import json
import secrets
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from eth_account import Account
from eth_keyfile import extract_key_from_keyfile
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

logger = logging.getLogger(__name__)


class WalletManager:
    """Secure multi-wallet keystore manager"""
    
    def __init__(self, keystore_dir: str = "/app/keystores", password: Optional[str] = None):
        self.keystore_dir = Path(keystore_dir)
        self.keystore_dir.mkdir(exist_ok=True)
        
        # Get password from environment or parameter
        self.password = password or os.getenv('KEYSTORE_PASSWORD', 'MemeTrader2024!')
        
        # Active wallets cache
        self.active_wallets: Dict[str, Dict] = {}
        
        # Load existing wallets
        self._load_wallets()
        
    def _derive_key(self, password: str, salt: bytes) -> bytes:
        """Derive encryption key from password"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))
    
    def _encrypt_data(self, data: str, password: str) -> Dict[str, str]:
        """Encrypt data with password"""
        salt = os.urandom(16)
        key = self._derive_key(password, salt)
        fernet = Fernet(key)
        
        encrypted_data = fernet.encrypt(data.encode())
        
        return {
            'encrypted_data': base64.b64encode(encrypted_data).decode(),
            'salt': base64.b64encode(salt).decode()
        }
    
    def _decrypt_data(self, encrypted_data: str, salt: str, password: str) -> str:
        """Decrypt data with password"""
        salt_bytes = base64.b64decode(salt.encode())
        key = self._derive_key(password, salt_bytes)
        fernet = Fernet(key)
        
        encrypted_bytes = base64.b64decode(encrypted_data.encode())
        decrypted_data = fernet.decrypt(encrypted_bytes)
        
        return decrypted_data.decode()
    
    def create_wallet(self, wallet_name: Optional[str] = None, blockchain: str = 'ethereum') -> Dict[str, str]:
        """
        Create a new wallet with encrypted keystore
        
        Args:
            wallet_name: Optional custom name for wallet
            blockchain: Blockchain type ('ethereum', 'solana')
            
        Returns:
            Wallet information dictionary
        """
        try:
            if blockchain == 'ethereum':
                # Generate Ethereum wallet
                private_key = "0x" + secrets.token_hex(32)
                account = Account.from_key(private_key)
                address = account.address
                
            elif blockchain == 'solana':
                # Generate Solana wallet (placeholder - would need solana-py)
                from solders.keypair import Keypair  # type: ignore
                keypair = Keypair()
                address = str(keypair.pubkey())
                private_key = bytes(keypair).hex()
                
            else:
                raise ValueError(f"Unsupported blockchain: {blockchain}")
            
            # Generate wallet name if not provided
            if not wallet_name:
                wallet_name = f"{blockchain}_wallet_{address[-8:].lower()}"
            
            # Create keystore file
            keystore_data = {
                'wallet_name': wallet_name,
                'blockchain': blockchain,
                'address': address,
                'created_at': str(datetime.utcnow()),
                'version': '1.0'
            }
            
            # Encrypt private key
            encrypted_key = self._encrypt_data(private_key, self.password)
            keystore_data['encrypted_private_key'] = encrypted_key
            
            # Save keystore file
            keystore_filename = f"{wallet_name}_{address.lower()}.json"
            keystore_path = self.keystore_dir / keystore_filename
            
            with open(keystore_path, 'w') as f:
                json.dump(keystore_data, f, indent=2)
            
            # Add to active wallets
            self.active_wallets[address.lower()] = {
                'name': wallet_name,
                'address': address,
                'blockchain': blockchain,
                'keystore_path': str(keystore_path),
                'created_at': keystore_data['created_at']
            }
            
            logger.info(f"Created {blockchain} wallet: {address}")
            
            return {
                'wallet_name': wallet_name,
                'address': address,
                'blockchain': blockchain,
                'keystore_path': str(keystore_path),
                'private_key': private_key  # Return for immediate use, not stored
            }
            
        except Exception as e:
            logger.error(f"Failed to create wallet: {e}")
            raise
    
    def load_private_key(self, address: str) -> Optional[str]:
        """
        Load private key for address from encrypted keystore
        
        Args:
            address: Wallet address
            
        Returns:
            Private key or None if not found/failed
        """
        try:
            address = address.lower()
            
            if address not in self.active_wallets:
                logger.error(f"Wallet not found: {address}")
                return None
            
            wallet_info = self.active_wallets[address]
            keystore_path = wallet_info['keystore_path']
            
            # Load keystore file
            with open(keystore_path, 'r') as f:
                keystore_data = json.load(f)
            
            # Decrypt private key
            encrypted_key = keystore_data['encrypted_private_key']
            private_key = self._decrypt_data(
                encrypted_key['encrypted_data'],
                encrypted_key['salt'],
                self.password
            )
            
            return private_key
            
        except Exception as e:
            logger.error(f"Failed to load private key for {address}: {e}")
            return None
    
    def get_wallet_info(self, address: str) -> Optional[Dict]:
        """Get wallet information without private key"""
        address = address.lower()
        return self.active_wallets.get(address)
    
    def list_wallets(self, blockchain: Optional[str] = None) -> List[Dict]:
        """
        List all available wallets
        
        Args:
            blockchain: Filter by blockchain type
            
        Returns:
            List of wallet info dictionaries
        """
        wallets = []
        
        for address, wallet_info in self.active_wallets.items():
            if blockchain and wallet_info['blockchain'] != blockchain:
                continue
                
            wallets.append({
                'address': wallet_info['address'],
                'name': wallet_info['name'],
                'blockchain': wallet_info['blockchain'],
                'created_at': wallet_info['created_at']
            })
        
        return wallets
    
    def delete_wallet(self, address: str) -> bool:
        """
        Delete wallet and its keystore file
        
        Args:
            address: Wallet address to delete
            
        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            address = address.lower()
            
            if address not in self.active_wallets:
                logger.error(f"Wallet not found: {address}")
                return False
            
            wallet_info = self.active_wallets[address]
            keystore_path = wallet_info['keystore_path']
            
            # Delete keystore file
            if os.path.exists(keystore_path):
                os.remove(keystore_path)
            
            # Remove from active wallets
            del self.active_wallets[address]
            
            logger.info(f"Deleted wallet: {address}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete wallet {address}: {e}")
            return False
    
    def _load_wallets(self):
        """Load all existing wallets from keystore directory"""
        try:
            for keystore_file in self.keystore_dir.glob("*.json"):
                try:
                    with open(keystore_file, 'r') as f:
                        keystore_data = json.load(f)
                    
                    address = keystore_data.get('address', '').lower()
                    if address:
                        self.active_wallets[address] = {
                            'name': keystore_data.get('wallet_name', 'Unknown'),
                            'address': keystore_data.get('address'),
                            'blockchain': keystore_data.get('blockchain', 'ethereum'),
                            'keystore_path': str(keystore_file),
                            'created_at': keystore_data.get('created_at', 'Unknown')
                        }
                        
                except Exception as e:
                    logger.warning(f"Failed to load keystore {keystore_file}: {e}")
                    
            logger.info(f"Loaded {len(self.active_wallets)} wallets")
            
        except Exception as e:
            logger.error(f"Failed to load wallets: {e}")
    
    def backup_keystores(self, backup_path: str) -> bool:
        """
        Create backup of all keystore files
        
        Args:
            backup_path: Path to save backup
            
        Returns:
            True if backup created successfully
        """
        try:
            import shutil
            import zipfile
            from datetime import datetime
            
            # Create timestamped backup
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            backup_file = f"{backup_path}/keystores_backup_{timestamp}.zip"
            
            with zipfile.ZipFile(backup_file, 'w') as backup_zip:
                for keystore_file in self.keystore_dir.glob("*.json"):
                    backup_zip.write(keystore_file, keystore_file.name)
            
            logger.info(f"Created keystore backup: {backup_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            return False
    
    def restore_keystores(self, backup_file: str) -> bool:
        """
        Restore keystores from backup file
        
        Args:
            backup_file: Path to backup zip file
            
        Returns:
            True if restored successfully
        """
        try:
            import zipfile
            
            with zipfile.ZipFile(backup_file, 'r') as backup_zip:
                backup_zip.extractall(self.keystore_dir)
            
            # Reload wallets
            self.active_wallets.clear()
            self._load_wallets()
            
            logger.info(f"Restored keystores from: {backup_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to restore backup: {e}")
            return False
    
    def rotate_password(self, new_password: str) -> bool:
        """
        Rotate keystore password for all wallets
        
        Args:
            new_password: New password for all keystores
            
        Returns:
            True if rotation successful
        """
        try:
            # Re-encrypt all keystores with new password
            for address, wallet_info in self.active_wallets.items():
                # Load current private key
                private_key = self.load_private_key(address)
                if not private_key:
                    logger.error(f"Failed to load private key for {address}")
                    continue
                
                # Load keystore data
                keystore_path = wallet_info['keystore_path']
                with open(keystore_path, 'r') as f:
                    keystore_data = json.load(f)
                
                # Re-encrypt with new password
                encrypted_key = self._encrypt_data(private_key, new_password)
                keystore_data['encrypted_private_key'] = encrypted_key
                
                # Save updated keystore
                with open(keystore_path, 'w') as f:
                    json.dump(keystore_data, f, indent=2)
            
            # Update password
            self.password = new_password
            
            logger.info("Password rotation completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Password rotation failed: {e}")
            return False
    
    def get_next_wallet(self, blockchain: str = 'ethereum') -> Optional[Dict]:
        """
        Get next wallet for rotation-based execution
        
        Args:
            blockchain: Blockchain type to filter
            
        Returns:
            Wallet info or None if no wallets available
        """
        try:
            available_wallets = [
                wallet for wallet in self.active_wallets.values()
                if wallet['blockchain'] == blockchain
            ]
            
            if not available_wallets:
                return None
            
            # Simple round-robin selection
            # In production, this could be more sophisticated
            import random
            return random.choice(available_wallets)
            
        except Exception as e:
            logger.error(f"Failed to get next wallet: {e}")
            return None
    
    def health_check(self) -> Dict[str, any]:
        """
        Perform health check on wallet manager
        
        Returns:
            Health check results
        """
        try:
            results = {
                'total_wallets': len(self.active_wallets),
                'keystore_dir_exists': self.keystore_dir.exists(),
                'keystore_files_count': len(list(self.keystore_dir.glob("*.json"))),
                'password_set': bool(self.password),
                'blockchain_breakdown': {},
                'corrupted_keystores': []
            }
            
            # Count wallets by blockchain
            for wallet_info in self.active_wallets.values():
                blockchain = wallet_info['blockchain']
                results['blockchain_breakdown'][blockchain] = results['blockchain_breakdown'].get(blockchain, 0) + 1
            
            # Check keystore integrity
            for address, wallet_info in self.active_wallets.items():
                try:
                    private_key = self.load_private_key(address)
                    if not private_key:
                        results['corrupted_keystores'].append(address)
                except:
                    results['corrupted_keystores'].append(address)
            
            results['health_status'] = 'healthy' if not results['corrupted_keystores'] else 'degraded'
            
            return results
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                'health_status': 'unhealthy',
                'error': str(e)
            }


# Import datetime here to avoid issues
from datetime import datetime

# Global wallet manager instance
wallet_manager = WalletManager()