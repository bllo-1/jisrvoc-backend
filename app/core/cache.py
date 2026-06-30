"""Redis caching layer for JisrVOC.

Provides caching decorators and utilities for:
- Customer enrichment data (24h TTL)
- Dashboard metrics (1h TTL)
- Theme analytics (30min TTL)
"""

import logging
import json
import functools
from typing import Optional, Any, Callable
from datetime import timedelta

import redis
from app.core.config import settings

logger = logging.getLogger(__name__)

# Redis client (singleton)
_redis_client: Optional[redis.Redis] = None


def get_redis() -> redis.Redis:
    """Get Redis client singleton.

    Returns:
        Redis client instance
    """
    global _redis_client

    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.redis_url,
            decode_responses=True,  # Auto-decode bytes to str
            socket_timeout=5.0,
            socket_connect_timeout=5.0,
        )
        logger.info("Redis client initialized")

    return _redis_client


def cached(
    ttl: int = 3600,
    key_prefix: str = "",
    key_builder: Optional[Callable] = None,
):
    """Decorator for caching function results in Redis.

    Args:
        ttl: Time to live in seconds (default: 1 hour)
        key_prefix: Prefix for cache keys (e.g., "dashboard_metrics")
        key_builder: Custom function to build cache key from args/kwargs

    Example:
        @cached(ttl=3600, key_prefix="customer_enrichment")
        async def get_customer_data(customer_id: str):
            # Expensive Chargebee API call
            return data
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Build cache key
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                # Default: use function name + stringified args
                args_str = "_".join(str(arg) for arg in args)
                kwargs_str = "_".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
                cache_key = f"{key_prefix}:{func.__name__}:{args_str}:{kwargs_str}"

            try:
                redis_client = get_redis()

                # Try to get from cache
                cached_value = redis_client.get(cache_key)
                if cached_value:
                    logger.debug(f"Cache HIT: {cache_key}")
                    return json.loads(cached_value)

                # Cache miss - call function
                logger.debug(f"Cache MISS: {cache_key}")
                result = await func(*args, **kwargs)

                # Store in cache
                redis_client.setex(
                    cache_key,
                    timedelta(seconds=ttl),
                    json.dumps(result, default=str),  # default=str handles datetime
                )

                return result

            except redis.RedisError as e:
                logger.warning(f"Redis error (continuing without cache): {e}")
                # Gracefully degrade - call function without caching
                return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Build cache key
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                args_str = "_".join(str(arg) for arg in args)
                kwargs_str = "_".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
                cache_key = f"{key_prefix}:{func.__name__}:{args_str}:{kwargs_str}"

            try:
                redis_client = get_redis()

                # Try to get from cache
                cached_value = redis_client.get(cache_key)
                if cached_value:
                    logger.debug(f"Cache HIT: {cache_key}")
                    return json.loads(cached_value)

                # Cache miss - call function
                logger.debug(f"Cache MISS: {cache_key}")
                result = func(*args, **kwargs)

                # Store in cache
                redis_client.setex(
                    cache_key,
                    timedelta(seconds=ttl),
                    json.dumps(result, default=str),
                )

                return result

            except redis.RedisError as e:
                logger.warning(f"Redis error (continuing without cache): {e}")
                return func(*args, **kwargs)

        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def invalidate_cache(pattern: str):
    """Invalidate all cache keys matching a pattern.

    Args:
        pattern: Redis key pattern (e.g., "customer_enrichment:*")

    Example:
        # Invalidate all customer enrichment caches
        invalidate_cache("customer_enrichment:*")
    """
    try:
        redis_client = get_redis()
        keys = redis_client.keys(pattern)

        if keys:
            redis_client.delete(*keys)
            logger.info(f"Invalidated {len(keys)} cache keys matching '{pattern}'")
        else:
            logger.debug(f"No cache keys found matching '{pattern}'")

    except redis.RedisError as e:
        logger.error(f"Error invalidating cache: {e}")


def cache_customer_enrichment(customer_id: str, data: dict, ttl: int = 86400):
    """Cache customer enrichment data.

    Args:
        customer_id: Customer ID
        data: Enrichment data dict
        ttl: Time to live in seconds (default: 24 hours)
    """
    try:
        redis_client = get_redis()
        key = f"customer_enrichment:{customer_id}"
        redis_client.setex(key, timedelta(seconds=ttl), json.dumps(data, default=str))
        logger.debug(f"Cached enrichment data for customer {customer_id}")
    except redis.RedisError as e:
        logger.warning(f"Failed to cache enrichment data: {e}")


def get_cached_customer_enrichment(customer_id: str) -> Optional[dict]:
    """Get cached customer enrichment data.

    Args:
        customer_id: Customer ID

    Returns:
        Enrichment data dict or None if not cached
    """
    try:
        redis_client = get_redis()
        key = f"customer_enrichment:{customer_id}"
        cached_value = redis_client.get(key)

        if cached_value:
            logger.debug(f"Cache HIT for customer enrichment: {customer_id}")
            return json.loads(cached_value)
        else:
            logger.debug(f"Cache MISS for customer enrichment: {customer_id}")
            return None

    except redis.RedisError as e:
        logger.warning(f"Redis error reading cache: {e}")
        return None
