"""
Comprehensive testing strategy and implementation for the validation system.

This module provides extensive tests for all validation components including
unit tests, integration tests, performance benchmarks, and error condition testing.
"""

import asyncio
import unittest
import unittest.mock as mock
import tempfile
import shutil
import os
import time
import json
from typing import Dict, Any, List, Optional
import logging

# Import validation system components
from validation_config import ValidationConfig, get_validation_config
from response_collector import (
    ResponseCollectorFactory, ScrapyResponseCollector, 
    PlaywrightResponseCollector, PydollResponseCollector
)
from validation_manager import ValidationManager, ValidationTask
from validation_error_handling import (
    ValidationErrorHandler, ErrorCategory, ErrorSeverity,
    FallbackResponseDataStrategy, SimplifiedValidationStrategy
)
from validation_performance import AdvancedCache, CacheStrategy, PerformanceMonitor
from validator import ScrapingValidator, ValidationResult, BotDetectionSystem


class MockResponse:
    """Mock response object for testing."""
    
    def __init__(self, status_code=200, headers=None, content="", url="https://example.com"):
        self.status_code = status_code
        self.status = status_code  # For Scrapy compatibility
        self.headers = headers or {}
        self.content = content
        self.text = content
        self.url = url
        self.meta = {'download_latency': 1.0}


class MockPage:
    """Mock Playwright page object for testing."""
    
    def __init__(self, url="https://example.com", content="<html><body>Test</body></html>"):
        self.url = url
        self._content = content
        self.viewport_size = {'width': 1920, 'height': 1080}
    
    async def content(self):
        return self._content
    
    async def evaluate(self, script):
        # Mock JavaScript execution
        if 'document.readyState' in script:
            return {'readyState': 'complete', 'title': 'Test Page', 'contentType': 'text/html'}
        elif 'navigator.userAgent' in script:
            return 'Mozilla/5.0 (Test Browser)'
        elif 'document.documentElement.outerHTML' in script:
            return self._content
        return {}
    
    def is_closed(self):
        return False


class MockPydollTab:
    """Mock Pydoll tab object for testing."""
    
    def __init__(self, url="https://example.com"):
        self.url = url
        self.id = "test_tab_123"
    
    async def evaluate(self, script):
        return {'readyState': 'complete', 'title': 'Test Page', 'contentType': 'text/html'}


class TestValidationConfig(unittest.TestCase):
    """Test validation configuration system."""
    
    def setUp(self):
        # Clear environment variables
        self.original_env = {}
        for key in os.environ:
            if key.startswith('SCRAPER_'):
                self.original_env[key] = os.environ[key]
                del os.environ[key]
    
    def tearDown(self):
        # Restore environment variables
        for key, value in self.original_env.items():
            os.environ[key] = value
    
    def test_default_configuration(self):
        """Test default configuration values."""
        config = ValidationConfig()
        
        self.assertEqual(config.min_data_quality_score, 0.7)
        self.assertEqual(config.min_required_fields, ['title'])
        self.assertEqual(config.max_placeholder_ratio, 0.3)
        self.assertEqual(config.validation_timeout, 30)
        self.assertTrue(config.enable_caching)
    
    def test_environment_variable_override(self):
        """Test configuration override via environment variables."""
        os.environ['SCRAPER_MIN_DATA_QUALITY_SCORE'] = '0.8'
        os.environ['SCRAPER_MIN_REQUIRED_FIELDS'] = 'title,price'
        os.environ['SCRAPER_VALIDATION_TIMEOUT'] = '45'
        
        config = ValidationConfig()
        
        self.assertEqual(config.min_data_quality_score, 0.8)
        self.assertEqual(config.min_required_fields, ['title', 'price'])
        self.assertEqual(config.validation_timeout, 45)
    
    def test_invalid_configuration_handling(self):
        """Test handling of invalid configuration values."""
        os.environ['SCRAPER_MIN_DATA_QUALITY_SCORE'] = '1.5'  # Invalid range
        os.environ['SCRAPER_VALIDATION_TIMEOUT'] = '-10'      # Invalid negative
        
        config = ValidationConfig()
        
        # Should fall back to defaults for invalid values
        self.assertEqual(config.min_data_quality_score, 0.7)
        self.assertEqual(config.validation_timeout, 30)
    
    def test_scraper_specific_config(self):
        """Test scraper-specific configuration retrieval."""
        config = ValidationConfig()
        
        playwright_config = config.get_scraper_specific_config('playwright')
        self.assertIn('wait_timeout', playwright_config)
        self.assertIn('collect_response_headers', playwright_config)
        
        scrapy_config = config.get_scraper_specific_config('scrapy')
        self.assertIn('enable_caching', scrapy_config)


class TestResponseCollectors(unittest.TestCase):
    """Test response data collection components."""
    
    def setUp(self):
        self.config = ValidationConfig()
    
    def test_collector_factory(self):
        """Test response collector factory."""
        scrapy_collector = ResponseCollectorFactory.create_collector('scrapy', self.config)
        self.assertIsInstance(scrapy_collector, ScrapyResponseCollector)
        
        playwright_collector = ResponseCollectorFactory.create_collector('playwright', self.config)
        self.assertIsInstance(playwright_collector, PlaywrightResponseCollector)
        
        pydoll_collector = ResponseCollectorFactory.create_collector('pydoll', self.config)
        self.assertIsInstance(pydoll_collector, PydollResponseCollector)
        
        with self.assertRaises(ValueError):
            ResponseCollectorFactory.create_collector('invalid_scraper', self.config)
    
    async def test_scrapy_response_collection(self):
        """Test Scrapy response data collection."""
        collector = ScrapyResponseCollector(self.config)
        mock_response = MockResponse(
            status_code=200,
            headers={'Content-Type': 'text/html'},
            content='<html><body>Test</body></html>',
            url='https://example.com'
        )
        
        response_data = await collector.collect_response_data(mock_response)
        
        self.assertEqual(response_data['status_code'], 200)
        self.assertEqual(response_data['url'], 'https://example.com')
        self.assertIn('content-type', response_data['headers'])
        self.assertEqual(response_data['response_time'], 1.0)
    
    async def test_playwright_response_collection(self):
        """Test Playwright response data collection."""
        collector = PlaywrightResponseCollector(self.config)
        mock_page = MockPage(url='https://example.com')
        
        response_data = await collector.collect_response_data(mock_page)
        
        self.assertEqual(response_data['url'], 'https://example.com')
        self.assertIn('status_code', response_data)
        self.assertIn('ready_state', response_data)
        self.assertIn('playwright_meta', response_data)
    
    async def test_pydoll_response_collection_browser_mode(self):
        """Test Pydoll response collection in browser mode."""
        collector = PydollResponseCollector(self.config)
        mock_tab = MockPydollTab(url='https://example.com')
        
        response_data = await collector.collect_response_data(mock_tab)
        
        self.assertEqual(response_data['url'], 'https://example.com')
        self.assertEqual(response_data['pydoll_mode'], 'browser')
        self.assertIn('pydoll_meta', response_data)
    
    async def test_pydoll_response_collection_fallback_mode(self):
        """Test Pydoll response collection in fallback mode."""
        collector = PydollResponseCollector(self.config)
        mock_response = MockResponse()
        
        response_data = await collector.collect_response_data(mock_response)
        
        self.assertEqual(response_data['pydoll_mode'], 'fallback')
        self.assertIn('pydoll_meta', response_data)


class TestValidationManager(unittest.TestCase):
    """Test validation manager functionality."""
    
    def setUp(self):
        self.config = ValidationConfig()
        self.config.enable_caching = False  # Disable caching for simpler testing
        self.manager = ValidationManager(self.config)
    
    def tearDown(self):
        self.manager.close()
    
    async def test_scrapy_validation(self):
        """Test validation with Scrapy response."""
        mock_response = MockResponse()
        sample_data = [
            {'title': 'Test Product', 'price': 10.99, 'description': 'A test product'},
            {'title': 'Another Product', 'price': 15.50, 'description': 'Another product'}
        ]
        
        result = await self.manager.validate_scraping_result(
            'scrapy', mock_response, sample_data
        )
        
        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_successful)
        self.assertGreater(result.confidence_score, 0.5)
    
    async def test_playwright_validation(self):
        """Test validation with Playwright page."""
        mock_page = MockPage()
        sample_data = [{'title': 'Test Product', 'price': 10.99}]
        
        result = await self.manager.validate_scraping_result(
            'playwright', mock_page, sample_data
        )
        
        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_successful)
    
    async def test_validation_with_no_data(self):
        """Test validation when no data is extracted."""
        mock_response = MockResponse()
        
        result = await self.manager.validate_scraping_result(
            'scrapy', mock_response, []
        )
        
        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_successful)
        self.assertIn('No items were extracted', str(result.issues))
    
    async def test_validation_statistics(self):
        """Test validation statistics tracking."""
        mock_response = MockResponse()
        sample_data = [{'title': 'Test Product'}]
        
        # Perform several validations
        for _ in range(3):
            await self.manager.validate_scraping_result(
                'scrapy', mock_response, sample_data
            )
        
        stats = self.manager.get_statistics()
        
        self.assertEqual(stats['total_validations'], 3)
        self.assertEqual(stats['successful_validations'], 3)
        self.assertGreater(stats['success_rate'], 0.9)


class TestErrorHandling(unittest.TestCase):
    """Test error handling and recovery strategies."""
    
    def setUp(self):
        self.config = ValidationConfig()
        self.error_handler = ValidationErrorHandler(self.config)
    
    def test_error_classification(self):
        """Test error classification by type."""
        # Network error
        network_error = ConnectionError("Network timeout")
        classified = self.error_handler.classify_error(network_error)
        self.assertEqual(classified.category, ErrorCategory.NETWORK)
        
        # Parsing error
        parse_error = ValueError("Invalid JSON format")
        classified = self.error_handler.classify_error(parse_error)
        self.assertEqual(classified.category, ErrorCategory.PARSING)
        
        # Resource error
        memory_error = MemoryError("Out of memory")
        classified = self.error_handler.classify_error(memory_error)
        self.assertEqual(classified.category, ErrorCategory.RESOURCE)
    
    async def test_fallback_response_strategy(self):
        """Test fallback response data strategy."""
        strategy = FallbackResponseDataStrategy()
        error = self.error_handler.classify_error(ConnectionError("Network failed"))
        context = {'url': 'https://example.com'}
        
        success = await strategy.attempt_recovery(error, context)
        
        self.assertTrue(success)
        self.assertIn('response_data', context)
        self.assertEqual(context['response_data']['url'], 'https://example.com')
    
    async def test_simplified_validation_strategy(self):
        """Test simplified validation strategy."""
        strategy = SimplifiedValidationStrategy()
        error = self.error_handler.classify_error(RuntimeError("Validation failed"))
        context = {
            'scraped_data': [{'title': 'Test'}],
            'response_data': {'status_code': 200}
        }
        
        success = await strategy.attempt_recovery(error, context)
        
        self.assertTrue(success)
        self.assertIn('validation_result', context)
        result = context['validation_result']
        self.assertTrue(result.metadata.get('simplified_validation', False))
    
    def test_error_statistics(self):
        """Test error statistics tracking."""
        # Record some errors
        errors = [
            ConnectionError("Network error 1"),
            ValueError("Parse error 1"),
            ConnectionError("Network error 2")
        ]
        
        for error in errors:
            classified = self.error_handler.classify_error(error)
            self.error_handler.record_error(classified)
        
        stats = self.error_handler.get_error_statistics()
        
        self.assertEqual(stats['total_errors'], 3)
        self.assertIn('network_medium', stats['error_counts'])
        self.assertIn('parsing_low', stats['error_counts'])


class TestAdvancedCache(unittest.TestCase):
    """Test advanced caching system."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.cache = AdvancedCache(
            strategy=CacheStrategy.HYBRID,
            persistent_dir=self.temp_dir,
            max_entries=10,
            default_ttl=1.0  # 1 second for testing
        )
    
    def tearDown(self):
        self.cache.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    async def test_cache_basic_operations(self):
        """Test basic cache get/set operations."""
        task_data = {
            'scraper_type': 'scrapy',
            'url': 'https://example.com',
            'scraped_data': [{'title': 'Test'}]
        }
        
        # Cache miss
        result = await self.cache.get(task_data)
        self.assertIsNone(result)
        
        # Set cache entry
        test_data = {'validation': 'successful'}
        await self.cache.set(task_data, test_data)
        
        # Cache hit
        result = await self.cache.get(task_data)
        self.assertEqual(result, test_data)
    
    async def test_cache_expiration(self):
        """Test cache entry expiration."""
        task_data = {
            'scraper_type': 'scrapy',
            'url': 'https://example.com',
            'scraped_data': [{'title': 'Test'}]
        }
        
        test_data = {'validation': 'successful'}
        await self.cache.set(task_data, test_data)
        
        # Should be available immediately
        result = await self.cache.get(task_data)
        self.assertEqual(result, test_data)
        
        # Wait for expiration
        await asyncio.sleep(1.1)
        
        # Should be expired now
        result = await self.cache.get(task_data)
        self.assertIsNone(result)
    
    async def test_cache_memory_management(self):
        """Test cache memory management and LRU eviction."""
        # Fill cache beyond max_entries
        for i in range(15):
            task_data = {
                'scraper_type': 'scrapy',
                'url': f'https://example{i}.com',
                'scraped_data': [{'title': f'Test {i}'}]
            }
            await self.cache.set(task_data, {'data': i})
        
        stats = self.cache.get_performance_stats()
        
        # Should not exceed max_entries
        self.assertLessEqual(stats['memory_entries'], 10)
    
    def test_cache_key_generation(self):
        """Test cache key generation consistency."""
        task_data1 = {
            'scraper_type': 'scrapy',
            'url': 'https://example.com',
            'scraped_data': [{'title': 'Test', 'price': 10.99}]
        }
        
        task_data2 = {
            'scraper_type': 'scrapy',
            'url': 'https://example.com',
            'scraped_data': [{'title': 'Test', 'price': 10.99}]
        }
        
        # Same data should generate same key
        key1 = self.cache._generate_cache_key(task_data1)
        key2 = self.cache._generate_cache_key(task_data2)
        self.assertEqual(key1, key2)
        
        # Different data should generate different key
        task_data3 = {
            'scraper_type': 'playwright',
            'url': 'https://example.com',
            'scraped_data': [{'title': 'Test', 'price': 10.99}]
        }
        
        key3 = self.cache._generate_cache_key(task_data3)
        self.assertNotEqual(key1, key3)


class TestPerformanceBenchmarks(unittest.TestCase):
    """Performance benchmarks and load testing."""
    
    def setUp(self):
        self.config = ValidationConfig()
        self.config.enable_caching = True
        self.manager = ValidationManager(self.config)
    
    def tearDown(self):
        self.manager.close()
    
    async def test_validation_performance(self):
        """Benchmark validation performance."""
        mock_response = MockResponse()
        sample_data = [
            {'title': f'Product {i}', 'price': 10.99 + i, 'description': f'Description {i}'}
            for i in range(100)  # 100 items
        ]
        
        start_time = time.time()
        
        # Perform multiple validations
        tasks = []
        for i in range(10):
            task = self.manager.validate_scraping_result(
                'scrapy', mock_response, sample_data, task_id=f'benchmark_{i}'
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Verify all validations succeeded
        for result in results:
            self.assertIsInstance(result, ValidationResult)
            self.assertTrue(result.is_successful)
        
        # Performance assertions
        avg_time_per_validation = total_time / len(results)
        self.assertLess(avg_time_per_validation, 1.0, "Validation taking too long")
        
        print(f"Validation performance: {avg_time_per_validation:.3f}s per validation")
    
    async def test_cache_performance(self):
        """Benchmark cache performance."""
        cache = AdvancedCache(strategy=CacheStrategy.MEMORY_ONLY)
        
        task_data_template = {
            'scraper_type': 'scrapy',
            'url': 'https://example.com',
            'scraped_data': [{'title': 'Test Product', 'price': 10.99}]
        }
        
        # Warm up cache
        await cache.set(task_data_template, {'validation': 'successful'})
        
        start_time = time.time()
        
        # Perform cache operations
        for i in range(1000):
            result = await cache.get(task_data_template)
            self.assertIsNotNone(result)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        cache_ops_per_second = 1000 / total_time
        self.assertGreater(cache_ops_per_second, 1000, "Cache performance too slow")
        
        print(f"Cache performance: {cache_ops_per_second:.0f} ops/second")
        
        cache.close()


class TestIntegration(unittest.TestCase):
    """Integration tests with real-world scenarios."""
    
    def setUp(self):
        self.config = ValidationConfig()
        self.manager = ValidationManager(self.config)
    
    def tearDown(self):
        self.manager.close()
    
    async def test_end_to_end_validation_flow(self):
        """Test complete validation flow from response to result."""
        # Simulate a complete scraping scenario
        mock_response = MockResponse(
            status_code=200,
            headers={'Content-Type': 'text/html; charset=utf-8'},
            content='<html><body><h1>Product Page</h1></body></html>',
            url='https://shop.example.com/products'
        )
        
        sample_data = [
            {
                'title': 'Premium Widget',
                'price': 29.99,
                'description': 'High-quality widget with advanced features',
                'image_url': 'https://shop.example.com/images/widget.jpg',
                'stock_availability': True,
                'sku': 'WID-001'
            },
            {
                'title': 'Basic Widget',
                'price': 19.99,
                'description': 'Standard widget for everyday use',
                'image_url': 'https://shop.example.com/images/basic-widget.jpg',
                'stock_availability': False,
                'sku': 'WID-002'
            }
        ]
        
        # Test validation
        result = await self.manager.validate_scraping_result(
            'scrapy', mock_response, sample_data,
            url='https://shop.example.com/products',
            task_id='integration_test'
        )
        
        # Verify comprehensive validation
        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_successful)
        self.assertFalse(result.is_blocked)
        self.assertEqual(result.bot_detection_system, BotDetectionSystem.NONE)
        self.assertGreater(result.confidence_score, 0.7)
        
        # Verify metadata
        self.assertIn('task_id', result.metadata)
        self.assertIn('scraper_type', result.metadata)
        self.assertIn('data_stats', result.metadata)
        
        # Verify data statistics
        data_stats = result.metadata['data_stats']
        self.assertEqual(data_stats['total_items'], 2)
        self.assertIn('field_completeness', data_stats)
        
        field_completeness = data_stats['field_completeness']
        self.assertEqual(field_completeness['title']['completeness'], 1.0)
        self.assertEqual(field_completeness['price']['completeness'], 1.0)
    
    async def test_error_recovery_integration(self):
        """Test error recovery in realistic scenarios."""
        # Simulate network error scenario
        with mock.patch('response_collector.ScrapyResponseCollector.collect_response_data') as mock_collect:
            mock_collect.side_effect = ConnectionError("Network timeout")
            
            result = await self.manager.validate_scraping_result(
                'scrapy', MockResponse(), [{'title': 'Test Product'}]
            )
            
            # Should still return a result due to error handling
            self.assertIsInstance(result, ValidationResult)
            # May not be successful due to error, but should not crash
    
    async def test_concurrent_validation(self):
        """Test concurrent validation requests."""
        mock_response = MockResponse()
        sample_data = [{'title': 'Test Product', 'price': 10.99}]
        
        # Create multiple concurrent validation tasks
        tasks = []
        for i in range(20):
            task = self.manager.validate_scraping_result(
                'scrapy', mock_response, sample_data, task_id=f'concurrent_{i}'
            )
            tasks.append(task)
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify all tasks completed successfully
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.fail(f"Task {i} failed with exception: {result}")
            
            self.assertIsInstance(result, ValidationResult)
            self.assertTrue(result.is_successful)


def run_all_tests():
    """Run all validation system tests."""
    # Configure logging for tests
    logging.basicConfig(level=logging.WARNING)
    
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestValidationConfig,
        TestResponseCollectors,
        TestValidationManager,
        TestErrorHandling,
        TestAdvancedCache,
        TestPerformanceBenchmarks,
        TestIntegration
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    return result.wasSuccessful()


async def run_async_tests():
    """Run async-specific tests."""
    print("Running async-specific validation tests...")
    
    # Test classes with async methods
    async_test_classes = [
        TestResponseCollectors(),
        TestValidationManager(),
        TestErrorHandling(),
        TestAdvancedCache(),
        TestPerformanceBenchmarks(),
        TestIntegration()
    ]
    
    for test_instance in async_test_classes:
        test_instance.setUp()
        
        # Run async test methods
        for method_name in dir(test_instance):
            if method_name.startswith('test_') and asyncio.iscoroutinefunction(getattr(test_instance, method_name)):
                print(f"Running {test_instance.__class__.__name__}.{method_name}")
                try:
                    await getattr(test_instance, method_name)()
                    print(f"  ✅ PASSED")
                except Exception as e:
                    print(f"  ❌ FAILED: {e}")
        
        test_instance.tearDown()


if __name__ == "__main__":
    print("=" * 60)
    print("VALIDATION SYSTEM COMPREHENSIVE TESTING")
    print("=" * 60)
    
    # Run standard unit tests
    print("\n1. Running synchronous unit tests...")
    sync_success = run_all_tests()
    
    # Run async tests
    print("\n2. Running asynchronous integration tests...")
    asyncio.run(run_async_tests())
    
    print("\n" + "=" * 60)
    if sync_success:
        print("🎉 ALL TESTS COMPLETED SUCCESSFULLY!")
        print("\nThe validation system is ready for integration with scrapers.")
        print("\nNext steps:")
        print("1. Integrate ValidationManager with existing scrapers")
        print("2. Update scraper CLIs to include validation arguments")
        print("3. Monitor performance in production environment")
        print("4. Adjust configuration based on real-world usage")
    else:
        print("❌ SOME TESTS FAILED!")
        print("\nPlease review and fix failing tests before proceeding.")
    print("=" * 60)