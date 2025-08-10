#!/usr/bin/env python3
"""
Test ScrapingValidator with real scraped data
"""

import sys
import os
import pandas as pd
from validator import ScrapingValidator, ValidationResult

def test_with_real_data():
    """Test validator with actual scraped data"""
    print("🔍 Testing ScrapingValidator with Real Data")
    print("=" * 50)
    
    # Initialize validator
    validator = ScrapingValidator()
    
    # Load real CSV data
    csv_path = 'scraped_results/books.toscrape.com_20250809_223108/scraped_data.csv'
    
    if not os.path.exists(csv_path):
        print(f"❌ Error: CSV file not found: {csv_path}")
        return False
    
    try:
        df = pd.read_csv(csv_path)
        scraped_data = df.to_dict('records')
        print(f"📊 Loaded {len(scraped_data)} items from CSV")
    except Exception as e:
        print(f"❌ Error loading CSV: {str(e)}")
        return False
    
    # Create mock response data for books.toscrape.com
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
        'response_time': 1.2
    }
    
    # Run validation
    print("\n🔄 Running comprehensive validation...")
    try:
        result = validator.validate_scraping_result(response_data, scraped_data)
        
        # Display results
        print("\n" + "=" * 50)
        print("📋 VALIDATION RESULTS")
        print("=" * 50)
        
        print(f"Summary: {validator.get_validation_summary(result)}")
        print()
        
        # Success status
        if result.is_successful:
            print("✅ SCRAPING STATUS: SUCCESSFUL")
            print("   Data quality meets validation standards")
        else:
            print("❌ SCRAPING STATUS: FAILED")
            print("   Data quality issues detected")
        
        # Blocking status
        if result.is_blocked:
            block_type = result.metadata.get('block_type', 'unknown')
            print(f"\n🚫 BLOCKING DETECTED: {block_type}")
        else:
            print("\n✅ NO BLOCKING DETECTED")
        
        # Bot detection
        if result.bot_detection_system and result.bot_detection_system.value != 'none':
            print(f"\n🛡️  BOT DETECTION SYSTEM: {result.bot_detection_system.value.upper()}")
        else:
            print("\n⭕ NO BOT DETECTION SYSTEM IDENTIFIED")
        
        # Data quality metrics
        if 'data_stats' in result.metadata:
            stats = result.metadata['data_stats']
            print(f"\n📊 DATA QUALITY METRICS:")
            print(f"   Total items: {stats.get('total_items', 0)}")
            print(f"   Overall quality score: {result.confidence_score:.2f}")
            
            field_stats = stats.get('field_completeness', {})
            if field_stats:
                print("   Field completeness:")
                for field, data in field_stats.items():
                    completeness = data.get('completeness', 0)
                    count = data.get('count', 0)
                    status = "✅" if completeness > 0.8 else "⚠️ " if completeness > 0.5 else "❌"
                    print(f"     {status} {field}: {completeness:.1%} ({count} items)")
        
        # Issues and warnings
        if result.issues:
            print("\n❌ ISSUES DETECTED:")
            for i, issue in enumerate(result.issues, 1):
                print(f"   {i}. {issue}")
        
        if result.warnings:
            print("\n⚠️  WARNINGS:")
            for i, warning in enumerate(result.warnings, 1):
                print(f"   {i}. {warning}")
        
        print("\n" + "=" * 50)
        
        return result.is_successful
        
    except Exception as e:
        print(f"❌ Validation failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_with_real_data()
    if success:
        print("🎉 Real data validation test PASSED!")
        sys.exit(0)
    else:
        print("❌ Real data validation test FAILED!")
        sys.exit(1)