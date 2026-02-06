from typing import Any, Optional, Callable, Dict
from collections import OrderedDict
import time
import logging
from config import config

logger = logging.getLogger(__name__)


class CacheService:
    """
    Unified caching service with TTL, LRU eviction, and statistics tracking.
    
    Features:
    - Time-to-live (TTL) for cache entries
    - Size limits with LRU (Least Recently Used) eviction
    - Cache statistics (hits, misses, evictions)
    - Thread-safe operations
    """
    
    def __init__(
        self,
        name: str = "default",
        ttl: int = config.cache.TLE_CACHE_TTL,
        max_size: int = config.cache.MAX_CACHE_SIZE,
        enable_stats: bool = config.cache.ENABLE_CACHE_STATS
    ):
        """
        Initialize cache service.
        
        Args:
            name: Cache name for logging/debugging
            ttl: Time-to-live in seconds for cache entries
            max_size: Maximum number of entries in cache
            enable_stats: Whether to track cache statistics
        """
        self.name = name
        self.ttl = ttl
        self.max_size = max_size
        self.enable_stats = enable_stats
        
        self._cache: OrderedDict[str, Any] = OrderedDict()
        self._timestamps: Dict[str, float] = {}
        
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "sets": 0,
        }
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value if found and not expired, None otherwise
        """
        if key not in self._cache:
            if self.enable_stats:
                self._stats["misses"] += 1
            return None
        
        if self._is_expired(key):
            self._remove(key)
            if self.enable_stats:
                self._stats["misses"] += 1
            return None
        
        self._cache.move_to_end(key)
        
        if self.enable_stats:
            self._stats["hits"] += 1
        
        return self._cache[key]
    
    def set(self, key: str, value: Any) -> None:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
        """
        if key in self._cache:
            self._cache.move_to_end(key)
        else:
            self._cache[key] = value
            
            if len(self._cache) > self.max_size:
                self._evict_lru()
        
        self._cache[key] = value
        self._timestamps[key] = time.time()
        
        if self.enable_stats:
            self._stats["sets"] += 1
    
    def get_or_fetch(
        self,
        key: str,
        fetch_func: Callable[[], Any],
        ttl: Optional[int] = None
    ) -> Any:
        """
        Get value from cache or fetch it using provided function.
        
        Args:
            key: Cache key
            fetch_func: Function to call if value not in cache
            ttl: Optional TTL override for this entry
            
        Returns:
            Cached or fetched value
        """
        value = self.get(key)
        
        if value is not None:
            return value
        
        value = fetch_func()
        
        if value is not None:
            old_ttl = self.ttl
            if ttl is not None:
                self.ttl = ttl
            
            self.set(key, value)
            
            if ttl is not None:
                self.ttl = old_ttl
        
        return value
    
    def delete(self, key: str) -> bool:
        """
        Delete entry from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if key was deleted, False if not found
        """
        if key in self._cache:
            self._remove(key)
            return True
        return False
    
    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()
        self._timestamps.clear()
        logger.info(f"Cache '{self.name}' cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        total_requests = self._stats["hits"] + self._stats["misses"]
        hit_rate = (
            self._stats["hits"] / total_requests * 100
            if total_requests > 0
            else 0.0
        )
        
        return {
            "name": self.name,
            "size": len(self._cache),
            "max_size": self.max_size,
            "ttl": self.ttl,
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "evictions": self._stats["evictions"],
            "sets": self._stats["sets"],
            "hit_rate": f"{hit_rate:.2f}%",
        }
    
    def reset_stats(self) -> None:
        """Reset cache statistics."""
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "sets": 0,
        }
    
    def _is_expired(self, key: str) -> bool:
        """Check if cache entry has expired."""
        if key not in self._timestamps:
            return True
        
        age = time.time() - self._timestamps[key]
        return age > self.ttl
    
    def _remove(self, key: str) -> None:
        """Remove entry from cache."""
        if key in self._cache:
            del self._cache[key]
        if key in self._timestamps:
            del self._timestamps[key]
    
    def _evict_lru(self) -> None:
        """Evict least recently used entry."""
        if self._cache:
            oldest_key = next(iter(self._cache))
            self._remove(oldest_key)
            
            if self.enable_stats:
                self._stats["evictions"] += 1
            
            logger.debug(f"Cache '{self.name}' evicted LRU entry: {oldest_key}")


_global_caches: Dict[str, CacheService] = {}


def get_cache(
    name: str = "default",
    ttl: Optional[int] = None,
    max_size: Optional[int] = None,
    enable_stats: Optional[bool] = None
) -> CacheService:
    """
    Get or create a named cache instance.
    
    Args:
        name: Cache name
        ttl: TTL in seconds (uses config default if not specified)
        max_size: Max cache size (uses config default if not specified)
        enable_stats: Enable statistics (uses config default if not specified)
        
    Returns:
        CacheService instance
    """
    if name not in _global_caches:
        kwargs = {"name": name}
        if ttl is not None:
            kwargs["ttl"] = ttl
        if max_size is not None:
            kwargs["max_size"] = max_size
        if enable_stats is not None:
            kwargs["enable_stats"] = enable_stats
        
        _global_caches[name] = CacheService(**kwargs)
    
    return _global_caches[name]


def get_tle_cache() -> CacheService:
    """Get TLE cache instance."""
    return get_cache("tle", ttl=config.cache.TLE_CACHE_TTL)


def get_document_cache() -> CacheService:
    """Get document cache instance."""
    return get_cache("documents", ttl=config.cache.DOCUMENT_CACHE_TTL)
