"""
Response data collection interfaces for the Super Scraper Suite.

This module provides unified interfaces for collecting response metadata from
different scraper types (Scrapy, Playwright, Pydoll) to enable consistent
validation across all scraping approaches.
"""

import time
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Union
from urllib.parse import urlparse

try:
    import requests
except ImportError:
    requests = None

try:
    from playwright.async_api import Page, Response as PlaywrightResponse
except ImportError:
    Page = None
    PlaywrightResponse = None

try:
    from scrapy.http import Response as ScrapyResponse
except ImportError:
    ScrapyResponse = None


class ResponseCollector(ABC):
    """
    Abstract base class for collecting response metadata from different scraper types.
    
    This interface ensures consistent response data collection across all scrapers
    while accommodating the unique characteristics of each scraping approach.
    """
    
    def __init__(self, config: Optional[Any] = None):
        """
        Initialize response collector with configuration.
        
        Args:
            config: ValidationConfig instance or None for defaults
        """
        self.logger = logging.getLogger(__name__)
        self.config = config
        
        # Default collection settings
        self.collect_headers = getattr(config, 'collect_response_headers', True) if config else True
        self.collect_content = getattr(config, 'collect_response_content', False) if config else False
        self.max_content_size = getattr(config, 'max_content_size', 1048576) if config else 1048576  # 1MB
    
    @abstractmethod
    async def collect_response_data(self, source: Any, url: str = None) -> Dict[str, Any]:
        """
        Collect response metadata from the scraper-specific source.
        
        Args:
            source: Scraper-specific response object
            url: Optional URL if not available in source
            
        Returns:
            Standardized response data dictionary
        """
        pass
    
    def _create_base_response_data(self, url: str, status_code: int = 200) -> Dict[str, Any]:
        """Create base response data structure with common fields."""
        return {
            'url': url,
            'status_code': status_code,
            'headers': {},
            'content': '',
            'response_time': 0.0,
            'timestamp': time.time(),
            'collector_type': self.__class__.__name__
        }
    
    def _sanitize_content(self, content: str) -> str:
        """Sanitize and truncate content if needed."""
        if not self.collect_content:
            return ''
        
        if not content:
            return ''
        
        # Truncate if too large
        if len(content) > self.max_content_size:
            self.logger.debug(f"Truncating content from {len(content)} to {self.max_content_size} bytes")
            return content[:self.max_content_size] + '... [truncated]'
        
        return content
    
    def _sanitize_headers(self, headers: Dict[str, Any]) -> Dict[str, str]:
        """Sanitize headers for validation use."""
        if not self.collect_headers:
            return {}
        
        sanitized = {}
        for key, value in headers.items():
            # Convert all header values to strings and lowercase keys
            try:
                sanitized[str(key).lower()] = str(value)
            except Exception as e:
                self.logger.debug(f"Error sanitizing header {key}: {e}")
                continue
        
        return sanitized


class ScrapyResponseCollector(ResponseCollector):
    """Response collector for Scrapy responses."""
    
    async def collect_response_data(self, response: Any, url: str = None) -> Dict[str, Any]:
        """
        Collect response data from Scrapy Response object.
        
        Args:
            response: Scrapy Response object
            url: Optional URL override
            
        Returns:
            Standardized response data dictionary
        """
        try:
            if not hasattr(response, 'status'):
                self.logger.error("Invalid Scrapy response object provided")
                return self._create_base_response_data(url or 'unknown')
            
            response_data = self._create_base_response_data(
                url or str(response.url),
                response.status
            )
            
            # Collect headers
            if hasattr(response, 'headers'):
                response_data['headers'] = self._sanitize_headers(dict(response.headers))
            
            # Collect content
            if hasattr(response, 'text'):
                response_data['content'] = self._sanitize_content(response.text)
            elif hasattr(response, 'body'):
                try:
                    content = response.body.decode('utf-8', errors='ignore')
                    response_data['content'] = self._sanitize_content(content)
                except Exception as e:
                    self.logger.debug(f"Error decoding response body: {e}")
            
            # Collect response time from meta if available
            if hasattr(response, 'meta') and 'download_latency' in response.meta:
                response_data['response_time'] = response.meta['download_latency']
            
            # Additional Scrapy-specific metadata
            if hasattr(response, 'meta'):
                response_data['scrapy_meta'] = {
                    'depth': response.meta.get('depth', 0),
                    'download_timeout': response.meta.get('download_timeout'),
                    'download_slot': response.meta.get('download_slot'),
                }
            
            self.logger.debug(f"Collected Scrapy response data for {response_data['url']}")
            return response_data
            
        except Exception as e:
            self.logger.error(f"Error collecting Scrapy response data: {e}")
            return self._create_base_response_data(url or 'unknown', status_code=0)


class PlaywrightResponseCollector(ResponseCollector):
    """Response collector for Playwright Page objects."""
    
    async def collect_response_data(self, page: Any, url: str = None) -> Dict[str, Any]:
        """
        Collect response data from Playwright Page object.
        
        Args:
            page: Playwright Page object
            url: Optional URL override
            
        Returns:
            Standardized response data dictionary
        """
        try:
            if not hasattr(page, 'url'):
                self.logger.error("Invalid Playwright page object provided")
                return self._create_base_response_data(url or 'unknown')
            
            start_time = time.time()
            
            # Get current URL and create base response
            current_url = url or str(page.url)
            response_data = self._create_base_response_data(current_url)
            
            try:
                # Try to get the main response from recent navigation
                # Note: This is a simplified approach - in production, you'd want to
                # capture the response during navigation
                
                # Evaluate JavaScript to get response information
                response_info = await page.evaluate("""() => {
                    return {
                        status: window.performance?.navigation?.redirectCount || 200,
                        readyState: document.readyState,
                        title: document.title,
                        contentType: document.contentType || 'text/html'
                    };
                }""")
                
                response_data['status_code'] = response_info.get('status', 200)
                response_data['ready_state'] = response_info.get('readyState', 'unknown')
                response_data['document_title'] = response_info.get('title', '')
                
                # Collect headers if possible (limited in browser context)
                response_data['headers'] = self._sanitize_headers({
                    'content-type': response_info.get('contentType', 'text/html'),
                    'user-agent': await page.evaluate('() => navigator.userAgent'),
                })
                
            except Exception as e:
                self.logger.debug(f"Error collecting detailed Playwright response info: {e}")
                response_data['status_code'] = 200  # Assume success if page loaded
            
            # Collect content if requested
            try:
                if self.collect_content:
                    content = await page.content()
                    response_data['content'] = self._sanitize_content(content)
            except Exception as e:
                self.logger.debug(f"Error collecting page content: {e}")
            
            # Calculate response time
            response_data['response_time'] = time.time() - start_time
            
            # Additional Playwright-specific metadata
            response_data['playwright_meta'] = {
                'viewport': page.viewport_size,
                'is_closed': page.is_closed(),
            }
            
            self.logger.debug(f"Collected Playwright response data for {response_data['url']}")
            return response_data
            
        except Exception as e:
            self.logger.error(f"Error collecting Playwright response data: {e}")
            return self._create_base_response_data(url or 'unknown', status_code=0)


class PydollResponseCollector(ResponseCollector):
    """Response collector for Pydoll (browser and fallback modes)."""
    
    async def collect_response_data(self, source: Any, url: str = None) -> Dict[str, Any]:
        """
        Collect response data from Pydoll source (tab or requests response).
        
        Args:
            source: Pydoll tab object or requests.Response object
            url: Optional URL override
            
        Returns:
            Standardized response data dictionary
        """
        try:
            # Determine if this is browser mode (Pydoll tab) or fallback mode (requests)
            if hasattr(source, 'url') and hasattr(source, 'go_to'):
                # Browser mode - Pydoll tab
                return await self._collect_browser_mode(source, url)
            elif hasattr(source, 'status_code') and hasattr(source, 'headers'):
                # Fallback mode - requests.Response
                return await self._collect_fallback_mode(source, url)
            else:
                self.logger.error("Unknown Pydoll source type provided")
                return self._create_base_response_data(url or 'unknown')
                
        except Exception as e:
            self.logger.error(f"Error collecting Pydoll response data: {e}")
            return self._create_base_response_data(url or 'unknown', status_code=0)
    
    async def _collect_browser_mode(self, tab: Any, url: str = None) -> Dict[str, Any]:
        """Collect response data from Pydoll tab (browser mode)."""
        try:
            current_url = url or str(tab.url)
            response_data = self._create_base_response_data(current_url)
            
            # Similar to Playwright, we have limited access to HTTP response details
            try:
                # Get basic page information
                page_info = await tab.evaluate("""() => {
                    return {
                        readyState: document.readyState,
                        title: document.title,
                        contentType: document.contentType || 'text/html'
                    };
                }""")
                
                response_data['status_code'] = 200  # Assume success if we can execute JS
                response_data['document_title'] = page_info.get('title', '')
                response_data['ready_state'] = page_info.get('readyState', 'unknown')
                
                # Basic headers
                response_data['headers'] = self._sanitize_headers({
                    'content-type': page_info.get('contentType', 'text/html'),
                })
                
            except Exception as e:
                self.logger.debug(f"Error collecting Pydoll browser page info: {e}")
                response_data['status_code'] = 200
            
            # Collect content if requested
            try:
                if self.collect_content:
                    # Get page content through Pydoll
                    content = await tab.evaluate('() => document.documentElement.outerHTML')
                    response_data['content'] = self._sanitize_content(content)
            except Exception as e:
                self.logger.debug(f"Error collecting Pydoll page content: {e}")
            
            response_data['pydoll_mode'] = 'browser'
            response_data['pydoll_meta'] = {
                'tab_id': getattr(tab, 'id', 'unknown'),
            }
            
            self.logger.debug(f"Collected Pydoll browser response data for {response_data['url']}")
            return response_data
            
        except Exception as e:
            self.logger.error(f"Error in Pydoll browser mode collection: {e}")
            return self._create_base_response_data(url or 'unknown', status_code=0)
    
    async def _collect_fallback_mode(self, response: Any, url: str = None) -> Dict[str, Any]:
        """Collect response data from requests.Response (fallback mode)."""
        try:
            current_url = url or str(response.url)
            response_data = self._create_base_response_data(current_url, response.status_code)
            
            # Collect headers
            response_data['headers'] = self._sanitize_headers(dict(response.headers))
            
            # Collect content
            try:
                if self.collect_content and hasattr(response, 'text'):
                    response_data['content'] = self._sanitize_content(response.text)
            except Exception as e:
                self.logger.debug(f"Error collecting response content: {e}")
            
            # Response time if available
            if hasattr(response, 'elapsed'):
                response_data['response_time'] = response.elapsed.total_seconds()
            
            response_data['pydoll_mode'] = 'fallback'
            response_data['pydoll_meta'] = {
                'encoding': getattr(response, 'encoding', 'unknown'),
                'apparent_encoding': getattr(response, 'apparent_encoding', 'unknown'),
                'is_redirect': getattr(response, 'is_redirect', False),
            }
            
            self.logger.debug(f"Collected Pydoll fallback response data for {response_data['url']}")
            return response_data
            
        except Exception as e:
            self.logger.error(f"Error in Pydoll fallback mode collection: {e}")
            return self._create_base_response_data(url or 'unknown', status_code=0)


class ResponseCollectorFactory:
    """Factory for creating appropriate response collectors."""
    
    @staticmethod
    def create_collector(scraper_type: str, config: Optional[Any] = None) -> ResponseCollector:
        """
        Create appropriate response collector for scraper type.
        
        Args:
            scraper_type: Type of scraper ('scrapy', 'playwright', 'pydoll')
            config: Optional ValidationConfig instance
            
        Returns:
            ResponseCollector instance
            
        Raises:
            ValueError: If scraper_type is not supported
        """
        collectors = {
            'scrapy': ScrapyResponseCollector,
            'playwright': PlaywrightResponseCollector,
            'pydoll': PydollResponseCollector,
        }
        
        if scraper_type not in collectors:
            raise ValueError(f"Unsupported scraper type: {scraper_type}. "
                           f"Supported types: {list(collectors.keys())}")
        
        return collectors[scraper_type](config)
    
    @staticmethod
    def auto_detect_collector(source: Any, config: Optional[Any] = None) -> ResponseCollector:
        """
        Automatically detect and create appropriate collector based on source type.
        
        Args:
            source: Response object from any scraper
            config: Optional ValidationConfig instance
            
        Returns:
            ResponseCollector instance
        """
        logger = logging.getLogger(__name__)
        
        # Try to detect scraper type based on source object attributes
        if hasattr(source, 'status') and hasattr(source, 'meta'):
            logger.debug("Detected Scrapy response")
            return ScrapyResponseCollector(config)
        elif hasattr(source, 'url') and hasattr(source, 'goto'):
            logger.debug("Detected Playwright page")
            return PlaywrightResponseCollector(config)
        elif hasattr(source, 'url') and hasattr(source, 'go_to'):
            logger.debug("Detected Pydoll tab")
            return PydollResponseCollector(config)
        elif hasattr(source, 'status_code') and hasattr(source, 'headers'):
            logger.debug("Detected requests response (Pydoll fallback)")
            return PydollResponseCollector(config)
        else:
            logger.warning("Could not auto-detect scraper type, defaulting to Scrapy")
            return ScrapyResponseCollector(config)


# Convenience functions for easy integration
async def collect_scrapy_response(response: Any, config: Optional[Any] = None) -> Dict[str, Any]:
    """Convenience function for collecting Scrapy response data."""
    collector = ScrapyResponseCollector(config)
    return await collector.collect_response_data(response)


async def collect_playwright_response(page: Any, config: Optional[Any] = None) -> Dict[str, Any]:
    """Convenience function for collecting Playwright response data."""
    collector = PlaywrightResponseCollector(config)
    return await collector.collect_response_data(page)


async def collect_pydoll_response(source: Any, config: Optional[Any] = None) -> Dict[str, Any]:
    """Convenience function for collecting Pydoll response data."""
    collector = PydollResponseCollector(config)
    return await collector.collect_response_data(source)


# Example usage
if __name__ == "__main__":
    import asyncio
    
    async def example_usage():
        """Example of how to use the response collectors."""
        from validation_config import ValidationConfig
        
        config = ValidationConfig()
        
        # Example with factory
        collector = ResponseCollectorFactory.create_collector('playwright', config)
        print(f"Created collector: {type(collector).__name__}")
        
        # Example response data structure
        sample_response = {
            'url': 'https://example.com',
            'status_code': 200,
            'headers': {'content-type': 'text/html'},
            'content': '<html><body>Sample</body></html>',
            'response_time': 1.5,
            'timestamp': time.time(),
            'collector_type': 'ExampleCollector'
        }
        
        print("Sample response data structure:")
        for key, value in sample_response.items():
            print(f"  {key}: {type(value).__name__}")
    
    asyncio.run(example_usage())