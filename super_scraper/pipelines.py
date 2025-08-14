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
        
        # Import validation components
        try:
            from validation_config import get_validation_config
            from validation_manager import ValidationManager
            
            # Get configuration from spider settings or use defaults
            self.config = get_validation_config()
            self.validation_manager = ValidationManager(self.config)
            self.validator_available = True
            
            self.logger.info("Enhanced ValidationManager initialized")
            
        except ImportError as e:
            # Fallback to legacy validator
            self.logger.warning(f"Enhanced validation not available, using legacy: {e}")
            try:
                from validator import ScrapingValidator
                self.validator = ScrapingValidator(self.logger)
                self.validation_manager = None
                self.validator_available = True
            except ImportError as e2:
                self.logger.warning(f"No validation available: {e2}")
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
            self.logger.info("Skipping validation - No validator available")
            return
        
        try:
            if self.validation_manager:
                # Use enhanced ValidationManager
                result = self._validate_with_manager(spider)
            else:
                # Use legacy validator
                result = self._validate_with_legacy(spider)
            
            if result:
                self._log_validation_results(result, spider)
                self._store_validation_stats(result, spider)
            
        except Exception as e:
            self.logger.error(f"Validation failed with error: {str(e)}")
            self.logger.exception("Full validation error traceback:")
            
            # Store error in stats
            if hasattr(spider, 'crawler') and spider.crawler:
                spider.crawler.stats.set_value('validation_error', str(e))
                spider.crawler.stats.set_value('validation_successful', False)
    
    def _validate_with_manager(self, spider):
        """Validate using the enhanced ValidationManager."""
        import asyncio
        
        # Create or get the event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Get the first response for validation
        first_response = getattr(spider, 'first_response', None)
        if not first_response:
            # Try to get from spider's internal state
            if hasattr(spider, '_responses') and spider._responses:
                first_response = spider._responses[0]
        
        # Create validation task
        validation_coro = self.validation_manager.validate_scraping_result(
            scraper_type='scrapy',
            response_source=first_response,
            scraped_data=self.items_collected,
            url=getattr(spider, 'start_urls', [''])[0] if hasattr(spider, 'start_urls') else '',
            task_id=f"scrapy_{spider.name}"
        )
        
        # Run validation
        if loop.is_running():
            # If loop is already running, create a task
            task = loop.create_task(validation_coro)
            # Note: This is a limitation - we can't easily wait for async in sync context
            # For now, we'll skip async validation in this case
            self.logger.warning("Async validation skipped - event loop already running")
            return None
        else:
            return loop.run_until_complete(validation_coro)
    
    def _validate_with_legacy(self, spider):
        """Validate using the legacy validator."""
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
        
        # Validate the scraping results
        return self.validator.validate_scraping_result(
            response_data=response_data,
            scraped_data=self.items_collected
        )
    
    def _log_validation_results(self, result, spider):
        """Log comprehensive validation results."""
        self.logger.info("=" * 50)
        self.logger.info("SCRAPING VALIDATION RESULTS")
        self.logger.info("=" * 50)
        
        # Use ValidationManager's summary if available, otherwise create basic summary
        if self.validation_manager:
            summary = f"Success: {result.is_successful}, Blocked: {result.is_blocked}, Confidence: {result.confidence_score:.2f}"
        else:
            summary = self.validator.get_validation_summary(result)
        
        self.logger.info(f"Summary: {summary}")
        
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
        
        self.logger.info("=" * 50)
    
    def _store_validation_stats(self, result, spider):
        """Store validation results in spider stats."""
        if hasattr(spider, 'crawler') and spider.crawler:
            spider.crawler.stats.set_value('validation_successful', result.is_successful)
            spider.crawler.stats.set_value('validation_blocked', result.is_blocked)
            spider.crawler.stats.set_value('validation_confidence', result.confidence_score)
            spider.crawler.stats.set_value('bot_detection_system', 
                                           result.bot_detection_system.value if result.bot_detection_system else 'none')
            spider.crawler.stats.set_value('validation_issues_count', len(result.issues))
            spider.crawler.stats.set_value('validation_warnings_count', len(result.warnings))
        
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


class SQLitePipeline:
    """
    Pipeline to save scraped items to SQLite database.
    
    This pipeline replaces CSV file output with database storage.
    Items are collected during processing and saved as a batch when the spider closes.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.items_collected = []
        self.scrape_job_id = None
        self.scraper_type = 'scrapy'
        self.target_url = None
        
        # Initialize database
        try:
            import database
            database.init_db()
            self.database_available = True
            self.logger.info("SQLite pipeline initialized - database ready")
        except Exception as e:
            self.logger.error(f"Failed to initialize SQLite pipeline: {e}")
            self.database_available = False
    
    def open_spider(self, spider):
        """
        Initialize pipeline when spider opens.
        
        Args:
            spider: The spider instance
        """
        if not self.database_available:
            return
        
        try:
            # Generate scrape_job_id using same format as other scrapers
            from datetime import datetime
            from urllib.parse import urlparse
            
            # Get target URL from spider
            if hasattr(spider, 'start_urls') and spider.start_urls:
                self.target_url = spider.start_urls[0]
                domain = urlparse(self.target_url).netloc.replace('www.', '')
            else:
                self.target_url = "unknown"
                domain = "unknown"
            
            # Generate job ID with same format as other scrapers
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.scrape_job_id = f"{domain}_{timestamp}"
            
            self.logger.info(f"SQLite pipeline opened for job: {self.scrape_job_id}")
            
        except Exception as e:
            self.logger.error(f"Error opening SQLite pipeline: {e}")
            self.database_available = False
    
    def process_item(self, item, spider):
        """
        Collect items for batch database insertion.
        
        Args:
            item: The scraped item
            spider: The spider instance
            
        Returns:
            The unchanged item
        """
        if self.database_available:
            try:
                adapter = ItemAdapter(item)
                item_dict = dict(adapter)
                self.items_collected.append(item_dict)
                self.logger.debug(f"Collected item for database: {item_dict.get('title', 'No title')}")
            except Exception as e:
                self.logger.error(f"Error collecting item for database: {e}")
        
        return item
    
    def close_spider(self, spider):
        """
        Save all collected items to database when spider closes.
        
        Args:
            spider: The spider instance
        """
        if not self.database_available:
            self.logger.warning("SQLite pipeline unavailable - items not saved to database")
            return
        
        if not self.items_collected:
            self.logger.info("No items collected - nothing to save to database")
            return
        
        try:
            # Import database module
            import database
            
            # Save items to database
            saved_count = database.save_items(
                items=self.items_collected,
                scrape_job_id=self.scrape_job_id,
                scraper_type=self.scraper_type,
                url=self.target_url or "unknown"
            )
            
            self.logger.info(f"SQLite Pipeline Statistics:")
            self.logger.info(f"  Items collected: {len(self.items_collected)}")
            self.logger.info(f"  Items saved to database: {saved_count}")
            self.logger.info(f"  Scrape job ID: {self.scrape_job_id}")
            self.logger.info(f"  Database location: {database.DB_PATH}")
            
            # Store stats in spider if available
            if hasattr(spider, 'crawler') and spider.crawler:
                spider.crawler.stats.set_value('database_items_saved', saved_count)
                spider.crawler.stats.set_value('database_scrape_job_id', self.scrape_job_id)
                spider.crawler.stats.set_value('database_location', database.DB_PATH)
            
        except Exception as e:
            self.logger.error(f"Failed to save items to database: {e}")
            self.logger.exception("Full database save error traceback:")
            
            # Store error in stats
            if hasattr(spider, 'crawler') and spider.crawler:
                spider.crawler.stats.set_value('database_save_error', str(e))
                spider.crawler.stats.set_value('database_items_saved', 0)
