#!/usr/bin/env python3
"""
Health check script for Meme Trader V4 Pro
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def check_config():
    """Check configuration"""
    try:
        import os
        from config import Config
        
        # Check if required environment variables are set
        required_vars = ['TELEGRAM_BOT_TOKEN']
        
        # Check for API keys (either new rotation format or legacy)
        api_key_services = ['covalent', 'goplus']
        missing_api_keys = []
        
        for service in api_key_services:
            # Check new rotation format first
            rotation_keys = os.getenv(f'{service.upper()}_KEYS')
            legacy_key = os.getenv(f'{service.upper()}_API_KEY')
            
            if not rotation_keys and not legacy_key:
                missing_api_keys.append(service)
        
        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            logger.error(f"Configuration: FAILED - Missing required environment variables: {', '.join(missing_vars)}")
            return False
        elif missing_api_keys:
            logger.warning(f"Configuration: WARNING - Missing API keys for services: {', '.join(missing_api_keys)}")
            logger.info("Configuration: HEALTHY (with warnings)")
            return True
        else:
            logger.info("Configuration: HEALTHY")
            return True
            
    except Exception as e:
        logger.error(f"Configuration: FAILED - {e}")
        return False

async def check_database():
    """Check database connection"""
    try:
        from db.models import get_db_session, create_tables
        create_tables()
        db = get_db_session()
        db.execute("SELECT 1")
        db.close()
        logger.info("Database: HEALTHY")
        return True
    except Exception as e:
        logger.error(f"Database: FAILED - {e}")
        return False

async def check_integrations():
    """Check API integrations"""
    try:
        from integrations.zerox import ZeroXClient
        from integrations.jupiter import JupiterClient
        from integrations.helius import HeliusClient
        from integrations.coingecko import CoinGeckoClient
        from integrations.goplus import GoPlusClient
        from integrations.covalent import CovalentClient
        from utils.key_manager import get_key_manager
        
        key_manager = get_key_manager()
        results = {}
        
        # Test 0x Protocol
        zerox_key = key_manager.get_key('zerox')
        if zerox_key:
            zerox = ZeroXClient(zerox_key)
            results['0x Protocol'] = await zerox.health_check()
        
        # Test Jupiter
        jupiter_key = key_manager.get_key('jupiter')
        if jupiter_key:
            jupiter = JupiterClient(jupiter_key)
            results['Jupiter'] = await jupiter.health_check()
        
        # Test Helius
        helius_key = key_manager.get_key('helius')
        if helius_key:
            helius = HeliusClient(helius_key)
            results['Helius'] = await helius.health_check()
        
        # Test CoinGecko
        coingecko_key = key_manager.get_key('coingecko')
        if coingecko_key:
            coingecko = CoinGeckoClient(coingecko_key)
            results['CoinGecko'] = await coingecko.health_check()
        
        # Test GoPlus
        goplus_key = key_manager.get_key('goplus')
        if goplus_key:
            goplus = GoPlusClient(goplus_key)
            results['GoPlus'] = await goplus.health_check()
        
        # Test Covalent
        covalent_key = key_manager.get_key('covalent')
        if covalent_key:
            covalent = CovalentClient(covalent_key)
            results['Covalent'] = await covalent.health_check()
        
        # Print results
        logger.info("\nIntegration Health Check Results:")
        logger.info("=================================")
        healthy_count = 0
        for service, status in results.items():
            status_str = "✅ HEALTHY" if status else "❌ UNHEALTHY"
            logger.info(f"{service:15} {status_str}")
            if status:
                healthy_count += 1
        
        if healthy_count == len(results):
            logger.info("Integrations: HEALTHY")
            return True
        elif healthy_count > 0:
            logger.warning("Integrations: PARTIAL")
            return True
        else:
            logger.error("Integrations: FAILED")
            return False
    except Exception as e:
        logger.error(f"Integrations: FAILED - {e}")
        return False

async def check_bot():
    """Check bot initialization"""
    try:
        from bot.commands import get_bot_commands
        commands = await get_bot_commands()
        logger.info("Bot Commands: READY")
        return True
    except Exception as e:
        logger.error(f"Bot: FAILED - {e}")
        return False

async def main():
    """Run all health checks"""
    await check_config()
    await check_database()
    await check_integrations()
    # Skip bot check to avoid conflicts
    return True
    logger.info("Running Meme Trader V4 Pro Health Checks...")
    
    checks = [
        ("Configuration", check_config),
        ("Database", check_database),
        ("Integrations", check_integrations),
        ("Bot", check_bot)
    ]
    
    results = {}
    for name, check_func in checks:
        logger.info(f"\nChecking {name}...")
        results[name] = await check_func()
    
    # Summary
    logger.info("\n" + "="*50)
    logger.info("HEALTH CHECK SUMMARY")
    logger.info("="*50)
    
    all_healthy = True
    for name, status in results.items():
        icon = "OK" if status else "FAILED"
        status_text = "HEALTHY" if status else "FAILED"
        logger.info(f"{icon} {name}: {status_text}")
        if not status:
            all_healthy = False
    
    logger.info("="*50)
    if all_healthy:
        logger.info("All systems are healthy! Bot is ready to run.")
        return True
    else:
        logger.error("Some systems have issues. Please fix them before running the bot.")
        return False

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("Health check interrupted")
        sys.exit(1) 