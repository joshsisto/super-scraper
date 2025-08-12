"""
ScrapingValidator - Intelligent validation for web scraping results

Provides three core capabilities:
1. Successful Data Validation - Confirms meaningful data extraction
2. Block Detection - Identifies when scraper is being blocked
3. Bot Detection System Identification - Infers anti-bot services
"""

import re
import logging
import configparser
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import pandas as pd
from enum import Enum

@dataclass
class ValidationResult:
    """Container for validation results with detailed analysis"""
    is_successful: bool
    is_blocked: bool
    bot_detection_system: Optional[str]
    confidence_score: float  # 0.0 to 1.0
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

class BlockType(Enum):
    """Types of blocking detected"""
    NONE = "none"
    HTTP_ERROR = "http_error"
    CAPTCHA = "captcha"
    LOGIN_REQUIRED = "login_required"
    ACCESS_DENIED = "access_denied"
    RATE_LIMITED = "rate_limited"
    GEOGRAPHIC_BLOCK = "geographic_block"

class BotDetectionSystem(Enum):
    """Known bot detection systems"""
    NONE = "none"
    CLOUDFLARE = "cloudflare"
    AKAMAI = "akamai"
    PERIMETERX = "perimeterx"
    INCAPSULA = "incapsula"
    DISTIL = "distil"
    DATADOME = "datadome"
    FASTLY = "fastly"
    CUSTOM = "custom_system"

class ScrapingValidator:
    """
    Intelligent validator for web scraping results.
    
    Provides three core capabilities:
    1. Successful Data Validation - Confirms meaningful data extraction
    2. Block Detection - Identifies when scraper is being blocked
    3. Bot Detection System Identification - Infers anti-bot services
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None, config_path: str = 'config.ini'):
        self.logger = logger or logging.getLogger(__name__)
        
        # Load configuration from file
        self._load_config(config_path)
        
        # Bot detection system signatures
        self._bot_detection_signatures = self._load_bot_signatures()
        
        # Common blocking indicators
        self._blocking_indicators = self._load_blocking_indicators()

    def _load_config(self, config_path: str):
        """Loads configuration from an INI file."""
        config = configparser.ConfigParser()
        try:
            if not config.read(config_path):
                self.logger.warning(f"Config file not found at {config_path}. Using default validation thresholds.")
                # Set default values if config file is not found
                self.min_data_quality_score = 0.7
                self.min_required_fields = ['title']
                self.max_placeholder_ratio = 0.3
                return

            validator_config = config['validator']

            # Load data validation thresholds
            self.min_data_quality_score = validator_config.getfloat('min_data_quality_score', 0.7)

            required_fields_str = validator_config.get('min_required_fields', 'title')
            self.min_required_fields = [field.strip() for field in required_fields_str.split(',')]

            self.max_placeholder_ratio = validator_config.getfloat('max_placeholder_ratio', 0.3)

            self.logger.info("Validator configuration loaded successfully.")

        except Exception as e:
            self.logger.error(f"Error loading config file: {e}. Using default values.")
            # Fallback to defaults in case of any error
            self.min_data_quality_score = 0.7
            self.min_required_fields = ['title']
            self.max_placeholder_ratio = 0.3

    def validate_scraping_result(self, 
                                response_data: Dict[str, Any],
                                scraped_data: Optional[List[Dict]] = None,
                                csv_file_path: Optional[str] = None) -> ValidationResult:
        """
        Main validation method that analyzes scraping outcome.
        
        Args:
            response_data: Dict containing response information:
                - status_code: HTTP status code
                - headers: Response headers dict
                - content: Raw response content (optional)
                - url: Final URL after redirects
                - response_time: Time taken for request
            scraped_data: List of extracted items (optional)
            csv_file_path: Path to generated CSV file (optional)
            
        Returns:
            ValidationResult object with comprehensive analysis
        """
        result = ValidationResult(
            is_successful=False,
            is_blocked=False,
            bot_detection_system=None,
            confidence_score=0.0
        )
        
        try:
            # Step 1: Check for blocking indicators
            block_analysis = self._analyze_blocking(response_data)
            result.is_blocked = block_analysis['is_blocked']
            if result.is_blocked:
                result.issues.extend(block_analysis['issues'])
                result.metadata['block_type'] = block_analysis['block_type']
            
            # Step 2: Detect bot detection systems
            bot_detection = self._detect_bot_system(response_data)
            result.bot_detection_system = bot_detection['system']
            if bot_detection['system'] != BotDetectionSystem.NONE:
                result.metadata['bot_system_confidence'] = bot_detection['confidence']
                result.metadata['bot_indicators'] = bot_detection['indicators']
            
            # Step 3: Validate data quality (if not blocked)
            if not result.is_blocked:
                data_validation = self._validate_data_quality(scraped_data, csv_file_path)
                result.is_successful = data_validation['is_valid']
                result.confidence_score = data_validation['quality_score']
                result.metadata['data_stats'] = data_validation['stats']
                
                if not result.is_successful:
                    result.issues.extend(data_validation['issues'])
                else:
                    result.warnings.extend(data_validation['warnings'])
            
            # Step 4: Calculate overall confidence
            result.confidence_score = self._calculate_confidence(result, response_data)
            
            self.logger.info(f"Validation complete: Success={result.is_successful}, "
                           f"Blocked={result.is_blocked}, "
                           f"BotSystem={result.bot_detection_system}, "
                           f"Confidence={result.confidence_score:.2f}")
            
        except Exception as e:
            self.logger.error(f"Validation error: {str(e)}")
            result.issues.append(f"Validation failed: {str(e)}")
            result.confidence_score = 0.0
        
        return result

    def _analyze_blocking(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyzes response for blocking indicators"""
        analysis = {
            'is_blocked': False,
            'block_type': BlockType.NONE,
            'issues': [],
            'confidence': 0.0
        }
        
        status_code = response_data.get('status_code', 0)
        headers = response_data.get('headers', {})
        content = response_data.get('content', '')
        url = response_data.get('url', '')
        
        # HTTP status code analysis
        blocking_status_codes = {
            403: ('Access forbidden', BlockType.ACCESS_DENIED, 0.9),
            429: ('Rate limited', BlockType.RATE_LIMITED, 0.95),
            503: ('Service unavailable - possible blocking', BlockType.HTTP_ERROR, 0.8),
            401: ('Authentication required', BlockType.LOGIN_REQUIRED, 0.9),
            451: ('Unavailable for legal reasons', BlockType.GEOGRAPHIC_BLOCK, 0.9)
        }
        
        if status_code in blocking_status_codes:
            issue, block_type, confidence = blocking_status_codes[status_code]
            analysis['is_blocked'] = True
            analysis['block_type'] = block_type
            analysis['issues'].append(f"HTTP {status_code}: {issue}")
            analysis['confidence'] = confidence
            return analysis
        
        # Content-based blocking detection
        if content:
            try:
                soup = BeautifulSoup(content, 'html.parser')
                page_text = soup.get_text().lower()
                page_title = soup.title.string.lower() if soup.title else ''
                
                # Use patterns from loaded blocking indicators
                for category, patterns in self._blocking_indicators.items():
                    for indicator in patterns:
                        # Use regex for more flexible matching
                        if re.search(r'\b' + re.escape(indicator) + r'\b', page_text, re.IGNORECASE) or \
                           re.search(r'\b' + re.escape(indicator) + r'\b', page_title, re.IGNORECASE):

                            block_type = self._get_block_type_from_category(category)
                            analysis['is_blocked'] = True
                            analysis['block_type'] = block_type
                            analysis['issues'].append(f'Content blocking detected: "{indicator}"')
                            analysis['confidence'] = max(analysis['confidence'], 0.85)
                            # Found a match in this category, move to the next
                            break
                    if analysis['is_blocked']:
                        # If a block is already detected, we can break early
                        # from checking other categories if we want. For now, we continue
                        # to potentially find more specific indicators.
                        pass

            except Exception as e:
                self.logger.warning(f"Error parsing HTML content for blocking detection: {str(e)}")
                # Fallback to simple text search if BeautifulSoup fails
                for category, patterns in self._blocking_indicators.items():
                    for indicator in patterns:
                        if indicator in content.lower():
                            block_type = self._get_block_type_from_category(category)
                            analysis['is_blocked'] = True
                            analysis['block_type'] = block_type
                            analysis['issues'].append(f'Basic blocking pattern detected: "{indicator}"')
                            analysis['confidence'] = max(analysis['confidence'], 0.7)
                            break
        
        # URL-based blocking detection
        blocking_url_patterns = [
            r'/login|/signin|/auth',
            r'/blocked|/banned|/denied',
            r'/captcha|/challenge',
            r'/error|/403|/404'
        ]
        
        for pattern in blocking_url_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                analysis['is_blocked'] = True
                analysis['issues'].append(f"Redirected to blocking page: {url}")
                analysis['confidence'] = max(analysis['confidence'], 0.7)
        
        # Header-based blocking indicators
        suspicious_headers = {
            'cf-ray': ('Cloudflare detected', 0.6),
            'x-blocked-by': ('Explicit blocking header', 0.9),
            'x-access-denied': ('Access denied header', 0.9)
        }
        
        for header, (message, confidence) in suspicious_headers.items():
            if header.lower() in [k.lower() for k in headers.keys()]:
                analysis['issues'].append(message)
                analysis['confidence'] = max(analysis['confidence'], confidence)
        
        return analysis

    def _detect_bot_system(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """Detects the presence of bot detection systems"""
        detection = {
            'system': BotDetectionSystem.NONE,
            'confidence': 0.0,
            'indicators': []
        }
        
        headers = response_data.get('headers', {})
        content = response_data.get('content', '')
        
        # Header-based detection
        for system, signatures in self._bot_detection_signatures['headers'].items():
            for header_pattern, confidence in signatures:
                for header_name in headers.keys():
                    if re.search(header_pattern, header_name, re.IGNORECASE):
                        if confidence > detection['confidence']:
                            detection['system'] = BotDetectionSystem(system)
                            detection['confidence'] = confidence
                        detection['indicators'].append(f"Header: {header_name}")
        
        # Content-based detection
        if content:
            for system, patterns in self._bot_detection_signatures['content'].items():
                for pattern, confidence in patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        if confidence > detection['confidence']:
                            detection['system'] = BotDetectionSystem(system)
                            detection['confidence'] = confidence
                        detection['indicators'].append(f"Content pattern: {pattern}")
        
        return detection

    def _get_block_type_from_category(self, category: str) -> BlockType:
        """Maps blocking indicator categories to BlockType enum values"""
        category_mapping = {
            'captcha_indicators': BlockType.CAPTCHA,
            'login_indicators': BlockType.LOGIN_REQUIRED,
            'access_denied_indicators': BlockType.ACCESS_DENIED,
            'rate_limit_indicators': BlockType.RATE_LIMITED
        }
        return category_mapping.get(category, BlockType.HTTP_ERROR)

    def _validate_data_quality(self, 
                              scraped_data: Optional[List[Dict]] = None,
                              csv_file_path: Optional[str] = None) -> Dict[str, Any]:
        """Validates the quality and completeness of scraped data"""
        validation = {
            'is_valid': False,
            'quality_score': 0.0,
            'issues': [],
            'warnings': [],
            'stats': {}
        }
        
        # Load data from CSV if provided and no direct data
        if scraped_data is None and csv_file_path:
            try:
                df = pd.read_csv(csv_file_path)
                scraped_data = df.to_dict('records')
            except Exception as e:
                validation['issues'].append(f"Could not load CSV file: {str(e)}")
                return validation
        
        if not scraped_data:
            validation['issues'].append("No scraped data provided for validation")
            return validation
        
        # Basic data statistics
        total_items = len(scraped_data)
        validation['stats']['total_items'] = total_items
        
        if total_items == 0:
            validation['issues'].append("No items were extracted")
            return validation
        
        # Field completeness analysis
        expected_fields = ['title', 'price', 'description', 'image_url', 'stock_availability', 'sku']
        field_completeness = {}
        
        for field in expected_fields:
            non_empty_count = sum(1 for item in scraped_data 
                                if item.get(field) and str(item[field]).strip() not in ['', 'None', 'null', 'N/A'])
            completeness = non_empty_count / total_items
            field_completeness[field] = {
                'completeness': completeness,
                'count': non_empty_count
            }
        
        validation['stats']['field_completeness'] = field_completeness
        
        # Required field validation
        missing_required = []
        for field in self.min_required_fields:
            if field_completeness.get(field, {}).get('completeness', 0) == 0:
                missing_required.append(field)
        
        if missing_required:
            validation['issues'].append(f"Missing required fields: {missing_required}")
            return validation
        
        # Data quality scoring
        quality_factors = []
        
        # 1. Title quality (most important)
        title_completeness = field_completeness.get('title', {}).get('completeness', 0)
        title_quality = self._analyze_title_quality(scraped_data)
        quality_factors.append(('title_completeness', title_completeness, 0.3))
        quality_factors.append(('title_quality', title_quality, 0.2))
        
        # 2. Price quality
        price_completeness = field_completeness.get('price', {}).get('completeness', 0)
        price_quality = self._analyze_price_quality(scraped_data)
        quality_factors.append(('price_completeness', price_completeness, 0.2))
        quality_factors.append(('price_quality', price_quality, 0.1))
        
        # 3. Overall field diversity
        filled_fields = sum(1 for field, data in field_completeness.items() 
                           if data['completeness'] > 0)
        field_diversity = filled_fields / len(expected_fields)
        quality_factors.append(('field_diversity', field_diversity, 0.1))
        
        # 4. Data consistency
        consistency_score = self._analyze_data_consistency(scraped_data)
        quality_factors.append(('consistency', consistency_score, 0.1))
        
        # Calculate weighted quality score
        total_score = sum(score * weight for name, score, weight in quality_factors)
        validation['quality_score'] = total_score
        validation['stats']['quality_factors'] = {name: score for name, score, weight in quality_factors}
        
        # Determine if data is valid
        validation['is_valid'] = total_score >= self.min_data_quality_score
        
        # Generate warnings for low-quality data
        if total_score < 0.9:
            validation['warnings'].append(f"Data quality score is moderate: {total_score:.2f}")
        
        if title_completeness < 0.8:
            validation['warnings'].append(f"Title completeness is low: {title_completeness:.2f}")
        
        if price_completeness < 0.5:
            validation['warnings'].append(f"Price completeness is low: {price_completeness:.2f}")
        
        return validation

    def _analyze_title_quality(self, scraped_data: List[Dict]) -> float:
        """Analyzes the quality of extracted titles"""
        if not scraped_data:
            return 0.0
        
        titles = [item.get('title', '') for item in scraped_data if item.get('title')]
        if not titles:
            return 0.0
        
        quality_score = 0.0
        total_titles = len(titles)
        
        # Check for placeholder content
        placeholder_patterns = [
            r'^title$|^product$|^item$',  # Generic placeholders
            r'^loading|^undefined|^null|^none',  # Loading/error states
            r'^\s*$',  # Empty or whitespace only
            r'^[0-9]+$',  # Numbers only (likely IDs, not titles)
        ]
        
        non_placeholder_count = 0
        for title in titles:
            title_str = str(title).strip().lower()
            is_placeholder = any(re.match(pattern, title_str) for pattern in placeholder_patterns)
            if not is_placeholder and len(title_str) > 3:  # Reasonable length
                non_placeholder_count += 1
        
        # Basic quality: ratio of non-placeholder titles
        basic_quality = non_placeholder_count / total_titles
        
        # Length quality: titles should have reasonable length
        avg_length = sum(len(str(title)) for title in titles) / total_titles
        length_quality = min(1.0, max(0.0, (avg_length - 5) / 50))  # 5-55 char range
        
        # Diversity quality: titles should not be too repetitive
        unique_titles = len(set(str(title).lower().strip() for title in titles))
        diversity_quality = unique_titles / total_titles if total_titles > 1 else 1.0
        
        # Combined quality score
        quality_score = (basic_quality * 0.5 + length_quality * 0.3 + diversity_quality * 0.2)
        
        return quality_score

    def _analyze_price_quality(self, scraped_data: List[Dict]) -> float:
        """
        Analyzes the quality of extracted prices.
        Assumes prices have been pre-processed into numeric types by a pipeline.
        """
        if not scraped_data:
            return 0.0
        
        prices = [item.get('price') for item in scraped_data if item.get('price') is not None]
        
        if not prices:
            return 0.0
        
        # Validate that prices are proper numeric types (int or float)
        valid_price_count = sum(1 for price in prices if isinstance(price, (int, float)) and price >= 0)
        
        return valid_price_count / len(prices)

    def _analyze_data_consistency(self, scraped_data: List[Dict]) -> float:
        """Analyzes consistency patterns in the scraped data"""
        if len(scraped_data) < 2:
            return 1.0  # Single item is always consistent
        
        consistency_factors = []
        
        # URL consistency (should all be from similar structure)
        image_urls = [item.get('image_url', '') for item in scraped_data if item.get('image_url')]
        if image_urls:
            # Check if URLs follow similar patterns
            domains = set()
            for url in image_urls:
                try:
                    parsed = urlparse(str(url))
                    if parsed.netloc:
                        domains.add(parsed.netloc)
                except:
                    pass
            
            # Most images should come from same domain
            if domains:
                most_common_domain_count = max(sum(1 for url in image_urls if domain in str(url)) 
                                             for domain in domains)
                url_consistency = most_common_domain_count / len(image_urls)
                consistency_factors.append(url_consistency)
        
        # Price format consistency
        prices = [item.get('price') for item in scraped_data if item.get('price')]
        if len(prices) > 1:
            price_types = {}
            for price in prices:
                price_type = type(price).__name__
                price_types[price_type] = price_types.get(price_type, 0) + 1
            
            most_common_type_count = max(price_types.values())
            price_consistency = most_common_type_count / len(prices)
            consistency_factors.append(price_consistency)
        
        # Return average consistency score
        return sum(consistency_factors) / len(consistency_factors) if consistency_factors else 0.8

    def _calculate_confidence(self, result: ValidationResult, response_data: Dict[str, Any]) -> float:
        """Calculates overall confidence in the validation result"""
        confidence_factors = []
        
        # HTTP response confidence
        status_code = response_data.get('status_code', 0)
        if 200 <= status_code < 300:
            confidence_factors.append(0.9)
        elif 400 <= status_code < 500:
            confidence_factors.append(0.8)  # Client errors are usually definitive
        else:
            confidence_factors.append(0.6)
        
        # Bot detection confidence
        if result.bot_detection_system != BotDetectionSystem.NONE:
            bot_confidence = result.metadata.get('bot_system_confidence', 0.5)
            confidence_factors.append(bot_confidence)
        
        # Data validation confidence
        if 'data_stats' in result.metadata:
            data_confidence = result.metadata['data_stats'].get('quality_factors', {}).get('consistency', 0.5)
            confidence_factors.append(data_confidence)
        
        # Issue count factor - more issues = lower confidence
        issue_penalty = max(0.0, 1.0 - len(result.issues) * 0.1)
        confidence_factors.append(issue_penalty)
        
        # Return weighted average
        return sum(confidence_factors) / len(confidence_factors)

    def _load_bot_signatures(self) -> Dict[str, Dict[str, List[tuple]]]:
        """Loads bot detection system signatures"""
        return {
            'headers': {
                'cloudflare': [
                    (r'cf-ray', 0.9),
                    (r'cf-cache-status', 0.8),
                    (r'cf-request-id', 0.8),
                    (r'server.*cloudflare', 0.9),
                ],
                'akamai': [
                    (r'akamai', 0.9),
                    (r'x-akamai', 0.9),
                    (r'ak-', 0.7),
                ],
                'perimeterx': [
                    (r'x-px', 0.9),
                    (r'perimeterx', 0.9),
                ],
                'incapsula': [
                    (r'x-iinfo', 0.9),
                    (r'incap_ses', 0.9),
                    (r'incapsula', 0.8),
                ],
                'distil': [
                    (r'x-distil', 0.9),
                    (r'distil', 0.8),
                ],
                'datadome': [
                    (r'x-dd', 0.9),
                    (r'datadome', 0.9),
                ],
                'fastly': [
                    (r'fastly', 0.8),
                    (r'x-served-by.*fastly', 0.9),
                ]
            },
            'content': {
                'cloudflare': [
                    (r'ray.id.*[a-f0-9]{16}', 0.8),
                    (r'cloudflare', 0.6),
                    (r'checking.your.browser', 0.9),
                ],
                'akamai': [
                    (r'reference.*[0-9a-f]{8}\.[0-9a-f]{8}', 0.7),
                    (r'akamai', 0.6),
                ],
                'perimeterx': [
                    (r'px-.*captcha', 0.9),
                    (r'perimeterx', 0.7),
                ],
                'incapsula': [
                    (r'incap_ses_[0-9]+', 0.8),
                    (r'incapsula.incident', 0.9),
                ],
                'custom': [
                    (r'please.complete.the.security.check', 0.7),
                    (r'verify.you.are.human', 0.7),
                    (r'anti.?robot.validation', 0.7),
                ]
            }
        }

    def _load_blocking_indicators(self) -> Dict[str, List[str]]:
        """Loads common blocking indicators"""
        return {
            'captcha_indicators': [
                'captcha', 'recaptcha', 'hcaptcha', 'prove you are human',
                'verify you are not a robot', 'security check'
            ],
            'login_indicators': [
                'please log in', 'sign in required', 'authentication required',
                'please sign in', 'login to continue'
            ],
            'access_denied_indicators': [
                'access denied', 'forbidden', 'not authorized', 'permission denied',
                'you do not have permission', 'access restricted'
            ],
            'rate_limit_indicators': [
                'rate limit', 'too many requests', 'request limit exceeded',
                'temporarily unavailable', 'try again later'
            ]
        }

    # Utility methods for external integration
    
    def validate_csv_output(self, csv_file_path: str) -> ValidationResult:
        """Convenience method to validate CSV output file"""
        return self.validate_scraping_result(
            response_data={'status_code': 200, 'headers': {}, 'url': ''},
            csv_file_path=csv_file_path
        )
    
    def quick_response_check(self, status_code: int, headers: Dict[str, str], content: str = '') -> bool:
        """Quick method to check if response indicates blocking"""
        response_data = {
            'status_code': status_code,
            'headers': headers,
            'content': content,
            'url': ''
        }
        result = self.validate_scraping_result(response_data)
        return result.is_blocked
    
    def get_validation_summary(self, result: ValidationResult) -> str:
        """Generate human-readable summary of validation result"""
        summary_parts = []
        
        if result.is_successful:
            summary_parts.append("✓ Scraping successful")
        else:
            summary_parts.append("✗ Scraping failed")
        
        if result.is_blocked:
            block_type = result.metadata.get('block_type', 'unknown')
            summary_parts.append(f"⚠ Blocked ({block_type})")
        
        if result.bot_detection_system and result.bot_detection_system != BotDetectionSystem.NONE:
            summary_parts.append(f"🛡 Bot detection: {result.bot_detection_system.value}")
        
        summary_parts.append(f"Confidence: {result.confidence_score:.1%}")
        
        if result.issues:
            summary_parts.append(f"Issues: {len(result.issues)}")
        
        if result.warnings:
            summary_parts.append(f"Warnings: {len(result.warnings)}")
        
        return " | ".join(summary_parts)