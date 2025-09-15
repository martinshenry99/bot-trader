"""
Secure Wallet Management for Meme Trader V4 Pro
Handles mnemonic generation, import, export, and deletion securely
"""

import os
import json
import logging
from typing import Optional, Dict, Any
from pathlib import Path
from datetime import datetime
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)

class SecureWallet:
    """Secure system for managing wallet mnemonics"""
    
    def __init__(self, config_dir: str):
        self.config_dir = Path(config_dir)
        self.wallet_file = self.config_dir / "wallets.enc"
        self.salt_file = self.config_dir / "salt"
        
        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize encryption
        self._init_encryption()
    
    def _init_encryption(self):
        """Initialize encryption system"""
        try:
            # Generate or load salt
            if self.salt_file.exists():
                with open(self.salt_file, 'rb') as f:
                    self.salt = f.read()
            else:
                self.salt = os.urandom(16)
                with open(self.salt_file, 'wb') as f:
                    f.write(self.salt)
            
        except Exception as e:
            logger.error(f"Error initializing encryption: {str(e)}")
            raise
    
    def _get_encryption_key(self, password: str) -> bytes:
        """Derive encryption key from password"""
        try:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=self.salt,
                iterations=100000
            )
            
            return base64.urlsafe_b64encode(
                kdf.derive(password.encode())
            )
            
        except Exception as e:
            logger.error(f"Error generating encryption key: {str(e)}")
            raise
    
    def generate_mnemonic(
        self,
        name: str,
        password: str,
        strength: int = 256
    ) -> str:
        """Generate new wallet mnemonic"""
        try:
            # Import here to avoid logging
            from eth_account import Account
            import secrets
            
            # Generate mnemonic
            entropy = secrets.token_bytes(strength // 8)
            account = Account.from_key(entropy)
            mnemonic = account._mnemonic
            
            # Store securely
            self.store_mnemonic(name, mnemonic, password)
            
            return mnemonic
            
        except Exception as e:
            logger.error(f"Error generating mnemonic: {str(e)}")
            raise
        finally:
            # Clear sensitive data
            if 'mnemonic' in locals():
                del mnemonic
            if 'entropy' in locals():
                del entropy
    
    def import_mnemonic(
        self,
        name: str,
        mnemonic: str,
        password: str
    ) -> bool:
        """Import existing mnemonic"""
        try:
            # Validate mnemonic
            self._validate_mnemonic(mnemonic)
            
            # Store securely
            self.store_mnemonic(name, mnemonic, password)
            
            return True
            
        except Exception as e:
            logger.error(f"Error importing mnemonic: {str(e)}")
            raise
        finally:
            # Clear sensitive data
            if 'mnemonic' in locals():
                del mnemonic
    
    def store_mnemonic(
        self,
        name: str,
        mnemonic: str,
        password: str
    ):
        """Securely store mnemonic"""
        try:
            # Get encryption key
            key = self._get_encryption_key(password)
            f = Fernet(key)
            
            # Load existing wallets
            wallets = self._load_wallets(password)
            
            # Encrypt and store
            encrypted = f.encrypt(mnemonic.encode())
            wallets[name] = {
                'encrypted_mnemonic': encrypted.decode(),
                'created_at': str(datetime.utcnow())
            }
            
            # Save updated wallets
            self._save_wallets(wallets, password)
            
        except Exception as e:
            logger.error(f"Error storing mnemonic: {str(e)}")
            raise
        finally:
            # Clear sensitive data
            if 'mnemonic' in locals():
                del mnemonic
            if 'key' in locals():
                del key
    
    def export_mnemonic(
        self,
        name: str,
        password: str
    ) -> Optional[str]:
        """Export mnemonic for backup"""
        try:
            # Get encryption key
            key = self._get_encryption_key(password)
            f = Fernet(key)
            
            # Load wallets
            wallets = self._load_wallets(password)
            
            if name not in wallets:
                raise ValueError(f"Wallet {name} not found")
            
            # Decrypt mnemonic
            encrypted = wallets[name]['encrypted_mnemonic'].encode()
            mnemonic = f.decrypt(encrypted).decode()
            
            return mnemonic
            
        except Exception as e:
            logger.error(f"Error exporting mnemonic: {str(e)}")
            raise
        finally:
            # Clear sensitive data
            if 'mnemonic' in locals():
                del mnemonic
            if 'key' in locals():
                del key
    
    def delete_mnemonic(
        self,
        name: str,
        password: str,
        confirmation: str
    ) -> bool:
        """Safely delete stored mnemonic"""
        try:
            # Verify confirmation
            if confirmation != f"DELETE {name}":
                raise ValueError("Invalid confirmation")
            
            # Load wallets
            wallets = self._load_wallets(password)
            
            if name not in wallets:
                raise ValueError(f"Wallet {name} not found")
            
            # Securely delete
            wallets.pop(name)
            self._save_wallets(wallets, password)
            
            return True
            
        except Exception as e:
            logger.error(f"Error deleting mnemonic: {str(e)}")
            raise
    
    def get_addresses(self, password: str) -> Dict[str, str]:
        """Get addresses for all stored wallets"""
        try:
            # Import here to avoid logging
            from eth_account import Account
            
            addresses = {}
            wallets = self._load_wallets(password)
            
            for name, data in wallets.items():
                # Get encryption key
                key = self._get_encryption_key(password)
                f = Fernet(key)
                
                # Decrypt mnemonic
                encrypted = data['encrypted_mnemonic'].encode()
                mnemonic = f.decrypt(encrypted).decode()
                
                # Get address
                account = Account.from_mnemonic(mnemonic)
                addresses[name] = account.address
            
            return addresses
            
        except Exception as e:
            logger.error(f"Error getting addresses: {str(e)}")
            raise
        finally:
            # Clear sensitive data
            if 'mnemonic' in locals():
                del mnemonic
            if 'key' in locals():
                del key
    
    def _load_wallets(self, password: str) -> Dict:
        """Load encrypted wallets"""
        try:
            if not self.wallet_file.exists():
                return {}
            
            # Get encryption key
            key = self._get_encryption_key(password)
            f = Fernet(key)
            
            # Load and decrypt
            with open(self.wallet_file, 'rb') as file:
                encrypted = file.read()
                if encrypted:
                    decrypted = f.decrypt(encrypted)
                    return json.loads(decrypted)
                return {}
            
        except Exception as e:
            logger.error(f"Error loading wallets: {str(e)}")
            raise
    
    def _save_wallets(self, wallets: Dict, password: str):
        """Save encrypted wallets"""
        try:
            # Get encryption key
            key = self._get_encryption_key(password)
            f = Fernet(key)
            
            # Encrypt and save
            encrypted = f.encrypt(json.dumps(wallets).encode())
            
            with open(self.wallet_file, 'wb') as file:
                file.write(encrypted)
            
        except Exception as e:
            logger.error(f"Error saving wallets: {str(e)}")
            raise
    
    def _validate_mnemonic(self, mnemonic: str):
        """Validate mnemonic phrase"""
        try:
            # Import here to avoid logging
            from eth_account import Account
            
            # Validate by attempting to create account
            Account.from_mnemonic(mnemonic)
            
        except Exception as e:
            raise ValueError("Invalid mnemonic phrase")
        finally:
            # Clear sensitive data
            if 'mnemonic' in locals():
                del mnemonic
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import secrets

from config import Config

logger = logging.getLogger(__name__)

class SecureWalletManager:
    """Secure wallet management with encrypted keystore"""
    
    def __init__(self, keystore_dir: str = "./keystores"):
        self.keystore_dir = Path(keystore_dir)
        self.keystore_dir.mkdir(exist_ok=True)
        self.keystore_file = self.keystore_dir / "wallet.keystore"
        
    def generate_wallet(self, password: str) -> Dict[str, Any]:
        """Generate a new wallet with mnemonic"""
        try:
            # Generate mnemonic (12 words)
            mnemonic = self._generate_mnemonic()
            
            # Generate addresses for different chains
            addresses = self._generate_addresses(mnemonic)
            
            # Encrypt and store
            keystore_data = {
                'mnemonic': mnemonic,
                'addresses': addresses,
                'created_at': self._get_timestamp(),
                'version': '1.0'
            }
            
            encrypted_data = self._encrypt_data(keystore_data, password)
            
            with open(self.keystore_file, 'wb') as f:
                f.write(encrypted_data)
            
            logger.info("New wallet generated and encrypted")
            
            return {
                'success': True,
                'addresses': addresses,
                'message': 'Wallet generated successfully. Mnemonic is encrypted and stored securely.'
            }
            
        except Exception as e:
            logger.error(f"Failed to generate wallet: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def import_wallet(self, mnemonic: str, password: str) -> Dict[str, Any]:
        """Import wallet from mnemonic"""
        try:
            # Validate mnemonic
            if not self._validate_mnemonic(mnemonic):
                return {
                    'success': False,
                    'error': 'Invalid mnemonic format'
                }
            
            # Generate addresses
            addresses = self._generate_addresses(mnemonic)
            
            # Encrypt and store
            keystore_data = {
                'mnemonic': mnemonic,
                'addresses': addresses,
                'created_at': self._get_timestamp(),
                'version': '1.0'
            }
            
            encrypted_data = self._encrypt_data(keystore_data, password)
            
            with open(self.keystore_file, 'wb') as f:
                f.write(encrypted_data)
            
            logger.info("Wallet imported and encrypted")
            
            return {
                'success': True,
                'addresses': addresses,
                'message': 'Wallet imported successfully. Mnemonic is encrypted and stored securely.'
            }
            
        except Exception as e:
            logger.error(f"Failed to import wallet: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def export_wallet(self, password: str) -> Dict[str, Any]:
        """Export encrypted wallet data"""
        try:
            if not self.keystore_file.exists():
                return {
                    'success': False,
                    'error': 'No wallet found'
                }
            
            with open(self.keystore_file, 'rb') as f:
                encrypted_data = f.read()
            
            # Decrypt to verify password
            keystore_data = self._decrypt_data(encrypted_data, password)
            
            # Return encrypted blob (not raw mnemonic)
            return {
                'success': True,
                'encrypted_data': base64.b64encode(encrypted_data).decode(),
                'addresses': keystore_data['addresses'],
                'message': 'Encrypted wallet data exported. Keep this secure.'
            }
            
        except Exception as e:
            logger.error(f"Failed to export wallet: {e}")
            return {
                'success': False,
                'error': 'Invalid password or corrupted keystore'
            }
    
    def delete_wallet(self, password: str) -> Dict[str, Any]:
        """Delete wallet after password confirmation"""
        try:
            if not self.keystore_file.exists():
                return {
                    'success': False,
                    'error': 'No wallet found'
                }
            
            # Verify password before deletion
            with open(self.keystore_file, 'rb') as f:
                encrypted_data = f.read()
            
            self._decrypt_data(encrypted_data, password)
            
            # Delete keystore file
            self.keystore_file.unlink()
            
            logger.info("Wallet deleted successfully")
            
            return {
                'success': True,
                'message': 'Wallet deleted successfully'
            }
            
        except Exception as e:
            logger.error(f"Failed to delete wallet: {e}")
            return {
                'success': False,
                'error': 'Invalid password or deletion failed'
            }
    
    def get_wallet_status(self) -> Dict[str, Any]:
        """Get wallet status without exposing sensitive data"""
        try:
            if not self.keystore_file.exists():
                return {
                    'configured': False,
                    'message': 'No wallet configured'
                }
            
            # Get file info without decrypting
            stat = self.keystore_file.stat()
            
            return {
                'configured': True,
                'created_at': stat.st_ctime,
                'file_size': stat.st_size,
                'message': 'Wallet is configured and encrypted'
            }
            
        except Exception as e:
            logger.error(f"Failed to get wallet status: {e}")
            return {
                'configured': False,
                'error': str(e)
            }
    
    def get_addresses(self, password: str) -> Dict[str, Any]:
        """Get wallet addresses"""
        try:
            if not self.keystore_file.exists():
                return {
                    'success': False,
                    'error': 'No wallet found'
                }
            
            with open(self.keystore_file, 'rb') as f:
                encrypted_data = f.read()
            
            keystore_data = self._decrypt_data(encrypted_data, password)
            
            return {
                'success': True,
                'addresses': keystore_data['addresses']
            }
            
        except Exception as e:
            logger.error(f"Failed to get addresses: {e}")
            return {
                'success': False,
                'error': 'Invalid password or corrupted keystore'
            }
    
    def _generate_mnemonic(self) -> str:
        """Generate a 12-word mnemonic phrase"""
        # This is a simplified implementation
        # In production, use a proper BIP39 library
        words = [
            "abandon", "ability", "able", "about", "above", "absent", "absorb", "abstract", "absurd", "abuse",
            "access", "accident", "account", "accuse", "achieve", "acid", "acoustic", "acquire", "across", "act",
            "action", "actor", "actress", "actual", "adapt", "add", "addict", "address", "adjust", "admit",
            "adult", "advance", "advice", "aerobic", "affair", "afford", "afraid", "again", "age", "agent"
        ]
        
        return " ".join(secrets.choice(words) for _ in range(12))
    
    def _validate_mnemonic(self, mnemonic: str) -> bool:
        """Validate mnemonic format"""
        words = mnemonic.strip().split()
        return len(words) == 12 and all(len(word) >= 3 for word in words)
    
    def _generate_addresses(self, mnemonic: str) -> Dict[str, str]:
        """Generate addresses for different chains from mnemonic"""
        # This is a simplified implementation
        # In production, use proper HD wallet derivation
        import hashlib
        
        # Generate deterministic addresses based on mnemonic
        seed = hashlib.sha256(mnemonic.encode()).hexdigest()
        
        return {
            'ethereum': f"0x{seed[:40]}",
            'bsc': f"0x{seed[40:80]}",
            'solana': f"{seed[:44]}"
        }
    
    def _encrypt_data(self, data: Dict[str, Any], password: str) -> bytes:
        """Encrypt data with password"""
        # Convert password to key
        password_bytes = password.encode()
        salt = os.urandom(16)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password_bytes))
        
        # Encrypt data
        fernet = Fernet(key)
        encrypted_data = fernet.encrypt(json.dumps(data).encode())
        
        # Prepend salt
        return salt + encrypted_data
    
    def _decrypt_data(self, encrypted_data: bytes, password: str) -> Dict[str, Any]:
        """Decrypt data with password"""
        # Extract salt
        salt = encrypted_data[:16]
        encrypted_data = encrypted_data[16:]
        
        # Convert password to key
        password_bytes = password.encode()
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password_bytes))
        
        # Decrypt data
        fernet = Fernet(key)
        decrypted_data = fernet.decrypt(encrypted_data)
        
        return json.loads(decrypted_data.decode())
    
    def _get_timestamp(self) -> str:
        """Get current timestamp"""
        from datetime import datetime
        return datetime.now().isoformat()

# Global instance
secure_wallet = SecureWalletManager()

def get_secure_wallet() -> SecureWalletManager:
    """Get secure wallet manager instance"""
    return secure_wallet