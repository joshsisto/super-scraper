"""
Unified validation management for the Super Scraper Suite.

This module provides a centralized ValidationManager that handles validation
across all scraper types with consistent interfaces, comprehensive error handling,
and performance optimizations.
"""

import asyncio
import logging
import time
import hashlib
import json
from typing import Dict, Any, Optional, List, Union, Tuple
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import threading

# Import validation components
from validator import ScrapingValidator, ValidationResult, BotDetectionSystem, BlockType
from response_collector import ResponseCollectorFactory, ResponseCollector
from validation_config import ValidationConfig, get_validation_config


@dataclass
class ValidationTask:
    """Container for validation task data."""
    scraper_type: str
    response_source: Any
    scraped_data: Optional[List[Dict]] = None
    csv_file_path: Optional[str] = None
    url: Optional[str] = None
    task_id: Optional[str] = None


class ValidationCache:
    """Simple in-memory cache for validation results."""
    
    def __init__(self, ttl: int = 300, max_size: int = 1000):
        """
        Initialize validation cache.
        
        Args:
            ttl: Time-to-live for cache entries in seconds
            max_size: Maximum number of entries to keep in cache
        """
        self.ttl = ttl
        self.max_size = max_size
        self._cache: Dict[str, Tuple[float, ValidationResult]] = {}
        self._lock = threading.RLock()
        self.logger = logging.getLogger(f"{__name__}.ValidationCache")
    
    def _generate_cache_key(self, task: ValidationTask) -> str:
        """Generate cache key for validation task."""
        # Create a hash of the key components
        key_data = {
            'scraper_type': task.scraper_type,
            'url': task.url or 'unknown',
            'data_count': len(task.scraped_data) if task.scraped_data else 0,
        }
        
        # Add data hash if we have scraped data
        if task.scraped_data:
            # Create a simple hash of the first few items for caching
            sample_data = task.scraped_data[:5]  # Use first 5 items for hash
            data_str = json.dumps(sample_data, sort_keys=True, default=str)
            key_data['data_hash'] = hashlib.md5(data_str.encode()).hexdigest()[:8]
        
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def get(self, task: ValidationTask) -> Optional[ValidationResult]:
        """Get cached validation result if available and not expired."""
        cache_key = self._generate_cache_key(task)
        
        with self._lock:
            if cache_key not in self._cache:
                return None
            
            timestamp, result = self._cache[cache_key]
            
            # Check if expired
            if time.time() - timestamp > self.ttl:
                del self._cache[cache_key]
                self.logger.debug(f"Cache entry expired for key: {cache_key[:8]}...")
                return None
            
            self.logger.debug(f"Cache hit for key: {cache_key[:8]}...")
            return result
    
    def set(self, task: ValidationTask, result: ValidationResult) -> None:
        """Store validation result in cache."""
        cache_key = self._generate_cache_key(task)
        
        with self._lock:
            # Clean up old entries if cache is full
            if len(self._cache) >= self.max_size:
                self._cleanup_expired()
                
                # If still full, remove oldest entries
                if len(self._cache) >= self.max_size:
                    oldest_keys = sorted(
                        self._cache.keys(),
                        key=lambda k: self._cache[k][0]
                    )[:self.max_size // 4]  # Remove 25% of entries
                    
                    for key in oldest_keys:
                        del self._cache[key]
                    
                    self.logger.debug(f"Removed {len(oldest_keys)} old cache entries")
            
            self._cache[cache_key] = (time.time(), result)
            self.logger.debug(f"Cached result for key: {cache_key[:8]}...")
    
    def _cleanup_expired(self) -> None:
        """Remove expired entries from cache."""
        current_time = time.time()
        expired_keys = [
            key for key, (timestamp, _) in self._cache.items()
            if current_time - timestamp > self.ttl
        ]
        
        for key in expired_keys:
            del self._cache[key]
        
        if expired_keys:
            self.logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
            self.logger.debug("Cache cleared")
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            current_time = time.time()
            active_entries = sum(
                1 for timestamp, _ in self._cache.values()
                if current_time - timestamp <= self.ttl
            )
            
            return {
                'total_entries': len(self._cache),
                'active_entries': active_entries,
                'expired_entries': len(self._cache) - active_entries,
                'max_size': self.max_size,
                'ttl': self.ttl,
            }


class ValidationManager:
    """
    Unified validation manager for all scraper types.
    
    This class provides a consistent interface for validation across Scrapy,
    Playwright, and Pydoll scrapers while handling the unique characteristics
    of each scraping approach.
    """
    
    def __init__(self, config: Optional[ValidationConfig] = None):
        """
        Initialize validation manager.
        
        Args:
            config: ValidationConfig instance or None for defaults
        """
        self.config = config or get_validation_config()
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.validator = ScrapingValidator(self.logger, self.config)
        self.cache = ValidationCache(
            ttl=getattr(self.config, 'cache_ttl', 300),
            max_size=1000
        ) if getattr(self.config, 'enable_caching', True) else None
        
        # Thread pool for async operations
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="validation")
        
        # Statistics tracking
        self._stats = {
            'total_validations': 0,
            'successful_validations': 0,
            'blocked_validations': 0,
            'cached_validations': 0,
            'error_validations': 0,
            'validation_times': [],
        }
        self._stats_lock = threading.Lock()
    
    async def validate_scraping_result(
        self,
        scraper_type: str,
        response_source: Any,
        scraped_data: Optional[List[Dict]] = None,
        csv_file_path: Optional[str] = None,
        url: Optional[str] = None,
        task_id: Optional[str] = None
    ) -> ValidationResult:
        """
        Validate scraping results with unified interface.
        
        Args:
            scraper_type: Type of scraper ('scrapy', 'playwright', 'pydoll')
            response_source: Scraper-specific response object
            scraped_data: Optional list of scraped items
            csv_file_path: Optional path to CSV file with scraped data
            url: Optional URL override
            task_id: Optional task identifier for logging
            
        Returns:
            ValidationResult with comprehensive analysis
        """
        start_time = time.time()
        task = ValidationTask(
            scraper_type=scraper_type,
            response_source=response_source,
            scraped_data=scraped_data,
            csv_file_path=csv_file_path,
            url=url,
            task_id=task_id
        )
        
        try:
            self.logger.info(f"Starting validation for {scraper_type} scraper" +
                           (f" (task: {task_id})" if task_id else ""))
            
            # Check cache first
            if self.cache and getattr(self.config, 'enable_caching', True):
                cached_result = self.cache.get(task)
                if cached_result:
                    self._update_stats('cached_validations', time.time() - start_time)
                    self.logger.debug("Returning cached validation result")
                    return cached_result
            
            # Collect response data
            response_data = await self._collect_response_data(task)
            
            # Perform validation
            result = await self._perform_validation(response_data, task)
            
            # Cache the result
            if self.cache and result:
                self.cache.set(task, result)
            
            # Update statistics
            self._update_stats('successful_validations' if result.is_successful else 'blocked_validations',
                             time.time() - start_time)
            
            # Log summary
            self._log_validation_summary(result, scraper_type, task_id)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Validation failed for {scraper_type}: {str(e)}", exc_info=True)
            self._update_stats('error_validations', time.time() - start_time)
            
            # Return a failed validation result
            return self._create_error_result(str(e), url or 'unknown')
    
    async def _collect_response_data(self, task: ValidationTask) -> Dict[str, Any]:
        """Collect response data using appropriate collector."""
        try:
            # Create response collector
            collector = ResponseCollectorFactory.create_collector(
                task.scraper_type,
                self.config
            )
            
            # Collect response data with timeout
            response_data = await asyncio.wait_for(
                collector.collect_response_data(task.response_source, task.url),
                timeout=getattr(self.config, 'validation_timeout', 30)
            )
            
            self.logger.debug(f"Collected response data: {response_data.get('status_code', 'unknown')} "
                            f"from {response_data.get('url', 'unknown')}")
            
            return response_data
            
        except asyncio.TimeoutError:
            self.logger.error(f"Response data collection timed out for {task.scraper_type}")
            return self._create_fallback_response_data(task.url)
        except Exception as e:
            self.logger.error(f"Error collecting response data: {str(e)}")
            return self._create_fallback_response_data(task.url)
    
    async def _perform_validation(self, response_data: Dict[str, Any], task: ValidationTask) -> ValidationResult:
        """Perform the actual validation using ScrapingValidator."""
        try:
            # Run validation in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor,
                self.validator.validate_scraping_result,
                response_data,
                task.scraped_data,
                task.csv_file_path
            )
            
            # Add task metadata to result
            if hasattr(result, 'metadata'):
                result.metadata['task_id'] = task.task_id
                result.metadata['scraper_type'] = task.scraper_type
                result.metadata['validation_timestamp'] = time.time()
            
            return result
            
        except Exception as e:
            self.logger.error(f"Validation execution failed: {str(e)}")
            return self._create_error_result(str(e), response_data.get('url', 'unknown'))
    
    def _create_fallback_response_data(self, url: Optional[str]) -> Dict[str, Any]:
        """Create minimal response data for fallback cases."""
        return {
            'url': url or 'unknown',
            'status_code': 0,
            'headers': {},
            'content': '',
            'response_time': 0.0,
            'timestamp': time.time(),
            'collector_type': 'fallback'
        }
    
    def _create_error_result(self, error_message: str, url: str) -> ValidationResult:
        """Create a ValidationResult for error cases."""
        return ValidationResult(
            is_successful=False,
            is_blocked=False,
            bot_detection_system=BotDetectionSystem.NONE,
            confidence_score=0.0,
            issues=[f"Validation error: {error_message}"],
            warnings=[],
            metadata={'error': True, 'url': url, 'timestamp': time.time()}
        )
    
    def _update_stats(self, stat_type: str, validation_time: float) -> None:
        """Update validation statistics."""
        with self._stats_lock:
            self._stats['total_validations'] += 1
            self._stats[stat_type] += 1
            self._stats['validation_times'].append(validation_time)
            
            # Keep only recent validation times (last 100)
            if len(self._stats['validation_times']) > 100:
                self._stats['validation_times'] = self._stats['validation_times'][-100:]
    
    def _log_validation_summary(self, result: ValidationResult, scraper_type: str, task_id: Optional[str]) -> None:
        """Log a summary of the validation result."""
        if not getattr(self.config, 'enable_detailed_reports', True):
            return
        
        summary = self.validator.get_validation_summary(result)
        log_prefix = f"[{scraper_type.upper()}]" + (f"[{task_id}]" if task_id else "")
        
        if result.is_successful:
            self.logger.info(f"{log_prefix} ✅ {summary}")
        elif result.is_blocked:
            self.logger.warning(f"{log_prefix} 🚫 {summary}")
        else:
            self.logger.warning(f"{log_prefix} ❌ {summary}")
        
        # Log issues and warnings if present
        if result.issues:
            for issue in result.issues:
                self.logger.warning(f"{log_prefix} Issue: {issue}")
        
        if result.warnings:
            for warning in result.warnings:
                self.logger.info(f"{log_prefix} Warning: {warning}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get validation manager statistics."""
        with self._stats_lock:
            stats = self._stats.copy()
            
            # Calculate derived statistics
            if stats['validation_times']:
                avg_time = sum(stats['validation_times']) / len(stats['validation_times'])
                max_time = max(stats['validation_times'])
                min_time = min(stats['validation_times'])
            else:
                avg_time = max_time = min_time = 0.0
            
            stats['average_validation_time'] = avg_time
            stats['max_validation_time'] = max_time
            stats['min_validation_time'] = min_time
            
            # Calculate success rates
            total = stats['total_validations']
            if total > 0:
                stats['success_rate'] = stats['successful_validations'] / total
                stats['block_rate'] = stats['blocked_validations'] / total
                stats['error_rate'] = stats['error_validations'] / total
                stats['cache_hit_rate'] = stats['cached_validations'] / total
            else:
                stats['success_rate'] = stats['block_rate'] = stats['error_rate'] = stats['cache_hit_rate'] = 0.0
            
            # Add cache statistics if available
            if self.cache:
                stats['cache_stats'] = self.cache.stats()
            
            return stats
    
    def reset_statistics(self) -> None:
        """Reset all validation statistics."""
        with self._stats_lock:
            self._stats = {
                'total_validations': 0,
                'successful_validations': 0,
                'blocked_validations': 0,
                'cached_validations': 0,
                'error_validations': 0,
                'validation_times': [],
            }
        
        if self.cache:
            self.cache.clear()
        
        self.logger.info("Validation statistics reset")
    
    def close(self) -> None:
        """Clean up resources."""
        if self.executor:
            self.executor.shutdown(wait=True)
        
        if self.cache:
            self.cache.clear()
        
        self.logger.info("ValidationManager closed")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Convenience functions for easy integration
async def validate_scrapy_result(
    response: Any,
    scraped_data: Optional[List[Dict]] = None,
    csv_file_path: Optional[str] = None,
    config: Optional[ValidationConfig] = None
) -> ValidationResult:
    """Convenience function for validating Scrapy results."""
    manager = ValidationManager(config)
    try:
        return await manager.validate_scraping_result(
            'scrapy', response, scraped_data, csv_file_path
        )
    finally:
        manager.close()


async def validate_playwright_result(
    page: Any,
    scraped_data: Optional[List[Dict]] = None,
    csv_file_path: Optional[str] = None,
    config: Optional[ValidationConfig] = None
) -> ValidationResult:
    """Convenience function for validating Playwright results."""
    manager = ValidationManager(config)
    try:
        return await manager.validate_scraping_result(
            'playwright', page, scraped_data, csv_file_path
        )
    finally:
        manager.close()


async def validate_pydoll_result(
    source: Any,
    scraped_data: Optional[List[Dict]] = None,
    csv_file_path: Optional[str] = None,
    config: Optional[ValidationConfig] = None
) -> ValidationResult:
    """Convenience function for validating Pydoll results."""
    manager = ValidationManager(config)
    try:
        return await manager.validate_scraping_result(
            'pydoll', source, scraped_data, csv_file_path
        )
    finally:
        manager.close()


# Example usage
if __name__ == "__main__":
    async def example_usage():
        """Example of how to use the ValidationManager."""
        from validation_config import ValidationConfig
        
        # Create configuration
        config = ValidationConfig()
        
        # Create validation manager
        with ValidationManager(config) as manager:
            # Example validation task
            sample_response_data = {
                'url': 'https://example.com',
                'status_code': 200,
                'headers': {'content-type': 'text/html'},
                'content': '<html><body>Sample</body></html>'
            }
            
            sample_data = [
                {'title': 'Test Product', 'price': 10.99, 'description': 'A test product'},
                {'title': 'Another Product', 'price': 15.50, 'description': 'Another test product'}
            ]
            
            # This would normally be a real response object
            print("Example validation manager created successfully")
            print("Configuration:")
            for key, value in config.to_dict().items():
                print(f"  {key}: {value}")
            
            print("\nStatistics:")
            stats = manager.get_statistics()
            for key, value in stats.items():
                if key != 'validation_times':  # Skip the list for cleaner output
                    print(f"  {key}: {value}")
    
    asyncio.run(example_usage())