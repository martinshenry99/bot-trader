"""
Health check implementations for various components
"""
from typing import Dict, Any
import aiohttp
import redis
from core.reliability import Cache

async def check_api_health(
    url: str,
    headers: Dict[str, str] = None
) -> Dict[str, Any]:
    """Check API health by making a request"""
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            return {
                'status_code': response.status,
                'response_time': response.elapsed.total_seconds()
            }

async def check_zerox_api() -> Dict[str, Any]:
    """Check 0x API health"""
    return await check_api_health(
        "https://api.0x.org/healthz"
    )

async def check_jupiter_api() -> Dict[str, Any]:
    """Check Jupiter API health"""
    return await check_api_health(
        "https://quote-api.jup.ag/v4/health"
    )

async def check_coingecko_api() -> Dict[str, Any]:
    """Check CoinGecko API health"""
    return await check_api_health(
        "https://api.coingecko.com/api/v3/ping"
    )

async def check_goplus_api(api_key: str) -> Dict[str, Any]:
    """Check GoPlus API health"""
    return await check_api_health(
        "https://api.gopluslabs.io/api/v1/health",
        headers={"X-API-KEY": api_key}
    )

async def check_covalent_api(api_key: str) -> Dict[str, Any]:
    """Check Covalent API health"""
    return await check_api_health(
        "https://api.covalenthq.com/v1/health/",
        headers={"Authorization": f"Bearer {api_key}"}
    )

async def check_helius_api(api_key: str) -> Dict[str, Any]:
    """Check Helius API health"""
    return await check_api_health(
        "https://api.helius.xyz/v0/health",
        headers={"Authorization": f"Bearer {api_key}"}
    )

async def check_redis_health(
    redis_client: redis.Redis
) -> Dict[str, Any]:
    """Check Redis health"""
    info = redis_client.info()
    return {
        'connected_clients': info['connected_clients'],
        'used_memory_human': info['used_memory_human'],
        'uptime_days': info['uptime_in_days']
    }

async def check_cache_health(
    cache: Cache
) -> Dict[str, Any]:
    """Check cache health"""
    test_key = "health_check_test"
    test_value = "test"
    
    # Test write
    write_success = await cache.set(
        test_key,
        test_value,
        ttl=60
    )
    
    # Test read
    read_value = await cache.get(test_key)
    
    # Test delete
    delete_success = await cache.delete(test_key)
    
    return {
        'write_success': write_success,
        'read_success': read_value == test_value,
        'delete_success': delete_success
    }

def check_system_resources() -> Dict[str, Any]:
    """Check system resource usage"""
    import psutil
    
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    return {
        'cpu_percent': psutil.cpu_percent(interval=1),
        'memory_usage': {
            'total': memory.total,
            'available': memory.available,
            'percent': memory.percent
        },
        'disk_usage': {
            'total': disk.total,
            'free': disk.free,
            'percent': disk.percent
        },
        'open_files': len(psutil.Process().open_files()),
        'connections': len(psutil.Process().connections())
    }

async def check_network_latency() -> Dict[str, Any]:
    """Check network latency to various endpoints"""
    endpoints = {
        'ethereum': 'https://cloudflare-eth.com',
        'solana': 'https://api.mainnet-beta.solana.com',
        'bsc': 'https://bsc-dataseed1.binance.org'
    }
    
    results = {}
    async with aiohttp.ClientSession() as session:
        for name, url in endpoints.items():
            try:
                start_time = time.time()
                async with session.get(url) as response:
                    latency = time.time() - start_time
                    results[name] = {
                        'latency': latency,
                        'status': response.status
                    }
            except Exception as e:
                results[name] = {
                    'error': str(e)
                }
                
    return results

class HealthChecker:
    """Manages health checks for all components"""
    
    def __init__(
        self,
        config: Dict[str, Any],
        cache: Cache,
        redis_client: redis.Redis
    ):
        self.config = config
        self.cache = cache
        self.redis = redis_client
        
    async def check_all(self) -> Dict[str, Any]:
        """Run all health checks"""
        results = {
            'timestamp': datetime.utcnow().isoformat(),
            'system': check_system_resources(),
            'network': await check_network_latency()
        }
        
        # Check APIs
        api_results = {}
        if self.config.get('zerox_api_key'):
            api_results['zerox'] = await check_zerox_api()
            
        if self.config.get('jupiter_enabled'):
            api_results['jupiter'] = await check_jupiter_api()
            
        if self.config.get('goplus_api_key'):
            api_results['goplus'] = await check_goplus_api(
                self.config['goplus_api_key']
            )
            
        if self.config.get('covalent_api_key'):
            api_results['covalent'] = await check_covalent_api(
                self.config['covalent_api_key']
            )
            
        if self.config.get('helius_api_key'):
            api_results['helius'] = await check_helius_api(
                self.config['helius_api_key']
            )
            
        api_results['coingecko'] = await check_coingecko_api()
        results['apis'] = api_results
        
        # Check infrastructure
        results['infrastructure'] = {
            'redis': await check_redis_health(self.redis),
            'cache': await check_cache_health(self.cache)
        }
        
        return results
        
    def get_health_summary(self) -> Dict[str, Any]:
        """Get a summary of system health"""
        results = {}
        
        # Check system resources
        sys_resources = check_system_resources()
        results['system'] = {
            'status': (
                'healthy'
                if sys_resources['cpu_percent'] < 80
                and sys_resources['memory_usage']['percent'] < 80
                and sys_resources['disk_usage']['percent'] < 80
                else 'degraded'
            ),
            'metrics': {
                'cpu': sys_resources['cpu_percent'],
                'memory': sys_resources['memory_usage']['percent'],
                'disk': sys_resources['disk_usage']['percent']
            }
        }
        
        # Quick Redis check
        try:
            self.redis.ping()
            results['redis'] = {'status': 'healthy'}
        except:
            results['redis'] = {
                'status': 'failed',
                'error': 'Connection failed'
            }
            
        # Quick cache check
        cache_status = 'healthy'
        try:
            await self.cache.set('health_check', '1', 60)
        except:
            cache_status = 'failed'
        results['cache'] = {'status': cache_status}
        
        return results
