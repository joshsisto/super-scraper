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
    # Creates: scraped_results/books.toscrape.com_20240115_143025/
  
  python run_scraper.py --url "https://example.com" --output data.csv
    # Creates: scraped_results/example.com_20240115_143025/data.csv
  
  python run_scraper.py --url "https://example.com" --loglevel DEBUG
    # Creates directory with debug-level logging
        '''
    )
    
    parser.add_argument(
        '--url', 
        required=True,
        help='Target URL to scrape (required)'
    )
    
    parser.add_argument(
        '--output',
        default='scraped_data.csv',
        help='Output CSV filename (default: scraped_data.csv)'
    )
    
    parser.add_argument(
        '--loglevel',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        default='INFO',
        help='Logging level (default: INFO)'
    )
    
    return parser.parse_args()


def run_spider(url: str, output_file: str, log_level: str, log_file: Optional[str] = None) -> None:
    """Run the Scrapy spider with the provided configuration."""
    # Get project settings
    settings = get_project_settings()
    
    # Update settings with command-line options
    settings.set('LOG_LEVEL', log_level)
    if log_file:
        settings.set('LOG_FILE', log_file)
    
    settings.set('FEEDS', {
        output_file: {
            'format': 'csv',
            'encoding': 'utf8',
            'store_empty': False,
            'fields': ['title', 'price', 'description', 'image_url', 'stock_availability', 'sku'],
            'indent': None,
        }
    })
    
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
    
    # Update output file path to be inside the directory
    output_file = os.path.join(output_dir, args.output)
    log_file = os.path.join(output_dir, 'scraper.log')
    
    print(f"Starting Super Scraper...")
    print(f"Target URL: {args.url}")
    print(f"Output directory: {output_dir}")
    print(f"Output file: {output_file}")
    print(f"Log file: {log_file}")
    print(f"Log level: {args.loglevel}")
    print("-" * 50)
    
    try:
        run_spider(args.url, output_file, args.loglevel, log_file)
        print("-" * 50)
        print(f"Scraping completed! Results saved to: {output_file}")
        print(f"Log file saved to: {log_file}")
    except Exception as e:
        print(f"Error occurred: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()