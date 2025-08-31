import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    
    # Covalent API
    COVALENT_API_KEY = os.getenv('COVALENT_API_KEY')
    
    # Ethereum Configuration
    ETHEREUM_RPC_URL = os.getenv('ETHEREUM_RPC_URL', 'https://sepolia.infura.io/v3/YOUR_INFURA_KEY')
    CHAIN_ID = int(os.getenv('CHAIN_ID', '11155111'))  # Sepolia testnet
    NETWORK_NAME = os.getenv('NETWORK_NAME', 'sepolia')
    
    # Database
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///meme_trader.db')
    
    # API Settings
    MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))
    REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '30'))
    RATE_LIMIT_DELAY = float(os.getenv('RATE_LIMIT_DELAY', '1'))
    
    # Trading Settings
    DEFAULT_SLIPPAGE = float(os.getenv('DEFAULT_SLIPPAGE', '0.01'))
    MAX_GAS_PRICE = int(os.getenv('MAX_GAS_PRICE', '50'))
    MIN_LIQUIDITY_USD = int(os.getenv('MIN_LIQUIDITY_USD', '1000'))
    
    # AI Settings
    AI_SCORING_ENABLED = os.getenv('AI_SCORING_ENABLED', 'true').lower() == 'true'
    SENTIMENT_ANALYSIS_ENABLED = os.getenv('SENTIMENT_ANALYSIS_ENABLED', 'true').lower() == 'true'
    
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        required_vars = [
            'TELEGRAM_BOT_TOKEN',
            'COVALENT_API_KEY'
        ]
        
        missing = []
        for var in required_vars:
            if not getattr(cls, var):
                missing.append(var)
        
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
        
        return True