#!/usr/bin/env python3
"""
Test ScrapingValidator with Pydoll scraped data (including fallback mode)
"""

import sys
import os
import pandas as pd
from validator import ScrapingValidator

def test_pydoll_data():
    """Test validator with Pydoll scraped data"""
    print("🔄 Testing ScrapingValidator with Pydoll Data")
    print("=" * 50)
    
    validator = ScrapingValidator()
    
    # Load Pydoll CSV data
    csv_path = 'scraped_results/books.toscrape.com_20250809_223542/scraped_data.csv'
    
    if not os.path.exists(csv_path):
        print(f"❌ Error: CSV file not found: {csv_path}")
        return False
    
    try:
        df = pd.read_csv(csv_path)
        scraped_data = df.to_dict('records')
        print(f"📊 Loaded {len(scraped_data)} items from Pydoll CSV")
        print(f"📝 Note: Pydoll fell back to requests mode (no Chrome available)")
    except Exception as e:
        print(f"❌ Error loading CSV: {str(e)}")
        return False
    
    # Create response data for fallback mode scenario
    response_data = {
        'status_code': 200,
        'headers': {
            'Content-Type': 'text/html; charset=utf-8',
            'Server': 'nginx/1.14.0 (Ubuntu)',
            'User-Agent': 'python-requests/2.31.0'  # Indicates requests-based scraping
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
        'response_time': 0.8  # Faster than browser automation
    }
    
    print("\n🔄 Running validation on Pydoll fallback results...")
    try:
        result = validator.validate_scraping_result(response_data, scraped_data)
        
        print(f"\n📋 RESULT: {validator.get_validation_summary(result)}")
        
        # Analyze data quality issues
        if 'data_stats' in result.metadata:
            stats = result.metadata['data_stats']
            field_stats = stats.get('field_completeness', {})
            
            print("\n🔍 Pydoll Fallback Data Analysis:")
            for field, data in field_stats.items():
                completeness = data.get('completeness', 0)
                count = data.get('count', 0)
                status = "✅" if completeness > 0.8 else "⚠️ " if completeness > 0.5 else "❌"
                print(f"   {status} {field}: {completeness:.1%} ({count}/{len(scraped_data)} items)")
        
        # Check for specific issues with fallback mode
        print("\n🕵️  Specific Issue Detection:")
        
        # Check image URL issues
        relative_urls = [item for item in scraped_data if item.get('image_url') and not item['image_url'].startswith('http')]
        if relative_urls:
            print(f"   ⚠️  Found {len(relative_urls)} relative image URLs (URL resolution issue)")
            print(f"       Example: {relative_urls[0]['image_url'][:50]}...")
        
        # Check title quality
        titles = [item.get('title') for item in scraped_data if item.get('title')]
        unique_titles = len(set(titles))
        print(f"   ✅ Title diversity: {unique_titles}/{len(titles)} unique titles ({unique_titles/len(titles):.1%})")
        
        # Check price consistency
        prices = [item.get('price') for item in scraped_data if item.get('price') is not None]
        valid_prices = [p for p in prices if isinstance(p, (int, float)) and p > 0]
        print(f"   ✅ Price validity: {len(valid_prices)}/{len(scraped_data)} valid prices ({len(valid_prices)/len(scraped_data):.1%})")
        
        print(f"\n🎯 Pydoll Assessment:")
        if result.is_successful:
            print("   ✅ Fallback mode scraping SUCCESSFUL")
            print("   ✅ Data extraction working despite browser unavailability")
            if relative_urls:
                print("   ⚠️  Minor URL resolution issue detected (could be improved)")
        
        print("\n💡 Recommendations for Pydoll:")
        print("   • Install Chrome/Chromium for full browser mode functionality")
        print("   • Fallback mode is working well as backup")
        if relative_urls:
            print("   • Consider improving URL resolution in fallback mode")
        
        return result.is_successful
        
    except Exception as e:
        print(f"❌ Validation failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_pydoll_data()
    if success:
        print("\n🎉 Pydoll validation test PASSED!")
        sys.exit(0)
    else:
        print("\n❌ Pydoll validation test FAILED!")
        sys.exit(1)