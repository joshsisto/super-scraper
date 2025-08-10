#!/usr/bin/env python3
"""
Test script for ScrapingValidator

Tests the three core capabilities:
1. Successful Data Validation
2. Block Detection  
3. Bot Detection System Identification
"""

import sys
import logging
from validator import ScrapingValidator, BotDetectionSystem, BlockType

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def test_successful_validation():
    """Test successful scraping validation"""
    print("\n=== Test 1: Successful Validation ===")
    
    validator = ScrapingValidator(logger)
    
    # Mock successful response
    response_data = {
        'status_code': 200,
        'headers': {
            'Content-Type': 'text/html',
            'Server': 'nginx/1.18.0'
        },
        'content': '<html><body><h1>Product Catalog</h1><div class="product">Test Product</div></body></html>',
        'url': 'https://example-store.com/products',
        'response_time': 1.5
    }
    
    # Mock quality scraped data
    scraped_items = [
        {
            'title': 'Premium Wireless Headphones',
            'price': 299.99,
            'description': 'High-quality wireless headphones with noise cancellation',
            'image_url': 'https://example.com/img1.jpg',
            'stock_availability': True,
            'sku': 'WH-001'
        },
        {
            'title': 'Bluetooth Speaker',
            'price': 89.99,
            'description': 'Portable bluetooth speaker with excellent sound quality',
            'image_url': 'https://example.com/img2.jpg',
            'stock_availability': False,
            'sku': 'BS-002'
        },
    ]
    
    result = validator.validate_scraping_result(response_data, scraped_items)
    
    print(f"✓ Successful: {result.is_successful}")
    print(f"✓ Not blocked: {not result.is_blocked}")
    print(f"✓ Quality score: {result.confidence_score:.2f}")
    print(f"✓ Summary: {validator.get_validation_summary(result)}")
    
    if result.metadata.get('data_stats'):
        stats = result.metadata['data_stats']
        print(f"✓ Total items: {stats['total_items']}")
        for field, data in stats.get('field_completeness', {}).items():
            print(f"  - {field}: {data['completeness']:.1%} complete")
    
    return result.is_successful and not result.is_blocked

def test_blocking_detection():
    """Test blocking detection capabilities"""
    print("\n=== Test 2: Blocking Detection ===")
    
    validator = ScrapingValidator(logger)
    
    # Test HTTP 403 blocking
    blocked_response = {
        'status_code': 403,
        'headers': {
            'Content-Type': 'text/html',
            'Server': 'cloudflare'
        },
        'content': '<html><head><title>Access Denied</title></head><body><h1>Access denied</h1><p>Your request has been blocked.</p></body></html>',
        'url': 'https://example-store.com/blocked',
        'response_time': 0.5
    }
    
    result = validator.validate_scraping_result(blocked_response)
    
    print(f"✓ Blocked detected: {result.is_blocked}")
    print(f"✓ Block type: {result.metadata.get('block_type')}")
    print(f"✓ Issues: {result.issues}")
    print(f"✓ Summary: {validator.get_validation_summary(result)}")
    
    # Test CAPTCHA blocking
    captcha_response = {
        'status_code': 200,
        'headers': {'Content-Type': 'text/html'},
        'content': '<html><body><h1>Security Check</h1><p>Please complete the CAPTCHA to continue</p><div class="recaptcha"></div></body></html>',
        'url': 'https://example-store.com/products',
        'response_time': 2.0
    }
    
    captcha_result = validator.validate_scraping_result(captcha_response)
    
    print(f"✓ CAPTCHA detected: {captcha_result.is_blocked}")
    print(f"✓ CAPTCHA type: {captcha_result.metadata.get('block_type')}")
    
    return result.is_blocked and captcha_result.is_blocked

def test_bot_detection():
    """Test bot detection system identification"""
    print("\n=== Test 3: Bot Detection System Identification ===")
    
    validator = ScrapingValidator(logger)
    
    # Test Cloudflare detection
    cloudflare_response = {
        'status_code': 200,
        'headers': {
            'cf-ray': '7d4f8c2e5a1b2c3d-SFO',
            'cf-cache-status': 'DYNAMIC',
            'Server': 'cloudflare'
        },
        'content': '<html><head><title>Just a moment...</title></head><body>Checking your browser before accessing the website.</body></html>',
        'url': 'https://example-store.com/products',
        'response_time': 2.1
    }
    
    result = validator.validate_scraping_result(cloudflare_response)
    
    print(f"✓ Bot system detected: {result.bot_detection_system}")
    print(f"✓ Expected Cloudflare: {result.bot_detection_system == BotDetectionSystem.CLOUDFLARE}")
    print(f"✓ Confidence: {result.metadata.get('bot_system_confidence', 0):.2f}")
    print(f"✓ Indicators: {result.metadata.get('bot_indicators', [])}")
    
    # Test Akamai detection
    akamai_response = {
        'status_code': 200,
        'headers': {
            'x-akamai-transformed': 'true',
            'Content-Type': 'text/html'
        },
        'content': '<html><body><p>Reference ID: 12345678.abcdefgh</p></body></html>',
        'url': 'https://example.com',
        'response_time': 1.0
    }
    
    akamai_result = validator.validate_scraping_result(akamai_response)
    
    print(f"✓ Akamai detected: {akamai_result.bot_detection_system == BotDetectionSystem.AKAMAI}")
    
    return (result.bot_detection_system == BotDetectionSystem.CLOUDFLARE and 
            akamai_result.bot_detection_system == BotDetectionSystem.AKAMAI)

def test_poor_quality_data():
    """Test detection of poor quality scraped data"""
    print("\n=== Test 4: Poor Quality Data Detection ===")
    
    validator = ScrapingValidator(logger)
    
    response_data = {
        'status_code': 200,
        'headers': {'Content-Type': 'text/html'},
        'content': '<html><body>Valid page</body></html>',
        'url': 'https://example.com',
        'response_time': 1.0
    }
    
    # Poor quality data - mostly empty or placeholder content
    poor_data = [
        {'title': 'loading...', 'price': None, 'description': '', 'image_url': '', 'stock_availability': None, 'sku': ''},
        {'title': 'product', 'price': 'N/A', 'description': 'null', 'image_url': None, 'stock_availability': True, 'sku': '123'},
        {'title': '', 'price': 0, 'description': 'undefined', 'image_url': 'invalid', 'stock_availability': None, 'sku': None}
    ]
    
    result = validator.validate_scraping_result(response_data, poor_data)
    
    print(f"✓ Poor data rejected: {not result.is_successful}")
    print(f"✓ Quality score: {result.confidence_score:.2f}")
    print(f"✓ Issues: {result.issues}")
    print(f"✓ Warnings: {result.warnings}")
    
    return not result.is_successful

def test_csv_validation():
    """Test CSV file validation"""
    print("\n=== Test 5: CSV File Validation ===")
    
    # Create a test CSV file
    import pandas as pd
    import os
    
    test_data = [
        {'title': 'Test Product 1', 'price': 19.99, 'description': 'Good product', 'image_url': 'https://test.com/1.jpg', 'stock_availability': True, 'sku': 'TEST-001'},
        {'title': 'Test Product 2', 'price': 29.99, 'description': 'Better product', 'image_url': 'https://test.com/2.jpg', 'stock_availability': False, 'sku': 'TEST-002'}
    ]
    
    test_csv = 'test_output.csv'
    df = pd.DataFrame(test_data)
    df.to_csv(test_csv, index=False)
    
    validator = ScrapingValidator(logger)
    result = validator.validate_csv_output(test_csv)
    
    print(f"✓ CSV validation successful: {result.is_successful}")
    print(f"✓ Quality score: {result.confidence_score:.2f}")
    
    # Cleanup
    if os.path.exists(test_csv):
        os.remove(test_csv)
    
    return result.is_successful

def main():
    """Run all validation tests"""
    print("Testing ScrapingValidator Implementation")
    print("=" * 50)
    
    tests = [
        ("Successful Validation", test_successful_validation),
        ("Blocking Detection", test_blocking_detection),
        ("Bot Detection", test_bot_detection),
        ("Poor Quality Data", test_poor_quality_data),
        ("CSV Validation", test_csv_validation)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
            status = "PASSED" if result else "FAILED"
            print(f"\n{test_name}: {status}")
        except Exception as e:
            print(f"\n{test_name}: ERROR - {str(e)}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("TEST SUMMARY:")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {test_name}")
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! ScrapingValidator is working correctly.")
        return 0
    else:
        print("❌ Some tests failed. Please check the implementation.")
        return 1

if __name__ == "__main__":
    sys.exit(main())