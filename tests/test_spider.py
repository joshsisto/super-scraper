"""
Unit tests for the Universal Spider.

These tests use mock HTML responses to verify the spider's functionality
without making actual HTTP requests.
"""

import unittest
from unittest.mock import Mock, patch
from scrapy.http import TextResponse, Request
from super_scraper.spiders.universal import UniversalSpider
from super_scraper.items import SuperScraperItem


class TestUniversalSpider(unittest.TestCase):
    """Test cases for the UniversalSpider class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.spider = UniversalSpider(start_url='https://example.com')
    
    def test_spider_initialization(self):
        """Test spider initialization with URL."""
        self.assertEqual(self.spider.start_urls, ['https://example.com'])
        self.assertEqual(self.spider.allowed_domains, ['example.com'])
    
    def test_spider_initialization_without_url(self):
        """Test spider initialization without URL raises error."""
        with self.assertRaises(ValueError):
            UniversalSpider()
    
    def test_extract_item_data_books_toscrape(self):
        """Test item extraction for books.toscrape.com format."""
        # Mock HTML response similar to books.toscrape.com
        html = '''
        <article class="product_pod">
            <h3><a href="book.html" title="Test Book">Test Book</a></h3>
            <p class="price_color">£51.77</p>
            <div class="image_container">
                <img src="media/image.jpg" alt="Test Book">
            </div>
            <p class="instock availability">In stock</p>
        </article>
        '''
        
        response = TextResponse(
            url='https://books.toscrape.com/',
            body=html.encode('utf-8')
        )
        
        selector = response.css('article.product_pod')[0]
        item = self.spider.extract_item_data(selector, response)
        
        self.assertIsInstance(item, SuperScraperItem)
        self.assertEqual(item['title'], 'Test Book')
        self.assertEqual(item['price'], 51.77)
        self.assertEqual(item['image_url'], 'https://books.toscrape.com/media/image.jpg')
        self.assertEqual(item['stock_availability'], True)
    
    def test_parse_price(self):
        """Test price parsing functionality."""
        # Test various price formats
        test_cases = [
            ('$19.99', 19.99),
            ('£51.77', 51.77),
            ('€25.50', 25.50),
            ('1,299.99', 1299.99),
            ('Price: $49.99', 49.99),
            ('invalid', None),
            ('', None),
        ]
        
        for price_text, expected in test_cases:
            result = self.spider.parse_price(price_text)
            self.assertEqual(result, expected, f"Failed for input: {price_text}")
    
    def test_parse_stock_availability(self):
        """Test stock availability parsing."""
        # Test various stock text formats
        test_cases = [
            ('In stock', True),
            ('Available', True),
            ('in-stock', True),
            ('Out of stock', False),
            ('Unavailable', True),
            ('Sold out', False),
            ('Unknown status', False),
            ('', None),
        ]
        
        for stock_text, expected in test_cases:
            result = self.spider.parse_stock_availability(stock_text)
            self.assertEqual(result, expected, f"Failed for input: {stock_text}")
    
    def test_parse_with_items(self):
        """Test parse method with items on page."""
        html = '''
        <html>
            <body>
                <article class="product_pod">
                    <h3><a href="book1.html" title="Book 1">Book 1</a></h3>
                    <p class="price_color">£10.00</p>
                </article>
                <article class="product_pod">
                    <h3><a href="book2.html" title="Book 2">Book 2</a></h3>
                    <p class="price_color">£20.00</p>
                </article>
                <li class="next">
                    <a href="page-2.html">next</a>
                </li>
            </body>
        </html>
        '''
        
        response = TextResponse(
            url='https://example.com/',
            body=html.encode('utf-8')
        )
        
        # Mock the follow method
        response.follow = Mock(side_effect=lambda url, callback: 
            {'url': url, 'callback': callback.__name__})
        
        results = list(self.spider.parse(response))
        
        # Should yield 2 items and 1 pagination follow
        items = [r for r in results if isinstance(r, SuperScraperItem)]
        follows = [r for r in results if isinstance(r, dict)]
        
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]['title'], 'Book 1')
        self.assertEqual(items[1]['title'], 'Book 2')
        
        # Check pagination follow
        pagination_follows = [f for f in follows if f['callback'] == 'parse']
        self.assertTrue(len(pagination_follows) > 0)
    
    def test_extract_single_item(self):
        """Test extraction from a single product page."""
        html = '''
        <html>
            <head><title>Product Title</title></head>
            <body>
                <h1>Amazing Product</h1>
                <div class="price">$99.99</div>
                <div class="description">
                    This is a great product with many features.
                </div>
                <div class="product-image">
                    <img src="/images/product.jpg" alt="Product">
                </div>
            </body>
        </html>
        '''
        
        response = TextResponse(
            url='https://example.com/product',
            body=html.encode('utf-8')
        )
        
        item = self.spider.extract_single_item(response)
        
        self.assertIsInstance(item, SuperScraperItem)
        self.assertEqual(item['title'], 'Amazing Product')
        self.assertEqual(item['price'], 99.99)
        self.assertIn('great product', item['description'])
        self.assertEqual(item['image_url'], 'https://example.com/images/product.jpg')


class TestSpiderIntegration(unittest.TestCase):
    """Integration tests for the spider with mocked Scrapy components."""
    
    def test_spider_with_crawler_process(self):
        """Test spider can be instantiated with CrawlerProcess settings."""
        from scrapy.utils.project import get_project_settings
        
        settings = get_project_settings()
        spider = UniversalSpider(start_url='https://example.com')
        
        # Verify spider has correct attributes
        self.assertEqual(spider.name, 'universal')
        self.assertIsNotNone(spider.logger)


if __name__ == '__main__':
    unittest.main()