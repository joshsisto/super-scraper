# Super Scraper Suite - Claude Context

## Project Overview
A comprehensive web scraping toolkit with three different scrapers:
1. **Scrapy-based** (`run_scraper.py`) - Fast, concurrent, standard HTML scraping
2. **Playwright-based** (`run_playwright_scraper.py`) - JavaScript-heavy sites, bot detection bypass
3. **Pydoll-based** (`run_pydoll_scraper.py`) - Flexible with automatic fallback

## Environment Setup

**CRITICAL**: This project uses a virtual environment. Always activate before running commands:
```bash
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows
```

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
python -m unittest discover tests -v

# Run specific tests
python -m unittest tests.test_spider
python -m unittest tests.test_pipelines  
python -m unittest tests.test_items
```

### Installation/Setup
```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# For Playwright scraper
playwright install chromium
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

## Scraper Selection Guide
| Website Type | Use | Reason |
|-------------|-----|---------|
| Static HTML | Scrapy | Fast concurrent processing |
| JavaScript-heavy | Playwright | Full browser rendering |
| Bot-protected | Playwright | Anti-detection measures |
| Mixed/Unknown | Pydoll | Adaptive with fallback |

## Architecture Notes
- **Data Pipeline**: URL → Scraper → Validation → Deduplication → CSV Export
- **Shared Components**: All scrapers use identical data fields and output structure
- **Error Handling**: Multi-layer (network, parsing, data, system) with graceful degradation
- **Performance**: Scrapy (high throughput), Playwright (high resource), Pydoll (adaptive)

## Common Issues
- No items found: Customize selectors in `spiders/universal.py` (Scrapy) or check site interactions
- Browser not found: Run `playwright install chromium` or Pydoll will fallback to requests
- JavaScript required: Use Playwright or Pydoll instead of Scrapy
- Rate limiting: All scrapers have delays, increase if needed
- **Always activate virtual environment first**: `source venv/bin/activate`