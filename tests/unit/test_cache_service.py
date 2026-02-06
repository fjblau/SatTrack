import unittest
import time
from api.services.cache_service import CacheService, get_cache


class TestCacheService(unittest.TestCase):
    """Test cases for CacheService"""
    
    def setUp(self):
        """Set up test cache instance"""
        self.cache = CacheService(
            name="test",
            ttl=2,
            max_size=3,
            enable_stats=True
        )
    
    def tearDown(self):
        """Clean up after each test"""
        self.cache.clear()
    
    def test_basic_get_set(self):
        """Test basic get and set operations"""
        self.cache.set("key1", "value1")
        self.assertEqual(self.cache.get("key1"), "value1")
        
        self.assertIsNone(self.cache.get("nonexistent"))
    
    def test_ttl_expiration(self):
        """Test that entries expire after TTL"""
        self.cache.set("key1", "value1")
        self.assertEqual(self.cache.get("key1"), "value1")
        
        time.sleep(2.1)
        
        self.assertIsNone(self.cache.get("key1"))
    
    def test_lru_eviction(self):
        """Test LRU eviction when cache is full"""
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")
        self.cache.set("key3", "value3")
        
        self.cache.set("key4", "value4")
        
        self.assertIsNone(self.cache.get("key1"))
        self.assertEqual(self.cache.get("key2"), "value2")
        self.assertEqual(self.cache.get("key3"), "value3")
        self.assertEqual(self.cache.get("key4"), "value4")
    
    def test_lru_access_updates_order(self):
        """Test that accessing an entry updates its LRU position"""
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")
        self.cache.set("key3", "value3")
        
        self.cache.get("key1")
        
        self.cache.set("key4", "value4")
        
        self.assertEqual(self.cache.get("key1"), "value1")
        self.assertIsNone(self.cache.get("key2"))
    
    def test_get_or_fetch_cache_hit(self):
        """Test get_or_fetch with cache hit"""
        self.cache.set("key1", "cached_value")
        
        fetch_called = False
        def fetch_func():
            nonlocal fetch_called
            fetch_called = True
            return "fetched_value"
        
        result = self.cache.get_or_fetch("key1", fetch_func)
        
        self.assertEqual(result, "cached_value")
        self.assertFalse(fetch_called)
    
    def test_get_or_fetch_cache_miss(self):
        """Test get_or_fetch with cache miss"""
        fetch_called = False
        def fetch_func():
            nonlocal fetch_called
            fetch_called = True
            return "fetched_value"
        
        result = self.cache.get_or_fetch("key1", fetch_func)
        
        self.assertEqual(result, "fetched_value")
        self.assertTrue(fetch_called)
        self.assertEqual(self.cache.get("key1"), "fetched_value")
    
    def test_delete(self):
        """Test deleting cache entries"""
        self.cache.set("key1", "value1")
        self.assertEqual(self.cache.get("key1"), "value1")
        
        deleted = self.cache.delete("key1")
        self.assertTrue(deleted)
        self.assertIsNone(self.cache.get("key1"))
        
        deleted_again = self.cache.delete("key1")
        self.assertFalse(deleted_again)
    
    def test_clear(self):
        """Test clearing all cache entries"""
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")
        
        self.cache.clear()
        
        self.assertIsNone(self.cache.get("key1"))
        self.assertIsNone(self.cache.get("key2"))
        stats = self.cache.get_stats()
        self.assertEqual(stats["size"], 0)
    
    def test_statistics_tracking(self):
        """Test cache statistics tracking"""
        self.cache.set("key1", "value1")
        self.cache.get("key1")
        self.cache.get("key1")
        self.cache.get("nonexistent")
        
        stats = self.cache.get_stats()
        
        self.assertEqual(stats["hits"], 2)
        self.assertEqual(stats["misses"], 1)
        self.assertEqual(stats["sets"], 1)
    
    def test_statistics_eviction_count(self):
        """Test that evictions are counted"""
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")
        self.cache.set("key3", "value3")
        self.cache.set("key4", "value4")
        
        stats = self.cache.get_stats()
        self.assertEqual(stats["evictions"], 1)
    
    def test_statistics_hit_rate(self):
        """Test hit rate calculation"""
        self.cache.set("key1", "value1")
        
        self.cache.get("key1")
        self.cache.get("key1")
        self.cache.get("nonexistent")
        
        stats = self.cache.get_stats()
        self.assertEqual(stats["hit_rate"], "66.67%")
    
    def test_reset_stats(self):
        """Test resetting statistics"""
        self.cache.set("key1", "value1")
        self.cache.get("key1")
        
        self.cache.reset_stats()
        
        stats = self.cache.get_stats()
        self.assertEqual(stats["hits"], 0)
        self.assertEqual(stats["misses"], 0)
        self.assertEqual(stats["sets"], 0)
    
    def test_get_cache_singleton(self):
        """Test that get_cache returns same instance for same name"""
        cache1 = get_cache("test_singleton")
        cache2 = get_cache("test_singleton")
        
        self.assertIs(cache1, cache2)
        
        cache1.set("key1", "value1")
        self.assertEqual(cache2.get("key1"), "value1")
    
    def test_different_named_caches(self):
        """Test that different named caches are independent"""
        cache1 = get_cache("cache1")
        cache2 = get_cache("cache2")
        
        cache1.set("key1", "value1")
        cache2.set("key1", "value2")
        
        self.assertEqual(cache1.get("key1"), "value1")
        self.assertEqual(cache2.get("key1"), "value2")


if __name__ == "__main__":
    unittest.main()
