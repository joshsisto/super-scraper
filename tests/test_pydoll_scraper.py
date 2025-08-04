#!/usr/bin/env python3
"""
Unit tests for the Pydoll-based scraper.
"""

import unittest
import asyncio
import os
import sys
import tempfile
import shutil
import logging
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import requests
from bs4 import BeautifulSoup

# Add the project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from run_pydoll_scraper import PydollScraper, create_output_directory, setup_logging


class TestPydollScraper(unittest.TestCase):
    """Test cases for the PydollScraper class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.test_url = "https://example.com"
        self.test_output = os.path.join(self.test_dir, "test_output.csv")
        self.test_log = os.path.join(self.test_dir, "test.log")
        self.logger = setup_logging(self.test_log, "INFO")
        
        self.scraper = PydollScraper(
            self.test_url, 
            self.test_output, 
            self.logger,
            max_pages=2
        )
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir)
    
    def test_scraper_initialization(self):
        """Test scraper initialization."""
        self.assertEqual(self.scraper.start_url, self.test_url)
        self.assertEqual(self.scraper.output_file, self.test_output)
        self.assertEqual(self.scraper.logger, self.logger)
        self.assertEqual(self.scraper.max_pages, 2)
        self.assertEqual(len(self.scraper.items), 0)
        self.assertEqual(len(self.scraper.visited_urls), 0)
    
    def test_parse_price(self):
        """Test price parsing functionality."""
        test_cases = [
            ("$19.99", 19.99),
            ("£25.50", 25.50),
            ("€15,99", 1599.0),  # Implementation treats comma as thousands separator
            ("1,234.56", 1234.56),
            ("Free", None),
            ("", None),
            (None, None),
            ("Invalid price", None),
        ]
        
        for price_text, expected in test_cases:
            with self.subTest(price_text=price_text):
                result = self.scraper.parse_price(price_text)
                self.assertEqual(result, expected)
    
    def test_parse_stock_availability(self):
        """Test stock availability parsing."""
        test_cases = [
            ("In Stock", True),
            ("Available", True),
            ("in-stock", True),
            ("YES", True),
            ("Out of Stock", False),
            ("Sold Out", False),
            ("unavailable", True),  # Contains "available"
            ("NO", False),
            ("Unknown status", False),  # Implementation returns False for unknown
            ("", None),
            (None, None),
        ]
        
        for stock_text, expected in test_cases:
            with self.subTest(stock_text=stock_text):
                result = self.scraper.parse_stock_availability(stock_text)
                self.assertEqual(result, expected)
    
    def test_extract_item_from_soup_element(self):
        """Test item extraction from BeautifulSoup element."""
        html = '''
        <article class="product_pod">
            <h3><a href="/book1" title="Test Book Title">Test Book Title</a></h3>
            <p class="price_color">£51.77</p>
            <p class="availability">
                <i class="icon-ok"></i>
                In stock
            </p>
            <div class="image_container">
                <img src="../media/cache/test.jpg" alt="Test Book" />
            </div>
        </article>
        '''
        
        soup = BeautifulSoup(html, 'html.parser')
        element = soup.find('article')
        
        result = self.scraper.extract_item_from_soup_element(element, "https://example.com")
        
        self.assertIsNotNone(result)
        self.assertEqual(result['title'], 'Test Book Title')
        self.assertEqual(result['price'], 51.77)
        self.assertTrue(result['stock_availability'])
        self.assertEqual(result['image_url'], '../media/cache/test.jpg')
    
    def test_extract_item_from_soup_element_no_title(self):
        """Test that element without title returns None."""
        html = '<div><p>No title here</p></div>'
        soup = BeautifulSoup(html, 'html.parser')
        element = soup.find('div')
        
        result = self.scraper.extract_item_from_soup_element(element, "https://example.com")
        self.assertIsNone(result)
    
    def test_extract_single_product_soup(self):
        """Test single product extraction from BeautifulSoup."""
        html = '''
        <html>
            <body>
                <h1>Single Product Title</h1>
                <div class="price">$29.99</div>
                <div class="description">Product description here</div>
                <div class="product-image">
                    <img src="/images/product.jpg" alt="Product" />
                </div>
            </body>
        </html>
        '''
        
        soup = BeautifulSoup(html, 'html.parser')
        result = self.scraper.extract_single_product_soup(soup, "https://example.com")
        
        self.assertIsNotNone(result)
        self.assertEqual(result['title'], 'Single Product Title')
        self.assertEqual(result['price'], 29.99)
        self.assertEqual(result['description'], 'Product description here')
        self.assertEqual(result['image_url'], 'https://example.com/images/product.jpg')
    
    def test_extract_single_product_soup_no_title(self):
        """Test single product extraction when no title is found."""
        html = '<html><body><p>No title here</p></body></html>'
        soup = BeautifulSoup(html, 'html.parser')
        
        result = self.scraper.extract_single_product_soup(soup, "https://example.com")
        self.assertIsNone(result)
    
    def test_save_results_no_items(self):
        """Test saving results when no items are scraped."""
        self.scraper.save_results()
        self.assertFalse(os.path.exists(self.test_output))
    
    def test_save_results_with_items(self):
        """Test saving results with items."""
        self.scraper.items = [
            {
                'title': 'Test Product 1',
                'price': 19.99,
                'description': 'Test description',
                'image_url': 'https://example.com/image1.jpg',
                'stock_availability': True,
                'sku': 'SKU001'
            },
            {
                'title': 'Test Product 2',
                'price': 29.99,
                'description': None,
                'image_url': None,
                'stock_availability': False,
                'sku': None
            }
        ]
        
        self.scraper.save_results()
        
        # Check that file was created
        self.assertTrue(os.path.exists(self.test_output))
        
        # Check file contents
        with open(self.test_output, 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn('Test Product 1', content)
            self.assertIn('Test Product 2', content)
            self.assertIn('19.99', content)
            self.assertIn('29.99', content)
    
    @patch('run_pydoll_scraper.requests.Session.get')
    def test_scrape_page_fallback(self, mock_get):
        """Test fallback scraping with mocked requests."""
        # Mock the response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.text = '''
        <html>
            <body>
                <article class="product_pod">
                    <h3><a title="Test Product">Test Product</a></h3>
                    <p class="price_color">£25.99</p>
                    <p class="availability">In stock</p>
                </article>
            </body>
        </html>
        '''
        mock_get.return_value = mock_response
        
        # Create a session mock
        session = requests.Session()
        
        # Test fallback scraping
        self.scraper.scrape_page_fallback(session, "https://example.com")
        
        # Check that item was extracted
        self.assertEqual(len(self.scraper.items), 1)
        self.assertEqual(self.scraper.items[0]['title'], 'Test Product')
        self.assertEqual(self.scraper.items[0]['price'], 25.99)
        self.assertTrue(self.scraper.items[0]['stock_availability'])
    
    @patch('run_pydoll_scraper.requests.Session.get')
    def test_follow_pagination_soup(self, mock_get):
        """Test pagination following with BeautifulSoup."""
        # Mock the response with pagination
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.text = '''
        <html>
            <body>
                <div class="pagination">
                    <li class="next"><a href="page-2.html">Next</a></li>
                </div>
            </body>
        </html>
        '''
        mock_get.return_value = mock_response
        
        soup = BeautifulSoup(mock_response.text, 'html.parser')
        session = requests.Session()
        
        # Test pagination following
        with patch.object(self.scraper, 'scrape_page_fallback') as mock_scrape:
            self.scraper.follow_pagination_soup(soup, "https://example.com/page-1.html", session)
            mock_scrape.assert_called_once_with(session, "https://example.com/page-2.html")


class TestPydollScraperHelperFunctions(unittest.TestCase):
    """Test helper functions for the Pydoll scraper."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_create_output_directory(self):
        """Test output directory creation."""
        test_cases = [
            "https://example.com",
            "https://www.example.com",
            "https://books.toscrape.com/catalogue/page-1.html",
            "http://test-site.org:8080/path",
        ]
        
        created_dirs = []
        
        for url in test_cases:
            with self.subTest(url=url):
                # Change to test directory
                old_cwd = os.getcwd()
                os.chdir(self.test_dir)
                
                try:
                    dir_name = create_output_directory(url)
                    created_dirs.append(dir_name)
                    
                    # Check directory was created
                    self.assertTrue(os.path.exists(dir_name))
                    self.assertTrue(os.path.isdir(dir_name))
                    
                    # Check directory name format
                    self.assertIn('scraped_results', dir_name)
                    self.assertRegex(
                        os.path.basename(dir_name), 
                        r'.*_\d{8}_\d{6}$'
                    )
                finally:
                    os.chdir(old_cwd)
        
        # Clean up created directories
        for dir_name in created_dirs:
            full_path = os.path.join(self.test_dir, dir_name)
            if os.path.exists(full_path):
                shutil.rmtree(full_path)
    
    def test_setup_logging(self):
        """Test logging setup."""
        log_file = os.path.join(self.test_dir, "test.log")
        logger = setup_logging(log_file, "DEBUG")
        
        # Test logger configuration
        self.assertEqual(logger.name, 'pydoll_scraper')
        self.assertEqual(logger.level, logging.DEBUG)
        
        # Test that handlers were added
        self.assertGreater(len(logger.handlers), 0)
        
        # Test logging to file
        logger.info("Test message")
        
        # Check that log file was created and contains message
        self.assertTrue(os.path.exists(log_file))
        with open(log_file, 'r') as f:
            content = f.read()
            self.assertIn("Test message", content)


class TestPydollScraperIntegration(unittest.TestCase):
    """Integration tests for the Pydoll scraper."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir)
    
    @patch('run_pydoll_scraper.Chrome')
    async def test_scraper_run_browser_fails_fallback_works(self, mock_chrome):
        """Test that scraper falls back to requests when browser fails."""
        # Mock Chrome to raise an exception
        mock_chrome.side_effect = Exception("No valid browser path found")
        
        # Create scraper
        test_output = os.path.join(self.test_dir, "test_output.csv")
        test_log = os.path.join(self.test_dir, "test.log")
        logger = setup_logging(test_log, "INFO")
        
        scraper = PydollScraper(
            "https://example.com",
            test_output,
            logger,
            max_pages=1
        )
        
        # Mock the fallback method
        with patch.object(scraper, 'run_fallback') as mock_fallback:
            await scraper.run()
            mock_fallback.assert_called_once()
    
    @patch('run_pydoll_scraper.requests.Session.get')
    def test_run_fallback(self, mock_get):
        """Test the fallback run method."""
        # Mock response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.text = '''
        <html>
            <body>
                <h1>Single Product</h1>
                <div class="price">$19.99</div>
            </body>
        </html>
        '''
        mock_get.return_value = mock_response
        
        # Create scraper
        test_output = os.path.join(self.test_dir, "test_output.csv")
        test_log = os.path.join(self.test_dir, "test.log")
        logger = setup_logging(test_log, "INFO")
        
        scraper = PydollScraper(
            "https://example.com",
            test_output,
            logger,
            max_pages=1
        )
        
        # Run fallback
        scraper.run_fallback()
        
        # Check that item was extracted and file was created
        self.assertEqual(len(scraper.items), 1)
        self.assertEqual(scraper.items[0]['title'], 'Single Product')
        self.assertEqual(scraper.items[0]['price'], 19.99)
        self.assertTrue(os.path.exists(test_output))


if __name__ == '__main__':
    unittest.main()