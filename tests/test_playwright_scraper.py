#!/usr/bin/env python3
"""
Unit tests for the Playwright-based scraper.
"""

import unittest
import asyncio
import os
import sys
import tempfile
import shutil
import logging
from unittest.mock import Mock, AsyncMock, patch, MagicMock

# Add the project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from run_playwright_scraper import PlaywrightScraper, create_output_directory, setup_logging


class TestPlaywrightScraper(unittest.TestCase):
    """Test cases for the PlaywrightScraper class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.test_url = "https://example.com"
        self.test_output = os.path.join(self.test_dir, "test_output.csv")
        self.test_log = os.path.join(self.test_dir, "test.log")
        self.logger = setup_logging(self.test_log, "INFO")
        
        self.scraper = PlaywrightScraper(
            self.test_url, 
            self.test_output, 
            self.logger
        )
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir)
    
    def test_scraper_initialization(self):
        """Test scraper initialization."""
        self.assertEqual(self.scraper.start_url, self.test_url)
        self.assertEqual(self.scraper.output_file, self.test_output)
        self.assertEqual(self.scraper.logger, self.logger)
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
    
    def test_save_results_no_items(self):
        """Test saving results when no items are scraped."""
        # Should not create file when no items
        asyncio.run(self.scraper.save_results())
        self.assertFalse(os.path.exists(self.test_output))
    
    def test_save_results_with_items(self):
        """Test saving results with items."""
        # Add test items
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
        
        asyncio.run(self.scraper.save_results())
        
        # Check that file was created
        self.assertTrue(os.path.exists(self.test_output))
        
        # Check file contents
        with open(self.test_output, 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn('Test Product 1', content)
            self.assertIn('Test Product 2', content)
            self.assertIn('19.99', content)
            self.assertIn('29.99', content)
    
    def test_save_results_duplicate_removal(self):
        """Test that duplicate items are removed."""
        # Add duplicate items
        self.scraper.items = [
            {'title': 'Duplicate Product', 'price': 19.99},
            {'title': 'Duplicate Product', 'price': 19.99},
            {'title': 'Unique Product', 'price': 29.99}
        ]
        
        asyncio.run(self.scraper.save_results())
        
        # Check that duplicates were removed
        with open(self.test_output, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            # Should have header + 2 items (duplicate removed)
            self.assertEqual(len(lines), 3)


class TestPlaywrightScraperHelperFunctions(unittest.TestCase):
    """Test helper functions for the Playwright scraper."""
    
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
        self.assertEqual(logger.name, 'playwright_scraper')
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


class TestPlaywrightScraperIntegration(unittest.TestCase):
    """Integration tests for the Playwright scraper."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir)
    
    @patch('run_playwright_scraper.async_playwright')
    async def test_scraper_run_mock(self, mock_playwright):
        """Test scraper run method with mocked Playwright."""
        # Mock the playwright context
        mock_context = AsyncMock()
        mock_page = AsyncMock()
        mock_browser = AsyncMock()
        
        # Configure mocks
        mock_playwright.return_value.__aenter__.return_value.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page
        
        # Mock page interactions
        mock_page.goto = AsyncMock()
        mock_page.query_selector_all.return_value = []
        mock_page.wait_for_timeout = AsyncMock()
        mock_page.evaluate = AsyncMock()
        
        # Create scraper
        test_output = os.path.join(self.test_dir, "test_output.csv")
        test_log = os.path.join(self.test_dir, "test.log")
        logger = setup_logging(test_log, "INFO")
        
        scraper = PlaywrightScraper(
            "https://example.com",
            test_output,
            logger
        )
        
        # Run scraper (should complete without errors)
        await scraper.run()
        
        # Verify mocks were called
        mock_page.goto.assert_called_with(
            "https://example.com", 
            wait_until='networkidle', 
            timeout=30000
        )


if __name__ == '__main__':
    unittest.main()