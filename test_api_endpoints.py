#!/usr/bin/env python3
"""
Test API endpoints for each integration
"""

import asyncio
import logging
import os
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).parent))

from integrations.zerox import ZeroXClient
from integrations.jupiter import JupiterClient
from integrations.coingecko import CoinGeckoClient
from integrations.goplus import GoPlusClient
from integrations.covalent import CovalentClient
from config import Config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_zerox():
    """Test 0x API endpoints"""
    api_key = Config.ZEROX_KEYS[0].strip() if Config.ZEROX_KEYS and Config.ZEROX_KEYS[0] else None
    if not api_key:
        logger.error("No 0x API key found")
        return False
        
    client = ZeroXClient(api_key)
    logger.info(f"Testing 0x API with key: {api_key[:8]}...")
    
    try:
        # Check health first
        logger.info("Testing 0x API health check...")
        health = await client.health_check()
        logger.info(f"0x Health check result: {health}")
        
        # Then try a quote
        logger.info("Testing 0x quote endpoint...")
        response = await client.get_quote(
            sell_token='ETH',
            buy_token='USDC',
            sell_amount='1000000000000000000'  # 1 ETH
        )
        
        logger.info(f"0x Quote response: {response}")
        return bool(response)
        
    except Exception as e:
        logger.error(f"0x API test failed: {e}")
        return False
    finally:
        await client.close()
        
async def test_jupiter():
    """Test Jupiter API endpoints"""
    client = JupiterClient()
    logger.info("Testing Jupiter API...")
    
    try:
        # Check health first
        logger.info("Testing Jupiter API health check...")
        health = await client.health_check()
        logger.info(f"Jupiter Health check result: {health}")
        
        # Then try a quote
        logger.info("Testing Jupiter quote endpoint...")
        response = await client.get_quote(
            input_mint='EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',  # USDC
            output_mint='So11111111111111111111111111111111111111112',   # SOL
            amount=1000000  # 1 USDC
        )
        
        logger.info(f"Jupiter Quote response: {response}")
        return bool(response)
        
    except Exception as e:
        logger.error(f"Jupiter API test failed: {e}")
        return False
    finally:
        await client.close()
        logger.info(f"Jupiter Response: {response}")
        return True
    except Exception as e:
        logger.error(f"Jupiter API test failed: {e}")
        return False
    finally:
        await client.close()

async def main():
    """Run all API tests"""
    results = await asyncio.gather(
        test_zerox(),
        test_jupiter()
    )
    
    logger.info("API Test Results:")
    logger.info(f"0x Protocol: {'✓' if results[0] else '✗'}")
    logger.info(f"Jupiter: {'✓' if results[1] else '✗'}")
    
if __name__ == '__main__':
    asyncio.run(main())
