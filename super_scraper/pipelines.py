# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from itemadapter import ItemAdapter
from scrapy.exceptions import DropItem
import logging
import re


class DataValidationPipeline:
    """
    Pipeline to validate and clean scraped data.
    
    This pipeline ensures data quality by:
    - Validating required fields
    - Cleaning and normalizing data
    - Dropping invalid items
    - Logging validation issues
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.stats = {
            'valid_items': 0,
            'dropped_items': 0,
            'cleaned_items': 0
        }
    
    def process_item(self, item, spider):
        """
        Process and validate each item.
        
        Args:
            item: The scraped item
            spider: The spider instance
            
        Returns:
            The processed item or raises DropItem
        """
        adapter = ItemAdapter(item)
        
        # Check for required fields
        if not self.validate_required_fields(adapter):
            self.stats['dropped_items'] += 1
            raise DropItem(f"Missing required fields: {item}")
        
        # Clean and normalize data
        self.clean_title(adapter)
        self.clean_price(adapter)
        self.clean_description(adapter)
        self.validate_image_url(adapter)
        self.normalize_stock_availability(adapter)
        self.clean_sku(adapter)
        
        self.stats['valid_items'] += 1
        self.logger.debug(f"Validated item: {adapter.get('title', 'No title')}")
        
        return item
    
    def validate_required_fields(self, adapter):
        """
        Check if the item has at least a title.
        
        Args:
            adapter: ItemAdapter instance
            
        Returns:
            bool: True if valid, False otherwise
        """
        title = adapter.get('title')
        
        if not title or not str(title).strip():
            self.logger.warning("Item dropped: No title found")
            return False
            
        return True
    
    def clean_title(self, adapter):
        """
        Clean and normalize the title field.
        
        Args:
            adapter: ItemAdapter instance
        """
        title = adapter.get('title')
        if title:
            # Remove extra whitespace and newlines
            cleaned_title = ' '.join(str(title).split())
            # Remove special characters that might cause CSV issues
            cleaned_title = cleaned_title.replace('"', "'").replace('\n', ' ')
            # Limit length
            cleaned_title = cleaned_title[:200]
            adapter['title'] = cleaned_title
            self.stats['cleaned_items'] += 1
    
    def clean_price(self, adapter):
        """
        Validate and clean the price field.
        
        Args:
            adapter: ItemAdapter instance
        """
        price = adapter.get('price')
        
        if price is not None:
            try:
                # Ensure price is a float
                if isinstance(price, str):
                    # Extract numeric value from string
                    price_match = re.search(r'[\d,]+\.?\d*', str(price))
                    if price_match:
                        price = float(price_match.group().replace(',', ''))
                    else:
                        adapter['price'] = None
                        return
                
                # Validate price range
                price = float(price)
                if price < 0:
                    self.logger.warning(f"Invalid price (negative): {price}")
                    adapter['price'] = None
                elif price > 1000000:  # Sanity check for unrealistic prices
                    self.logger.warning(f"Suspiciously high price: {price}")
                    adapter['price'] = price
                else:
                    adapter['price'] = round(price, 2)
                    
            except (ValueError, TypeError) as e:
                self.logger.warning(f"Invalid price format: {price} - {str(e)}")
                adapter['price'] = None
    
    def clean_description(self, adapter):
        """
        Clean and normalize the description field.
        
        Args:
            adapter: ItemAdapter instance
        """
        description = adapter.get('description')
        
        if description:
            # Remove extra whitespace and newlines
            cleaned_desc = ' '.join(str(description).split())
            # Remove special characters that might cause CSV issues
            cleaned_desc = cleaned_desc.replace('"', "'").replace('\n', ' ')
            # Limit length
            cleaned_desc = cleaned_desc[:500]
            adapter['description'] = cleaned_desc
    
    def validate_image_url(self, adapter):
        """
        Validate the image URL format.
        
        Args:
            adapter: ItemAdapter instance
        """
        image_url = adapter.get('image_url')
        
        if image_url:
            # Basic URL validation
            if not (str(image_url).startswith('http://') or 
                    str(image_url).startswith('https://') or 
                    str(image_url).startswith('//')):
                self.logger.warning(f"Invalid image URL format: {image_url}")
                adapter['image_url'] = None
            else:
                # Clean the URL
                adapter['image_url'] = str(image_url).strip()
    
    def normalize_stock_availability(self, adapter):
        """
        Ensure stock_availability is a boolean value.
        
        Args:
            adapter: ItemAdapter instance
        """
        stock = adapter.get('stock_availability')
        
        if stock is not None:
            # Convert to boolean if it's not already
            if isinstance(stock, str):
                stock_lower = stock.lower()
                if any(word in stock_lower for word in ['yes', 'true', 'in stock', 'available']):
                    adapter['stock_availability'] = True
                elif any(word in stock_lower for word in ['no', 'false', 'out of stock', 'sold out']):
                    adapter['stock_availability'] = False
                else:
                    adapter['stock_availability'] = None
            elif not isinstance(stock, bool):
                adapter['stock_availability'] = bool(stock)
    
    def clean_sku(self, adapter):
        """
        Clean and validate the SKU field.
        
        Args:
            adapter: ItemAdapter instance
        """
        sku = adapter.get('sku')
        
        if sku:
            # Remove whitespace and ensure it's a string
            cleaned_sku = str(sku).strip()
            # Remove special characters that might cause issues
            cleaned_sku = re.sub(r'[^\w\-_.]', '', cleaned_sku)
            adapter['sku'] = cleaned_sku[:50]  # Limit length
    
    def close_spider(self, spider):
        """
        Log statistics when spider closes.
        
        Args:
            spider: The spider instance
        """
        self.logger.info(f"Validation Pipeline Statistics:")
        self.logger.info(f"  Valid items: {self.stats['valid_items']}")
        self.logger.info(f"  Dropped items: {self.stats['dropped_items']}")
        self.logger.info(f"  Items cleaned: {self.stats['cleaned_items']}")


class DuplicateFilterPipeline:
    """
    Pipeline to filter out duplicate items based on title and price.
    """
    
    def __init__(self):
        self.seen_items = set()
        self.logger = logging.getLogger(__name__)
        self.duplicates_count = 0
    
    def process_item(self, item, spider):
        """
        Check for duplicate items.
        
        Args:
            item: The scraped item
            spider: The spider instance
            
        Returns:
            The item if unique, or raises DropItem
        """
        adapter = ItemAdapter(item)
        
        # Create a unique identifier based on title and price
        title = adapter.get('title', '')
        price = adapter.get('price', '')
        item_id = f"{title}:{price}"
        
        if item_id in self.seen_items:
            self.duplicates_count += 1
            self.logger.debug(f"Duplicate item dropped: {title}")
            raise DropItem(f"Duplicate item: {title}")
        else:
            self.seen_items.add(item_id)
            return item
    
    def close_spider(self, spider):
        """
        Log duplicate statistics when spider closes.
        
        Args:
            spider: The spider instance
        """
        self.logger.info(f"Duplicate Filter Statistics:")
        self.logger.info(f"  Unique items: {len(self.seen_items)}")
        self.logger.info(f"  Duplicates filtered: {self.duplicates_count}")


class ValidationPipeline:
    """
    Pipeline to validate scraping results using the ScrapingValidator.
    
    This pipeline runs after all items are processed and provides comprehensive
    analysis of scraping success, blocking detection, and bot detection.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.items_collected = []
        self.response_data = None
        # Import validator here to avoid dependency issues if not available
        try:
            from validator import ScrapingValidator
            self.validator = ScrapingValidator(self.logger)
            self.validator_available = True
        except ImportError as e:
            self.logger.warning(f"ScrapingValidator not available: {e}")
            self.validator_available = False
    
    def process_item(self, item, spider):
        """
        Collect items for batch validation.
        
        Args:
            item: The scraped item
            spider: The spider instance
            
        Returns:
            The unchanged item
        """
        if self.validator_available:
            adapter = ItemAdapter(item)
            self.items_collected.append(dict(adapter))
        return item
    
    def close_spider(self, spider):
        """
        Validate collected results when spider finishes.
        
        Args:
            spider: The spider instance
        """
        if not self.validator_available:
            self.logger.info("Skipping validation - ScrapingValidator not available")
            return
        
        # Get response data from spider if available
        if hasattr(spider, 'response_data') and spider.response_data:
            response_data = spider.response_data
        else:
            # Create minimal response data if not available
            response_data = {
                'status_code': 200,
                'headers': {},
                'content': '',
                'url': getattr(spider, 'start_urls', [''])[0] if hasattr(spider, 'start_urls') else '',
                'response_time': 0
            }
        
        try:
            # Validate the scraping results
            result = self.validator.validate_scraping_result(
                response_data=response_data,
                scraped_data=self.items_collected
            )
            
            # Log comprehensive validation results
            self.logger.info("=" * 50)
            self.logger.info("SCRAPING VALIDATION RESULTS")
            self.logger.info("=" * 50)
            self.logger.info(f"Summary: {self.validator.get_validation_summary(result)}")
            
            if result.is_successful:
                self.logger.info("✓ SCRAPING SUCCESSFUL - Data quality meets standards")
            else:
                self.logger.warning("✗ SCRAPING ISSUES DETECTED")
            
            if result.is_blocked:
                self.logger.warning(f"⚠ BLOCKING DETECTED - Type: {result.metadata.get('block_type', 'unknown')}")
            
            if result.bot_detection_system and result.bot_detection_system.value != 'none':
                self.logger.info(f"🛡 BOT DETECTION SYSTEM: {result.bot_detection_system.value}")
                if result.metadata.get('bot_indicators'):
                    self.logger.info(f"   Indicators: {', '.join(result.metadata['bot_indicators'])}")
            
            # Log data statistics if available
            if 'data_stats' in result.metadata:
                stats = result.metadata['data_stats']
                self.logger.info(f"📊 DATA STATISTICS:")
                self.logger.info(f"   Total items: {stats.get('total_items', 0)}")
                self.logger.info(f"   Quality score: {result.confidence_score:.2f}")
                
                field_stats = stats.get('field_completeness', {})
                if field_stats:
                    self.logger.info("   Field completeness:")
                    for field, data in field_stats.items():
                        completeness = data.get('completeness', 0)
                        count = data.get('count', 0)
                        self.logger.info(f"     {field}: {completeness:.1%} ({count} items)")
            
            # Log issues and warnings
            if result.issues:
                self.logger.warning("❌ ISSUES FOUND:")
                for issue in result.issues:
                    self.logger.warning(f"   - {issue}")
            
            if result.warnings:
                self.logger.info("⚠ WARNINGS:")
                for warning in result.warnings:
                    self.logger.info(f"   - {warning}")
            
            # Store validation results in spider stats
            if hasattr(spider, 'crawler') and spider.crawler:
                spider.crawler.stats.set_value('validation_successful', result.is_successful)
                spider.crawler.stats.set_value('validation_blocked', result.is_blocked)
                spider.crawler.stats.set_value('validation_confidence', result.confidence_score)
                spider.crawler.stats.set_value('bot_detection_system', 
                                               result.bot_detection_system.value if result.bot_detection_system else 'none')
                spider.crawler.stats.set_value('validation_issues_count', len(result.issues))
                spider.crawler.stats.set_value('validation_warnings_count', len(result.warnings))
            
            self.logger.info("=" * 50)
            
            # Provide actionable recommendations
            if result.is_blocked and not result.is_successful:
                self.logger.warning("💡 RECOMMENDATION: Site is blocking access. Consider using:")
                self.logger.warning("   - Playwright scraper for JavaScript rendering and anti-detection")
                self.logger.warning("   - Pydoll scraper for adaptive fallback capabilities")
                self.logger.warning("   - Different user agents or request delays")
            elif not result.is_successful and not result.is_blocked:
                self.logger.warning("💡 RECOMMENDATION: Data quality issues detected. Consider:")
                self.logger.warning("   - Reviewing CSS selectors in spiders/universal.py")
                self.logger.warning("   - Checking if site structure has changed")
                self.logger.warning("   - Using browser automation for dynamic content")
            elif result.is_successful and result.bot_detection_system and result.bot_detection_system.value != 'none':
                self.logger.info("💡 NOTE: Bot detection system detected but scraping succeeded.")
                self.logger.info("   Monitor for potential future blocking.")
            
        except Exception as e:
            self.logger.error(f"Validation failed with error: {str(e)}")
            self.logger.exception("Full validation error traceback:")
            
            # Store error in stats
            if hasattr(spider, 'crawler') and spider.crawler:
                spider.crawler.stats.set_value('validation_error', str(e))
                spider.crawler.stats.set_value('validation_successful', False)
