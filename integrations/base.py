"""
Base integration classes for Meme Trader V4 Pro
"""

import asyncio
import aiohttp
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class BaseAPIClient(ABC):
    """Base class for all API integrations"""
    
    def __init__(self, api_key: str, base_url: str, rate_limit: int = 60):
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.rate_limit = rate_limit
        self.session = None
        self.last_request_time = datetime.utcnow()
        self.request_count = 0
        
    async def get_session(self):
        """Get or create aiohttp session with proper headers"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            trace_config = aiohttp.TraceConfig()
            trace_config.on_request_start.append(self._on_request_start)
            
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                trace_configs=[trace_config],
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Accept': 'application/json',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Cache-Control': 'no-cache',
                    'Connection': 'keep-alive'
                }
            )
        return self.session
        
    async def _on_request_start(self, session, trace_config_ctx, params):
        """Add request-specific headers"""
        params.headers.update({
            'Referer': self.base_url,
            'Origin': self.base_url
        })
    
    async def close(self):
        """Close the session"""
        if self.session and not self.session.closed:
            await self.session.close()
            
    async def rate_limit_check(self):
        """Check and enforce rate limits"""
        now = datetime.utcnow()
        
        # Reset counter every minute
        if now - self.last_request_time > timedelta(minutes=1):
            self.request_count = 0
            self.last_request_time = now
            
        # Wait if we've hit the limit
        if self.request_count >= self.rate_limit:
            wait_time = 60 - (now - self.last_request_time).total_seconds()
            if wait_time > 0:
                logger.info(f"Rate limit hit for {self.__class__.__name__}, waiting {wait_time:.1f}s")
                await asyncio.sleep(wait_time)
                self.request_count = 0
                self.last_request_time = datetime.utcnow()
        
        self.request_count += 1
    
    async def make_request(self, method: str, endpoint: str, **kwargs) -> Optional[Dict]:
        """Make rate-limited API request"""
        await self.rate_limit_check()
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        # Add default headers to bypass Cloudflare
        headers = kwargs.get('headers', {})
        headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive'
        })
        
        # Add API key to headers if provided
        if self.api_key:
            # Support both Bearer and API key formats
            if 'Authorization' not in headers:
                if '0x-api-key' not in headers:  # For 0x Protocol
                    headers['Authorization'] = f'Bearer {self.api_key}'
        
        kwargs['headers'] = headers
        try:
            session = await self.get_session()
            async with session.request(method, url, **kwargs) as response:
                # Handle different response statuses
                if response.status == 200:
                    return await response.json()
                elif response.status == 429:
                    logger.warning(f"Rate limited by {self.__class__.__name__}")
                    await asyncio.sleep(60)
                    return await self.make_request(method, endpoint, **kwargs)
                elif response.status in (403, 503):
                    # Check for Cloudflare block
                    error_text = await response.text()
                    if "cloudflare" in error_text.lower():
                        logger.warning("Cloudflare block detected, retrying with enhanced headers...")
                        # Update headers with better browser emulation
                        headers.update({
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36',
                            'Accept': 'application/json,text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                            'Accept-Language': 'en-US,en;q=0.5',
                            'Accept-Encoding': 'gzip, deflate, br',
                            'Connection': 'keep-alive',
                            'Upgrade-Insecure-Requests': '1',
                            'Sec-Fetch-Dest': 'document',
                            'Sec-Fetch-Mode': 'navigate',
                            'Sec-Fetch-Site': 'same-origin',
                            'Pragma': 'no-cache',
                            'Cache-Control': 'no-cache'
                        })
                        kwargs['headers'] = headers
                        await self.close()  # Close the old session
                        self.session = None  # Force new session creation
                        await asyncio.sleep(5)
                        return await self.make_request(method, endpoint, **kwargs)
                
                # Log error for any other status
                error_text = await response.text()
                logger.error(f"API error {response.status}: {error_text}")
                return None
        except Exception as e:
            logger.error(f"Request failed: {e}")
            return None
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the API is healthy"""
        pass


class BaseChainClient(ABC):
    """Base class for blockchain RPC clients"""
    
    def __init__(self, rpc_url: str, chain_id: int):
        self.rpc_url = rpc_url
        self.chain_id = chain_id
        self.session = None
        
    async def get_session(self):
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            # Use async with for session management
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session
    
    async def close(self):
        """Close the session"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    @abstractmethod
    async def get_balance(self, address: str) -> float:
        """Get native token balance"""
        pass
    
    @abstractmethod
    async def get_token_balance(self, address: str, token_address: str) -> float:
        """Get ERC20/SPL token balance"""
        pass
    
    @abstractmethod
    async def simulate_transaction(self, transaction: Dict) -> bool:
        """Simulate transaction execution"""
        pass


class IntegrationManager:
    """Manages all API integrations"""
    
    def __init__(self):
        self.clients = {}
        self.health_status = {}
        
    def register_client(self, name: str, client: BaseAPIClient):
        """Register a new API client"""
        self.clients[name] = client
        self.health_status[name] = None
        
    async def health_check_all(self) -> Dict[str, bool]:
        """Check health of all registered clients"""
        results = {}
        
        for name, client in self.clients.items():
            try:
                status = await client.health_check()
                results[name] = status
                self.health_status[name] = status
            except Exception as e:
                logger.error(f"Health check failed for {name}: {e}")
                results[name] = False
                self.health_status[name] = False
                
        return results
    
    async def close_all(self):
        """Close all client sessions"""
        for client in self.clients.values():
            await client.close()
    
    def get_client(self, name: str) -> Optional[BaseAPIClient]:
        """Get a registered client by name"""
        return self.clients.get(name)
    
    def is_healthy(self, name: str) -> bool:
        """Check if a specific client is healthy"""
        return self.health_status.get(name, False)


# Global integration manager instance
integration_manager = IntegrationManager()