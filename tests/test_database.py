"""
Unit tests for the database module.

Tests database initialization, data storage, retrieval, and utility functions.
"""

import unittest
import tempfile
import os
import json
import sqlite3
from datetime import datetime

import database


class TestDatabase(unittest.TestCase):
    """Test cases for the database module."""
    
    def setUp(self):
        """Set up test fixtures with temporary database."""
        # Create temporary database for testing
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db.close()
        
        # Set database path to temporary file
        self.original_db_path = database.DB_PATH
        database.DB_PATH = self.temp_db.name
        
        # Initialize test database
        database.init_db()
    
    def tearDown(self):
        """Clean up test fixtures."""
        # Close any open connections
        database.close_connection()
        
        # Restore original database path
        database.DB_PATH = self.original_db_path
        
        # Remove temporary database
        try:
            os.unlink(self.temp_db.name)
        except FileNotFoundError:
            pass
    
    def test_database_initialization(self):
        """Test that database and tables are created correctly."""
        # Database should exist
        self.assertTrue(os.path.exists(self.temp_db.name))
        
        # Connect and check table structure
        conn = sqlite3.connect(self.temp_db.name)
        cursor = conn.cursor()
        
        # Check that scraped_items table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='scraped_items'")
        table_exists = cursor.fetchone()
        self.assertIsNotNone(table_exists)
        
        # Check table schema
        cursor.execute("PRAGMA table_info(scraped_items)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        expected_columns = [
            'id', 'scrape_job_id', 'scraper_type', 'url', 'title', 'price',
            'description', 'image_url', 'stock_availability', 'sku', 'scraped_at', 'metadata'
        ]
        
        for col in expected_columns:
            self.assertIn(col, column_names)
        
        conn.close()
    
    def test_save_items(self):
        """Test saving items to database."""
        test_items = [
            {
                'title': 'Test Product 1',
                'price': 19.99,
                'description': 'First test product',
                'image_url': 'https://example.com/image1.jpg',
                'stock_availability': True,
                'sku': 'SKU001'
            },
            {
                'title': 'Test Product 2',
                'price': 29.99,
                'description': 'Second test product',
                'image_url': 'https://example.com/image2.jpg',
                'stock_availability': False,
                'sku': 'SKU002'
            }
        ]
        
        saved_count = database.save_items(
            items=test_items,
            scrape_job_id='test_job_123',
            scraper_type='test',
            url='https://example.com'
        )
        
        self.assertEqual(saved_count, 2)
        
        # Verify data was saved correctly
        conn = database.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM scraped_items WHERE scrape_job_id = ?", ('test_job_123',))
        count = cursor.fetchone()[0]
        self.assertEqual(count, 2)
        
        cursor.execute("""
            SELECT title, price, stock_availability, scraper_type, url 
            FROM scraped_items 
            WHERE scrape_job_id = ? 
            ORDER BY title
        """, ('test_job_123',))
        
        rows = cursor.fetchall()
        self.assertEqual(len(rows), 2)
        
        # Check first item
        self.assertEqual(rows[0][0], 'Test Product 1')
        self.assertEqual(rows[0][1], 19.99)
        self.assertEqual(rows[0][2], 1)  # True stored as 1
        self.assertEqual(rows[0][3], 'test')
        self.assertEqual(rows[0][4], 'https://example.com')
        
        # Check second item
        self.assertEqual(rows[1][0], 'Test Product 2')
        self.assertEqual(rows[1][1], 29.99)
        self.assertEqual(rows[1][2], 0)  # False stored as 0
    
    def test_save_empty_items(self):
        """Test saving empty list of items."""
        saved_count = database.save_items(
            items=[],
            scrape_job_id='empty_job',
            scraper_type='test',
            url='https://example.com'
        )
        
        self.assertEqual(saved_count, 0)
    
    def test_save_items_with_metadata(self):
        """Test saving items with extra metadata fields."""
        test_items = [
            {
                'title': 'Product with metadata',
                'price': 99.99,
                'custom_field': 'custom_value',
                'rating': 4.5,
                'category': 'electronics'
            }
        ]
        
        saved_count = database.save_items(
            items=test_items,
            scrape_job_id='metadata_job',
            scraper_type='test',
            url='https://example.com'
        )
        
        self.assertEqual(saved_count, 1)
        
        # Verify metadata was stored as JSON
        conn = database.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT metadata FROM scraped_items WHERE scrape_job_id = ?", ('metadata_job',))
        metadata_json = cursor.fetchone()[0]
        
        metadata = json.loads(metadata_json)
        self.assertEqual(metadata['custom_field'], 'custom_value')
        self.assertEqual(metadata['rating'], 4.5)
        self.assertEqual(metadata['category'], 'electronics')
    
    def test_get_items_by_job_id(self):
        """Test retrieving items by job ID."""
        # Save test items
        test_items = [
            {'title': 'Job Test 1', 'price': 10.00},
            {'title': 'Job Test 2', 'price': 20.00}
        ]
        
        database.save_items(test_items, 'retrieve_test', 'test', 'https://example.com')
        
        # Retrieve items
        items = database.get_items_by_job_id('retrieve_test')
        
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]['title'], 'Job Test 1')
        self.assertEqual(items[1]['title'], 'Job Test 2')
    
    def test_get_recent_jobs(self):
        """Test retrieving recent jobs."""
        # Save items for multiple jobs
        for i in range(3):
            database.save_items(
                [{'title': f'Product {i}', 'price': 10.00}],
                f'job_{i}',
                'test',
                f'https://example{i}.com'
            )
        
        recent_jobs = database.get_recent_jobs(limit=2)
        
        self.assertLessEqual(len(recent_jobs), 2)
        
        # Check job information structure
        if recent_jobs:
            job = recent_jobs[0]
            self.assertIn('scrape_job_id', job.keys())
            self.assertIn('scraper_type', job.keys())
            self.assertIn('url', job.keys())
            self.assertIn('item_count', job.keys())
    
    def test_database_stats(self):
        """Test getting database statistics."""
        # Add some test data
        database.save_items(
            [{'title': 'Stats Test 1'}],
            'stats_job_scrapy',
            'scrapy',
            'https://example.com'
        )
        
        database.save_items(
            [{'title': 'Stats Test 2'}, {'title': 'Stats Test 3'}],
            'stats_job_playwright',
            'playwright',
            'https://example.com'
        )
        
        stats = database.get_database_stats()
        
        self.assertIsInstance(stats, dict)
        self.assertIn('total_items', stats)
        self.assertIn('by_scraper_type', stats)
        self.assertIn('database_size_bytes', stats)
        self.assertIn('database_path', stats)
        
        self.assertGreaterEqual(stats['total_items'], 3)
        self.assertIn('scrapy', stats['by_scraper_type'])
        self.assertIn('playwright', stats['by_scraper_type'])
    
    def test_thread_safety(self):
        """Test that multiple connections work correctly."""
        import threading
        
        results = []
        errors = []
        
        def save_items_thread(thread_id):
            try:
                items = [{'title': f'Thread {thread_id} Product', 'price': 10.00}]
                count = database.save_items(items, f'thread_job_{thread_id}', 'test', 'https://example.com')
                results.append(count)
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=save_items_thread, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Check results
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")
        self.assertEqual(len(results), 5)
        self.assertEqual(sum(results), 5)  # Each thread should save 1 item
    
    def test_database_connection_recovery(self):
        """Test that database connections can be recovered after errors."""
        # Force close the connection
        database.close_connection()
        
        # Should be able to reconnect and use database
        test_items = [{'title': 'Recovery Test', 'price': 5.00}]
        saved_count = database.save_items(test_items, 'recovery_job', 'test', 'https://example.com')
        
        self.assertEqual(saved_count, 1)


if __name__ == '__main__':
    unittest.main()