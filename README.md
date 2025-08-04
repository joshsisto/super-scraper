# Super Scraper Suite

A comprehensive web scraping toolkit featuring three powerful scrapers: Scrapy-based, Playwright-based, and Pydoll-based. Each scraper is designed for different use cases while maintaining the same interface and output format.

## Overview of Scrapers

### 1. Scrapy-based Scraper (`run_scraper.py`)
- **Best for**: General web scraping with built-in features
- **Strengths**: Fast, concurrent requests, built-in retry logic, respects robots.txt
- **Use when**: Scraping standard HTML websites with good structure

### 2. Playwright-based Scraper (`run_playwright_scraper.py`)
- **Best for**: JavaScript-heavy sites and bot detection bypass
- **Strengths**: Handles dynamic content, anti-detection measures, browser automation
- **Use when**: Sites block traditional scrapers or require JavaScript rendering

### 3. Pydoll-based Scraper (`run_pydoll_scraper.py`)
- **Best for**: Flexible scraping with automatic fallback
- **Strengths**: Browser automation with requests-based fallback, works without Chrome
- **Use when**: You need a robust solution that works in various environments

## Common Features

All three scrapers share these features:
- **Dynamic URL Input**: Accept any target URL via command-line argument
- **Smart Data Extraction**: Automatically identifies and extracts common e-commerce data fields
- **Data Validation**: Cleaning and validation of scraped data
- **Duplicate Filtering**: Automatically filters out duplicate items
- **Robust Error Handling**: Comprehensive error handling with retry mechanisms
- **Detailed Logging**: Logs to both console and file for debugging
- **CSV Export**: Clean, well-structured CSV output with proper headers
- **Pagination Support**: Automatically follows pagination links
- **Organized Output**: Automatically creates timestamped directories for each scraping job
- **No Overwrites**: Each scrape creates a unique directory based on URL and timestamp

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/super_scraper.git
cd super_scraper
```

2. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. For Playwright scraper, install browser:
```bash
playwright install chromium
```

5. For Pydoll scraper (if not available via pip):
```bash
pip install git+https://github.com/autoscrape-labs/pydoll.git
```

## Usage

All scrapers share the same basic interface and create the same directory structure:

```
scraped_results/
└── domain_YYYYMMDD_HHMMSS/
    ├── scraped_data.csv    # Or your custom filename
    └── scraper.log         # Or playwright_scraper.log / pydoll_scraper.log
```

### 1. Scrapy-based Scraper

```bash
# Basic usage
python run_scraper.py --url "https://books.toscrape.com/"

# With custom output
python run_scraper.py --url "https://example.com" --output results.csv

# With debug logging
python run_scraper.py --url "https://example.com" --loglevel DEBUG
```

**Arguments:**
- `--url` (required): Target URL to scrape
- `--output` (optional): Output CSV filename (default: scraped_data.csv)
- `--loglevel` (optional): Logging level (default: INFO)

### 2. Playwright-based Scraper

```bash
# Basic usage
python run_playwright_scraper.py --url "https://books.toscrape.com/"

# With custom settings
python run_playwright_scraper.py --url "https://example.com" --output data.csv --max-pages 5

# With debug logging
python run_playwright_scraper.py --url "https://example.com" --loglevel DEBUG
```

**Arguments:**
- `--url` (required): Target URL to scrape
- `--output` (optional): Output CSV filename (default: scraped_data.csv)
- `--loglevel` (optional): Logging level (default: INFO)
- `--max-pages` (optional): Maximum pages to scrape (default: 10)

### 3. Pydoll-based Scraper

```bash
# Basic usage
python run_pydoll_scraper.py --url "https://books.toscrape.com/"

# With custom settings
python run_pydoll_scraper.py --url "https://example.com" --output data.csv --max-pages 5

# With debug logging
python run_pydoll_scraper.py --url "https://example.com" --loglevel DEBUG
```

**Arguments:**
- `--url` (required): Target URL to scrape
- `--output` (optional): Output CSV filename (default: scraped_data.csv)
- `--loglevel` (optional): Logging level (default: INFO)
- `--max-pages` (optional): Maximum pages to scrape (default: 10)

## Data Fields

The scraper extracts the following fields when available:

- **title**: The title/name of the item (string)
- **price**: The price of the item (float)
- **description**: A short description of the item (string, max 200 chars)
- **image_url**: The full URL of the item's image (string)
- **stock_availability**: Whether the item is in stock (boolean)
- **sku**: The Stock Keeping Unit identifier (string)

## Project Structure

```
super_scraper/
├── run_scraper.py              # Scrapy-based scraper CLI
├── run_playwright_scraper.py   # Playwright-based scraper CLI
├── run_pydoll_scraper.py       # Pydoll-based scraper CLI
├── scrapy.cfg                  # Scrapy configuration
├── requirements.txt            # Python dependencies
├── README.md                   # This file
│
├── scraped_results/           # All scraping outputs (created automatically)
│   └── domain_YYYYMMDD_HHMMSS/ # Timestamped directory for each scrape
│       ├── scraped_data.csv    # Scraped data (or custom filename)
│       └── *.log               # Log file (scraper.log, playwright_scraper.log, or pydoll_scraper.log)
│
├── super_scraper/             # Scrapy project package (used by run_scraper.py)
│   ├── __init__.py
│   ├── items.py               # Data structure definitions
│   ├── pipelines.py           # Data validation and processing
│   ├── settings.py            # Scrapy settings
│   │
│   └── spiders/               # Spider implementations
│       ├── __init__.py
│       └── universal.py       # Universal spider for any website
│
└── tests/                     # Unit tests (for Scrapy components)
    ├── __init__.py
    ├── test_spider.py         # Spider tests
    ├── test_pipelines.py      # Pipeline tests
    └── test_items.py          # Item tests
```

## Running Tests

Run all unit tests:

```bash
# From the project root directory
python -m unittest discover tests

# Or run specific test files
python -m unittest tests.test_spider
python -m unittest tests.test_pipelines
python -m unittest tests.test_items

# Run with verbose output
python -m unittest discover tests -v
```

## Scraper-Specific Details

### Scrapy-based Scraper

**Configuration:**
- Respects robots.txt rules
- Implements download delays (1 second between requests)
- Limits concurrent requests per domain
- Built-in retry mechanism for failed requests
- Auto-throttle for adaptive delays

**Data Pipeline:**
- DataValidationPipeline: Cleans and validates all fields
- DuplicateFilterPipeline: Removes duplicate items

### Playwright-based Scraper

**Features:**
- Headless browser automation (Chromium)
- Anti-detection measures (realistic browser fingerprints)
- JavaScript execution and dynamic content loading
- Automatic scrolling for lazy-loaded content
- Human-like delays between actions

**Requirements:**
- Chromium browser (installed via `playwright install chromium`)
- More resource-intensive than other scrapers

### Pydoll-based Scraper

**Features:**
- Primary mode: Browser automation with Pydoll
- Fallback mode: Requests + BeautifulSoup when browser unavailable
- Works without Chrome/Chromium installed
- Flexible and adaptable to different environments

**Behavior:**
- Attempts browser automation first
- Automatically falls back to HTTP requests if browser fails
- Maintains same data extraction logic in both modes

### Logging

Logs are written to both:
- Console output (for real-time monitoring)
- Log file in the timestamped output directory (for detailed debugging)

Log format includes timestamp, logger name, level, and message.

### Output Organization

The scraper automatically organizes output to prevent data loss:
- All outputs are saved in the `scraped_results` directory
- Each scraping job creates a unique subdirectory named `domain_YYYYMMDD_HHMMSS`
- Both the CSV data and log file are saved in this subdirectory
- Multiple scrapes of the same website won't overwrite previous results

## Example Output

The scraper produces a CSV file with the following structure:

```csv
title,price,description,image_url,stock_availability,sku
"Example Product",19.99,"A great product for testing","https://example.com/image.jpg",True,"SKU-123"
"Another Product",29.99,"Another description","https://example.com/image2.jpg",False,"SKU-456"
```

## Choosing the Right Scraper

| Use Case | Recommended Scraper | Why |
|----------|-------------------|-----|
| Standard HTML websites | Scrapy | Fast, efficient, built for web scraping |
| JavaScript-heavy sites | Playwright | Full browser rendering, handles dynamic content |
| Sites with bot detection | Playwright | Anti-detection measures, realistic browser behavior |
| Limited environment (no browser) | Pydoll | Falls back to requests when browser unavailable |
| Maximum compatibility | Pydoll | Works in most environments with automatic fallback |
| High-volume scraping | Scrapy | Best performance, concurrent requests |

## Troubleshooting

### Common Issues

1. **No items found**: 
   - For Scrapy: Customize selectors in `spiders/universal.py`
   - For Playwright/Pydoll: Check if site requires specific interactions

2. **Browser not found** (Playwright/Pydoll):
   - Playwright: Run `playwright install chromium`
   - Pydoll: Will automatically fall back to requests mode

3. **Rate limiting**: 
   - All scrapers implement delays
   - Increase delays or reduce concurrent requests if needed

4. **JavaScript required**:
   - Switch from Scrapy to Playwright or Pydoll

### Debug Mode

Run any scraper with debug logging:

```bash
python run_scraper.py --url "https://example.com" --loglevel DEBUG
python run_playwright_scraper.py --url "https://example.com" --loglevel DEBUG
python run_pydoll_scraper.py --url "https://example.com" --loglevel DEBUG
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This tool is for educational purposes only. Always respect website terms of service and robots.txt files. Ensure you have permission to scrape any website you target.