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
python run_scraper.py --url "https://example.com" [--loglevel DEBUG]

# Playwright scraper  
python run_playwright_scraper.py --url "https://example.com" [--max-pages 5] [--loglevel DEBUG]

# Pydoll scraper
python run_pydoll_scraper.py --url "https://example.com" [--max-pages 5] [--loglevel DEBUG]
```

### Validation Options
All scrapers support unified validation arguments:
```bash
--validation-quality-score 0.8     # Confidence threshold (0.0-1.0)
--validation-required-fields title,price  # Required field validation
--validation-timeout 30            # Validation timeout seconds
--enable-validation-cache          # Enable response caching
```

### Database Operations
```bash
# View database statistics
python database.py stats

# Initialize database (if needed)
python database.py init

# Clean up old data (optional)
python database.py cleanup [days_to_keep]
```

### Testing
```bash
# Run all tests
python -m unittest discover tests -v

# Run specific tests
python -m unittest tests.test_spider
python -m unittest tests.test_pipelines  
python -m unittest tests.test_database
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
├── database.py                 # SQLite database operations
├── scraped_data.db             # SQLite database file
├── validation_manager.py       # Unified validation system
├── response_collector.py       # Response metadata collection
├── validation_config.py        # Validation configuration
├── super_scraper/              # Scrapy package
│   ├── items.py               # Data structures
│   ├── pipelines.py           # Data validation/processing
│   ├── settings.py            # Scrapy config
│   └── spiders/universal.py   # Universal spider
├── tests/                     # Unit tests
└── scraped_results/           # Log files only
```

## Key Data Fields Extracted
- `title` (string) - Item name/title
- `price` (float) - Item price  
- `description` (string, max 200 chars) - Item description
- `image_url` (string) - Full image URL
- `stock_availability` (boolean) - In stock status
- `sku` (string) - Stock Keeping Unit ID

## Data Storage
- **Database**: All scraped data saved to SQLite database `scraped_data.db`
- **Logs**: Each run creates `scraped_results/domain_YYYYMMDD_HHMMSS/` directory for log files
- **Job Tracking**: Each scrape gets unique job ID for database queries
- **Statistics**: Use `python database.py stats` to view data summary

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
- **Data Pipeline**: URL → Scraper → ValidationManager → Deduplication → SQLite Database
- **Database**: Thread-safe SQLite with job tracking and metadata support
- **Validation System**: Unified ValidationManager with response collectors and caching
- **Shared Components**: All scrapers use identical data fields and database schema
- **Error Handling**: Multi-layer (network, parsing, data, system) with graceful degradation
- **Performance**: Scrapy (high throughput), Playwright (high resource), Pydoll (adaptive)

## Common Issues
- No items found: Customize selectors in `spiders/universal.py` (Scrapy) or check site interactions
- Browser not found: Run `playwright install chromium` or Pydoll will fallback to requests
- JavaScript required: Use Playwright or Pydoll instead of Scrapy
- Rate limiting: All scrapers have delays, increase if needed
- **Always activate virtual environment first**: `source venv/bin/activate`