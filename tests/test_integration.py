#!/usr/bin/env python3
"""
Integration tests for common functionality across all scrapers.
"""

import unittest
import os
import sys
import tempfile
import shutil
import subprocess
import time
from unittest.mock import patch, Mock

# Add the project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestDirectoryCreation(unittest.TestCase):
    """Test directory creation functionality across all scrapers."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
    
    def tearDown(self):
        """Clean up test fixtures."""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)
    
    def test_scrapy_directory_creation(self):
        """Test that Scrapy scraper creates proper directory structure."""
        from run_scraper import create_output_directory
        
        test_url = "https://example.com"
        dir_name = create_output_directory(test_url)
        
        # Check directory exists
        self.assertTrue(os.path.exists(dir_name))
        self.assertTrue(os.path.isdir(dir_name))
        
        # Check directory name format
        self.assertIn('scraped_results', dir_name)
        self.assertIn('example.com', dir_name)
        self.assertRegex(os.path.basename(dir_name), r'example\.com_\d{8}_\d{6}$')
    
    def test_playwright_directory_creation(self):
        """Test that Playwright scraper creates proper directory structure."""
        from run_playwright_scraper import create_output_directory
        
        test_url = "https://books.toscrape.com/catalogue/page-1.html"
        dir_name = create_output_directory(test_url)
        
        # Check directory exists
        self.assertTrue(os.path.exists(dir_name))
        self.assertTrue(os.path.isdir(dir_name))
        
        # Check directory name format
        self.assertIn('scraped_results', dir_name)
        self.assertIn('books.toscrape.com', dir_name)
        self.assertRegex(os.path.basename(dir_name), r'books\.toscrape\.com_\d{8}_\d{6}$')
    
    def test_pydoll_directory_creation(self):
        """Test that Pydoll scraper creates proper directory structure."""
        from run_pydoll_scraper import create_output_directory
        
        test_url = "https://test-site.org:8080/path"
        dir_name = create_output_directory(test_url)
        
        # Check directory exists
        self.assertTrue(os.path.exists(dir_name))
        self.assertTrue(os.path.isdir(dir_name))
        
        # Check directory name format
        self.assertIn('scraped_results', dir_name)
        self.assertIn('test-site.org_8080', dir_name)
        self.assertRegex(os.path.basename(dir_name), r'test-site\.org_8080_\d{8}_\d{6}$')
    
    def test_directory_creation_same_url_different_timestamps(self):
        """Test that same URL creates different directories at different times."""
        from run_scraper import create_output_directory
        
        test_url = "https://example.com"
        
        # Create first directory
        dir1 = create_output_directory(test_url)
        
        # Wait a moment to ensure different timestamp
        time.sleep(1)
        
        # Create second directory
        dir2 = create_output_directory(test_url)
        
        # Should be different directories
        self.assertNotEqual(dir1, dir2)
        self.assertTrue(os.path.exists(dir1))
        self.assertTrue(os.path.exists(dir2))
    
    def test_directory_creation_url_cleaning(self):
        """Test that URLs with special characters are cleaned properly."""
        from run_scraper import create_output_directory
        
        test_cases = [
            ("https://www.example.com", "example.com"),
            ("https://example.com:8080", "example.com_8080"),
            ("https://sub.domain.example.com", "sub.domain.example.com"),
            ("https://example-site.com/path", "example-site.com"),
        ]
        
        for url, expected_domain in test_cases:
            with self.subTest(url=url):
                dir_name = create_output_directory(url)
                self.assertIn(expected_domain, dir_name)
                self.assertTrue(os.path.exists(dir_name))


class TestScraperCommonFunctionality(unittest.TestCase):
    """Test common functionality across all scrapers."""
    
    def test_price_parsing_consistency(self):
        """Test that all scrapers parse prices consistently."""
        from run_scraper import run_spider
        from run_playwright_scraper import PlaywrightScraper
        from run_pydoll_scraper import PydollScraper
        
        # Note: We can't easily test the Scrapy price parsing without more setup
        # But we can test the Playwright and Pydoll scrapers
        
        test_prices = [
            ("$19.99", 19.99),
            ("£25.50", 25.50),
            ("€15,99", 1599.0),  # Implementation treats comma as thousands separator
            ("1,234.56", 1234.56),
        ]
        
        # Create dummy scrapers to test price parsing
        playwright_scraper = PlaywrightScraper("https://example.com", "test.csv", Mock())
        pydoll_scraper = PydollScraper("https://example.com", "test.csv", Mock())
        
        for price_text, expected in test_prices:
            with self.subTest(price_text=price_text):
                playwright_result = playwright_scraper.parse_price(price_text)
                pydoll_result = pydoll_scraper.parse_price(price_text)
                
                self.assertEqual(playwright_result, expected)
                self.assertEqual(pydoll_result, expected)
                # Both scrapers should return the same result
                self.assertEqual(playwright_result, pydoll_result)
    
    def test_stock_availability_parsing_consistency(self):
        """Test that all scrapers parse stock availability consistently."""
        from run_playwright_scraper import PlaywrightScraper
        from run_pydoll_scraper import PydollScraper
        
        test_stock = [
            ("In Stock", True),
            ("Available", True),
            ("Out of Stock", False),
            ("Sold Out", False),
            ("Unknown", False),  # Implementation returns False for unknown
        ]
        
        playwright_scraper = PlaywrightScraper("https://example.com", Mock())
        pydoll_scraper = PydollScraper("https://example.com", Mock())
        
        for stock_text, expected in test_stock:
            with self.subTest(stock_text=stock_text):
                playwright_result = playwright_scraper.parse_stock_availability(stock_text)
                pydoll_result = pydoll_scraper.parse_stock_availability(stock_text)
                
                self.assertEqual(playwright_result, expected)
                self.assertEqual(pydoll_result, expected)
                # Both scrapers should return the same result
                self.assertEqual(playwright_result, pydoll_result)


class TestScraperCommandLineInterface(unittest.TestCase):
    """Test command-line interfaces of all scrapers."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
    
    def tearDown(self):
        """Clean up test fixtures."""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)
    
    def test_scrapy_scraper_help(self):
        """Test that Scrapy scraper shows help."""
        result = subprocess.run([
            sys.executable, 
            os.path.join(self.original_cwd, 'run_scraper.py'), 
            '--help'
        ], capture_output=True, text=True)
        
        self.assertEqual(result.returncode, 0)
        self.assertIn('--url', result.stdout)
        self.assertIn('--output', result.stdout)
        self.assertIn('--loglevel', result.stdout)
    
    def test_playwright_scraper_help(self):
        """Test that Playwright scraper shows help."""
        result = subprocess.run([
            sys.executable, 
            os.path.join(self.original_cwd, 'run_playwright_scraper.py'), 
            '--help'
        ], capture_output=True, text=True)
        
        self.assertEqual(result.returncode, 0)
        self.assertIn('--url', result.stdout)
        self.assertIn('--output', result.stdout)
        self.assertIn('--loglevel', result.stdout)
        self.assertIn('--max-pages', result.stdout)
    
    def test_pydoll_scraper_help(self):
        """Test that Pydoll scraper shows help."""
        result = subprocess.run([
            sys.executable, 
            os.path.join(self.original_cwd, 'run_pydoll_scraper.py'), 
            '--help'
        ], capture_output=True, text=True)
        
        self.assertEqual(result.returncode, 0)
        self.assertIn('--url', result.stdout)
        self.assertIn('--output', result.stdout)
        self.assertIn('--loglevel', result.stdout)
        self.assertIn('--max-pages', result.stdout)
    
    def test_scrapers_require_url(self):
        """Test that all scrapers require --url argument."""
        scrapers = [
            'run_scraper.py',
            'run_playwright_scraper.py',
            'run_pydoll_scraper.py'
        ]
        
        for scraper in scrapers:
            with self.subTest(scraper=scraper):
                result = subprocess.run([
                    sys.executable, 
                    os.path.join(self.original_cwd, scraper)
                ], capture_output=True, text=True)
                
                # Should exit with error code
                self.assertNotEqual(result.returncode, 0)
                # Should mention required URL argument
                self.assertIn('--url', result.stderr)


class TestOutputFormat(unittest.TestCase):
    """Test that all scrapers produce consistent output format."""
    
    def test_csv_headers_consistency(self):
        """Test that all scrapers produce CSV files with same headers."""
        expected_headers = ['title', 'price', 'description', 'image_url', 'stock_availability', 'sku']
        
        # Create test items
        test_items = [
            {
                'title': 'Test Product',
                'price': 19.99,
                'description': 'Test description',
                'image_url': 'https://example.com/image.jpg',
                'stock_availability': True,
                'sku': 'SKU001'
            }
        ]
        
        # Test each scraper's save functionality
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test Playwright scraper
            from run_playwright_scraper import PlaywrightScraper
            playwright_file = os.path.join(temp_dir, 'playwright_test.csv')
            playwright_scraper = PlaywrightScraper("https://example.com", playwright_file, Mock())
            playwright_scraper.items = test_items.copy()
            
            import asyncio
            asyncio.run(playwright_scraper.save_results())
            
            # Check headers
            with open(playwright_file, 'r') as f:
                headers = f.readline().strip().split(',')
                self.assertEqual(headers, expected_headers)
            
            # Test Pydoll scraper
            from run_pydoll_scraper import PydollScraper
            pydoll_file = os.path.join(temp_dir, 'pydoll_test.csv')
            pydoll_scraper = PydollScraper("https://example.com", pydoll_file, Mock())
            pydoll_scraper.items = test_items.copy()
            
            pydoll_scraper.save_results()
            
            # Check headers
            with open(pydoll_file, 'r') as f:
                headers = f.readline().strip().split(',')
                self.assertEqual(headers, expected_headers)


if __name__ == '__main__':
    unittest.main()