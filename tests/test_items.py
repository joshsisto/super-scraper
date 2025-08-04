"""
Unit tests for Scrapy items.

Tests the SuperScraperItem class and field definitions.
"""

import unittest
from super_scraper.items import SuperScraperItem


class TestSuperScraperItem(unittest.TestCase):
    """Test cases for the SuperScraperItem class."""
    
    def test_item_creation(self):
        """Test creating an item with all fields."""
        item = SuperScraperItem()
        
        # Test that all fields can be set
        item['title'] = 'Test Product'
        item['price'] = 19.99
        item['description'] = 'A test product'
        item['image_url'] = 'https://example.com/image.jpg'
        item['stock_availability'] = True
        item['sku'] = 'TEST-123'
        
        # Verify all fields are set correctly
        self.assertEqual(item['title'], 'Test Product')
        self.assertEqual(item['price'], 19.99)
        self.assertEqual(item['description'], 'A test product')
        self.assertEqual(item['image_url'], 'https://example.com/image.jpg')
        self.assertEqual(item['stock_availability'], True)
        self.assertEqual(item['sku'], 'TEST-123')
    
    def test_item_field_names(self):
        """Test that the item has all expected fields."""
        item = SuperScraperItem()
        expected_fields = ['title', 'price', 'description', 
                          'image_url', 'stock_availability', 'sku']
        
        for field in expected_fields:
            self.assertIn(field, item.fields)
    
    def test_item_initialization_with_dict(self):
        """Test creating an item from a dictionary."""
        data = {
            'title': 'Product from Dict',
            'price': 29.99,
            'description': 'Created from dictionary'
        }
        
        item = SuperScraperItem(data)
        
        self.assertEqual(item['title'], 'Product from Dict')
        self.assertEqual(item['price'], 29.99)
        self.assertEqual(item['description'], 'Created from dictionary')
    
    def test_item_missing_fields(self):
        """Test accessing missing fields raises KeyError."""
        item = SuperScraperItem()
        
        with self.assertRaises(KeyError):
            _ = item['title']
    
    def test_item_get_method(self):
        """Test the get method with default values."""
        item = SuperScraperItem()
        item['title'] = 'Test'
        
        # Field that exists
        self.assertEqual(item.get('title'), 'Test')
        
        # Field that doesn't exist with default
        self.assertEqual(item.get('price', 0.0), 0.0)
        
        # Field that doesn't exist without default
        self.assertIsNone(item.get('description'))
    
    def test_item_update(self):
        """Test updating item fields."""
        item = SuperScraperItem()
        item['title'] = 'Original Title'
        item['price'] = 10.00
        
        # Update the item
        item.update({
            'title': 'Updated Title',
            'description': 'New description'
        })
        
        self.assertEqual(item['title'], 'Updated Title')
        self.assertEqual(item['price'], 10.00)
        self.assertEqual(item['description'], 'New description')
    
    def test_item_copy(self):
        """Test copying an item."""
        original = SuperScraperItem({
            'title': 'Original',
            'price': 15.00
        })
        
        # Create a copy
        copy = original.copy()
        
        # Modify the copy
        copy['title'] = 'Copy'
        copy['price'] = 20.00
        
        # Original should be unchanged
        self.assertEqual(original['title'], 'Original')
        self.assertEqual(original['price'], 15.00)
        
        # Copy should have new values
        self.assertEqual(copy['title'], 'Copy')
        self.assertEqual(copy['price'], 20.00)


if __name__ == '__main__':
    unittest.main()