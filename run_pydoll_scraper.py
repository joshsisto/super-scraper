#!/usr/bin/env python3
"""
Pydoll-based intelligent web scraper with automatic data extraction.

This script uses Pydoll's intelligent extraction capabilities to automatically
identify and extract structured data from web pages without manual selectors.

Usage: python run_pydoll_scraper.py --url "https://example.com"
"""

import argparse
import csv
import logging
import os
import re
import sys
import time
from datetime import datetime
from urllib.parse import urlparse, urljoin
from typing import List, Dict, Optional, Any

import asyncio
import requests
from bs4 import BeautifulSoup
import pandas as pd

try:
    from pydoll.browser import Chrome
except ImportError:
    print("Pydoll not installed. Please run: pip install git+https://github.com/autoscrape-labs/pydoll.git")
    sys.exit(1)


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
    logger = logging.getLogger('pydoll_scraper')
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers to avoid duplication
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
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


class PydollScraper:
    """Pydoll-based browser automation scraper."""
    
    def __init__(self, start_url: str, logger: logging.Logger, max_pages: int = 10):
        self.start_url = start_url
        self.logger = logger
        self.max_pages = max_pages
        self.items = []
        self.visited_urls = set()
        self.scrape_job_id = None
        
        # Initialize database
        try:
            import database
            database.init_db()
            self.database_available = True
            self.logger.info("Database initialized for Pydoll scraper")
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
            self.database_available = False
        
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
        
        # Common pagination selectors
        self.pagination_selectors = [
            'li.next a',
            'a.next',
            '.pagination .next',
            'a[rel="next"]',
            '[class*="pagination"] a[class*="next"]',
        ]
    
    def parse_price(self, price_text: str) -> Optional[float]:
        """Parse price text and convert to float."""
        if not price_text:
            return None
            
        try:
            # Remove currency symbols and other non-numeric characters
            price_digits = re.findall(r'[\d,]+\.?\d*', str(price_text))
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
            
        stock_text_lower = str(stock_text).lower()
        
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
    
    async def extract_item_data(self, tab, selector: str) -> None:
        """Extract data from items on the page using Pydoll."""
        try:
            elements = await tab.query_all(selector)
            if not elements:
                return
            
            self.logger.info(f"Found {len(elements)} items using selector: {selector}")
            
            for element in elements:
                try:
                    item = {}
                    
                    # Extract title
                    title_selectors = ['h3 a', 'h2 a', 'a[title]', '.title', '[class*="title"]', 'h4', 'a']
                    for title_sel in title_selectors:
                        try:
                            title_elem = await element.find(title_sel)
                            if title_elem:
                                title = await title_elem.get_attribute('title')
                                if not title:
                                    title = await title_elem.text
                                if title and title.strip():
                                    item['title'] = title.strip()
                                    break
                        except:
                            continue
                    
                    if not item.get('title'):
                        continue
                    
                    # Extract price
                    price_selectors = ['.price_color', '.price', '[class*="price"]', 'span.price', 'p.price_color']
                    for price_sel in price_selectors:
                        try:
                            price_elem = await element.find(price_sel)
                            if price_elem:
                                price_text = await price_elem.text
                                if price_text:
                                    item['price'] = self.parse_price(price_text)
                                    break
                        except:
                            continue
                    
                    # Extract description
                    desc_selectors = ['.description', '[class*="description"]', 'p']
                    for desc_sel in desc_selectors:
                        try:
                            desc_elem = await element.find(desc_sel)
                            if desc_elem:
                                desc_text = await desc_elem.text
                                if desc_text and len(desc_text.strip()) > 10:
                                    item['description'] = desc_text.strip()[:200]
                                    break
                        except:
                            continue
                    
                    # Extract image URL
                    try:
                        img_elem = await element.find('img')
                        if img_elem:
                            img_src = await img_elem.get_attribute('src')
                            if not img_src:
                                img_src = await img_elem.get_attribute('data-src')
                            if img_src:
                                if img_src.startswith('//'):
                                    img_src = 'https:' + img_src
                                elif img_src.startswith('/'):
                                    img_src = urljoin(self.start_url, img_src)
                                item['image_url'] = img_src
                    except:
                        pass
                    
                    # Extract stock availability
                    stock_selectors = ['.availability', '.instock', '[class*="availability"]', '[class*="stock"]']
                    for stock_sel in stock_selectors:
                        try:
                            stock_elem = await element.find(stock_sel)
                            if stock_elem:
                                stock_text = await stock_elem.text
                                if stock_text:
                                    item['stock_availability'] = self.parse_stock_availability(stock_text)
                                    break
                        except:
                            continue
                    
                    # Extract SKU
                    sku_selectors = ['[class*="sku"]', '[id*="sku"]', '.product-id']
                    for sku_sel in sku_selectors:
                        try:
                            sku_elem = await element.find(sku_sel)
                            if sku_elem:
                                sku_text = await sku_elem.text
                                if sku_text:
                                    item['sku'] = sku_text.strip()
                                    break
                        except:
                            continue
                    
                    self.items.append(item)
                    
                except Exception as e:
                    self.logger.error(f"Error extracting item: {str(e)}")
                    continue
                    
        except Exception as e:
            self.logger.error(f"Error finding elements with selector {selector}: {str(e)}")
    
    async def scrape_page(self, tab, url: str) -> None:
        """Scrape a single page using Pydoll."""
        if url in self.visited_urls or len(self.visited_urls) >= self.max_pages:
            return
            
        self.visited_urls.add(url)
        self.logger.info(f"Scraping page: {url}")
        
        try:
            # Navigate to the page
            await tab.go_to(url)
            
            # Wait a bit for page to load
            await asyncio.sleep(2)
            
            # Try to find items using various selectors
            items_found = False
            
            for selector in self.item_selectors:
                elements = await tab.query_all(selector)
                if elements:
                    items_found = True
                    await self.extract_item_data(tab, selector)
                    break
            
            if not items_found:
                self.logger.warning(f"No items found on page: {url}")
                # Try to extract as a single product page
                await self.extract_single_product(tab)
            
            # Look for pagination
            if items_found and len(self.visited_urls) < self.max_pages:
                await self.follow_pagination(tab)
                
        except Exception as e:
            self.logger.error(f"Error scraping page {url}: {str(e)}")
    
    async def extract_single_product(self, tab) -> None:
        """Extract data from a single product page."""
        try:
            item = {}
            
            # Extract title
            title_elem = await tab.find('h1')
            if not title_elem:
                title_elem = await tab.find('h2.title')
            
            if title_elem:
                title = await title_elem.text
                if title and title.strip():
                    item['title'] = title.strip()
                else:
                    return
            else:
                return
            
            # Extract price
            try:
                price_elem = await tab.find('[class*="price"]')
                if price_elem:
                    price_text = await price_elem.text
                    if price_text:
                        item['price'] = self.parse_price(price_text)
            except:
                pass
            
            # Extract description
            try:
                desc_elem = await tab.find('[class*="description"]')
                if desc_elem:
                    desc_text = await desc_elem.text
                    if desc_text:
                        item['description'] = desc_text.strip()[:200]
            except:
                pass
            
            # Extract image
            try:
                img_elem = await tab.find('[class*="product-image"] img, img.main-image, #product-image img')
                if img_elem:
                    img_src = await img_elem.get_attribute('src')
                    if img_src:
                        if img_src.startswith('//'):
                            img_src = 'https:' + img_src
                        elif img_src.startswith('/'):
                            img_src = urljoin(tab.url, img_src)
                        item['image_url'] = img_src
            except:
                pass
            
            if item:
                self.items.append(item)
                
        except Exception as e:
            self.logger.error(f"Error extracting single product: {str(e)}")
    
    async def follow_pagination(self, tab) -> None:
        """Follow pagination links."""
        try:
            for selector in self.pagination_selectors:
                try:
                    next_link = await tab.find(selector)
                    if next_link:
                        href = await next_link.get_attribute('href')
                        if href:
                            if href.startswith('/'):
                                next_url = urljoin(tab.url, href)
                            else:
                                next_url = href
                            
                            if next_url not in self.visited_urls:
                                self.logger.info(f"Following pagination to: {next_url}")
                                await self.scrape_page(tab, next_url)
                            break
                except:
                    continue
                    
        except Exception as e:
            self.logger.debug(f"Error following pagination: {str(e)}")
    
    def save_results(self) -> int:
        """Save scraped items to database."""
        if not self.items:
            self.logger.warning("No items to save")
            return 0
        
        if not self.database_available:
            self.logger.error("Database not available - items not saved")
            return 0
        
        try:
            # Import database module
            import database
            from datetime import datetime
            from urllib.parse import urlparse
            
            # Generate scrape_job_id if not set
            if not self.scrape_job_id:
                domain = urlparse(self.start_url).netloc.replace('www.', '')
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                self.scrape_job_id = f"{domain}_{timestamp}"
            
            # Remove duplicates based on title and price
            unique_items = []
            seen = set()
            
            for item in self.items:
                # Create identifier for deduplication
                identifier = f"{item.get('title', '')}:{item.get('price', '')}"
                if identifier not in seen:
                    seen.add(identifier)
                    unique_items.append(item)
                else:
                    self.logger.debug(f"Skipping duplicate item: {item.get('title', 'No title')}")
            
            # Save to database
            saved_count = database.save_items(
                items=unique_items,
                scrape_job_id=self.scrape_job_id,
                scraper_type='pydoll',
                url=self.start_url
            )
            
            self.logger.info(f"Pydoll Scraper Statistics:")
            self.logger.info(f"  Items collected: {len(self.items)}")
            self.logger.info(f"  Unique items saved: {saved_count}")
            self.logger.info(f"  Duplicates removed: {len(self.items) - len(unique_items)}")
            self.logger.info(f"  Scrape job ID: {self.scrape_job_id}")
            self.logger.info(f"  Database location: {database.DB_PATH}")
            
            return saved_count
            
        except Exception as e:
            self.logger.error(f"Failed to save items to database: {e}")
            return 0
    
    async def run(self, config=None) -> int:
        """Run the scraper with optional validation."""
        scraping_source = None
        scraping_mode = None
        
        try:
            # Try to start browser
            async with Chrome() as browser:
                tab = await browser.start()
                scraping_source = tab
                scraping_mode = 'browser'
                
                # Start scraping
                await self.scrape_page(tab, self.start_url)
                
                # Save results
                saved_count = self.save_results()
                return saved_count
            
        except Exception as e:
            self.logger.warning(f"Browser automation failed: {str(e)}")
            self.logger.info("Falling back to requests-based scraping...")
            
            try:
                # Fallback to requests-based scraping
                scraping_source = self.run_fallback()
                scraping_mode = 'fallback'
                saved_count = len(self.items)
                return saved_count
            except Exception as fallback_error:
                self.logger.error(f"Fallback scraping also failed: {str(fallback_error)}")
                raise
        
        # Perform validation if available
        await self._validate_results(scraping_source, scraping_mode, config)
    
    def run_fallback(self) -> requests.Session:
        """Fallback scraping using requests and BeautifulSoup."""
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        
        self.scrape_page_fallback(session, self.start_url)
        return session
    
    def scrape_page_fallback(self, session: requests.Session, url: str) -> None:
        """Scrape a single page using requests and BeautifulSoup."""
        if url in self.visited_urls or len(self.visited_urls) >= self.max_pages:
            return
            
        self.visited_urls.add(url)
        self.logger.info(f"Scraping page (fallback): {url}")
        
        try:
            response = session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Try to find items using various selectors
            items_found = False
            
            for selector in self.item_selectors:
                elements = soup.select(selector)
                if elements:
                    self.logger.info(f"Found {len(elements)} items using selector: {selector}")
                    items_found = True
                    
                    for element in elements:
                        item = self.extract_item_from_soup_element(element, url)
                        if item:
                            self.items.append(item)
                    break
            
            if not items_found:
                self.logger.warning(f"No items found on page: {url}")
                # Try to extract as a single product page
                single_item = self.extract_single_product_soup(soup, url)
                if single_item:
                    self.items.append(single_item)
            
            # Look for pagination
            if items_found and len(self.visited_urls) < self.max_pages:
                self.follow_pagination_soup(soup, url, session)
                
        except Exception as e:
            self.logger.error(f"Error scraping page {url}: {str(e)}")
    
    def extract_item_from_soup_element(self, element, base_url: str) -> Optional[Dict[str, Any]]:
        """Extract item data from a BeautifulSoup element."""
        try:
            item = {}
            
            # Extract title
            title_selectors = ['h3 a', 'h2 a', 'a[title]', '.title', '[class*="title"]', 'h4', 'a']
            for sel in title_selectors:
                title_elem = element.select_one(sel)
                if title_elem:
                    title = title_elem.get('title') or title_elem.get_text(strip=True)
                    if title:
                        item['title'] = title
                        break
            
            if not item.get('title'):
                return None
            
            # Extract price
            price_selectors = ['.price_color', '.price', '[class*="price"]', 'span.price', 'p.price_color']
            for sel in price_selectors:
                price_elem = element.select_one(sel)
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    if price_text:
                        item['price'] = self.parse_price(price_text)
                        break
            
            # Extract description
            desc_selectors = ['.description', '[class*="description"]', 'p']
            for sel in desc_selectors:
                desc_elem = element.select_one(sel)
                if desc_elem:
                    desc_text = desc_elem.get_text(strip=True)
                    if desc_text and len(desc_text) > 10:
                        item['description'] = desc_text[:200]
                        break
            
            # Extract image
            img_elem = element.select_one('img')
            if img_elem:
                img_src = img_elem.get('src') or img_elem.get('data-src')
                if img_src:
                    if img_src.startswith('//'):
                        img_src = 'https:' + img_src
                    elif img_src.startswith('/'):
                        img_src = urljoin(base_url, img_src)
                    item['image_url'] = img_src
            
            # Extract stock
            stock_selectors = ['.availability', '.instock', '[class*="availability"]', '[class*="stock"]']
            for sel in stock_selectors:
                stock_elem = element.select_one(sel)
                if stock_elem:
                    stock_text = stock_elem.get_text(strip=True)
                    if stock_text:
                        item['stock_availability'] = self.parse_stock_availability(stock_text)
                        break
            
            # Extract SKU
            sku_selectors = ['[class*="sku"]', '[id*="sku"]', '.product-id']
            for sel in sku_selectors:
                sku_elem = element.select_one(sel)
                if sku_elem:
                    sku_text = sku_elem.get_text(strip=True)
                    if sku_text:
                        item['sku'] = sku_text
                        break
            
            return item
            
        except Exception as e:
            self.logger.error(f"Error extracting item from element: {str(e)}")
            return None
    
    def extract_single_product_soup(self, soup: BeautifulSoup, base_url: str) -> Optional[Dict[str, Any]]:
        """Extract data from a single product page using BeautifulSoup."""
        try:
            item = {}
            
            # Extract title
            title_elem = soup.select_one('h1') or soup.select_one('h2.title')
            if title_elem:
                title = title_elem.get_text(strip=True)
                if title:
                    item['title'] = title
                else:
                    return None
            else:
                return None
            
            # Extract price
            price_elem = soup.select_one('[class*="price"]')
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                if price_text:
                    item['price'] = self.parse_price(price_text)
            
            # Extract description
            desc_elem = soup.select_one('[class*="description"]')
            if desc_elem:
                desc_text = desc_elem.get_text(strip=True)
                if desc_text:
                    item['description'] = desc_text[:200]
            
            # Extract image
            img_elem = soup.select_one('[class*="product-image"] img, img.main-image, #product-image img')
            if img_elem:
                img_src = img_elem.get('src')
                if img_src:
                    item['image_url'] = urljoin(base_url, img_src)
            
            return item
            
        except Exception as e:
            self.logger.error(f"Error extracting single product: {str(e)}")
            return None
    
    def follow_pagination_soup(self, soup: BeautifulSoup, base_url: str, session: requests.Session) -> None:
        """Follow pagination links using BeautifulSoup."""
        try:
            for selector in self.pagination_selectors:
                next_link = soup.select_one(selector)
                if next_link:
                    href = next_link.get('href')
                    if href:
                        next_url = urljoin(base_url, href)
                        
                        if next_url not in self.visited_urls:
                            self.logger.info(f"Following pagination to: {next_url}")
                            time.sleep(1)  # Be respectful
                            self.scrape_page_fallback(session, next_url)
                        break
                        
        except Exception as e:
            self.logger.debug(f"Error following pagination: {str(e)}")
    
    async def _validate_results(self, scraping_source, scraping_mode, config=None):
        """Validate scraping results using ValidationManager."""
        if not self.items:
            self.logger.warning("No items scraped, skipping validation")
            return
        
        try:
            # Import validation components
            from validation_config import get_validation_config
            from validation_manager import ValidationManager
            
            # Get configuration
            validation_config = config or get_validation_config()
            
            # Create ValidationManager
            with ValidationManager(validation_config) as manager:
                # Validate results
                result = await manager.validate_scraping_result(
                    scraper_type='pydoll',
                    response_source=scraping_source,
                    scraped_data=self.items,
                    url=self.start_url,
                    task_id=f"pydoll_{scraping_mode}_{int(time.time())}"
                )
                
                # Log validation summary
                self.logger.info("=" * 50)
                self.logger.info(f"PYDOLL VALIDATION RESULTS ({scraping_mode.upper()} MODE)")
                self.logger.info("=" * 50)
                
                if result.is_successful:
                    self.logger.info("✅ Validation successful!")
                else:
                    self.logger.warning("❌ Validation issues detected")
                
                self.logger.info(f"Scraping Mode: {scraping_mode}")
                self.logger.info(f"Confidence Score: {result.confidence_score:.2f}")
                self.logger.info(f"Items Validated: {len(self.items)}")
                
                if result.is_blocked:
                    self.logger.warning(f"🚫 Blocking detected: {result.metadata.get('block_type', 'unknown')}")
                
                if result.bot_detection_system and result.bot_detection_system.value != 'none':
                    self.logger.info(f"🛡️ Bot detection system: {result.bot_detection_system.value}")
                
                # Log issues and warnings
                if result.issues:
                    self.logger.warning("Issues found:")
                    for issue in result.issues:
                        self.logger.warning(f"  - {issue}")
                
                if result.warnings:
                    self.logger.info("Warnings:")
                    for warning in result.warnings:
                        self.logger.info(f"  - {warning}")
                
                # Mode-specific recommendations
                if scraping_mode == 'fallback' and not result.is_successful:
                    self.logger.warning("💡 FALLBACK MODE RECOMMENDATION:")
                    self.logger.warning("   - Consider installing Chrome for better browser automation")
                    self.logger.warning("   - Try Playwright scraper for advanced JavaScript handling")
                
                self.logger.info("=" * 50)
                
        except ImportError:
            self.logger.info("Enhanced validation not available, skipping")
        except Exception as e:
            self.logger.error(f"Validation failed: {str(e)}")
            # Don't let validation errors stop the scraper


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Run the Pydoll-based intelligent web scraper',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python run_pydoll_scraper.py --url "https://books.toscrape.com/"
    # Saves data to database and creates log directory: scraped_results/books.toscrape.com_20240115_143025/
  
  python run_pydoll_scraper.py --url "https://example.com" --loglevel DEBUG --max-pages 5
    # Saves data to database with debug logging and limit to 5 pages
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
    
    parser.add_argument(
        '--max-pages',
        type=int,
        default=10,
        help='Maximum number of pages to scrape (default: 10)'
    )
    
    # Add validation arguments using helper function
    try:
        from validation_config import add_validation_args
        add_validation_args(parser)
    except ImportError:
        # Validation system not available, skip validation args
        pass
    
    return parser.parse_args()


async def main():
    """Main entry point for the script."""
    args = parse_arguments()
    
    # Create output directory based on URL and timestamp
    output_dir = create_output_directory(args.url)
    
    # Create log file path inside the directory
    log_file = os.path.join(output_dir, 'pydoll_scraper.log')
    
    # Set up logging
    logger = setup_logging(log_file, args.loglevel)
    
    print(f"Starting Pydoll Scraper...")
    print(f"Target URL: {args.url}")
    print(f"Output directory: {output_dir}")
    print(f"Data will be saved to SQLite database")
    print(f"Log file: {log_file}")
    print(f"Log level: {args.loglevel}")
    print(f"Max pages: {args.max_pages}")
    print("-" * 50)
    
    try:
        # Get validation configuration
        validation_config = None
        try:
            from validation_config import get_validation_config
            validation_config = get_validation_config(args)
            logger.info(f"Validation enabled with quality threshold: {validation_config.min_data_quality_score}")
        except ImportError:
            logger.info("Enhanced validation not available")
        
        # Create and run scraper
        scraper = PydollScraper(args.url, logger, args.max_pages)
        saved_count = await scraper.run(validation_config)
        
        print("-" * 50)
        print(f"Scraping completed! {saved_count or 0} items saved to SQLite database")
        print(f"Log file saved to: {log_file}")
        print(f"Use 'python database.py stats' to view database statistics")
        
    except Exception as e:
        print(f"Error occurred: {str(e)}", file=sys.stderr)
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())