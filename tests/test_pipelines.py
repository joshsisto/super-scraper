"""
Unit tests for the Scrapy pipelines.

Tests data validation, cleaning, duplicate filtering, and database integration functionality.
"""

import unittest
import tempfile
import os
from unittest.mock import Mock, MagicMock, patch
from scrapy.exceptions import DropItem
from super_scraper.pipelines import DataValidationPipeline, DuplicateFilterPipeline, SQLitePipeline
from super_scraper.items import SuperScraperItem


class TestDataValidationPipeline(unittest.TestCase):
    """Test cases for the DataValidationPipeline."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.pipeline = DataValidationPipeline()
        self.spider = Mock()
        self.spider.logger = Mock()
    
    def test_valid_item_processing(self):
        """Test processing of a valid item."""
        item = SuperScraperItem({
            'title': 'Test Product',
            'price': '19.99',
            'description': 'A test product description',
            'image_url': 'https://example.com/image.jpg',
            'stock_availability': 'In stock',
            'sku': 'TEST-123'
        })
        
        processed_item = self.pipeline.process_item(item, self.spider)
        
        self.assertEqual(processed_item['title'], 'Test Product')
        self.assertEqual(processed_item['price'], 19.99)
        self.assertEqual(processed_item['stock_availability'], True)
        self.assertEqual(self.pipeline.stats['valid_items'], 1)
    
    def test_missing_title_drops_item(self):
        """Test that items without title are dropped."""
        item = SuperScraperItem({
            'price': '19.99',
            'description': 'No title item'
        })
        
        with self.assertRaises(DropItem):
            self.pipeline.process_item(item, self.spider)
        
        self.assertEqual(self.pipeline.stats['dropped_items'], 1)
    
    def test_clean_title(self):
        """Test title cleaning functionality."""
        test_cases = [
            ('  Test  Product  ', 'Test Product'),
            ('Test\nProduct', 'Test Product'),
            ('Test"Product"', "Test'Product'"),
            ('A' * 250, 'A' * 200),  # Length limit
        ]
        
        for input_title, expected_title in test_cases:
            item = SuperScraperItem({'title': input_title})
            self.pipeline.process_item(item, self.spider)
            self.assertEqual(item['title'], expected_title)
    
    def test_clean_price_various_formats(self):
        """Test price cleaning with various formats."""
        test_cases = [
            ('19.99', 19.99),
            ('$19.99', 19.99),
            ('1,299.99', 1299.99),
            (-10, None),  # Negative price
            ('invalid', None),
            (None, None),
        ]
        
        for input_price, expected_price in test_cases:
            item = SuperScraperItem({
                'title': 'Test',
                'price': input_price
            })
            processed = self.pipeline.process_item(item, self.spider)
            self.assertEqual(processed.get('price'), expected_price)
    
    def test_validate_image_url(self):
        """Test image URL validation."""
        test_cases = [
            ('https://example.com/image.jpg', 'https://example.com/image.jpg'),
            ('http://example.com/image.jpg', 'http://example.com/image.jpg'),
            ('//example.com/image.jpg', '//example.com/image.jpg'),
            ('invalid-url', None),
            ('/relative/path.jpg', None),
        ]
        
        for input_url, expected_url in test_cases:
            item = SuperScraperItem({
                'title': 'Test',
                'image_url': input_url
            })
            processed = self.pipeline.process_item(item, self.spider)
            self.assertEqual(processed.get('image_url'), expected_url)
    
    def test_normalize_stock_availability(self):
        """Test stock availability normalization."""
        test_cases = [
            ('yes', True),
            ('in stock', True),
            ('available', True),
            ('no', False),
            ('out of stock', False),
            ('sold out', False),
            ('maybe', None),
            (1, True),
            (0, False),
        ]
        
        for input_stock, expected_stock in test_cases:
            item = SuperScraperItem({
                'title': 'Test',
                'stock_availability': input_stock
            })
            processed = self.pipeline.process_item(item, self.spider)
            self.assertEqual(processed.get('stock_availability'), expected_stock)
    
    def test_clean_sku(self):
        """Test SKU cleaning."""
        test_cases = [
            ('TEST-123', 'TEST-123'),
            ('  TEST-123  ', 'TEST-123'),
            ('TEST@#$123', 'TEST123'),
            ('A' * 60, 'A' * 50),  # Length limit
        ]
        
        for input_sku, expected_sku in test_cases:
            item = SuperScraperItem({
                'title': 'Test',
                'sku': input_sku
            })
            processed = self.pipeline.process_item(item, self.spider)
            self.assertEqual(processed.get('sku'), expected_sku)
    
    def test_statistics_tracking(self):
        """Test that statistics are properly tracked."""
        # Process some valid items
        for i in range(3):
            item = SuperScraperItem({
                'title': f'Product {i}',
                'price': '10.00'
            })
            self.pipeline.process_item(item, self.spider)
        
        # Try to process invalid item
        try:
            invalid_item = SuperScraperItem({'price': '10.00'})
            self.pipeline.process_item(invalid_item, self.spider)
        except DropItem:
            pass
        
        self.assertEqual(self.pipeline.stats['valid_items'], 3)
        self.assertEqual(self.pipeline.stats['dropped_items'], 1)


class TestDuplicateFilterPipeline(unittest.TestCase):
    """Test cases for the DuplicateFilterPipeline."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.pipeline = DuplicateFilterPipeline()
        self.spider = Mock()
    
    def test_unique_items_pass_through(self):
        """Test that unique items pass through the pipeline."""
        items = [
            SuperScraperItem({'title': 'Product 1', 'price': 10.00}),
            SuperScraperItem({'title': 'Product 2', 'price': 20.00}),
            SuperScraperItem({'title': 'Product 3', 'price': 10.00}),
        ]
        
        for item in items:
            result = self.pipeline.process_item(item, self.spider)
            self.assertEqual(result, item)
        
        self.assertEqual(len(self.pipeline.seen_items), 3)
        self.assertEqual(self.pipeline.duplicates_count, 0)
    
    def test_duplicate_items_are_dropped(self):
        """Test that duplicate items are dropped."""
        item1 = SuperScraperItem({'title': 'Product 1', 'price': 10.00})
        item2 = SuperScraperItem({'title': 'Product 1', 'price': 10.00})
        
        # First item should pass
        result1 = self.pipeline.process_item(item1, self.spider)
        self.assertEqual(result1, item1)
        
        # Duplicate should be dropped
        with self.assertRaises(DropItem):
            self.pipeline.process_item(item2, self.spider)
        
        self.assertEqual(self.pipeline.duplicates_count, 1)
    
    def test_same_title_different_price_not_duplicate(self):
        """Test that items with same title but different price are not duplicates."""
        item1 = SuperScraperItem({'title': 'Product 1', 'price': 10.00})
        item2 = SuperScraperItem({'title': 'Product 1', 'price': 15.00})
        
        result1 = self.pipeline.process_item(item1, self.spider)
        result2 = self.pipeline.process_item(item2, self.spider)
        
        self.assertEqual(result1, item1)
        self.assertEqual(result2, item2)
        self.assertEqual(len(self.pipeline.seen_items), 2)
    
    def test_missing_fields_handling(self):
        """Test handling of items with missing fields."""
        item1 = SuperScraperItem({'title': 'Product 1'})
        item2 = SuperScraperItem({'price': 10.00})
        
        # Both should pass as they have different identifiers
        result1 = self.pipeline.process_item(item1, self.spider)
        result2 = self.pipeline.process_item(item2, self.spider)
        
        self.assertEqual(result1, item1)
        self.assertEqual(result2, item2)


class TestSQLitePipeline(unittest.TestCase):
    """Test cases for the SQLitePipeline."""
    
    def setUp(self):
        """Set up test fixtures with temporary database."""
        self.pipeline = SQLitePipeline()
        self.spider = Mock()
        self.spider.start_urls = ['https://example.com']
        
        # Create temporary database for testing
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db.close()
        
        # Mock database module to use temp database
        self.database_patcher = patch('super_scraper.pipelines.database')
        self.mock_database = self.database_patcher.start()
        self.mock_database.DB_PATH = self.temp_db.name
        self.mock_database.init_db.return_value = None
        self.mock_database.save_items.return_value = 2  # Mock successful save
    
    def tearDown(self):
        """Clean up test fixtures."""
        self.database_patcher.stop()
        
        # Remove temporary database
        try:
            os.unlink(self.temp_db.name)
        except FileNotFoundError:
            pass
    
    def test_pipeline_initialization(self):
        """Test that pipeline initializes correctly."""
        # Mock successful database initialization
        self.mock_database.init_db.side_effect = None
        
        pipeline = SQLitePipeline()
        
        self.mock_database.init_db.assert_called_once()
        self.assertTrue(pipeline.database_available)
    
    def test_pipeline_initialization_failure(self):
        """Test handling of database initialization failure."""
        # Mock database initialization failure
        self.mock_database.init_db.side_effect = Exception("Database error")
        
        pipeline = SQLitePipeline()
        
        self.assertFalse(pipeline.database_available)
    
    def test_open_spider(self):
        """Test spider opening functionality."""
        self.pipeline.open_spider(self.spider)
        
        self.assertIsNotNone(self.pipeline.scrape_job_id)
        self.assertIn('example.com', self.pipeline.scrape_job_id)
        self.assertEqual(self.pipeline.target_url, 'https://example.com')
    
    def test_process_item(self):
        """Test item processing and collection."""
        self.pipeline.database_available = True
        
        item = SuperScraperItem({
            'title': 'Test Product',
            'price': 19.99,
            'description': 'Test description'
        })
        
        result = self.pipeline.process_item(item, self.spider)
        
        self.assertEqual(result, item)
        self.assertEqual(len(self.pipeline.items_collected), 1)
        self.assertEqual(self.pipeline.items_collected[0]['title'], 'Test Product')
    
    def test_close_spider_saves_items(self):
        """Test that closing spider saves items to database."""
        self.pipeline.database_available = True
        self.pipeline.scrape_job_id = 'test_job_123'
        self.pipeline.target_url = 'https://example.com'
        
        # Add some test items
        self.pipeline.items_collected = [
            {'title': 'Product 1', 'price': 10.99},
            {'title': 'Product 2', 'price': 20.99}
        ]
        
        self.pipeline.close_spider(self.spider)
        
        # Verify database.save_items was called with correct parameters
        self.mock_database.save_items.assert_called_once_with(
            items=self.pipeline.items_collected,
            scrape_job_id='test_job_123',
            scraper_type='scrapy',
            url='https://example.com'
        )
    
    def test_close_spider_no_items(self):
        """Test closing spider with no items."""
        self.pipeline.database_available = True
        
        self.pipeline.close_spider(self.spider)
        
        # Should not call save_items when no items
        self.mock_database.save_items.assert_not_called()
    
    def test_close_spider_database_unavailable(self):
        """Test closing spider when database is unavailable."""
        self.pipeline.database_available = False
        self.pipeline.items_collected = [{'title': 'Test'}]
        
        self.pipeline.close_spider(self.spider)
        
        # Should not call save_items when database unavailable
        self.mock_database.save_items.assert_not_called()
    
    def test_close_spider_save_error(self):
        """Test handling of database save errors."""
        self.pipeline.database_available = True
        self.pipeline.items_collected = [{'title': 'Test'}]
        self.pipeline.scrape_job_id = 'test_job'
        self.pipeline.target_url = 'https://example.com'
        
        # Mock database save error
        self.mock_database.save_items.side_effect = Exception("Database save error")
        
        # Should not raise exception, just log error
        self.pipeline.close_spider(self.spider)
        
        self.mock_database.save_items.assert_called_once()


if __name__ == '__main__':
    unittest.main()