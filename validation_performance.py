"""
Performance optimization and advanced caching for validation system.

This module provides sophisticated caching strategies, performance monitoring,
and optimization techniques to ensure the validation system operates efficiently
even under high load or with large datasets.
"""

import asyncio
import hashlib
import json
import logging
import pickle
import time
import threading
from typing import Dict, Any, Optional, List, Union, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import weakref
import os
import tempfile


class CacheStrategy(Enum):
    """Different caching strategies available."""
    MEMORY_ONLY = "memory_only"       # In-memory cache only
    PERSISTENT = "persistent"         # Disk-based persistent cache
    HYBRID = "hybrid"                 # Memory + disk for best performance
    DISTRIBUTED = "distributed"      # For future multi-instance support


class PerformanceMetric(Enum):
    """Performance metrics tracked."""
    VALIDATION_TIME = "validation_time"
    CACHE_HIT_RATE = "cache_hit_rate"
    MEMORY_USAGE = "memory_usage"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"


@dataclass
class CacheEntry:
    """Enhanced cache entry with metadata."""
    data: Any
    timestamp: float
    access_count: int = 0
    last_access: float = field(default_factory=time.time)
    size_bytes: int = 0
    ttl_override: Optional[float] = None
    
    def is_expired(self, default_ttl: float) -> bool:
        """Check if cache entry is expired."""
        ttl = self.ttl_override if self.ttl_override is not None else default_ttl
        return time.time() - self.timestamp > ttl
    
    def access(self) -> None:
        """Record cache access."""
        self.access_count += 1
        self.last_access = time.time()


@dataclass
class PerformanceStats:
    """Container for performance statistics."""
    start_time: float = field(default_factory=time.time)
    total_operations: int = 0
    successful_operations: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    total_time: float = 0.0
    max_time: float = 0.0
    min_time: float = float('inf')
    error_count: int = 0
    memory_peak: float = 0.0
    
    @property
    def average_time(self) -> float:
        """Calculate average operation time."""
        return self.total_time / max(self.total_operations, 1)
    
    @property
    def cache_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total_requests = self.cache_hits + self.cache_misses
        return self.cache_hits / max(total_requests, 1)
    
    @property
    def success_rate(self) -> float:
        """Calculate operation success rate."""
        return self.successful_operations / max(self.total_operations, 1)
    
    @property
    def throughput(self) -> float:
        """Calculate operations per second."""
        elapsed = time.time() - self.start_time
        return self.total_operations / max(elapsed, 1)


class AdvancedCache:
    """
    Advanced caching system with multiple strategies and optimization features.
    
    Features:
    - Multiple cache strategies (memory, persistent, hybrid)
    - LRU eviction with access frequency consideration
    - Compression for large entries
    - Cache warming and preloading
    - Performance monitoring and optimization
    """
    
    def __init__(
        self,
        strategy: CacheStrategy = CacheStrategy.HYBRID,
        max_memory_size: int = 100 * 1024 * 1024,  # 100MB
        max_entries: int = 10000,
        default_ttl: float = 300,  # 5 minutes
        persistent_dir: Optional[str] = None,
        compression_enabled: bool = True,
        compression_threshold: int = 1024  # Compress entries > 1KB
    ):
        """
        Initialize advanced cache.
        
        Args:
            strategy: Caching strategy to use
            max_memory_size: Maximum memory usage in bytes
            max_entries: Maximum number of cache entries
            default_ttl: Default time-to-live for entries
            persistent_dir: Directory for persistent cache files
            compression_enabled: Whether to compress large entries
            compression_threshold: Size threshold for compression
        """
        self.strategy = strategy
        self.max_memory_size = max_memory_size
        self.max_entries = max_entries
        self.default_ttl = default_ttl
        self.compression_enabled = compression_enabled
        self.compression_threshold = compression_threshold
        
        # Cache storage
        self._memory_cache: Dict[str, CacheEntry] = {}
        self._access_order = deque()  # For LRU tracking
        self._lock = threading.RLock()
        
        # Performance tracking
        self.stats = PerformanceStats()
        
        # Setup persistent storage if needed
        if strategy in [CacheStrategy.PERSISTENT, CacheStrategy.HYBRID]:
            self.persistent_dir = persistent_dir or tempfile.mkdtemp(prefix="validation_cache_")
            os.makedirs(self.persistent_dir, exist_ok=True)
        else:
            self.persistent_dir = None
        
        # Compression support
        if compression_enabled:
            try:
                import lz4.frame
                self.compressor = lz4.frame
            except ImportError:
                try:
                    import gzip
                    self.compressor = gzip
                except ImportError:
                    self.compressor = None
                    self.compression_enabled = False
        
        self.logger = logging.getLogger(__name__)
        
        # Start background maintenance task
        self._maintenance_task = None
        self._start_maintenance()
    
    def _start_maintenance(self) -> None:
        """Start background maintenance task."""
        if self._maintenance_task is None:
            loop = None
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                pass
            
            if loop and loop.is_running():
                self._maintenance_task = loop.create_task(self._maintenance_worker())
    
    async def _maintenance_worker(self) -> None:
        """Background worker for cache maintenance."""
        while True:
            try:
                await asyncio.sleep(60)  # Run every minute
                self._cleanup_expired()
                self._optimize_memory_usage()
                await self._persist_hot_entries()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Cache maintenance error: {e}")
    
    def _generate_cache_key(self, task_data: Dict[str, Any]) -> str:
        """Generate stable cache key from task data."""
        # Create a normalized representation for hashing
        key_components = {
            'scraper_type': task_data.get('scraper_type', 'unknown'),
            'url': task_data.get('url', 'unknown'),
            'data_signature': self._generate_data_signature(task_data.get('scraped_data'))
        }
        
        key_str = json.dumps(key_components, sort_keys=True)
        return hashlib.sha256(key_str.encode()).hexdigest()
    
    def _generate_data_signature(self, scraped_data: Optional[List[Dict]]) -> str:
        """Generate signature for scraped data."""
        if not scraped_data:
            return "no_data"
        
        # Use first few items and total count for signature
        sample_size = min(3, len(scraped_data))
        sample_data = scraped_data[:sample_size]
        
        signature_data = {
            'count': len(scraped_data),
            'sample': sample_data,
            'fields': list(scraped_data[0].keys()) if scraped_data else []
        }
        
        sig_str = json.dumps(signature_data, sort_keys=True, default=str)
        return hashlib.md5(sig_str.encode()).hexdigest()[:16]
    
    def _serialize_entry(self, data: Any) -> bytes:
        """Serialize cache entry data."""
        serialized = pickle.dumps(data)
        
        # Compress if enabled and data is large enough
        if (self.compression_enabled and 
            self.compressor and 
            len(serialized) > self.compression_threshold):
            
            try:
                if hasattr(self.compressor, 'compress'):
                    # lz4 or gzip
                    compressed = self.compressor.compress(serialized)
                    return b'COMPRESSED:' + compressed
                else:
                    return serialized
            except Exception as e:
                self.logger.warning(f"Compression failed: {e}")
        
        return serialized
    
    def _deserialize_entry(self, data: bytes) -> Any:
        """Deserialize cache entry data."""
        if data.startswith(b'COMPRESSED:'):
            # Decompress first
            compressed_data = data[11:]  # Remove 'COMPRESSED:' prefix
            
            try:
                if hasattr(self.compressor, 'decompress'):
                    # lz4 or gzip
                    decompressed = self.compressor.decompress(compressed_data)
                    return pickle.loads(decompressed)
                else:
                    return pickle.loads(compressed_data)
            except Exception as e:
                self.logger.error(f"Decompression failed: {e}")
                raise
        
        return pickle.loads(data)
    
    async def get(self, task_data: Dict[str, Any]) -> Optional[Any]:
        """Get entry from cache."""
        cache_key = self._generate_cache_key(task_data)
        
        with self._lock:
            # Check memory cache first
            if cache_key in self._memory_cache:
                entry = self._memory_cache[cache_key]
                
                if entry.is_expired(self.default_ttl):
                    del self._memory_cache[cache_key]
                    self._remove_from_access_order(cache_key)
                    self.stats.cache_misses += 1
                    return None
                
                entry.access()
                self._update_access_order(cache_key)
                self.stats.cache_hits += 1
                return entry.data
            
            # Check persistent cache if hybrid strategy
            if self.strategy == CacheStrategy.HYBRID and self.persistent_dir:
                persistent_data = await self._load_from_persistent(cache_key)
                if persistent_data:
                    # Load into memory cache
                    await self.set(task_data, persistent_data, promote_to_memory=True)
                    self.stats.cache_hits += 1
                    return persistent_data
            
            self.stats.cache_misses += 1
            return None
    
    async def set(
        self,
        task_data: Dict[str, Any],
        data: Any,
        ttl_override: Optional[float] = None,
        promote_to_memory: bool = False
    ) -> None:
        """Set entry in cache."""
        cache_key = self._generate_cache_key(task_data)
        
        # Serialize and calculate size
        try:
            serialized_data = self._serialize_entry(data)
            size_bytes = len(serialized_data)
        except Exception as e:
            self.logger.error(f"Failed to serialize cache entry: {e}")
            return
        
        # Create cache entry
        entry = CacheEntry(
            data=data,
            timestamp=time.time(),
            size_bytes=size_bytes,
            ttl_override=ttl_override
        )
        
        with self._lock:
            # Memory cache logic
            if (self.strategy in [CacheStrategy.MEMORY_ONLY, CacheStrategy.HYBRID] or 
                promote_to_memory):
                
                # Check if we need to evict entries
                if len(self._memory_cache) >= self.max_entries:
                    self._evict_lru_entries(1)
                
                self._memory_cache[cache_key] = entry
                self._update_access_order(cache_key)
            
            # Persistent cache logic
            if self.strategy in [CacheStrategy.PERSISTENT, CacheStrategy.HYBRID]:
                await self._save_to_persistent(cache_key, data, entry.timestamp)
    
    def _evict_lru_entries(self, count: int) -> None:
        """Evict least recently used entries."""
        evicted = 0
        while evicted < count and self._access_order:
            lru_key = self._access_order.popleft()
            if lru_key in self._memory_cache:
                del self._memory_cache[lru_key]
                evicted += 1
    
    def _update_access_order(self, cache_key: str) -> None:
        """Update access order for LRU tracking."""
        self._remove_from_access_order(cache_key)
        self._access_order.append(cache_key)
    
    def _remove_from_access_order(self, cache_key: str) -> None:
        """Remove key from access order tracking."""
        try:
            self._access_order.remove(cache_key)
        except ValueError:
            pass  # Key not in access order, which is fine
    
    async def _load_from_persistent(self, cache_key: str) -> Optional[Any]:
        """Load entry from persistent storage."""
        if not self.persistent_dir:
            return None
        
        file_path = os.path.join(self.persistent_dir, f"{cache_key}.cache")
        
        try:
            if os.path.exists(file_path):
                # Check file modification time for TTL
                file_mtime = os.path.getmtime(file_path)
                if time.time() - file_mtime > self.default_ttl:
                    os.remove(file_path)
                    return None
                
                with open(file_path, 'rb') as f:
                    data = f.read()
                    return self._deserialize_entry(data)
        except Exception as e:
            self.logger.error(f"Failed to load persistent cache entry {cache_key}: {e}")
        
        return None
    
    async def _save_to_persistent(self, cache_key: str, data: Any, timestamp: float) -> None:
        """Save entry to persistent storage."""
        if not self.persistent_dir:
            return
        
        file_path = os.path.join(self.persistent_dir, f"{cache_key}.cache")
        
        try:
            serialized_data = self._serialize_entry(data)
            
            with open(file_path, 'wb') as f:
                f.write(serialized_data)
            
            # Set file modification time to match cache timestamp
            os.utime(file_path, (timestamp, timestamp))
            
        except Exception as e:
            self.logger.error(f"Failed to save persistent cache entry {cache_key}: {e}")
    
    async def _persist_hot_entries(self) -> None:
        """Persist frequently accessed entries to disk."""
        if (self.strategy != CacheStrategy.HYBRID or 
            not self.persistent_dir or 
            not self._memory_cache):
            return
        
        # Find hot entries (high access count)
        hot_threshold = 3
        hot_entries = [
            (key, entry) for key, entry in self._memory_cache.items()
            if entry.access_count >= hot_threshold
        ]
        
        for cache_key, entry in hot_entries:
            await self._save_to_persistent(cache_key, entry.data, entry.timestamp)
    
    def _cleanup_expired(self) -> None:
        """Clean up expired entries from memory cache."""
        with self._lock:
            current_time = time.time()
            expired_keys = [
                key for key, entry in self._memory_cache.items()
                if entry.is_expired(self.default_ttl)
            ]
            
            for key in expired_keys:
                del self._memory_cache[key]
                self._remove_from_access_order(key)
            
            if expired_keys:
                self.logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    def _optimize_memory_usage(self) -> None:
        """Optimize memory usage by evicting less useful entries."""
        with self._lock:
            current_memory = sum(entry.size_bytes for entry in self._memory_cache.values())
            
            if current_memory > self.max_memory_size:
                # Calculate how many entries to evict based on memory usage
                target_memory = self.max_memory_size * 0.8  # Target 80% of max
                memory_to_free = current_memory - target_memory
                
                # Sort entries by utility (access frequency / size ratio)
                entries_by_utility = sorted(
                    self._memory_cache.items(),
                    key=lambda x: x[1].access_count / max(x[1].size_bytes, 1)
                )
                
                freed_memory = 0
                for key, entry in entries_by_utility:
                    del self._memory_cache[key]
                    self._remove_from_access_order(key)
                    freed_memory += entry.size_bytes
                    
                    if freed_memory >= memory_to_free:
                        break
                
                self.logger.info(f"Freed {freed_memory} bytes of cache memory")
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get comprehensive performance statistics."""
        with self._lock:
            memory_usage = sum(entry.size_bytes for entry in self._memory_cache.values())
            
            return {
                'cache_strategy': self.strategy.value,
                'memory_entries': len(self._memory_cache),
                'memory_usage_bytes': memory_usage,
                'memory_usage_mb': memory_usage / (1024 * 1024),
                'cache_hit_rate': self.stats.cache_hit_rate,
                'total_hits': self.stats.cache_hits,
                'total_misses': self.stats.cache_misses,
                'average_operation_time': self.stats.average_time,
                'throughput': self.stats.throughput,
                'success_rate': self.stats.success_rate,
                'compression_enabled': self.compression_enabled,
                'persistent_dir': self.persistent_dir,
            }
    
    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._memory_cache.clear()
            self._access_order.clear()
        
        # Clear persistent cache if exists
        if self.persistent_dir and os.path.exists(self.persistent_dir):
            try:
                for file in os.listdir(self.persistent_dir):
                    if file.endswith('.cache'):
                        os.remove(os.path.join(self.persistent_dir, file))
            except Exception as e:
                self.logger.error(f"Failed to clear persistent cache: {e}")
        
        self.logger.info("Cache cleared")
    
    def close(self) -> None:
        """Clean up resources."""
        if self._maintenance_task:
            self._maintenance_task.cancel()
        
        # Optional: cleanup persistent directory
        # Note: We don't remove it by default to preserve cache across restarts


class PerformanceMonitor:
    """Monitor and optimize validation performance."""
    
    def __init__(self, window_size: int = 1000):
        """
        Initialize performance monitor.
        
        Args:
            window_size: Size of sliding window for metrics
        """
        self.window_size = window_size
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=window_size))
        self.logger = logging.getLogger(__name__)
        self._lock = threading.Lock()
    
    def record_metric(self, metric: PerformanceMetric, value: float) -> None:
        """Record a performance metric."""
        with self._lock:
            self.metrics[metric.value].append((time.time(), value))
    
    def get_metric_stats(self, metric: PerformanceMetric) -> Dict[str, float]:
        """Get statistics for a metric."""
        with self._lock:
            values = [v for _, v in self.metrics[metric.value]]
            
            if not values:
                return {'count': 0, 'avg': 0, 'min': 0, 'max': 0}
            
            return {
                'count': len(values),
                'avg': sum(values) / len(values),
                'min': min(values),
                'max': max(values),
                'recent': values[-10:] if len(values) >= 10 else values
            }
    
    def analyze_performance(self) -> Dict[str, Any]:
        """Analyze overall performance and provide recommendations."""
        analysis = {}
        
        for metric in PerformanceMetric:
            stats = self.get_metric_stats(metric)
            analysis[metric.value] = stats
        
        # Generate recommendations
        recommendations = []
        
        # Check validation time
        validation_stats = analysis.get('validation_time', {})
        if validation_stats.get('avg', 0) > 5.0:
            recommendations.append("Consider enabling caching to reduce validation times")
        
        # Check cache hit rate
        cache_stats = analysis.get('cache_hit_rate', {})
        if cache_stats.get('avg', 0) < 0.3:
            recommendations.append("Low cache hit rate - consider increasing cache TTL")
        
        # Check error rate
        error_stats = analysis.get('error_rate', {})
        if error_stats.get('avg', 0) > 0.1:
            recommendations.append("High error rate detected - check error handling")
        
        analysis['recommendations'] = recommendations
        return analysis


# Integration helpers
def create_optimized_cache(config: Optional[Any] = None) -> AdvancedCache:
    """Create an optimized cache based on configuration."""
    if not config:
        return AdvancedCache()
    
    cache_config = {
        'strategy': CacheStrategy.HYBRID,
        'max_memory_size': getattr(config, 'cache_max_memory', 100 * 1024 * 1024),
        'max_entries': getattr(config, 'cache_max_entries', 10000),
        'default_ttl': getattr(config, 'cache_ttl', 300),
        'compression_enabled': getattr(config, 'cache_compression', True),
    }
    
    return AdvancedCache(**cache_config)


# Example usage
if __name__ == "__main__":
    async def example_usage():
        """Example of advanced caching and performance monitoring."""
        
        # Create cache and monitor
        cache = AdvancedCache(strategy=CacheStrategy.HYBRID)
        monitor = PerformanceMonitor()
        
        # Example task data
        task_data = {
            'scraper_type': 'playwright',
            'url': 'https://example.com',
            'scraped_data': [
                {'title': 'Test Item', 'price': 10.99},
                {'title': 'Another Item', 'price': 15.50}
            ]
        }
        
        # Test cache operations
        start_time = time.time()
        
        # Cache miss
        result = await cache.get(task_data)
        print(f"Cache miss result: {result}")
        
        # Set cache entry
        validation_result = {'is_successful': True, 'confidence_score': 0.85}
        await cache.set(task_data, validation_result)
        
        # Cache hit
        result = await cache.get(task_data)
        print(f"Cache hit result: {result}")
        
        # Record performance metrics
        validation_time = time.time() - start_time
        monitor.record_metric(PerformanceMetric.VALIDATION_TIME, validation_time)
        monitor.record_metric(PerformanceMetric.CACHE_HIT_RATE, 0.5)
        
        # Show performance stats
        print("\nCache Performance:")
        cache_stats = cache.get_performance_stats()
        for key, value in cache_stats.items():
            print(f"  {key}: {value}")
        
        print("\nPerformance Analysis:")
        analysis = monitor.analyze_performance()
        for metric, stats in analysis.items():
            if metric != 'recommendations':
                print(f"  {metric}: avg={stats.get('avg', 0):.3f}")
        
        print(f"\nRecommendations:")
        for rec in analysis.get('recommendations', []):
            print(f"  - {rec}")
        
        # Cleanup
        cache.close()
    
    asyncio.run(example_usage())