#!/usr/bin/env python3
"""
Test the standalone validator functionality
"""

from simple_validator_test import SimpleValidator, ValidationResult, BotDetectionSystem

def test_standalone():
    """Test standalone validation functionality"""
    print("🔍 Testing Standalone Validator")
    print("=" * 40)
    
    validator = SimpleValidator()
    
    # Test data
    response_data = {
        'status_code': 200,
        'headers': {'Content-Type': 'text/html'},
        'content': '<html><body>Test content</body></html>',
        'url': 'https://test.com',
        'response_time': 1.0
    }
    
    scraped_data = [
        {'title': 'Test Product 1', 'price': 19.99},
        {'title': 'Test Product 2', 'price': 29.99}
    ]
    
    result = validator.validate_scraping_result(response_data, scraped_data)
    
    # Manual summary (since SimpleValidator doesn't have get_validation_summary)
    summary = []
    if result.is_successful:
        summary.append("✓ Scraping successful")
    else:
        summary.append("✗ Scraping failed")
    
    if result.is_blocked:
        summary.append("⚠ Blocked")
    
    if result.bot_detection_system and result.bot_detection_system != BotDetectionSystem.NONE:
        summary.append(f"🛡 Bot detection: {result.bot_detection_system.value}")
    
    summary.append(f"Confidence: {result.confidence_score:.1%}")
    
    print("📋 VALIDATION SUMMARY:")
    print("   " + " | ".join(summary))
    print()
    print("✅ DETAILED RESULTS:")
    print(f"   Successful: {result.is_successful}")
    print(f"   Blocked: {result.is_blocked}")
    print(f"   Bot Detection: {result.bot_detection_system}")
    print(f"   Confidence: {result.confidence_score:.2f}")
    print(f"   Issues: {result.issues}")
    print()
    
    return result.is_successful

if __name__ == "__main__":
    success = test_standalone()
    if success:
        print("🎉 Standalone validator test passed!")
    else:
        print("❌ Standalone validator test failed!")
        exit(1)