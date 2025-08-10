# Architecture Overview

The Super Scraper Suite is designed as a modular web scraping toolkit with three distinct scraping engines that share common interfaces and output formats.

## System Architecture

The Super Scraper Suite is composed of three main components:

1. **Scrapy Engine**: The core of the `run_scraper.py` script, handling concurrent requests, the data pipeline, and item processing.
2. **Browser Automation (Playwright/Pydoll)**: Used by `run_playwright_scraper.py` and `run_pydoll_scraper.py` to control a web browser for scraping dynamic content.
3. **Shared Components**: All scrapers use a common output format and directory structure.

## Data Flow

```
Target Website → Scraper (Scrapy/Playwright/Pydoll) → Item Pipeline (Validation, Deduplication) → CSV File
```

### Detailed Flow

1. **Input**: User provides URL and optional parameters via command line
2. **Directory Creation**: Timestamped output directory created in `scraped_results/`
3. **Scraping Engine**: One of three scraping methods processes the website
4. **Data Extraction**: Common data fields extracted using CSS selectors
5. **Data Processing**: Items validated, cleaned, and deduplicated
6. **Output**: Clean CSV file saved with comprehensive logging

## Component Details

### 1. Scrapy-based Scraper (`run_scraper.py`)

```
run_scraper.py
    ↓
super_scraper/ (Scrapy Project)
    ├── settings.py (Configuration)
    ├── items.py (Data Structures)  
    ├── pipelines.py (Data Processing)
    └── spiders/universal.py (Scraping Logic)
```

**Key Features**:
- Concurrent request handling
- Built-in retry mechanisms
- Respects robots.txt
- Auto-throttling
- Duplicate filtering pipeline
- Data validation pipeline

**Data Pipeline**:
```
Raw HTML → Spider → Item → ValidationPipeline → DuplicateFilterPipeline → CSV Export
```

### 2. Playwright-based Scraper (`run_playwright_scraper.py`)

```
run_playwright_scraper.py
    ↓
PlaywrightScraper Class
    ├── setup_browser() (Anti-detection)
    ├── create_page() (Page configuration)
    ├── scrape_page() (Data extraction)
    ├── extract_item_data() (Item processing)
    └── save_results() (CSV export)
```

**Key Features**:
- Headless browser automation
- JavaScript execution
- Anti-bot detection measures
- Dynamic content handling
- Pagination following

**Browser Pipeline**:
```
URL → Browser Launch → Page Creation → Content Loading → Data Extraction → CSV Export
```

### 3. Pydoll-based Scraper (`run_pydoll_scraper.py`)

```
run_pydoll_scraper.py
    ↓
PydollScraper Class
    ├── try_browser_mode() (Primary method)
    ├── fallback_requests_mode() (Backup method)
    ├── extract_items() (Data processing)
    └── save_to_csv() (Output)
```

**Key Features**:
- Dual-mode operation (browser + requests fallback)
- Environment adaptability
- Automatic fallback on browser failure
- Same data extraction logic in both modes

**Adaptive Pipeline**:
```
URL → Browser Attempt → Success: Browser Extraction / Failure: Requests Fallback → CSV Export
```

## Shared Components

### Output Directory Structure
```
scraped_results/
└── domain_YYYYMMDD_HHMMSS/
    ├── scraped_data.csv (or custom filename)
    └── [scraper_name].log
```

### Common Data Fields
All scrapers extract these standardized fields:
- `title` (string): Item name/title
- `price` (float): Item price
- `description` (string): Item description (max 200 chars)
- `image_url` (string): Full image URL
- `stock_availability` (boolean): In stock status
- `sku` (string): Stock Keeping Unit ID

### Logging System
- Consistent logging format across all scrapers
- Both file and console output
- Configurable log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Timestamped entries with logger identification

## Scraper Selection Logic

The architecture allows users to choose the appropriate scraper based on website characteristics:

| Website Type | Recommended Scraper | Reason |
|-------------|-------------------|---------|
| Static HTML | Scrapy | Performance and efficiency |
| JavaScript-heavy | Playwright | Full browser rendering |
| Bot-protected | Playwright | Anti-detection measures |
| Mixed/Unknown | Pydoll | Adaptive with fallback |
| High-volume | Scrapy | Concurrent processing |

## Design Patterns

### 1. Strategy Pattern
Each scraper implements the same interface but uses different strategies:
- **Scrapy**: HTTP requests with concurrent processing
- **Playwright**: Browser automation with anti-detection
- **Pydoll**: Adaptive browser-first with requests fallback

### 2. Template Method Pattern
All scrapers follow the same general process:
1. Initialize (setup logging, create output directory)
2. Configure (set up scraper-specific settings)
3. Extract (process target website)
4. Transform (clean and validate data)
5. Load (save to CSV file)

### 3. Pipeline Pattern (Scrapy)
Data flows through a series of processing stages:
- Item extraction
- Data validation
- Duplicate filtering
- Format standardization
- File output

## Configuration Management

### Scrapy Configuration (`super_scraper/settings.py`)
- Request delays and concurrency limits
- User agent and header settings
- Pipeline activation and ordering
- Retry and timeout configurations

### Playwright Configuration (In-code)
- Browser launch arguments
- Page context settings
- Anti-detection measures
- Viewport and user agent settings

### Pydoll Configuration (In-code)
- Browser preference settings
- Fallback triggers
- Request timeout configurations

## Error Handling Strategy

### Layered Error Handling
1. **Network Level**: Connection timeouts, SSL errors
2. **Parsing Level**: Invalid CSS selectors, missing elements
3. **Data Level**: Type conversion errors, validation failures
4. **System Level**: File I/O errors, permission issues

### Graceful Degradation
- **Scrapy**: Built-in retry mechanisms and error pipelines
- **Playwright**: Page reload attempts and element waiting
- **Pydoll**: Automatic fallback to requests mode

## Performance Characteristics

### Scrapy Scraper
- **Throughput**: High (concurrent requests)
- **Memory**: Low to moderate
- **CPU**: Low to moderate
- **Latency**: Low (direct HTTP)

### Playwright Scraper  
- **Throughput**: Moderate (sequential)
- **Memory**: High (browser overhead)
- **CPU**: High (JavaScript execution)
- **Latency**: High (browser startup)

### Pydoll Scraper
- **Throughput**: Moderate (adaptive)
- **Memory**: Variable (depends on mode)
- **CPU**: Variable (browser vs requests)
- **Latency**: Moderate (mode detection overhead)

## Extensibility

### Adding New Scrapers
To add a new scraper engine:
1. Follow the established CLI argument pattern
2. Implement the same data extraction interface
3. Use the common output directory structure
4. Return data in the standardized field format

### Customizing Data Fields
Modify the `columns` list in each scraper's save method to add new fields.

### Adding New Selection Strategies
Extend the `item_selectors` lists in each scraper to support new website patterns.

## Dependencies

### Core Dependencies
- **Python 3.8+**: Base runtime
- **pandas**: Data manipulation and CSV export
- **requests**: HTTP client (fallback mode)
- **beautifulsoup4**: HTML parsing (fallback mode)

### Scrapy Dependencies
- **Scrapy >=2.11.0**: Web scraping framework

### Playwright Dependencies
- **Playwright >=1.40.0**: Browser automation
- **Chromium browser**: Installed via `playwright install`

### Pydoll Dependencies
- **Pydoll >=0.1.0**: Hybrid scraping framework

This architecture provides a flexible, scalable foundation for web scraping that can adapt to different website types and deployment environments while maintaining consistent interfaces and output formats.