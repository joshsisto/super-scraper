"""
Unit tests for the Scrapy pipelines.

Tests data validation, cleaning, and duplicate filtering functionality.
"""

import unittest
from unittest.mock import Mock, MagicMock
from scrapy.exceptions import DropItem
from super_scraper.pipelines import DataValidationPipeline, DuplicateFilterPipeline
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


if __name__ == '__main__':
    unittest.main()