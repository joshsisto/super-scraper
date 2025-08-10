# Validator Implementation Plan

This document outlines the plan for creating and integrating a `ScrapingValidator` module into the Super Scraper Suite.

## 1. Proposed Validator Code

Below is the complete Python code for the proposed `ScrapingValidator` class. This class is self-contained and designed to be easily integrated into all three existing scrapers.

```python
import re
from typing import List, Dict, Any, Tuple, Optional

# A generic response object to define the expected interface
class GenericResponse:
    """A simple class to mimic response objects from different libraries."""
    def __init__(self, status_code: int, headers: Dict, text: str, url: str):
        self.status_code = status_code
        self.headers = {k.lower(): v for k, v in headers.items()} # Headers are case-insensitive
        self.text = text
        self.url = url

class ScrapingValidator:
    """
    An intelligent validator to determine the outcome of a scraping attempt.

    This class provides methods to:
    1. Validate the integrity and format of successfully scraped data.
    2. Detect various forms of blocking (e.g., HTTP errors, CAPTCHAs).
    3. Identify the presence of common anti-bot services.
    """

    # Common anti-bot service identifiers
    BOT_DETECTION_SIGNATURES = {
        "Cloudflare": {
            "headers": ["cf-ray", "cf-cache-status", "__cfduid"],
            "server": "cloudflare",
            "body_text": ["challenge-platform", "why_am_i_blocked", "checking_your_browser"]
        },
        "Akamai": {
            "headers": ["x-akamai-transformed"],
            "server": "AkamaiGHost",
            "body_text": ["akamai_error_reference"]
        },
        "PerimeterX": {
            "headers": ["_px_"],
            "server": "",
            "body_text": ["px-captcha", "perimeterx"]
        },
        "Imperva/Incapsula": {
            "headers": ["x-iinfo", "incap_ses"],
            "server": "",
            "body_text": ["incapsula_support_id"]
        }
    }
    
    # Fields required for a valid item
    REQUIRED_FIELDS = {"title", "price"}

    def __init__(self, required_fields: Optional[set] = None):
        """
        Initializes the validator.

        Args:
            required_fields (Optional[set]): A set of field names that must be present 
                                             in each scraped item for it to be considered valid. 
                                             Defaults to {"title", "price"}.
        """
        self.required_fields = required_fields or self.REQUIRED_FIELDS

    def validate_data(self, items: List[Dict[str, Any]]) -> Tuple[bool, str]:
        """
        Validates a list of scraped items against a set of rules.

        Checks for:
        - Presence of required fields.
        - Non-empty values for required fields.
        - Correct data types (e.g., price should be a number).

        Args:
            items (List[Dict[str, Any]]): A list of dictionaries, where each dictionary 
                                          represents a scraped item.

        Returns:
            Tuple[bool, str]: A tuple containing a boolean indicating overall validity
                              and a string with a report of any issues found.
        """
        if not items:
            return (False, "Validation failed: No items were provided.")

        errors = []
        for i, item in enumerate(items):
            # Check for missing required fields
            missing_fields = self.required_fields - set(item.keys())
            if missing_fields:
                errors.append(f"Item {i} ('{item.get('title', 'N/A')}') is missing fields: {', '.join(missing_fields)}")
                continue

            # Check for empty values and correct types
            for field in self.required_fields:
                value = item.get(field)
                if value is None or str(value).strip() == "":
                    errors.append(f"Item {i} ('{item.get('title', 'N/A')}') has an empty value for required field: '{field}'")
                
                if field == 'price' and not isinstance(value, (int, float)):
                    errors.append(f"Item {i} ('{item.get('title', 'N/A')}') has an invalid type for 'price'. Expected number, got {type(value).__name__}.")

        if errors:
            report = "Data validation failed with the following errors:
- " + "
- ".join(errors)
            return (False, report)

        return (True, f"Data validation successful for {len(items)} items.")

    def check_for_block(self, response: GenericResponse) -> Tuple[bool, str]:
        """
        Checks if the scraper was blocked based on the HTTP response.

        Detects:
        - Blocking HTTP status codes (403, 429, 503).
        - Presence of CAPTCHA-related keywords.
        - Redirection to login or error pages.

        Args:
            response (GenericResponse): A response object with `status_code`, `text`, and `url` attributes.

        Returns:
            Tuple[bool, str]: A tuple containing a boolean (True if blocked) and a
                              string describing the reason.
        """
        # 1. Check status codes
        if response.status_code in [403, 429, 503]:
            return (True, f"Block detected: Received HTTP status code {response.status_code}")

        # 2. Check for CAPTCHA in page content
        if re.search(r'captcha|are you a robot', response.text, re.IGNORECASE):
            return (True, "Block detected: CAPTCHA challenge found on page.")

        # 3. Check for redirection to login/denied pages
        if re.search(r'login|access denied|error', response.url, re.IGNORECASE):
            return (True, f"Block detected: Redirected to a potential block page: {response.url}")
            
        return (False, "No block detected.")

    def identify_bot_protection(self, response: GenericResponse) -> Optional[str]:
        """
        Infers the presence of a known anti-bot service from the response.

        Inspects response headers, server name, and body content for signatures
        of services like Cloudflare, Akamai, etc.

        Args:
            response (GenericResponse): A response object with `status_code`, `headers`, and `text` attributes.

        Returns:
            Optional[str]: The name of the detected anti-bot service, or None if none are identified.
        """
        response_headers = response.headers.keys()
        server_name = response.headers.get("server", "").lower()

        for service, signatures in self.BOT_DETECTION_SIGNATURES.items():
            # Check server name
            if signatures["server"] and signatures["server"] in server_name:
                return service
            
            # Check headers
            if any(h in response_headers for h in signatures["headers"]):
                return service

            # Check body content
            if any(re.search(s, response.text, re.IGNORECASE) for s in signatures["body_text"]):
                return service
        
        return None

```

## 2. Library Recommendations

No new external libraries are required. The proposed `ScrapingValidator` is built using Python's standard libraries (`re`, `typing`). It is designed to work with the response objects and data structures already available in the project's existing libraries (Scrapy, Playwright, Requests).

## 3. Integration Guide

The `ScrapingValidator` should be saved in a new file, `super_scraper/validator.py`, and integrated into each scraper as follows.

### Step 1: Create the Validator File

Create a new file: `/home/josh/Documents/projects/super-scraper/super_scraper/validator.py` and paste the code from Section 1 into it. Also, create an `__init__.py` file in the same directory if it doesn't exist to make it a package.

### Step 2: Integration with Scrapy (`run_scraper.py`)

The validator should be integrated as a new Scrapy pipeline.

**A. Modify `super_scraper/pipelines.py`:**

Add the `ValidatorPipeline` to this file. This pipeline will run *after* the `DataValidationPipeline` to ensure data types are already cleaned.

```python
# In /home/josh/Documents/projects/super-scraper/super_scraper/pipelines.py
# ... (existing pipelines) ...
from .validator import ScrapingValidator, GenericResponse

class ValidatorPipeline:
    """
    A pipeline to perform advanced validation on scraped items and responses.
    """
    def __init__(self):
        self.validator = ScrapingValidator()
        self.items_buffer = []

    def process_item(self, item, spider):
        self.items_buffer.append(item)
        return item

    def close_spider(self, spider):
        # Create a response object from the last known response in the spider
        # Note: This is a simplification. For per-response checks, this logic
        # would need to be in a spider middleware.
        if hasattr(spider, 'latest_response'):
            response = spider.latest_response
            generic_response = GenericResponse(response.status, response.headers, response.text, response.url)

            # Check for blocking
            is_blocked, block_reason = self.validator.check_for_block(generic_response)
            if is_blocked:
                spider.logger.error(f"Scraping was likely blocked. Reason: {block_reason}")

            # Identify bot protection
            protection = self.validator.identify_bot_protection(generic_response)
            if protection:
                spider.logger.warning(f"Detected anti-bot service: {protection}")

        # Validate all collected data at the end
        if self.items_buffer:
            is_valid, report = self.validator.validate_data(self.items_buffer)
            if not is_valid:
                spider.logger.error(report)
            else:
                spider.logger.info(report)

```

**B. Modify `super_scraper/spiders/universal.py`:**

Store the latest response on the spider instance so the pipeline can access it.

```python
# In /home/josh/Documents/projects/super-scraper/super_scraper/spiders/universal.py
# ... (inside UniversalSpider class) ...
    def parse(self, response):
        """
        Main parsing logic for the spider.
        It extracts data from the current page and follows pagination.
        """
        self.latest_response = response # <-- ADD THIS LINE
        self.logger.info(f"Parsing page: {response.url}")
        # ... (rest of the method) ...
```

**C. Modify `super_scraper/settings.py`:**

Activate the new pipeline. Add it after the `DataValidationPipeline`.

```python
# In /home/josh/Documents/projects/super-scraper/super_scraper/settings.py
ITEM_PIPELINES = {
   'super_scraper.pipelines.DataValidationPipeline': 300,
   'super_scraper.pipelines.DuplicateFilterPipeline': 400,
   'super_scraper.pipelines.ValidatorPipeline': 500, # <-- ADD THIS LINE
}
```

### Step 3: Integration with Playwright (`run_playwright_scraper.py`)

Instantiate the validator in the `PlaywrightScraper` class and use it after page loads and before saving.

**A. Modify `run_playwright_scraper.py`:**

```python
# In /home/josh/Documents/projects/super-scraper/run_playwright_scraper.py
# ... (imports) ...
from super_scraper.validator import ScrapingValidator, GenericResponse

# ... (inside PlaywrightScraper class) ...
    def __init__(self, url, ...):
        # ... (existing code) ...
        self.validator = ScrapingValidator() # <-- ADD THIS LINE

    def scrape_page(self, page, url):
        # ... (existing code) ...
        try:
            self.logger.debug(f"Navigating to {url}")
            response = page.goto(url, wait_until="domcontentloaded", timeout=60000) # <-- CAPTURE RESPONSE
            
            if response:
                generic_response = GenericResponse(response.status, response.headers(), response.text(), response.url)
                
                # Perform validation checks
                is_blocked, reason = self.validator.check_for_block(generic_response)
                if is_blocked:
                    self.logger.error(f"Scraping blocked on {url}. Reason: {reason}")
                    return # Stop scraping this page

                protection = self.validator.identify_bot_protection(generic_response)
                if protection:
                    self.logger.warning(f"Detected anti-bot service on {url}: {protection}")

            # ... (rest of the method) ...

    def save_results(self):
        # ... (existing code before saving) ...
        
        # Validate data before saving
        is_valid, report = self.validator.validate_data(self.scraped_items)
        if not is_valid:
            self.logger.error(f"Data validation failed, results may be compromised. {report}")
        else:
            self.logger.info(report)

        df.to_csv(output_path, index=False)
        # ... (rest of the method) ...
```

### Step 4: Integration with Pydoll (`run_pydoll_scraper.py`)

The integration is similar for both browser and requests mode.

**A. Modify `run_pydoll_scraper.py`:**

```python
# In /home/josh/Documents/projects/super-scraper/run_pydoll_scraper.py
# ... (imports) ...
from super_scraper.validator import ScrapingValidator, GenericResponse

# ... (inside PydollScraper class) ...
    def __init__(self, url, ...):
        # ... (existing code) ...
        self.validator = ScrapingValidator() # <-- ADD THIS LINE

    def try_browser_mode(self):
        # ... (inside the while loop) ...
        response = doll.get(current_url)
        generic_response = GenericResponse(response.status_code, response.headers, response.text, response.url)
        
        # Perform validation checks
        is_blocked, reason = self.validator.check_for_block(generic_response)
        if is_blocked:
            self.logger.error(f"Scraping blocked on {current_url}. Reason: {reason}")
            break # Exit loop

        # ... (rest of the method) ...

    def fallback_requests_mode(self):
        # ... (inside the while loop and try block) ...
        response = requests.get(current_url, headers=headers, timeout=30)
        response.raise_for_status()
        generic_response = GenericResponse(response.status_code, response.headers, response.text, response.url)

        # Perform validation checks
        is_blocked, reason = self.validator.check_for_block(generic_response)
        if is_blocked:
            self.logger.error(f"Scraping blocked on {current_url}. Reason: {reason}")
            break # Exit loop

        # ... (rest of the method) ...

    def save_to_csv(self):
        # ... (existing code before saving) ...
        
        # Validate data before saving
        is_valid, report = self.validator.validate_data(self.scraped_items)
        if not is_valid:
            self.logger.error(f"Data validation failed, results may be compromised. {report}")
        else:
            self.logger.info(report)
            
        df.to_csv(output_path, index=False)
        # ... (rest of the method) ...
```

## 4. Usage Examples

Here is how you could use the `ScrapingValidator` methods independently.

```python
# Assume validator has been imported and instantiated
# from super_scraper.validator import ScrapingValidator, GenericResponse
# validator = ScrapingValidator()

# --- Example 1: Successful Data Validation ---
valid_items = [
    {'title': 'Product A', 'price': 19.99, 'sku': 'A123'},
    {'title': 'Product B', 'price': 25.50, 'sku': 'B456'}
]
is_valid, report = validator.validate_data(valid_items)
print(f"Validation Result: {is_valid}
Report: {report}
")
# Expected Output:
# Validation Result: True
# Report: Data validation successful for 2 items.

# --- Example 2: Failed Data Validation ---
invalid_items = [
    {'title': 'Product C', 'price': None}, # Missing price
    {'price': 99.00, 'sku': 'C789'} # Missing title
]
is_valid, report = validator.validate_data(invalid_items)
print(f"Validation Result: {is_valid}
Report: {report}
")
# Expected Output:
# Validation Result: False
# Report: Data validation failed with the following errors:
# - Item 0 ('Product C') has an empty value for required field: 'price'
# - Item 0 ('Product C') has an invalid type for 'price'. Expected number, got NoneType.
# - Item 1 ('N/A') is missing fields: title

# --- Example 3: Block Detection (CAPTCHA) ---
captcha_html = "<html><body>Please solve this CAPTCHA to continue.</body></html>"
blocked_response = GenericResponse(200, {}, captcha_html, "http://example.com/products")
is_blocked, reason = validator.check_for_block(blocked_response)
print(f"Block Detection Result: {is_blocked}
Reason: {reason}
")
# Expected Output:
# Block Detection Result: True
# Reason: Block detected: CAPTCHA challenge found on page.

# --- Example 4: Bot Detection (Cloudflare) ---
cf_headers = {'Server': 'cloudflare', 'CF-RAY': '12345-abc'}
cf_response = GenericResponse(200, cf_headers, "<html>...</html>", "http://example.com")
protection = validator.identify_bot_protection(cf_response)
print(f"Bot Protection Result: {protection}
")
# Expected Output:
# Bot Protection Result: Cloudflare
```
