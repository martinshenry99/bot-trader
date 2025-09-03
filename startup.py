"""
Startup script to initialize all integrations and services
"""

import logging
import asyncio
from config import Config
from integrations.base import integration_manager
from integrations.zerox import ZeroXClient
from integrations.jupiter import JupiterClient
from integrations.coingecko import CoinGeckoClient
from integrations.goplus import GoPlusClient
from integrations.covalent import CovalentClient

logger = logging.getLogger(__name__)


async def initialize_integrations():
    """Initialize all API integrations"""
    try:
        logger.info("Initializing API integrations...")
        
        # Initialize 0x clients for different chains
        if Config.ZEROX_API_KEY:
            # Ethereum client
            zerox_eth = ZeroXClient(Config.ZEROX_API_KEY, chain_id=Config.CHAIN_ID)
            integration_manager.register_client('zerox_eth', zerox_eth)
            
            # BSC client
            zerox_bsc = ZeroXClient(Config.ZEROX_API_KEY, chain_id=Config.BSC_CHAIN_ID)
            integration_manager.register_client('zerox_bsc', zerox_bsc)
            
            # Default 0x client (for backward compatibility)
            integration_manager.register_client('zerox', zerox_eth)
            
            logger.info("0x Protocol clients initialized")
        else:
            logger.warning("0x API key not found")
        
        # Initialize Jupiter client for Solana
        jupiter_client = JupiterClient()
        integration_manager.register_client('jupiter', jupiter_client)
        logger.info("Jupiter client initialized")
        
        # Initialize CoinGecko client
        if Config.COINGECKO_API_KEY:
            coingecko_client = CoinGeckoClient(Config.COINGECKO_API_KEY)
            integration_manager.register_client('coingecko', coingecko_client)
            logger.info("CoinGecko client initialized")
        else:
            logger.warning("CoinGecko API key not found")
        
        # Initialize GoPlus client
        if Config.GOPLUS_API_KEY:
            goplus_client = GoPlusClient(Config.GOPLUS_API_KEY)
            integration_manager.register_client('goplus', goplus_client)
            logger.info("GoPlus client initialized")
        else:
            logger.warning("GoPlus API key not found")
        
        # Initialize Covalent client
        if Config.COVALENT_API_KEY:
            covalent_client = CovalentClient(Config.COVALENT_API_KEY)
            integration_manager.register_client('covalent', covalent_client)
            logger.info("Covalent client initialized")
        else:
            logger.warning("Covalent API key not found")
        
        # Health check all clients
        logger.info("Running health checks...")
        health_results = await integration_manager.health_check_all()
        
        healthy_clients = sum(1 for status in health_results.values() if status)
        total_clients = len(health_results)
        
        logger.info(f"Health check results: {healthy_clients}/{total_clients} clients healthy")
        
        for client_name, is_healthy in health_results.items():
            status = "HEALTHY" if is_healthy else "UNHEALTHY"
            logger.info(f"  - {client_name}: {status}")
        
        if healthy_clients == 0:
            logger.error("No healthy clients found! Check API keys and network connectivity.")
            return False
        elif healthy_clients < total_clients:
            logger.warning(f"{total_clients - healthy_clients} clients are unhealthy. Some features may be limited.")
        
        logger.info("Integration initialization completed successfully.")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize integrations: {e}")
        return False


async def startup_sequence():
    """Complete startup sequence"""
    try:
        logger.info("🚀 Starting Meme Trader V4 Pro...")
        
        # Initialize integrations
        integration_success = await initialize_integrations()
        
        if not integration_success:
            logger.error("❌ Critical: Integration initialization failed")
            return False
        
        # Initialize trading engine
        from core.trading_engine import trading_engine
        logger.info("✅ Trading engine initialized")
        
        # Log configuration summary
        logger.info("📋 Configuration Summary:")
        logger.info(f"  • Ethereum RPC: {Config.ETHEREUM_RPC_URL[:50]}...")
        logger.info(f"  • BSC RPC: {Config.BSC_RPC_URL[:50]}...")
        logger.info(f"  • Solana RPC: {Config.SOLANA_RPC_URL[:50]}...")
        logger.info(f"  • Jupiter API: {Config.JUPITER_API_URL}")
        logger.info(f"  • Trading enabled on: ETH (Chain {Config.CHAIN_ID}), BSC (Chain {Config.BSC_CHAIN_ID}), Solana")
        
        # Trading engine configuration
        config = trading_engine.config
        logger.info("⚙️ Trading Engine Configuration:")
        logger.info(f"  • Safe Mode: {'ON' if config['safe_mode'] else 'OFF'}")
        logger.info(f"  • Mirror Sell: {'ON' if config['mirror_sell_enabled'] else 'OFF'}")
        logger.info(f"  • Mirror Buy: {'ON' if config['mirror_buy_enabled'] else 'OFF'}")
        logger.info(f"  • Max Auto Buy: ${config['max_auto_buy_usd']}")
        logger.info(f"  • Max Slippage: {config['max_slippage']*100:.1f}%")
        
        logger.info("🎯 All systems initialized successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Startup sequence failed: {e}")
        return False


def run_startup():
    """Run startup sequence synchronously"""
    return asyncio.run(startup_sequence())


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    
    success = run_startup()
    if success:
        print("✅ Startup completed successfully!")
    else:
        print("❌ Startup failed!")
        exit(1)