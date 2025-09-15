"""
Webhook handlers for real-time monitoring
"""

import logging
from aiohttp import web
import asyncio
from typing import Dict, Any
from monitor.watchlist_monitor import watchlist_monitor
from config import Config

logger = logging.getLogger(__name__)

routes = web.RouteTableDef()

@routes.post('/webhook/helius')
async def handle_helius_webhook(request):
    """Handle Helius webhook for Solana transactions"""
    try:
        data = await request.json()
        
        # Verify webhook signature
        signature = request.headers.get('x-signature')
        if not signature or not verify_helius_signature(signature, data):
            return web.Response(status=401, text='Invalid signature')
            
        # Process transaction
        await process_helius_transaction(data)
        return web.Response(status=200, text='OK')
        
    except Exception as e:
        logger.error(f"Helius webhook error: {e}")
        return web.Response(status=500, text=str(e))

@routes.post('/webhook/covalent')
async def handle_covalent_webhook(request):
    """Handle Covalent webhook for EVM chain transactions"""
    try:
        data = await request.json()
        
        # Verify webhook signature
        signature = request.headers.get('x-signature')
        if not signature or not verify_covalent_signature(signature, data):
            return web.Response(status=401, text='Invalid signature')
            
        # Process transaction
        await process_covalent_transaction(data)
        return web.Response(status=200, text='OK')
        
    except Exception as e:
        logger.error(f"Covalent webhook error: {e}")
        return web.Response(status=500, text=str(e))

def verify_helius_signature(signature: str, data: Dict[str, Any]) -> bool:
    """Verify Helius webhook signature"""
    try:
        import hmac
        import hashlib
        
        # Get webhook secret from config
        webhook_secret = Config.HELIUS_WEBHOOK_SECRET
        if not webhook_secret:
            logger.error("Helius webhook secret not configured")
            return False
            
        # Calculate expected signature
        message = str(data).encode('utf-8')
        expected = hmac.new(
            webhook_secret.encode('utf-8'),
            message,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected)
        
    except Exception as e:
        logger.error(f"Signature verification failed: {e}")
        return False

def verify_covalent_signature(signature: str, data: Dict[str, Any]) -> bool:
    """Verify Covalent webhook signature"""
    try:
        import hmac
        import hashlib
        
        # Get webhook secret from config
        webhook_secret = Config.COVALENT_WEBHOOK_SECRET
        if not webhook_secret:
            logger.error("Covalent webhook secret not configured")
            return False
            
        # Calculate expected signature
        message = str(data).encode('utf-8')
        expected = hmac.new(
            webhook_secret.encode('utf-8'),
            message,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected)
        
    except Exception as e:
        logger.error(f"Signature verification failed: {e}")
        return False

async def process_helius_transaction(data: Dict[str, Any]):
    """Process Helius transaction data"""
    try:
        # Extract transaction info
        tx = {
            'signature': data.get('signature'),
            'timestamp': data.get('timestamp'),
            'instructions': data.get('instructions', []),
            'accounts': data.get('accounts', [])
        }
        
        # Process through monitor
        await watchlist_monitor._process_solana_transaction(tx)
        
    except Exception as e:
        logger.error(f"Failed to process Helius transaction: {e}")

async def process_covalent_transaction(data: Dict[str, Any]):
    """Process Covalent transaction data"""
    try:
        # Extract transaction info
        tx = {
            'hash': data.get('hash'),
            'timestamp': data.get('timestamp'),
            'from_address': data.get('from_address'),
            'to_address': data.get('to_address'),
            'value': data.get('value'),
            'log_events': data.get('log_events', [])
        }
        
        # Process through monitor
        await watchlist_monitor._process_evm_transaction(tx)
        
    except Exception as e:
        logger.error(f"Failed to process Covalent transaction: {e}")

async def start_webhook_server():
    """Start webhook server"""
    app = web.Application()
    app.add_routes(routes)
    
    host = Config.WEBHOOK_HOST
    port = Config.WEBHOOK_PORT
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    
    logger.info(f"Webhook server running on http://{host}:{port}")
    
    return runner

async def stop_webhook_server(runner):
    """Stop webhook server"""
    await runner.cleanup()
