#!/usr/bin/env python3
"""
Command-line interface for the Super Scraper project.

This script provides a CLI to run the Scrapy spider with a target URL.
It automatically creates a directory for each scraping job based on the 
URL domain and timestamp to avoid overwriting previous results.

Usage: python run_scraper.py --url "https://example.com"
"""

import argparse
import sys
import os
import re
from datetime import datetime
from urllib.parse import urlparse
from typing import Optional
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

# Add the project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def create_output_directory(url: str) -> str:
    """Create a directory name based on URL and timestamp."""
    # Parse the URL to get the domain
    parsed_url = urlparse(url)
    domain = parsed_url.netloc or parsed_url.path
    
    # Clean the domain name to be filesystem-friendly
    # Remove www. prefix if present
    domain = domain.replace('www.', '')
    # Replace non-alphanumeric characters with underscores
    domain = re.sub(r'[^a-zA-Z0-9.-]', '_', domain)
    # Remove trailing dots or underscores
    domain = domain.strip('._')
    
    # Create timestamp in a short format (YYYYMMDD_HHMMSS)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Create directory path inside scraped_results
    dir_name = os.path.join('scraped_results', f"{domain}_{timestamp}")
    
    # Create the directory if it doesn't exist
    os.makedirs(dir_name, exist_ok=True)
    
    return dir_name


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Run the Super Scraper with a target URL',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python run_scraper.py --url "https://books.toscrape.com/"
    # Saves data to database and creates log directory: scraped_results/books.toscrape.com_20240115_143025/
  
  python run_scraper.py --url "https://example.com" --loglevel DEBUG
    # Saves data to database with debug-level logging
        '''
    )
    
    parser.add_argument(
        '--url', 
        required=True,
        help='Target URL to scrape (required)'
    )
    
    
    parser.add_argument(
        '--loglevel',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        default='INFO',
        help='Logging level (default: INFO)'
    )
    
    # Add validation arguments using helper function
    try:
        from validation_config import add_validation_args
        add_validation_args(parser)
    except ImportError:
        # Validation system not available, skip validation args
        pass
    
    return parser.parse_args()


def run_spider(url: str, log_level: str, log_file: Optional[str] = None) -> None:
    """Run the Scrapy spider with the provided configuration."""
    # Get project settings
    settings = get_project_settings()
    
    # Update settings with command-line options
    settings.set('LOG_LEVEL', log_level)
    if log_file:
        settings.set('LOG_FILE', log_file)
    
    
    # Create crawler process
    process = CrawlerProcess(settings)
    
    # Run the spider with the provided URL
    process.crawl('universal', start_url=url)
    process.start()


def main() -> None:
    """Main entry point for the script."""
    args = parse_arguments()
    
    # Create output directory based on URL and timestamp
    output_dir = create_output_directory(args.url)
    
    # Create log file path inside the directory
    log_file = os.path.join(output_dir, 'scraper.log')
    
    print(f"Starting Super Scraper...")
    print(f"Target URL: {args.url}")
    print(f"Output directory: {output_dir}")
    print(f"Data will be saved to SQLite database")
    print(f"Log file: {log_file}")
    print(f"Log level: {args.loglevel}")
    print("-" * 50)
    
    try:
        run_spider(args.url, args.loglevel, log_file)
        print("-" * 50)
        print(f"Scraping completed! Results saved to SQLite database")
        print(f"Log file saved to: {log_file}")
        print(f"Use 'python database.py stats' to view database statistics")
    except Exception as e:
        print(f"Error occurred: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()