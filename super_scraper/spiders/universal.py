"""
Universal spider that can scrape any website provided via command line.

This spider is designed to be flexible and handle various website structures.
It uses robust selectors and handles pagination automatically.
"""

import scrapy
from urllib.parse import urljoin, urlparse
import logging
from super_scraper.items import SuperScraperItem


class UniversalSpider(scrapy.Spider):
    """
    A universal spider that accepts a URL from command line and scrapes data.
    
    The spider attempts to identify common patterns in e-commerce and listing sites
    to extract relevant product/item information.
    """
    name = 'universal'
    
    def __init__(self, start_url=None, *args, **kwargs):
        """
        Initialize the spider with a dynamic start URL.
        
        Args:
            start_url: The URL to start scraping from
        """
        super(UniversalSpider, self).__init__(*args, **kwargs)
        
        if not start_url:
            raise ValueError("start_url is required. Use: scrapy crawl universal -a start_url='http://example.com'")
        
        self.start_urls = [start_url]
        self.allowed_domains = [urlparse(start_url).netloc]
        self.logger.info(f"Initialized spider for URL: {start_url}")
        self.logger.info(f"Allowed domain: {self.allowed_domains[0]}")
    
    def parse(self, response):
        """
        Main parsing method that identifies and extracts items from the page.
        
        This method uses multiple strategies to find product/item containers
        and extract relevant information.
        """
        self.logger.info(f"Parsing page: {response.url}")
        
        # Common selectors for product/item containers
        item_selectors = [
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
        
        items_found = False
        
        # Try each selector until we find items
        for selector in item_selectors:
            items = response.css(selector)
            if items:
                self.logger.info(f"Found {len(items)} items using selector: {selector}")
                items_found = True
                
                for item in items:
                    try:
                        scraped_item = self.extract_item_data(item, response)
                        if scraped_item:
                            yield scraped_item
                    except Exception as e:
                        self.logger.error(f"Error extracting item: {str(e)}")
                        continue
                break
        
        if not items_found:
            self.logger.warning(f"No items found on page: {response.url}")
            # Try to extract single item page
            single_item = self.extract_single_item(response)
            if single_item:
                yield single_item
        
        # Follow pagination links
        yield from self.follow_pagination(response)
        
        # Follow product detail links if we're on a listing page
        if items_found:
            yield from self.follow_product_links(response)
    
    def extract_item_data(self, selector, response):
        """
        Extract data from an item selector.
        
        Args:
            selector: The selector containing the item
            response: The response object for URL resolution
            
        Returns:
            SuperScraperItem or None
        """
        item = SuperScraperItem()
        
        # Extract title - try multiple common patterns
        title = (
            selector.css('h3 a::attr(title)').get() or
            selector.css('h3 a::text').get() or
            selector.css('h2 a::text').get() or
            selector.css('a::attr(title)').get() or
            selector.css('.title::text').get() or
            selector.css('[class*="title"]::text').get() or
            selector.css('h4::text').get() or
            selector.css('a::text').get()
        )
        
        if title:
            item['title'] = title.strip()
        else:
            self.logger.debug("No title found for item")
            return None
        
        # Extract price
        price_text = (
            selector.css('.price_color::text').get() or
            selector.css('.price::text').get() or
            selector.css('[class*="price"]::text').get() or
            selector.css('span.price::text').get() or
            selector.css('p.price_color::text').get()
        )
        
        if price_text:
            item['price'] = self.parse_price(price_text)
        
        # Extract description (often not available in list view)
        description = (
            selector.css('.description::text').get() or
            selector.css('[class*="description"]::text').get() or
            selector.css('p::text').get()
        )
        
        if description:
            item['description'] = description.strip()[:200]  # Limit to 200 chars
        
        # Extract image URL
        image_url = (
            selector.css('img::attr(src)').get() or
            selector.css('img::attr(data-src)').get() or
            selector.css('.image img::attr(src)').get() or
            selector.css('[class*="image"] img::attr(src)').get()
        )
        
        if image_url:
            item['image_url'] = urljoin(response.url, image_url)
        
        # Extract stock availability
        stock_text = (
            selector.css('.availability::text').get() or
            selector.css('.instock::text').get() or
            selector.css('[class*="availability"]::text').get() or
            selector.css('[class*="stock"]::text').get()
        )
        
        if stock_text:
            item['stock_availability'] = self.parse_stock_availability(stock_text)
        
        # Extract SKU (if available)
        sku = (
            selector.css('[class*="sku"]::text').get() or
            selector.css('[id*="sku"]::text').get() or
            selector.css('.product-id::text').get()
        )
        
        if sku:
            item['sku'] = sku.strip()
        
        return item
    
    def extract_single_item(self, response):
        """
        Extract data when the page is a single product/item page.
        
        Args:
            response: The response object
            
        Returns:
            SuperScraperItem or None
        """
        item = SuperScraperItem()
        
        # Extract title from various possible locations
        title = (
            response.css('h1::text').get() or
            response.css('h2.title::text').get() or
            response.css('[class*="product-title"]::text').get() or
            response.css('title::text').get()
        )
        
        if not title:
            return None
            
        item['title'] = title.strip()
        
        # Extract other fields using broader selectors
        price_text = response.css('[class*="price"]::text').re_first(r'[\d,]+\.?\d*')
        if price_text:
            item['price'] = self.parse_price(price_text)
        
        # Description might be in multiple paragraphs
        description_parts = response.css('[class*="description"] ::text').getall()
        if description_parts:
            item['description'] = ' '.join(description_parts).strip()[:200]
        
        # Image URL
        image_url = (
            response.css('[class*="product-image"] img::attr(src)').get() or
            response.css('img.main-image::attr(src)').get() or
            response.css('#product-image img::attr(src)').get()
        )
        
        if image_url:
            item['image_url'] = urljoin(response.url, image_url)
        
        return item
    
    def follow_pagination(self, response):
        """
        Follow pagination links to scrape all pages.
        
        Args:
            response: The response object
        """
        # Common pagination selectors
        next_page_selectors = [
            'li.next a::attr(href)',
            'a.next::attr(href)',
            '.pagination .next::attr(href)',
            'a[rel="next"]::attr(href)',
            '[class*="pagination"] a[class*="next"]::attr(href)',
            'a:contains("Next")::attr(href)',
        ]
        
        for selector in next_page_selectors:
            next_page = response.css(selector).get()
            if next_page:
                next_page_url = urljoin(response.url, next_page)
                self.logger.info(f"Following pagination to: {next_page_url}")
                yield response.follow(next_page_url, self.parse)
                break
    
    def follow_product_links(self, response):
        """
        Follow links to individual product pages for more detailed information.
        
        Args:
            response: The response object
        """
        # Common product link selectors
        product_link_selectors = [
            'article.product_pod h3 a::attr(href)',
            '.product a::attr(href)',
            '.item a::attr(href)',
            'a.product-link::attr(href)',
            '[class*="product"] a::attr(href)',
        ]
        
        for selector in product_link_selectors:
            links = response.css(selector).getall()
            if links:
                for link in links[:5]:  # Limit to first 5 to avoid too many requests
                    yield response.follow(link, self.parse_product_detail)
                break
    
    def parse_product_detail(self, response):
        """
        Parse individual product detail pages.
        
        Args:
            response: The response object
        """
        self.logger.info(f"Parsing product detail page: {response.url}")
        
        # Try to extract as a single item page
        item = self.extract_single_item(response)
        if item:
            yield item
    
    def parse_price(self, price_text):
        """
        Parse price text and convert to float.
        
        Args:
            price_text: Raw price text
            
        Returns:
            float or None
        """
        try:
            # Remove currency symbols and other non-numeric characters
            import re
            price_digits = re.findall(r'[\d,]+\.?\d*', price_text)
            if price_digits:
                # Remove commas and convert to float
                return float(price_digits[0].replace(',', ''))
        except (ValueError, IndexError) as e:
            self.logger.debug(f"Could not parse price: {price_text} - {str(e)}")
        
        return None
    
    def parse_stock_availability(self, stock_text):
        """
        Parse stock availability text to boolean.
        
        Args:
            stock_text: Raw stock availability text
            
        Returns:
            bool
        """
        if not stock_text:
            return None
            
        stock_text_lower = stock_text.lower()
        
        # Common patterns for in-stock
        in_stock_patterns = ['in stock', 'available', 'in-stock', 'yes']
        out_of_stock_patterns = ['out of stock', 'sold out', 'no']
        
        for pattern in in_stock_patterns:
            if pattern in stock_text_lower:
                return True
                
        for pattern in out_of_stock_patterns:
            if pattern in stock_text_lower:
                return False
                
        return None