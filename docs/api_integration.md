# Meme Trader V4 Pro - API Integration Guide

## Overview
This guide documents all external API integrations used in Meme Trader V4 Pro.

## API Services

### 1. Covalent API
**Purpose:** Blockchain data and analytics

**Integration Details:**
```python
from integrations.covalent import CovalentAPI

client = CovalentAPI()
```

**Key Features:**
- Token holder data
- Transaction history
- Contract metadata
- Token balances

**Rate Limits:**
- Free Tier: 100,000 credits/month
- Production: Custom limits
- Retry After: 429 response

**Error Handling:**
```python
try:
    data = await client.get_token_holders(token_address)
except RateLimitError:
    await client.rotate_key()
    data = await client.get_token_holders(token_address)
```

### 2. GoPlus API
**Purpose:** Token security analysis

**Integration Details:**
```python
from integrations.goplus import GoPlusAPI

client = GoPlusAPI()
```

**Key Features:**
- Honeypot detection
- Contract analysis
- Security scoring
- Risk assessment

**Rate Limits:**
- Default: 60 requests/minute
- Custom plans available
- IP-based limiting

**Error Handling:**
```python
try:
    security = await client.check_token_security(token_address)
except APIError as e:
    if e.status == 429:
        await client.rotate_key()
```

### 3. 0x Protocol API
**Purpose:** DEX aggregation and trading

**Integration Details:**
```python
from integrations.zerox import ZeroXAPI

client = ZeroXAPI()
```

**Key Features:**
- Price quotes
- Swap transactions
- Gas estimation
- Token allowances

**Rate Limits:**
- Standard: 120 requests/minute
- Professional: Custom limits
- Per-endpoint limits

**Error Handling:**
```python
try:
    quote = await client.get_swap_quote(params)
except QuoteError:
    # Fallback to backup DEX
    quote = await backup_dex.get_quote(params)
```

### 4. Jupiter API
**Purpose:** Solana trading

**Integration Details:**
```python
from integrations.jupiter import JupiterAPI

client = JupiterAPI()
```

**Key Features:**
- Solana swaps
- Route finding
- Price impact
- Slippage control

**Rate Limits:**
- Public: 50 requests/minute
- Private: 300 requests/minute
- WebSocket limits

**Error Handling:**
```python
try:
    route = await client.get_route(params)
except WebSocketError:
    await client.reconnect()
```

### 5. Helius API
**Purpose:** Solana data and webhooks

**Integration Details:**
```python
from integrations.helius import HeliusAPI

client = HeliusAPI()
```

**Key Features:**
- NFT metadata
- Transaction parsing
- Webhook alerts
- RPC endpoints

**Rate Limits:**
- Starter: 100 requests/second
- Business: Custom limits
- Webhook rate limits

**Error Handling:**
```python
try:
    tx = await client.parse_transaction(signature)
except ParseError:
    await client.switch_endpoint()
```

### 6. CoinGecko API
**Purpose:** Market data and pricing

**Integration Details:**
```python
from integrations.coingecko import CoinGeckoAPI

client = CoinGeckoAPI()
```

**Key Features:**
- Token prices
- Market data
- Historical data
- Trending tokens

**Rate Limits:**
- Free: 50 requests/minute
- Pro: 500 requests/minute
- Retail limits

**Error Handling:**
```python
try:
    price = await client.get_token_price(token_id)
except RateLimitError:
    price = await backup_price_source.get_price(token_id)
```

## API Key Management

### Key Rotation
```python
# Define rotation strategy
rotation_config = {
    "max_usage": 80,  # % of rate limit
    "rotation_interval": 3600,  # seconds
    "cooldown_period": 300  # seconds
}

# Implement rotation
async def rotate_api_key(service: str):
    current_usage = await get_usage_stats(service)
    if current_usage > rotation_config["max_usage"]:
        await switch_to_next_key(service)
```

### Rate Limiting
```python
# Rate limit decorator
def rate_limit(limit: int, window: int):
    async def decorator(func):
        async def wrapper(*args, **kwargs):
            if await is_rate_limited():
                await rotate_api_key()
            return await func(*args, **kwargs)
        return wrapper
    return decorator
```

### Error Handling
```python
# Common error handler
async def handle_api_error(error: APIError, service: str):
    if error.status == 429:  # Rate limit
        await rotate_api_key(service)
    elif error.status == 401:  # Auth error
        await refresh_api_key(service)
    elif error.status >= 500:  # Server error
        await use_backup_service(service)
```

## Monitoring & Alerts

### Health Checks
```python
async def check_api_health():
    status = {}
    for service in API_SERVICES:
        try:
            health = await service.health_check()
            status[service.name] = health
        except Exception as e:
            status[service.name] = {"status": "error", "error": str(e)}
    return status
```

### Usage Tracking
```python
async def track_api_usage():
    metrics = {}
    for service in API_SERVICES:
        usage = await service.get_usage_stats()
        metrics[service.name] = {
            "requests": usage.requests,
            "rate_limit": usage.limit,
            "reset_time": usage.reset_at
        }
    return metrics
```

### Alert Configuration
```python
ALERT_THRESHOLDS = {
    "rate_limit": 80,  # Alert at 80% usage
    "error_rate": 5,   # Alert at 5% error rate
    "latency": 1000    # Alert at 1000ms latency
}

async def check_alert_conditions():
    for service in API_SERVICES:
        metrics = await service.get_metrics()
        if metrics.usage > ALERT_THRESHOLDS["rate_limit"]:
            await send_alert(f"{service.name} approaching rate limit")
```

## Best Practices

### 1. Rate Limit Management
- Implement exponential backoff
- Use multiple API keys
- Monitor usage patterns
- Set conservative limits

### 2. Error Handling
- Implement retries with backoff
- Use fallback services
- Log all errors
- Monitor error rates

### 3. Performance
- Cache responses
- Use connection pooling
- Implement request queuing
- Monitor latency

### 4. Security
- Secure API key storage
- Regular key rotation
- Access logging
- IP whitelisting

## Testing

### Integration Tests
```python
async def test_api_integration():
    # Test each service
    for service in API_SERVICES:
        # Basic connectivity
        assert await service.health_check()
        
        # Rate limiting
        await test_rate_limiting(service)
        
        # Error handling
        await test_error_scenarios(service)
        
        # Response validation
        await test_response_validation(service)
```

### Load Testing
```python
async def load_test_api():
    # Concurrent requests
    tasks = []
    for _ in range(100):
        tasks.append(api_client.make_request())
    
    # Monitor performance
    results = await asyncio.gather(*tasks)
    analyze_results(results)
```

## Troubleshooting

### Common Issues

1. Rate Limit Exceeded
```python
# Check current usage
usage = await api_client.get_usage()

# Rotate keys if needed
if usage.is_high():
    await api_client.rotate_keys()
```

2. Authentication Errors
```python
# Verify API key
await api_client.verify_key()

# Refresh if needed
await api_client.refresh_auth()
```

3. Connection Issues
```python
# Check connectivity
await api_client.check_connection()

# Switch endpoints if needed
await api_client.use_backup_endpoint()
```
