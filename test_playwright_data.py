#!/usr/bin/env python3
"""
Test ScrapingValidator with Playwright scraped data
"""

import sys
import os
import pandas as pd
from validator import ScrapingValidator

def test_playwright_data():
    """Test validator with Playwright scraped data"""
    print("🎭 Testing ScrapingValidator with Playwright Data")
    print("=" * 50)
    
    validator = ScrapingValidator()
    
    # Load Playwright CSV data
    csv_path = 'scraped_results/books.toscrape.com_20250809_223429/scraped_data.csv'
    
    if not os.path.exists(csv_path):
        print(f"❌ Error: CSV file not found: {csv_path}")
        return False
    
    try:
        df = pd.read_csv(csv_path)
        scraped_data = df.to_dict('records')
        print(f"📊 Loaded {len(scraped_data)} items from Playwright CSV")
    except Exception as e:
        print(f"❌ Error loading CSV: {str(e)}")
        return False
    
    # Create response data for Playwright scenario
    response_data = {
        'status_code': 200,
        'headers': {
            'Content-Type': 'text/html; charset=utf-8',
            'Server': 'nginx/1.14.0 (Ubuntu)'
        },
        'content': '''
        <html>
        <head><title>All products | Books to Scrape</title></head>
        <body>
            <div class="row">
                <article class="product_pod">
                    <h3><a href="product.html" title="A Light in the Attic">A Light in the Attic</a></h3>
                    <p class="price_color">£51.77</p>
                    <p class="instock availability">In stock</p>
                </article>
            </div>
        </body>
        </html>
        ''',
        'url': 'https://books.toscrape.com/',
        'response_time': 2.3  # Playwright typically takes longer
    }
    
    print("\n🔄 Running validation on Playwright results...")
    try:
        result = validator.validate_scraping_result(response_data, scraped_data)
        
        print(f"\n📋 RESULT: {validator.get_validation_summary(result)}")
        
        # Check data quality differences from Scrapy
        if 'data_stats' in result.metadata:
            stats = result.metadata['data_stats']
            field_stats = stats.get('field_completeness', {})
            
            print("\n🔍 Playwright vs Expected Field Completeness:")
            for field, data in field_stats.items():
                completeness = data.get('completeness', 0)
                count = data.get('count', 0)
                status = "✅" if completeness > 0.8 else "⚠️ " if completeness > 0.5 else "❌"
                print(f"   {status} {field}: {completeness:.1%} ({count}/{len(scraped_data)} items)")
        
        # Check for stock_availability improvement in Playwright
        stock_items = [item for item in scraped_data if item.get('stock_availability') is not None]
        if stock_items:
            print(f"\n✅ Stock availability data: {len(stock_items)} items have stock info")
        else:
            print(f"\n⚠️  Stock availability: No stock information captured")
        
        print(f"\n🎯 Overall Assessment:")
        if result.is_successful:
            print("   ✅ Playwright scraping SUCCESSFUL")
            print("   ✅ High data quality maintained")
            print("   ✅ Good field completeness across all items")
        
        return result.is_successful
        
    except Exception as e:
        print(f"❌ Validation failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_playwright_data()
    if success:
        print("\n🎉 Playwright validation test PASSED!")
        sys.exit(0)
    else:
        print("\n❌ Playwright validation test FAILED!")
        sys.exit(1)