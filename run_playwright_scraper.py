#!/usr/bin/env python3
"""
Playwright-based web scraper for JavaScript-heavy sites and bot detection bypass.

This script provides similar functionality to the Scrapy scraper but uses Playwright
for better handling of dynamic content and anti-bot measures.

Usage: python run_playwright_scraper.py --url "https://example.com"
"""

import argparse
import asyncio
import csv
import logging
import os
import re
import sys
from datetime import datetime
from urllib.parse import urlparse, urljoin
from typing import List, Dict, Optional, Any

from playwright.async_api import async_playwright, Page, Browser
import pandas as pd


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


def setup_logging(log_file: str, log_level: str) -> logging.Logger:
    """Set up logging configuration."""
    logger = logging.getLogger('playwright_scraper')
    logger.setLevel(getattr(logging, log_level))
    
    # File handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(getattr(logging, log_level))
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level))
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s [%(name)s] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


class PlaywrightScraper:
    """Playwright-based web scraper with anti-detection features."""
    
    def __init__(self, start_url: str, output_file: str, logger: logging.Logger):
        self.start_url = start_url
        self.output_file = output_file
        self.logger = logger
        self.items = []
        self.visited_urls = set()
        
        # Common selectors for product/item containers
        self.item_selectors = [
            'article.product_pod',  # books.toscrape.com
            'div.product',
            'div.item',
            'article.product',
            'li.product',
            'div.product-item',
            'div.listing-item',
            'div[class*="product"]',
            'div[class*="item"]',
            'article[class*="product"]',
        ]
        
        # Pagination selectors
        self.pagination_selectors = [
            'li.next a',
            'a.next',
            '.pagination .next',
            'a[rel="next"]',
            '[class*="pagination"] a[class*="next"]',
            'a:has-text("Next")',
        ]
    
    async def setup_browser(self) -> Browser:
        """Set up browser with anti-detection measures."""
        playwright = await async_playwright().start()
        
        # Launch browser with anti-detection settings
        browser = await playwright.chromium.launch(
            headless=True,  # Set to False for debugging
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-features=IsolateOrigins,site-per-process',
                '--disable-site-isolation-trials',
                '--disable-web-security',
                '--disable-features=BlockInsecurePrivateNetworkRequests',
                '--no-sandbox',
                '--disable-setuid-sandbox',
            ]
        )
        
        return browser
    
    async def create_page(self, browser: Browser) -> Page:
        """Create a new page with anti-detection measures."""
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='en-US',
            timezone_id='America/New_York',
            permissions=['geolocation'],
            geolocation={'latitude': 40.7128, 'longitude': -74.0060},
            color_scheme='light',
            device_scale_factor=1,
            has_touch=False,
            is_mobile=False,
            extra_http_headers={
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
        )
        
        page = await context.new_page()
        
        # Additional anti-detection measures
        await page.add_init_script("""
            // Override the navigator.webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // Override plugins to look more realistic
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            // Override languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
            
            // Override permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)
        
        return page
    
    def parse_price(self, price_text: str) -> Optional[float]:
        """Parse price text and convert to float."""
        if not price_text:
            return None
            
        try:
            # Remove currency symbols and other non-numeric characters
            price_digits = re.findall(r'[\d,]+\.?\d*', price_text)
            if price_digits:
                # Remove commas and convert to float
                return float(price_digits[0].replace(',', ''))
        except (ValueError, IndexError) as e:
            self.logger.debug(f"Could not parse price: {price_text} - {str(e)}")
        
        return None
    
    def parse_stock_availability(self, stock_text: str) -> Optional[bool]:
        """Parse stock availability text to boolean."""
        if not stock_text:
            return None
            
        stock_text_lower = stock_text.lower()
        
        # Common patterns for in-stock
        in_stock_patterns = ['in stock', 'available', 'in-stock', 'yes']
        out_of_stock_patterns = ['out of stock', 'sold out', 'unavailable', 'no']
        
        for pattern in in_stock_patterns:
            if pattern in stock_text_lower:
                return True
                
        for pattern in out_of_stock_patterns:
            if pattern in stock_text_lower:
                return False
                
        return None
    
    async def extract_item_data(self, page: Page, selector: str) -> List[Dict[str, Any]]:
        """Extract data from items on the page."""
        items = []
        elements = await page.query_selector_all(selector)
        
        for element in elements:
            try:
                item = {}
                
                # Extract title
                title = None
                title_selectors = [
                    'h3 a',
                    'h2 a', 
                    'a[title]',
                    '.title',
                    '[class*="title"]',
                    'h4',
                    'a'
                ]
                
                for title_sel in title_selectors:
                    title_elem = await element.query_selector(title_sel)
                    if title_elem:
                        title = await title_elem.get_attribute('title') or await title_elem.text_content()
                        if title:
                            break
                
                if not title:
                    continue
                    
                item['title'] = title.strip()
                
                # Extract price
                price_selectors = [
                    '.price_color',
                    '.price',
                    '[class*="price"]',
                    'span.price',
                    'p.price_color'
                ]
                
                for price_sel in price_selectors:
                    price_elem = await element.query_selector(price_sel)
                    if price_elem:
                        price_text = await price_elem.text_content()
                        if price_text:
                            item['price'] = self.parse_price(price_text)
                            break
                
                # Extract description
                desc_selectors = [
                    '.description',
                    '[class*="description"]',
                    'p'
                ]
                
                for desc_sel in desc_selectors:
                    desc_elem = await element.query_selector(desc_sel)
                    if desc_elem:
                        desc_text = await desc_elem.text_content()
                        if desc_text:
                            item['description'] = desc_text.strip()[:200]
                            break
                
                # Extract image URL
                img_elem = await element.query_selector('img')
                if img_elem:
                    img_src = await img_elem.get_attribute('src') or await img_elem.get_attribute('data-src')
                    if img_src:
                        item['image_url'] = urljoin(self.start_url, img_src)
                
                # Extract stock availability
                stock_selectors = [
                    '.availability',
                    '.instock',
                    '[class*="availability"]',
                    '[class*="stock"]'
                ]
                
                for stock_sel in stock_selectors:
                    stock_elem = await element.query_selector(stock_sel)
                    if stock_elem:
                        stock_text = await stock_elem.text_content()
                        if stock_text:
                            item['stock_availability'] = self.parse_stock_availability(stock_text)
                            break
                
                # Extract SKU
                sku_selectors = [
                    '[class*="sku"]',
                    '[id*="sku"]',
                    '.product-id'
                ]
                
                for sku_sel in sku_selectors:
                    sku_elem = await element.query_selector(sku_sel)
                    if sku_elem:
                        sku_text = await sku_elem.text_content()
                        if sku_text:
                            item['sku'] = sku_text.strip()
                            break
                
                items.append(item)
                
            except Exception as e:
                self.logger.error(f"Error extracting item: {str(e)}")
                continue
        
        return items
    
    async def scrape_page(self, page: Page, url: str) -> None:
        """Scrape a single page."""
        if url in self.visited_urls:
            return
            
        self.visited_urls.add(url)
        self.logger.info(f"Scraping page: {url}")
        
        try:
            # Navigate to the page
            await page.goto(url, wait_until='networkidle', timeout=30000)
            
            # Wait a bit to seem more human-like
            await page.wait_for_timeout(1000)
            
            # Scroll down to trigger lazy loading
            await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            await page.wait_for_timeout(500)
            
            # Try to find items using various selectors
            items_found = False
            
            for selector in self.item_selectors:
                elements = await page.query_selector_all(selector)
                if elements:
                    self.logger.info(f"Found {len(elements)} items using selector: {selector}")
                    items = await self.extract_item_data(page, selector)
                    self.items.extend(items)
                    items_found = True
                    break
            
            if not items_found:
                self.logger.warning(f"No items found on page: {url}")
                # Try to extract as a single product page
                await self.extract_single_product(page)
            
            # Look for pagination
            if items_found and len(self.visited_urls) < 10:  # Limit to 10 pages
                await self.follow_pagination(page)
                
        except Exception as e:
            self.logger.error(f"Error scraping page {url}: {str(e)}")
    
    async def extract_single_product(self, page: Page) -> None:
        """Extract data when the page is a single product page."""
        try:
            item = {}
            
            # Extract title
            title_elem = await page.query_selector('h1') or await page.query_selector('h2.title')
            if title_elem:
                title = await title_elem.text_content()
                if title:
                    item['title'] = title.strip()
                else:
                    return
            else:
                return
            
            # Extract price
            price_elem = await page.query_selector('[class*="price"]')
            if price_elem:
                price_text = await price_elem.text_content()
                if price_text:
                    item['price'] = self.parse_price(price_text)
            
            # Extract description
            desc_elem = await page.query_selector('[class*="description"]')
            if desc_elem:
                desc_text = await desc_elem.text_content()
                if desc_text:
                    item['description'] = desc_text.strip()[:200]
            
            # Extract image
            img_elem = await page.query_selector('[class*="product-image"] img, img.main-image, #product-image img')
            if img_elem:
                img_src = await img_elem.get_attribute('src')
                if img_src:
                    item['image_url'] = urljoin(page.url, img_src)
            
            self.items.append(item)
            
        except Exception as e:
            self.logger.error(f"Error extracting single product: {str(e)}")
    
    async def follow_pagination(self, page: Page) -> None:
        """Follow pagination links."""
        for selector in self.pagination_selectors:
            try:
                next_link = await page.query_selector(selector)
                if next_link:
                    href = await next_link.get_attribute('href')
                    if href:
                        next_url = urljoin(page.url, href)
                        if next_url not in self.visited_urls:
                            self.logger.info(f"Following pagination to: {next_url}")
                            await self.scrape_page(page, next_url)
                        break
            except Exception as e:
                self.logger.debug(f"Error checking pagination selector {selector}: {str(e)}")
    
    async def save_results(self) -> None:
        """Save scraped items to CSV file."""
        if not self.items:
            self.logger.warning("No items to save")
            return
        
        # Create DataFrame
        df = pd.DataFrame(self.items)
        
        # Define column order
        columns = ['title', 'price', 'description', 'image_url', 'stock_availability', 'sku']
        
        # Ensure all columns exist
        for col in columns:
            if col not in df.columns:
                df[col] = None
        
        # Remove duplicates based on available columns
        duplicate_columns = []
        if 'title' in df.columns:
            duplicate_columns.append('title')
        if 'price' in df.columns and not df['price'].isna().all():
            duplicate_columns.append('price')
        
        if duplicate_columns:
            df = df.drop_duplicates(subset=duplicate_columns, keep='first')
        
        # Save to CSV
        df[columns].to_csv(self.output_file, index=False, encoding='utf-8')
        self.logger.info(f"Saved {len(df)} items to {self.output_file}")
    
    async def run(self) -> None:
        """Run the scraper."""
        browser = None
        
        try:
            browser = await self.setup_browser()
            page = await self.create_page(browser)
            
            # Start scraping
            await self.scrape_page(page, self.start_url)
            
            # Save results
            await self.save_results()
            
        except Exception as e:
            self.logger.error(f"Fatal error: {str(e)}")
            raise
        finally:
            if browser:
                await browser.close()


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Run the Playwright-based web scraper',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python run_playwright_scraper.py --url "https://books.toscrape.com/"
    # Creates: scraped_results/books.toscrape.com_20240115_143025/
  
  python run_playwright_scraper.py --url "https://example.com" --output data.csv
    # Creates: scraped_results/example.com_20240115_143025/data.csv
  
  python run_playwright_scraper.py --url "https://example.com" --loglevel DEBUG --headless false
    # Run with browser visible for debugging
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
    
    parser.add_argument(
        '--max-pages',
        type=int,
        default=10,
        help='Maximum number of pages to scrape (default: 10)'
    )
    
    return parser.parse_args()


async def main():
    """Main entry point for the script."""
    args = parse_arguments()
    
    # Create output directory based on URL and timestamp
    output_dir = create_output_directory(args.url)
    
    # Update output file path to be inside the directory
    output_file = os.path.join(output_dir, args.output)
    log_file = os.path.join(output_dir, 'playwright_scraper.log')
    
    # Set up logging
    logger = setup_logging(log_file, args.loglevel)
    
    print(f"Starting Playwright Scraper...")
    print(f"Target URL: {args.url}")
    print(f"Output directory: {output_dir}")
    print(f"Output file: {output_file}")
    print(f"Log file: {log_file}")
    print(f"Log level: {args.loglevel}")
    print("-" * 50)
    
    try:
        # Create and run scraper
        scraper = PlaywrightScraper(args.url, output_file, logger)
        await scraper.run()
        
        print("-" * 50)
        print(f"Scraping completed! Results saved to: {output_file}")
        print(f"Log file saved to: {log_file}")
        
    except Exception as e:
        print(f"Error occurred: {str(e)}", file=sys.stderr)
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    # Install playwright browsers if not already installed
    try:
        import playwright
        asyncio.run(main())
    except ImportError:
        print("Playwright not installed. Please run: pip install playwright && playwright install chromium")
        sys.exit(1)