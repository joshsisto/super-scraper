# Database Migration Plan: From CSV to SQLite

This document outlines the plan to migrate the Super Scraper Suite from saving scraped data to CSV files to using a centralized SQLite database.

## 1. Rationale

Switching to SQLite will provide:
-   **Centralized Data Storage:** All scraped data will be in one place, making it easier to query and analyze.
-   **Structured Data:** A database schema enforces data types and constraints.
-   **No More File Proliferation:** Reduces the number of individual CSV files in `scraped_results`.
-   **Improved Performance for Lookups:** Faster to query data from a database than to read multiple CSVs.
-   **Transactional Integrity:** Ensures data is written correctly.

## 2. Database Schema

A single SQLite database file will be created at the project root: `scraped_data.db`.

It will contain one main table: `scraped_items`.

### `scraped_items` table schema:

| Column Name          | Data Type | Description                                                                 |
| -------------------- | --------- | --------------------------------------------------------------------------- |
| `id`                 | INTEGER   | Primary Key, Auto-incrementing.                                             |
| `scrape_job_id`      | TEXT      | A unique identifier for each scraping run (e.g., `domain_YYYYMMDD_HHMMSS`). |
| `scraper_type`       | TEXT      | The scraper used ('scrapy', 'playwright', 'pydoll').                        |
| `url`                | TEXT      | The target URL that was scraped.                                            |
| `title`              | TEXT      | Item name/title.                                                            |
| `price`              | REAL      | Item price.                                                                 |
| `description`        | TEXT      | Item description.                                                           |
| `image_url`          | TEXT      | Full image URL.                                                             |
| `stock_availability` | INTEGER   | In stock status (1 for True, 0 for False).                                  |
| `sku`                | TEXT      | Stock Keeping Unit ID.                                                      |
| `scraped_at`         | TIMESTAMP | Timestamp when the item was scraped.                                        |

## 3. Implementation Steps

### Step 3.1: Create a Database Module

-   Create a new file `database.py` in the project root.
-   This module will contain:
    -   A function `get_db_connection()` to connect to `scraped_data.db`.
    -   A function `init_db()` to create the `scraped_items` table if it doesn't exist. This should be called by each scraper at startup.
    -   A function `save_items(items: List[Dict], scrape_job_id: str, scraper_type: str, url: str)` to insert a list of scraped items into the database.

### Step 3.2: Update Scraper Scripts

The core change in each scraper will be to replace the CSV saving logic with calls to the new database module. The `output_dir` creation logic can still be used for logs, but not for CSVs. The `scrape_job_id` can be derived from the directory name.

#### `run_playwright_scraper.py`

-   In `PlaywrightScraper.run()`:
    -   Remove the call to `self.save_results()`.
    -   After scraping is complete, call the new `database.save_items()` function, passing `self.items` and other relevant metadata.
-   In `PlaywrightScraper.save_results()`:
    -   This method will be removed or refactored. The logic for saving to the database will be in `database.py`. The deduplication logic inside `save_results` should be moved or re-evaluated. It might be better to handle duplicates at the database level (e.g., with a UNIQUE constraint on `title` and `scrape_job_id`).

#### `run_pydoll_scraper.py`

-   Similar to Playwright, update `PydollScraper.run()` and remove/refactor `PydollScraper.save_results()`.
-   Call `database.save_items()` with the scraped data.

#### `run_scraper.py` (Scrapy)

-   This is the most involved change. We need to replace the Scrapy Feed Exporter with a custom pipeline.
-   Create a new pipeline in `super_scraper/pipelines.py`, e.g., `SQLitePipeline`.
-   This pipeline will:
    -   Implement `open_spider` to initialize the database connection and get the `scrape_job_id`.
    -   Implement `process_item` to collect items.
    -   Implement `close_spider` to call `database.save_items()` with all collected items.
-   Update `super_scraper/settings.py`:
    -   Disable the default CSV Feed Exporter.
    -   Enable the new `SQLitePipeline` in `ITEM_PIPELINES`.

### Step 3.3: Update Validation Logic

-   The `validator.py` script's `validate_scraping_result` method currently accepts `scraped_data` as a list of dicts, or a `csv_file_path`.
-   The calls to the validator from `run_playwright_scraper.py` and `run_pydoll_scraper.py` already pass the `scraped_data` in memory, so they should continue to work without changes to the validator itself.
-   The `validate_csv_output` method in `ScrapingValidator` will become obsolete and should be removed or marked as deprecated.
-   The validation logic within the Scrapy pipeline needs to be checked. The `ValidationPipeline` in `super_scraper/pipelines.py` likely processes items one by one. It should continue to work as is, before the new `SQLitePipeline`.

## 4. Command-Line Interface (CLI) Changes

-   The `--output` argument in all `run_*.py` scripts, which specifies the CSV filename, will no longer be needed. It should be removed to avoid confusion.
-   The scripts' help text and documentation (`CLAUDE.md`, `README.md`) should be updated to reflect the new database storage mechanism.

## 5. Backwards Compatibility & Data Migration

-   This is a breaking change. Existing scripts that rely on CSV output will fail.
-   A separate, one-off script `migrate_csv_to_sqlite.py` could be created to migrate data from existing CSV files in `scraped_results/` into the new SQLite database. This is optional but recommended for data continuity.

## 6. Testing

-   Update existing tests that check for CSV output. They should now query the database to verify that data was saved correctly.
-   Create new tests for the `database.py` module to ensure connection and data insertion work as expected.
-   Integration tests for each scraper should be updated to confirm end-to-end flow into the database.
