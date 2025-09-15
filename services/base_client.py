"""
Base API client implementation with error handling, retries and metrics
"""

import logging
import aiohttp
import asyncio
import backoff
import time
from typing import Dict, Any, Optional, Union
from services.api_manager import api_manager, APIError, RateLimitError
from services.key_manager import key_manager
from monitor.metrics import metrics_manager

logger = logging.getLogger(__name__)

class BaseAPIClient:
    """Base class for API clients with error handling and retries"""
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def ensure_session(self):
        """Ensure aiohttp session exists"""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=30)  # 30 second timeout
            self.session = aiohttp.ClientSession(timeout=timeout)
            
    async def close(self):
        """Close aiohttp session"""
        if self.session:
            await self.session.close()
            self.session = None
            
    @backoff.on_exception(
        backoff.expo,
        (aiohttp.ClientError, asyncio.TimeoutError),
        max_tries=3,
        max_time=30
    )
    async def _request(
        self,
        method: str,
        url: str,
        api_key: Optional[str] = None,
        **kwargs
    ) -> Any:
        """Make HTTP request with error handling, retries and metrics"""
        start_time = time.time()
        error = None
        try:
            await self.ensure_session()
            
            # Get API key if not provided
            if not api_key and self.service_name:
                api_key = await key_manager.get_key(self.service_name)
                
            # Add API key to headers
            if api_key:
                if 'headers' not in kwargs:
                    kwargs['headers'] = {}
                kwargs['headers']['Authorization'] = f'Bearer {api_key}'
                
            # Add default headers
            if 'headers' not in kwargs:
                kwargs['headers'] = {}
            kwargs['headers'].update({
                'User-Agent': 'MemeTraderV4Pro/1.0',
                'Accept': 'application/json'
            })
            
            # Make request with timeout
            async with self.session.request(method, url, **kwargs) as response:
                # Handle rate limits
                if response.status == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    if api_key:
                        await key_manager.update_key_usage(
                            self.service_name,
                            api_key,
                            error="Rate limit exceeded"
                        )
                    raise RateLimitError(retry_after)
                    
                # Handle other errors
                if response.status >= 400:
                    error_text = await response.text()
                    if api_key:
                        await key_manager.update_key_usage(
                            self.service_name,
                            api_key,
                            error=f"HTTP {response.status}: {error_text}"
                        )
                    raise APIError(response.status, error_text)
                    
                # Parse response
                try:
                    data = await response.json()
                except ValueError:
                    text = await response.text()
                    raise APIError(
                        response.status,
                        f"Invalid JSON response: {text[:200]}"
                    )
                    
                # Update key usage
                if api_key:
                    await key_manager.update_key_usage(
                        self.service_name,
                        api_key
                    )
                    
                # Record successful API call
                latency = time.time() - start_time
                metrics_manager.record_api_call(
                    service=self.service_name,
                    success=True,
                    latency=latency
                )
                return data
                
        except RateLimitError as e:
            error = str(e)
            raise
        except APIError as e:
            error = str(e)
            raise
        except asyncio.TimeoutError:
            error = "Request timed out"
            logger.error(f"Request timeout: {url}")
            raise APIError(504, error)
        except Exception as e:
            error = str(e)
            logger.error(f"Request failed: {e}")
            raise APIError(500, error)
        finally:
            if error:
                # Record failed API call
                latency = time.time() - start_time
                metrics_manager.record_api_call(
                    service=self.service_name,
                    success=False,
                    latency=latency,
                    error=error
                )
            
    @api_manager.rate_limit(service="default", max_calls=60, window_seconds=60)
    async def get(self, url: str, **kwargs) -> Any:
        """Make GET request"""
        return await self._request('GET', url, **kwargs)
        
    @api_manager.rate_limit(service="default", max_calls=60, window_seconds=60)
    async def post(self, url: str, **kwargs) -> Any:
        """Make POST request"""
        return await self._request('POST', url, **kwargs)
        
    def __del__(self):
        """Close session on deletion"""
        if self.session:
            asyncio.create_task(self.close())
