"""
Database module for Super Scraper Suite
Provides thread-safe SQLite operations for storing scraped data.
"""

import sqlite3
import logging
import os
import threading
from typing import List, Dict, Any, Optional
from datetime import datetime
import json

# Thread-local storage for database connections
_thread_local = threading.local()

# Default database path (configurable via environment variable)
DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), 'scraped_data.db')
DB_PATH = os.environ.get('SUPER_SCRAPER_DB_PATH', DEFAULT_DB_PATH)

logger = logging.getLogger(__name__)


def get_db_connection() -> sqlite3.Connection:
    """
    Get a thread-safe database connection.
    Creates a new connection per thread to ensure thread safety.
    """
    if not hasattr(_thread_local, 'connection') or _thread_local.connection is None:
        try:
            _thread_local.connection = sqlite3.connect(
                DB_PATH,
                timeout=30.0,  # 30 second timeout for database locks
                check_same_thread=False
            )
            _thread_local.connection.row_factory = sqlite3.Row
            # Enable WAL mode for better concurrent access
            _thread_local.connection.execute('PRAGMA journal_mode=WAL')
            _thread_local.connection.execute('PRAGMA synchronous=NORMAL')
            _thread_local.connection.execute('PRAGMA cache_size=10000')
        except sqlite3.Error as e:
            logger.error(f"Failed to connect to database at {DB_PATH}: {e}")
            raise
    
    return _thread_local.connection


def init_db() -> None:
    """
    Initialize the database by creating tables and indexes if they don't exist.
    This should be called by each scraper at startup.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create scraped_items table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scraped_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scrape_job_id TEXT NOT NULL,
                scraper_type TEXT NOT NULL,
                url TEXT NOT NULL,
                title TEXT,
                price REAL,
                description TEXT,
                image_url TEXT,
                stock_availability INTEGER,
                sku TEXT,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT  -- JSON field for additional data
            )
        ''')
        
        # Create indexes for common queries
        indexes = [
            'CREATE INDEX IF NOT EXISTS idx_scrape_job_id ON scraped_items(scrape_job_id)',
            'CREATE INDEX IF NOT EXISTS idx_scraper_type ON scraped_items(scraper_type)',
            'CREATE INDEX IF NOT EXISTS idx_scraped_at ON scraped_items(scraped_at)',
            'CREATE INDEX IF NOT EXISTS idx_url ON scraped_items(url)',
            'CREATE INDEX IF NOT EXISTS idx_sku ON scraped_items(sku)'
        ]
        
        for index_sql in indexes:
            cursor.execute(index_sql)
        
        conn.commit()
        logger.info(f"Database initialized successfully at {DB_PATH}")
        
    except sqlite3.Error as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during database initialization: {e}")
        raise


def save_items(items: List[Dict[str, Any]], scrape_job_id: str, scraper_type: str, url: str) -> int:
    """
    Save a list of scraped items to the database.
    
    Args:
        items: List of item dictionaries containing scraped data
        scrape_job_id: Unique identifier for this scraping run
        scraper_type: Type of scraper used ('scrapy', 'playwright', 'pydoll')
        url: The target URL that was scraped
        
    Returns:
        Number of items successfully saved
        
    Raises:
        sqlite3.Error: If database operation fails
    """
    if not items:
        logger.warning("No items to save")
        return 0
    
    conn = get_db_connection()
    cursor = conn.cursor()
    saved_count = 0
    
    try:
        # Begin transaction
        conn.execute('BEGIN TRANSACTION')
        
        for item in items:
            try:
                # Extract metadata (any extra fields not in main schema)
                main_fields = {'title', 'price', 'description', 'image_url', 'stock_availability', 'sku'}
                metadata = {k: v for k, v in item.items() if k not in main_fields}
                
                cursor.execute('''
                    INSERT INTO scraped_items (
                        scrape_job_id, scraper_type, url, title, price, 
                        description, image_url, stock_availability, sku, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    scrape_job_id,
                    scraper_type,
                    url,
                    item.get('title'),
                    item.get('price'),
                    item.get('description'),
                    item.get('image_url'),
                    1 if item.get('stock_availability') else 0,  # Convert boolean to integer
                    item.get('sku'),
                    json.dumps(metadata) if metadata else None
                ))
                saved_count += 1
                
            except sqlite3.Error as e:
                logger.error(f"Failed to save individual item: {e}, item: {item}")
                # Continue with other items rather than failing entire batch
                continue
        
        # Commit transaction
        conn.commit()
        logger.info(f"Successfully saved {saved_count}/{len(items)} items to database")
        
    except sqlite3.Error as e:
        # Rollback transaction on error
        conn.rollback()
        logger.error(f"Failed to save items, transaction rolled back: {e}")
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Unexpected error saving items: {e}")
        raise
    
    return saved_count


def get_items_by_job_id(scrape_job_id: str) -> List[sqlite3.Row]:
    """
    Retrieve all items for a specific scraping job.
    
    Args:
        scrape_job_id: The scraping job identifier
        
    Returns:
        List of database rows containing item data
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            'SELECT * FROM scraped_items WHERE scrape_job_id = ? ORDER BY scraped_at',
            (scrape_job_id,)
        )
        
        return cursor.fetchall()
    
    except sqlite3.Error as e:
        logger.error(f"Failed to retrieve items for job {scrape_job_id}: {e}")
        raise


def get_recent_jobs(limit: int = 10) -> List[sqlite3.Row]:
    """
    Get information about recent scraping jobs.
    
    Args:
        limit: Maximum number of jobs to return
        
    Returns:
        List of rows with job information
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                scrape_job_id,
                scraper_type,
                url,
                COUNT(*) as item_count,
                MIN(scraped_at) as started_at,
                MAX(scraped_at) as completed_at
            FROM scraped_items 
            GROUP BY scrape_job_id, scraper_type, url
            ORDER BY MAX(scraped_at) DESC
            LIMIT ?
        ''', (limit,))
        
        return cursor.fetchall()
    
    except sqlite3.Error as e:
        logger.error(f"Failed to retrieve recent jobs: {e}")
        raise


def cleanup_old_data(days_to_keep: int = 30) -> int:
    """
    Remove old data from the database to prevent unlimited growth.
    
    Args:
        days_to_keep: Number of days of data to retain
        
    Returns:
        Number of items deleted
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            DELETE FROM scraped_items 
            WHERE scraped_at < datetime('now', '-{} days')
        '''.format(days_to_keep))
        
        deleted_count = cursor.rowcount
        conn.commit()
        
        logger.info(f"Cleaned up {deleted_count} old items (older than {days_to_keep} days)")
        return deleted_count
    
    except sqlite3.Error as e:
        logger.error(f"Failed to cleanup old data: {e}")
        raise


def close_connection():
    """Close the thread-local database connection."""
    if hasattr(_thread_local, 'connection') and _thread_local.connection:
        _thread_local.connection.close()
        _thread_local.connection = None


def get_database_stats() -> Dict[str, Any]:
    """
    Get basic statistics about the database.
    
    Returns:
        Dictionary with database statistics
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Total items
        cursor.execute('SELECT COUNT(*) FROM scraped_items')
        total_items = cursor.fetchone()[0]
        
        # Items by scraper type
        cursor.execute('''
            SELECT scraper_type, COUNT(*) 
            FROM scraped_items 
            GROUP BY scraper_type
        ''')
        by_scraper = dict(cursor.fetchall())
        
        # Database file size
        db_size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
        
        return {
            'total_items': total_items,
            'by_scraper_type': by_scraper,
            'database_size_bytes': db_size,
            'database_path': DB_PATH
        }
    
    except (sqlite3.Error, OSError) as e:
        logger.error(f"Failed to get database stats: {e}")
        return {'error': str(e)}


if __name__ == '__main__':
    # Simple CLI for database operations
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python database.py [init|stats|cleanup]")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == 'init':
        init_db()
        print("Database initialized successfully")
    elif command == 'stats':
        stats = get_database_stats()
        print(json.dumps(stats, indent=2))
    elif command == 'cleanup':
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        deleted = cleanup_old_data(days)
        print(f"Deleted {deleted} old items")
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)