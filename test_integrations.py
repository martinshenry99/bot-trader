"""
Test integration health directly
"""
import asyncio
import logging
from integrations.zerox import ZeroXClient
from integrations.jupiter import JupiterClient
from integrations.helius import HeliusClient
from integrations.coingecko import CoinGeckoClient
from integrations.goplus import GoPlusClient
from integrations.covalent import CovalentClient
from config import Config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_integrations():
    results = {}
    
    # Test 0x Protocol
    try:
        logger.info("Testing 0x Protocol integration...")
        if hasattr(Config, 'ZEROX_KEYS') and Config.ZEROX_KEYS:
            zerox = ZeroXClient(Config.ZEROX_KEYS[0])
            results['0x Protocol'] = await zerox.health_check()
            logger.info(f"0x Protocol test complete: {'HEALTHY' if results['0x Protocol'] else 'UNHEALTHY'}")
        else:
            logger.warning("0x Protocol keys not configured")
    except Exception as e:
        logger.error(f"0x Protocol test failed: {e}")
        results['0x Protocol'] = False
    
    # Test Jupiter
    try:
        logger.info("Testing Jupiter integration...")
        if hasattr(Config, 'JUPITER_KEYS') and Config.JUPITER_KEYS:
            jupiter = JupiterClient(Config.JUPITER_KEYS[0])
            results['Jupiter'] = await jupiter.health_check()
            logger.info(f"Jupiter test complete: {'HEALTHY' if results['Jupiter'] else 'UNHEALTHY'}")
        else:
            logger.warning("Jupiter keys not configured")
    except Exception as e:
        logger.error(f"Jupiter test failed: {e}")
        results['Jupiter'] = False
    
    # Test Helius
    try:
        logger.info("Testing Helius integration...")
        if hasattr(Config, 'HELIUS_KEYS') and Config.HELIUS_KEYS:
            helius = HeliusClient(Config.HELIUS_KEYS[0])
            results['Helius'] = await helius.health_check()
            logger.info(f"Helius test complete: {'HEALTHY' if results['Helius'] else 'UNHEALTHY'}")
        else:
            logger.warning("Helius keys not configured")
    except Exception as e:
        logger.error(f"Helius test failed: {e}")
        results['Helius'] = False
    
    # Test CoinGecko
    try:
        logger.info("Testing CoinGecko integration...")
        if Config.COINGECKO_API_KEY:
            coingecko = CoinGeckoClient(Config.COINGECKO_API_KEY)
            results['CoinGecko'] = await coingecko.health_check()
            logger.info(f"CoinGecko test complete: {'HEALTHY' if results['CoinGecko'] else 'UNHEALTHY'}")
        else:
            logger.warning("CoinGecko key not configured")
    except Exception as e:
        logger.error(f"CoinGecko test failed: {e}")
        results['CoinGecko'] = False
    
    # Test GoPlus
    try:
        logger.info("Testing GoPlus integration...")
        if Config.GOPLUS_API_KEY:
            goplus = GoPlusClient(Config.GOPLUS_API_KEY)
            results['GoPlus'] = await goplus.health_check()
            logger.info(f"GoPlus test complete: {'HEALTHY' if results['GoPlus'] else 'UNHEALTHY'}")
        else:
            logger.warning("GoPlus key not configured")
    except Exception as e:
        logger.error(f"GoPlus test failed: {e}")
        results['GoPlus'] = False
    
    # Test Covalent
    try:
        logger.info("Testing Covalent integration...")
        if hasattr(Config, 'COVALENT_KEYS') and Config.COVALENT_KEYS:
            covalent = CovalentClient(Config.COVALENT_KEYS[0])
            results['Covalent'] = await covalent.health_check()
            logger.info(f"Covalent test complete: {'HEALTHY' if results['Covalent'] else 'UNHEALTHY'}")
        else:
            logger.warning("Covalent keys not configured")
    except Exception as e:
        logger.error(f"Covalent test failed: {e}")
        results['Covalent'] = False
    
    return results

if __name__ == "__main__":
    results = asyncio.run(test_integrations())
    print("\nIntegration Health Check Results:")
    print("=================================")
    for service, status in results.items():
        status_str = "✅ HEALTHY" if status else "❌ UNHEALTHY"
        print(f"{service:15} {status_str}")
