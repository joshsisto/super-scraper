#!/usr/bin/env python3
"""
Standalone validator tool for validating scraping results

Usage:
    python validate_results.py --csv scraped_results/domain_20241210_143022/scraped_data.csv
    python validate_results.py --url "https://example.com" --response-data response.json
"""

import sys
import os
import argparse
import json
from simple_validator_test import SimpleValidator, ValidationResult, BotDetectionSystem, BlockType

def load_csv_data(csv_path):
    """Load CSV data without pandas dependency"""
    import csv
    
    if not os.path.exists(csv_path):
        print(f"❌ Error: CSV file not found: {csv_path}")
        return None
    
    data = []
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            data = list(reader)
        
        print(f"📊 Loaded {len(data)} items from CSV")
        return data
        
    except Exception as e:
        print(f"❌ Error loading CSV: {str(e)}")
        return None

def create_sample_response_data(url):
    """Create sample response data for URL validation"""
    return {
        'status_code': 200,
        'headers': {'Content-Type': 'text/html'},
        'content': '<html><body>Sample content</body></html>',
        'url': url,
        'response_time': 1.0
    }

def format_validation_report(result, validator):
    """Format a detailed validation report"""
    report = []
    
    report.append("=" * 60)
    report.append("🔍 SCRAPING VALIDATION REPORT")
    report.append("=" * 60)
    
    # Summary
    report.append(f"\n📋 SUMMARY: {validator.get_validation_summary(result)}")
    
    # Success Status
    if result.is_successful:
        report.append("\n✅ SCRAPING STATUS: SUCCESSFUL")
        report.append("   Data quality meets validation standards")
    else:
        report.append("\n❌ SCRAPING STATUS: FAILED")
        report.append("   Data quality issues detected")
    
    # Blocking Status
    if result.is_blocked:
        block_type = result.metadata.get('block_type', 'unknown')
        report.append(f"\n🚫 BLOCKING DETECTED: {block_type}")
        report.append("   The scraper is being prevented from accessing content")
    else:
        report.append("\n✅ NO BLOCKING DETECTED")
        report.append("   The scraper has access to the target content")
    
    # Bot Detection
    if result.bot_detection_system and result.bot_detection_system != BotDetectionSystem.NONE:
        report.append(f"\n🛡️  BOT DETECTION SYSTEM: {result.bot_detection_system.value.upper()}")
        if result.metadata.get('bot_indicators'):
            report.append("   Indicators found:")
            for indicator in result.metadata['bot_indicators']:
                report.append(f"   - {indicator}")
    else:
        report.append("\n⭕ NO BOT DETECTION SYSTEM IDENTIFIED")
    
    # Data Quality Metrics
    if 'data_stats' in result.metadata:
        stats = result.metadata['data_stats']
        report.append(f"\n📊 DATA QUALITY METRICS:")
        report.append(f"   Total items: {stats.get('total_items', 0)}")
        report.append(f"   Overall quality score: {result.confidence_score:.2f}")
        
        field_stats = stats.get('field_completeness', {})
        if field_stats:
            report.append("   Field completeness:")
            for field, data in field_stats.items():
                completeness = data.get('completeness', 0)
                count = data.get('count', 0)
                status = "✅" if completeness > 0.8 else "⚠️ " if completeness > 0.5 else "❌"
                report.append(f"     {status} {field}: {completeness:.1%} ({count} items)")
    
    # Issues and Warnings
    if result.issues:
        report.append("\n❌ ISSUES DETECTED:")
        for i, issue in enumerate(result.issues, 1):
            report.append(f"   {i}. {issue}")
    
    if result.warnings:
        report.append("\n⚠️  WARNINGS:")
        for i, warning in enumerate(result.warnings, 1):
            report.append(f"   {i}. {warning}")
    
    # Recommendations
    report.append("\n💡 RECOMMENDATIONS:")
    if result.is_blocked and not result.is_successful:
        report.append("   🔧 BLOCKING DETECTED - Try alternative scrapers:")
        report.append("      • Use Playwright scraper for JavaScript rendering")
        report.append("      • Use Pydoll scraper for adaptive fallback")
        report.append("      • Check robots.txt compliance")
        report.append("      • Consider using different user agents or proxies")
    elif not result.is_successful and not result.is_blocked:
        report.append("   🔧 DATA QUALITY ISSUES - Improve extraction:")
        report.append("      • Review CSS selectors in spider configuration")
        report.append("      • Check if website structure has changed")
        report.append("      • Consider using browser automation for dynamic content")
        report.append("      • Verify target elements exist on the page")
    elif result.is_successful:
        if result.bot_detection_system and result.bot_detection_system != BotDetectionSystem.NONE:
            report.append("   🔧 BOT DETECTION PRESENT - Monitor for future issues:")
            report.append("      • Scraping successful but detection system identified")
            report.append("      • Consider rotating user agents or using proxies")
            report.append("      • Monitor for potential rate limiting")
        else:
            report.append("   🎉 EXCELLENT RESULTS:")
            report.append("      • Scraping successful with good data quality")
            report.append("      • No blocking or bot detection systems identified")
            report.append("      • Continue with current scraping approach")
    
    report.append("\n" + "=" * 60)
    
    return "\n".join(report)

def main():
    """Main CLI interface for validation tool"""
    parser = argparse.ArgumentParser(
        description='Validate scraping results for quality, blocking, and bot detection',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python validate_results.py --csv scraped_results/domain_20241210_143022/scraped_data.csv
  python validate_results.py --url "https://example.com"
  python validate_results.py --csv data.csv --show-details
        '''
    )
    
    parser.add_argument('--csv', help='Path to CSV file with scraped data')
    parser.add_argument('--url', help='URL to create basic validation for')
    parser.add_argument('--response-data', help='Path to JSON file with response data')
    parser.add_argument('--show-details', action='store_true', help='Show detailed field analysis')
    parser.add_argument('--output', help='Save report to file')
    
    args = parser.parse_args()
    
    if not args.csv and not args.url:
        parser.error("Either --csv or --url must be specified")
    
    print("🔍 ScrapingValidator - Intelligent Validation Tool")
    print("=" * 50)
    
    # Initialize validator
    validator = SimpleValidator()
    
    # Load data
    scraped_data = None
    if args.csv:
        scraped_data = load_csv_data(args.csv)
        if scraped_data is None:
            return 1
    
    # Create or load response data
    response_data = None
    if args.response_data and os.path.exists(args.response_data):
        try:
            with open(args.response_data, 'r') as f:
                response_data = json.load(f)
            print(f"📥 Loaded response data from {args.response_data}")
        except Exception as e:
            print(f"⚠️  Warning: Could not load response data: {str(e)}")
    
    if not response_data:
        if args.url:
            response_data = create_sample_response_data(args.url)
        else:
            # Create minimal response data
            response_data = create_sample_response_data('unknown')
    
    # Validate
    print("🔄 Running validation analysis...")
    try:
        result = validator.validate_scraping_result(response_data, scraped_data)
        
        # Generate report
        report = format_validation_report(result, validator)
        
        # Output report
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"📄 Report saved to: {args.output}")
        else:
            print(report)
        
        # Exit code based on success
        if result.is_successful and not result.is_blocked:
            return 0  # Success
        elif result.is_blocked:
            return 2  # Blocked
        else:
            return 1  # Data quality issues
        
    except Exception as e:
        print(f"❌ Validation failed: {str(e)}")
        return 3

if __name__ == "__main__":
    sys.exit(main())