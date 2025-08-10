# Troubleshooting Guide

This guide covers common issues you might encounter when using the Super Scraper Suite and how to resolve them.

## Common Issues

### Issue: No Items Found

If the scraper runs but doesn't find any items, try the following:

**For the Scrapy scraper (`run_scraper.py`)**:
- The CSS selectors in `super_scraper/spiders/universal.py` might not match the target website's structure
- Inspect the website's HTML and update the `item_selectors` list
- Check if the website requires user-agent spoofing or additional headers
- Verify that the website doesn't block the Scrapy user agent

**For Playwright/Pydoll scrapers**:
- The website might require a login or other interaction before displaying content
- Try running the scraper with debug logging: `--loglevel DEBUG`
- For Playwright, you can set `headless=False` in the code to observe browser behavior
- Check if the website loads content dynamically after page load

**General debugging steps**:
```bash
# Run with debug logging to see detailed information
python run_scraper.py --url "https://example.com" --loglevel DEBUG
python run_playwright_scraper.py --url "https://example.com" --loglevel DEBUG
python run_pydoll_scraper.py --url "https://example.com" --loglevel DEBUG
```

### Issue: Browser Not Found

**For Playwright scraper**:
```
Error: Executable doesn't exist at /path/to/chromium
```

**Solution**:
```bash
# Install Playwright browsers
playwright install chromium

# Or install all browsers
playwright install
```

**For Pydoll scraper**:
- Pydoll will automatically fall back to requests mode if browser is unavailable
- No action needed - this is expected behavior
- If you want browser mode, ensure Chrome/Chromium is installed

### Issue: Permission Denied or Access Errors

**Linux/Mac users**:
```bash
# Make sure you have write permissions to the current directory
chmod 755 .
mkdir scraped_results
chmod 755 scraped_results
```

**Docker users**:
```bash
# Run Playwright install inside the container
docker exec -it your_container playwright install chromium
```

### Issue: Rate Limiting / 429 Errors

If you're getting HTTP 429 (Too Many Requests) errors:

**For Scrapy scraper**:
- Increase delays in `super_scraper/settings.py`:
  ```python
  DOWNLOAD_DELAY = 3  # 3 seconds between requests
  RANDOMIZE_DOWNLOAD_DELAY = 0.5  # 0.5 * to 1.5 * DOWNLOAD_DELAY
  ```

**For Playwright/Pydoll scrapers**:
- The scrapers already include human-like delays
- Consider reducing the `max-pages` parameter: `--max-pages 3`
- Add longer delays by modifying the code

### Issue: JavaScript Required

If you see empty pages or missing content:

**Switch from Scrapy to Playwright or Pydoll**:
```bash
# Instead of:
python run_scraper.py --url "https://spa-website.com"

# Use:
python run_playwright_scraper.py --url "https://spa-website.com"
# or
python run_pydoll_scraper.py --url "https://spa-website.com"
```

### Issue: SSL Certificate Errors

```
SSL: CERTIFICATE_VERIFY_FAILED
```

**For Scrapy scraper**:
- Add to `super_scraper/settings.py`:
  ```python
  ROBOTSTXT_OBEY = False
  DOWNLOAD_VERIFY_TLS = False
  ```

**For Playwright/Pydoll scrapers**:
- The scrapers already ignore SSL errors for compatibility

### Issue: Memory Issues / High Resource Usage

**For Playwright scraper**:
- Reduce the `max-pages` parameter: `--max-pages 5`
- The browser automation requires more memory than other scrapers
- Consider using the Scrapy scraper for simple sites

**For all scrapers**:
- Process smaller batches by limiting pages
- Monitor system resources with `htop` or Task Manager

### Issue: Import Errors

**Missing dependencies**:
```bash
# Reinstall requirements
pip install -r requirements.txt

# For Playwright specifically
pip install playwright
playwright install chromium

# For Pydoll (if needed)
pip install git+https://github.com/autoscrape-labs/pydoll.git
```

**Virtual environment issues**:
```bash
# Recreate virtual environment
deactivate
rm -rf venv
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Debug Mode

Enable detailed logging for any scraper:

```bash
# Scrapy scraper with debug output
python run_scraper.py --url "https://example.com" --loglevel DEBUG

# Playwright scraper with debug output
python run_playwright_scraper.py --url "https://example.com" --loglevel DEBUG

# Pydoll scraper with debug output
python run_pydoll_scraper.py --url "https://example.com" --loglevel DEBUG
```

Debug mode will show:
- Detailed HTTP requests and responses
- CSS selector matching attempts
- JavaScript execution (for Playwright/Pydoll)
- Error stack traces
- Browser actions (for Playwright/Pydoll)

## Website-Specific Tips

### E-commerce Sites
- Many e-commerce sites have anti-bot measures
- Use Playwright scraper for better success rates
- Check if the site has an API instead of scraping

### Single-Page Applications (SPAs)
- Always use Playwright or Pydoll scrapers
- Scrapy won't work with dynamically loaded content
- Allow extra time for JavaScript execution

### Sites with Login Requirements
- Currently not directly supported
- Consider modifying the Playwright scraper to handle login
- Some sites may work with session cookies

## Performance Optimization

### Choose the Right Scraper
- **Scrapy**: Best performance for static HTML sites
- **Playwright**: Best for JavaScript-heavy sites, slower but more capable
- **Pydoll**: Good middle ground with fallback capability

### Adjust Concurrency
**Scrapy scraper**:
- Modify `CONCURRENT_REQUESTS` in `super_scraper/settings.py`
- Default is conservative (1) to avoid overwhelming sites

**Playwright/Pydoll scrapers**:
- Currently single-threaded for stability
- Consider running multiple instances for different URLs

## Getting Help

If you continue to have issues:

1. **Check the log files** in your output directory
2. **Run with DEBUG logging** to see detailed information
3. **Try a different scraper** (Scrapy → Playwright → Pydoll)
4. **Inspect the target website** manually in a browser
5. **Check if the website has an API** as an alternative

## Common Error Messages

| Error | Likely Cause | Solution |
|-------|-------------|----------|
| `No items found` | Wrong selectors or dynamic content | Try Playwright/Pydoll, check selectors |
| `Browser not found` | Playwright not installed | Run `playwright install chromium` |
| `Permission denied` | Directory permissions | Check write permissions |
| `SSL Certificate error` | HTTPS/TLS issues | Disable SSL verification |
| `Rate limited` | Too many requests | Increase delays, reduce concurrency |
| `Import Error` | Missing dependencies | Reinstall requirements |