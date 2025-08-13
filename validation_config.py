"""
Configuration management for the Super Scraper Suite validation system.

This module provides a unified configuration interface that maintains consistency
with existing project patterns while enabling external configuration through
environment variables and command-line arguments.
"""

import os
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class ValidationConfig:
    """
    Unified configuration for scraping validation across all scrapers.
    
    This configuration system uses environment variables with sensible defaults,
    maintaining consistency with the existing project's configuration patterns.
    
    Environment Variables:
        SCRAPER_MIN_DATA_QUALITY_SCORE: Minimum quality score for successful validation (default: 0.7)
        SCRAPER_MIN_REQUIRED_FIELDS: Comma-separated list of required fields (default: "title")
        SCRAPER_MAX_PLACEHOLDER_RATIO: Maximum ratio of placeholder content (default: 0.3)
        SCRAPER_VALIDATION_TIMEOUT: Maximum time for validation in seconds (default: 30)
        SCRAPER_ENABLE_CACHING: Enable validation result caching (default: True)
        SCRAPER_CACHE_TTL: Cache time-to-live in seconds (default: 300)
        SCRAPER_LOG_LEVEL: Validation logging level (default: INFO)
        SCRAPER_ENABLE_DETAILED_REPORTS: Enable detailed validation reports (default: True)
    """
    
    # Data quality thresholds
    min_data_quality_score: float = field(default_factory=lambda: float(os.getenv('SCRAPER_MIN_DATA_QUALITY_SCORE', '0.7')))
    min_required_fields: List[str] = field(default_factory=lambda: os.getenv('SCRAPER_MIN_REQUIRED_FIELDS', 'title').split(','))
    max_placeholder_ratio: float = field(default_factory=lambda: float(os.getenv('SCRAPER_MAX_PLACEHOLDER_RATIO', '0.3')))
    
    # Performance and timeout settings
    validation_timeout: int = field(default_factory=lambda: int(os.getenv('SCRAPER_VALIDATION_TIMEOUT', '30')))
    enable_caching: bool = field(default_factory=lambda: os.getenv('SCRAPER_ENABLE_CACHING', 'True').lower() == 'true')
    cache_ttl: int = field(default_factory=lambda: int(os.getenv('SCRAPER_CACHE_TTL', '300')))
    
    # Logging and reporting
    log_level: str = field(default_factory=lambda: os.getenv('SCRAPER_LOG_LEVEL', 'INFO'))
    enable_detailed_reports: bool = field(default_factory=lambda: os.getenv('SCRAPER_ENABLE_DETAILED_REPORTS', 'True').lower() == 'true')
    
    # Response data collection settings
    collect_response_headers: bool = field(default_factory=lambda: os.getenv('SCRAPER_COLLECT_RESPONSE_HEADERS', 'True').lower() == 'true')
    collect_response_content: bool = field(default_factory=lambda: os.getenv('SCRAPER_COLLECT_RESPONSE_CONTENT', 'False').lower() == 'true')
    max_content_size: int = field(default_factory=lambda: int(os.getenv('SCRAPER_MAX_CONTENT_SIZE', '1048576')))  # 1MB default
    
    # Scraper-specific settings
    playwright_wait_timeout: int = field(default_factory=lambda: int(os.getenv('SCRAPER_PLAYWRIGHT_WAIT_TIMEOUT', '30000')))
    pydoll_fallback_timeout: int = field(default_factory=lambda: int(os.getenv('SCRAPER_PYDOLL_FALLBACK_TIMEOUT', '10')))
    
    def __post_init__(self):
        """Validate configuration values after initialization."""
        self._validate_config()
    
    def _validate_config(self):
        """Validate configuration values and log warnings for invalid settings."""
        logger = logging.getLogger(__name__)
        
        # Validate numeric ranges
        if not 0.0 <= self.min_data_quality_score <= 1.0:
            logger.warning(f"Invalid min_data_quality_score: {self.min_data_quality_score}, using default 0.7")
            self.min_data_quality_score = 0.7
        
        if not 0.0 <= self.max_placeholder_ratio <= 1.0:
            logger.warning(f"Invalid max_placeholder_ratio: {self.max_placeholder_ratio}, using default 0.3")
            self.max_placeholder_ratio = 0.3
        
        if self.validation_timeout <= 0:
            logger.warning(f"Invalid validation_timeout: {self.validation_timeout}, using default 30")
            self.validation_timeout = 30
        
        if self.cache_ttl <= 0:
            logger.warning(f"Invalid cache_ttl: {self.cache_ttl}, using default 300")
            self.cache_ttl = 300
        
        # Validate required fields
        if not self.min_required_fields or not any(field.strip() for field in self.min_required_fields):
            logger.warning("No required fields specified, using default ['title']")
            self.min_required_fields = ['title']
        else:
            # Clean up field names
            self.min_required_fields = [field.strip() for field in self.min_required_fields if field.strip()]
        
        # Validate log level
        valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if self.log_level.upper() not in valid_log_levels:
            logger.warning(f"Invalid log_level: {self.log_level}, using default INFO")
            self.log_level = 'INFO'
        else:
            self.log_level = self.log_level.upper()
    
    @classmethod
    def create_from_args(cls, args: Optional[Any] = None) -> 'ValidationConfig':
        """
        Create configuration instance from command-line arguments.
        
        This method allows scrapers to override configuration values through
        command-line arguments while maintaining environment variable defaults.
        
        Args:
            args: Parsed command-line arguments object (argparse.Namespace)
            
        Returns:
            ValidationConfig instance with argument overrides applied
        """
        config = cls()
        
        if args:
            # Override with command-line arguments if provided
            if hasattr(args, 'validation_quality_score'):
                config.min_data_quality_score = args.validation_quality_score
            
            if hasattr(args, 'validation_required_fields'):
                config.min_required_fields = args.validation_required_fields.split(',')
            
            if hasattr(args, 'validation_timeout'):
                config.validation_timeout = args.validation_timeout
            
            if hasattr(args, 'enable_validation_cache'):
                config.enable_caching = args.enable_validation_cache
            
            if hasattr(args, 'loglevel'):
                config.log_level = args.loglevel
        
        return config
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary for serialization."""
        return {
            'min_data_quality_score': self.min_data_quality_score,
            'min_required_fields': self.min_required_fields,
            'max_placeholder_ratio': self.max_placeholder_ratio,
            'validation_timeout': self.validation_timeout,
            'enable_caching': self.enable_caching,
            'cache_ttl': self.cache_ttl,
            'log_level': self.log_level,
            'enable_detailed_reports': self.enable_detailed_reports,
            'collect_response_headers': self.collect_response_headers,
            'collect_response_content': self.collect_response_content,
            'max_content_size': self.max_content_size,
            'playwright_wait_timeout': self.playwright_wait_timeout,
            'pydoll_fallback_timeout': self.pydoll_fallback_timeout,
        }
    
    def get_logger_config(self) -> Dict[str, Any]:
        """Get logger configuration for validation components."""
        return {
            'level': getattr(logging, self.log_level),
            'format': '%(asctime)s [%(name)s] %(levelname)s: %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        }
    
    def is_field_required(self, field_name: str) -> bool:
        """Check if a specific field is required for validation."""
        return field_name in self.min_required_fields
    
    def get_scraper_specific_config(self, scraper_type: str) -> Dict[str, Any]:
        """
        Get scraper-specific configuration values.
        
        Args:
            scraper_type: Type of scraper ('scrapy', 'playwright', 'pydoll')
            
        Returns:
            Dictionary of scraper-specific configuration values
        """
        base_config = {
            'validation_timeout': self.validation_timeout,
            'log_level': self.log_level,
            'enable_detailed_reports': self.enable_detailed_reports,
        }
        
        if scraper_type == 'playwright':
            base_config.update({
                'wait_timeout': self.playwright_wait_timeout,
                'collect_response_headers': self.collect_response_headers,
                'collect_response_content': self.collect_response_content,
                'max_content_size': self.max_content_size,
            })
        elif scraper_type == 'pydoll':
            base_config.update({
                'fallback_timeout': self.pydoll_fallback_timeout,
                'collect_response_headers': self.collect_response_headers,
                'collect_response_content': self.collect_response_content,
                'max_content_size': self.max_content_size,
            })
        elif scraper_type == 'scrapy':
            base_config.update({
                'enable_caching': self.enable_caching,
                'cache_ttl': self.cache_ttl,
            })
        
        return base_config


# Global configuration instance - can be imported and used across modules
DEFAULT_CONFIG = ValidationConfig()


def get_validation_config(args: Optional[Any] = None) -> ValidationConfig:
    """
    Get validation configuration instance.
    
    This function provides a consistent interface for obtaining configuration
    across all scrapers and validation components.
    
    Args:
        args: Optional command-line arguments to override defaults
        
    Returns:
        ValidationConfig instance
    """
    if args:
        return ValidationConfig.create_from_args(args)
    return DEFAULT_CONFIG


def add_validation_args(parser) -> None:
    """
    Add validation-related command-line arguments to an ArgumentParser.
    
    This function allows scrapers to easily add validation configuration
    options to their existing argument parsers.
    
    Args:
        parser: argparse.ArgumentParser instance
    """
    validation_group = parser.add_argument_group('validation options')
    
    validation_group.add_argument(
        '--validation-quality-score',
        type=float,
        default=DEFAULT_CONFIG.min_data_quality_score,
        help=f'Minimum data quality score for successful validation (default: {DEFAULT_CONFIG.min_data_quality_score})'
    )
    
    validation_group.add_argument(
        '--validation-required-fields',
        default=','.join(DEFAULT_CONFIG.min_required_fields),
        help=f'Comma-separated list of required fields (default: {",".join(DEFAULT_CONFIG.min_required_fields)})'
    )
    
    validation_group.add_argument(
        '--validation-timeout',
        type=int,
        default=DEFAULT_CONFIG.validation_timeout,
        help=f'Maximum validation timeout in seconds (default: {DEFAULT_CONFIG.validation_timeout})'
    )
    
    validation_group.add_argument(
        '--enable-validation-cache',
        action='store_true',
        default=DEFAULT_CONFIG.enable_caching,
        help='Enable validation result caching'
    )
    
    validation_group.add_argument(
        '--disable-validation-cache',
        dest='enable_validation_cache',
        action='store_false',
        help='Disable validation result caching'
    )


# Example usage and environment variable documentation
if __name__ == "__main__":
    print("=== Validation Configuration System ===")
    print()
    
    config = ValidationConfig()
    print("Current Configuration:")
    for key, value in config.to_dict().items():
        print(f"  {key}: {value}")
    
    print()
    print("Environment Variables:")
    print("  SCRAPER_MIN_DATA_QUALITY_SCORE=0.8")
    print("  SCRAPER_MIN_REQUIRED_FIELDS=title,price")
    print("  SCRAPER_MAX_PLACEHOLDER_RATIO=0.2")
    print("  SCRAPER_VALIDATION_TIMEOUT=45")
    print("  SCRAPER_ENABLE_CACHING=False")
    print("  SCRAPER_LOG_LEVEL=DEBUG")
    print()
    print("Example Integration:")
    print("  from validation_config import get_validation_config, add_validation_args")
    print("  config = get_validation_config(args)")
    print("  scraper_config = config.get_scraper_specific_config('playwright')")