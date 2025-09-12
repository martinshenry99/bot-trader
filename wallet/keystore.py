
import logging
import os
import json
from cryptography.fernet import Fernet
from hashlib import sha256

logger = logging.getLogger("keystore")

class KeystoreManager:
    def __init__(self, keystore_dir="keystores"):
        self.keystore_dir = keystore_dir
        os.makedirs(self.keystore_dir, exist_ok=True)

    def _get_key(self, password):
        return sha256(password.encode()).digest()[:32]

    def generate_keystore(self, mnemonic, password):
        key = Fernet.generate_key()
        cipher = Fernet(key)
        encrypted = cipher.encrypt(mnemonic.encode())
        keystore = {
            "encrypted_mnemonic": encrypted.decode(),
            "key": key.decode()
        }
        filename = os.path.join(self.keystore_dir, f"keystore_{sha256(mnemonic.encode()).hexdigest()[:8]}.json")
        with open(filename, "w") as f:
            json.dump(keystore, f)
        logger.info(f"Keystore generated: {filename}")
        return filename

    def import_keystore(self, path, password):
        with open(path, "r") as f:
            keystore = json.load(f)
        cipher = Fernet(keystore["key"].encode())
        mnemonic = cipher.decrypt(keystore["encrypted_mnemonic"].encode()).decode()
        return mnemonic

    def export_keystore(self, address, password):
        filename = os.path.join(self.keystore_dir, f"keystore_{address[:8]}.json")
        if not os.path.exists(filename):
            raise FileNotFoundError("Keystore not found")
        with open(filename, "r") as f:
            keystore = json.load(f)
        return keystore

    def delete_keystore(self, address):
        filename = os.path.join(self.keystore_dir, f"keystore_{address[:8]}.json")
        if os.path.exists(filename):
            os.remove(filename)
            logger.info(f"Keystore deleted: {filename}")
