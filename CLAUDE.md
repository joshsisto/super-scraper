# Super Scraper Suite - Claude Context

## Project Overview
A comprehensive web scraping toolkit with three different scrapers:
1. **Scrapy-based** (`run_scraper.py`) - Fast, concurrent, standard HTML scraping
2. **Playwright-based** (`run_playwright_scraper.py`) - JavaScript-heavy sites, bot detection bypass
3. **Pydoll-based** (`run_pydoll_scraper.py`) - Flexible with automatic fallback

## Quick Commands

### Running Scrapers
```bash
# Scrapy scraper
python run_scraper.py --url "https://example.com" [--output filename.csv] [--loglevel DEBUG]

# Playwright scraper  
python run_playwright_scraper.py --url "https://example.com" [--output filename.csv] [--max-pages 5] [--loglevel DEBUG]

# Pydoll scraper
python run_pydoll_scraper.py --url "https://example.com" [--output filename.csv] [--max-pages 5] [--loglevel DEBUG]
```

### Testing
```bash
# Run all tests
python -m unittest discover tests

# Run specific tests
python -m unittest tests.test_spider
python -m unittest tests.test_pipelines  
python -m unittest tests.test_items
python -m unittest tests.test_playwright_scraper
python -m unittest tests.test_pydoll_scraper
python -m unittest tests.test_integration

# Verbose output
python -m unittest discover tests -v
```

### Installation/Setup
```bash
# Install dependencies
pip install -r requirements.txt

# For Playwright scraper
playwright install chromium

# For Pydoll (if needed)
pip install git+https://github.com/autoscrape-labs/pydoll.git
```

## Project Structure
```
super_scraper/
├── run_scraper.py              # Scrapy CLI
├── run_playwright_scraper.py   # Playwright CLI  
├── run_pydoll_scraper.py       # Pydoll CLI
├── super_scraper/              # Scrapy package
│   ├── items.py               # Data structures
│   ├── pipelines.py           # Data validation/processing
│   ├── settings.py            # Scrapy config
│   └── spiders/universal.py   # Universal spider
├── tests/                     # Unit tests
└── scraped_results/           # Auto-generated output dirs
```

## Key Data Fields Extracted
- `title` (string) - Item name/title
- `price` (float) - Item price  
- `description` (string, max 200 chars) - Item description
- `image_url` (string) - Full image URL
- `stock_availability` (boolean) - In stock status
- `sku` (string) - Stock Keeping Unit ID

## Output Organization
- All outputs saved to `scraped_results/`
- Each run creates `domain_YYYYMMDD_HHMMSS/` directory
- Contains CSV data file and log file
- No overwrites - each scrape gets unique directory

## Dependencies
- Python 3.8+
- Scrapy >=2.11.0
- Playwright >=1.40.0 (with Chromium browser)
- Pydoll >=0.1.0
- pandas, requests, beautifulsoup4

## Development Notes
- All scrapers share same interface and output format
- Scrapy: Best for standard HTML, respects robots.txt, concurrent requests
- Playwright: Handles JavaScript, anti-detection, browser automation  
- Pydoll: Browser automation with requests fallback, works without Chrome
- Comprehensive error handling and logging across all scrapers
- Built-in duplicate filtering and data validation pipelines

## Common Issues
- No items found: Customize selectors in `spiders/universal.py` (Scrapy) or check site interactions (others)
- Browser not found: Run `playwright install chromium` or Pydoll will fallback to requests
- JavaScript required: Use Playwright or Pydoll instead of Scrapy
- Rate limiting: All scrapers have delays, increase if needed