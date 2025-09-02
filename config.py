import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '8300046520:AAE6wdXTyK0w_-moczD33zSxjYkNsyp2cyY')
    
    # API Keys
    COVALENT_API_KEY = os.getenv('COVALENT_API_KEY')
    ZEROX_API_KEY = os.getenv('ZEROX_API_KEY')
    GOPLUS_API_KEY = os.getenv('GOPLUS_API_KEY') 
    COINGECKO_API_KEY = os.getenv('COINGECKO_API_KEY')
    
    # Ethereum Configuration
    ETHEREUM_RPC_URL = os.getenv('ETHEREUM_RPC_URL', 'https://eth-sepolia.g.alchemy.com/v2/Iurh2GQfC9EzY-mtDP3dI')
    CHAIN_ID = int(os.getenv('CHAIN_ID', '11155111'))  # Sepolia testnet
    NETWORK_NAME = os.getenv('NETWORK_NAME', 'sepolia')
    
    # BSC Configuration
    BSC_RPC_URL = os.getenv('BSC_RPC_URL', 'https://bnb-testnet.g.alchemy.com/v2/Iurh2GQfC9EzY-mtDP3dI')
    BSC_CHAIN_ID = int(os.getenv('BSC_CHAIN_ID', '97'))  # BSC testnet
    BSC_NETWORK_NAME = os.getenv('BSC_NETWORK_NAME', 'bsc-testnet')
    
    # Alchemy WebSocket URLs
    ALCHEMY_ETH_WS_URL = os.getenv('ALCHEMY_ETH_WS_URL', 'wss://eth-sepolia.g.alchemy.com/v2/Iurh2GQfC9EzY-mtDP3dI')
    ALCHEMY_BSC_WS_URL = os.getenv('ALCHEMY_BSC_WS_URL', 'wss://bnb-testnet.g.alchemy.com/v2/Iurh2GQfC9EzY-mtDP3dI')
    
    # 0x Protocol APIs
    ZEROEX_ETH_API = os.getenv('ZEROEX_ETH_API', 'https://sepolia.api.0x.org')
    ZEROEX_BSC_API = os.getenv('ZEROEX_BSC_API', 'https://bsc.api.0x.org')
    
    # Jupiter/Solana Configuration
    JUPITER_API_URL = os.getenv('JUPITER_API_URL', 'https://quote-api.jup.ag/v6')
    SOLANA_RPC_URL = os.getenv('SOLANA_RPC_URL', 'https://solana-devnet.g.alchemy.com/v2/Iurh2GQfC9EzY-mtDP3dI')
    SOLANA_NETWORK = os.getenv('SOLANA_NETWORK', 'devnet')
    
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
    GAS_LIMIT_BUFFER = float(os.getenv('GAS_LIMIT_BUFFER', '1.2'))
    
    # AI Settings
    AI_SCORING_ENABLED = os.getenv('AI_SCORING_ENABLED', 'true').lower() == 'true'
    SENTIMENT_ANALYSIS_ENABLED = os.getenv('SENTIMENT_ANALYSIS_ENABLED', 'true').lower() == 'true'
    EMERGENT_LLM_KEY = os.getenv('EMERGENT_LLM_KEY')
    
    # Security Settings
    KEYSTORE_PASSWORD_REQUIRED = os.getenv('KEYSTORE_PASSWORD_REQUIRED', 'true').lower() == 'true'
    DRY_RUN_MODE = os.getenv('DRY_RUN_MODE', 'false').lower() == 'true'
    
    # Router Addresses (for honeypot detection)
    UNISWAP_V2_ROUTER = '0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D'
    PANCAKESWAP_ROUTER = '0xD99D1c33F9fC3444f8101754aBC46c52416550D1'  # BSC testnet
    SUSHISWAP_ROUTER = '0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F'
    
    # Common token addresses
    WETH_ADDRESS = '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2'
    WETH_SEPOLIA = '0x7b79995e5f793A07Bc00c21412e50Ecae098E7f9'
    WBNB_ADDRESS = '0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c'
    WBNB_TESTNET = '0xae13d989daC2f0dEbFf460aC112a837C89BAa7cd'
    
    @classmethod
    def get_wrapped_native_token(cls, chain_id: int) -> str:
        """Get wrapped native token address for chain"""
        if chain_id == 1:  # Ethereum mainnet
            return cls.WETH_ADDRESS
        elif chain_id == 11155111:  # Sepolia
            return cls.WETH_SEPOLIA
        elif chain_id == 56:  # BSC mainnet
            return cls.WBNB_ADDRESS
        elif chain_id == 97:  # BSC testnet
            return cls.WBNB_TESTNET
        else:
            return cls.WETH_SEPOLIA  # Default to Sepolia WETH
    
    @classmethod
    def get_router_address(cls, chain_id: int) -> str:
        """Get router address for chain"""
        if chain_id in [1, 11155111]:  # Ethereum/Sepolia
            return cls.UNISWAP_V2_ROUTER
        elif chain_id in [56, 97]:  # BSC
            return cls.PANCAKESWAP_ROUTER
        else:
            return cls.UNISWAP_V2_ROUTER
    
    @classmethod
    def get_0x_api_url(cls, chain_id: int) -> str:
        """Get 0x API URL for chain"""
        if chain_id in [1, 11155111]:  # Ethereum/Sepolia
            return cls.ZEROEX_ETH_API
        elif chain_id in [56, 97]:  # BSC
            return cls.ZEROEX_BSC_API
        else:
            return cls.ZEROEX_ETH_API
    
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