#!/usr/bin/env python3
"""
Local test script to validate Lambda function without deployment
"""
import sys
import os
import json
from unittest.mock import Mock, patch

# Add lambda directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lambda'))

def test_config_loading():
    """Test campground config loading"""
    try:
        from index import load_campground_config
        config = load_campground_config()
        
        # Validate structure
        assert isinstance(config, dict), "Config should be dict"
        assert 'campgrounds' in config, "Config should have 'campgrounds' key"
        assert isinstance(config['campgrounds'], list), "Campgrounds should be list"
        
        print("✅ Config loading test passed")
        return True
    except Exception as e:
        print(f"❌ Config loading test failed: {e}")
        return False

def test_function_definitions():
    """Test that all functions are properly defined"""
    try:
        from index import (
            load_campground_config,
            group_campgrounds_by_provider,
            get_campground_metadata,
            get_campground_info_by_facility_name,
            generate_dashboard,
            send_notification
        )
        print("✅ All functions properly defined")
        return True
    except ImportError as e:
        print(f"❌ Function definition test failed: {e}")
        return False

def test_date_formatting():
    """Test date formatting with correct timezone"""
    try:
        from index import format_date_with_relative
        from datetime import datetime, timedelta
        import pytz
        
        # Test with tomorrow's date
        pacific_tz = pytz.timezone('US/Pacific')
        today = datetime.now(pacific_tz).date()
        tomorrow = today + timedelta(days=1)
        tomorrow_str = tomorrow.isoformat()
        
        formatted = format_date_with_relative(tomorrow_str)
        print(f"Tomorrow's date formatted: {formatted}")
        
        if "tomorrow" in formatted:
            print("✅ Date formatting uses correct timezone")
            return True
        else:
            print("❌ Date formatting timezone issue")
            return False
            
    except Exception as e:
        print(f"❌ Date formatting test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        from datetime import datetime
        import pytz
        
        # Test with tomorrow's date
        pacific_tz = pytz.timezone('US/Pacific')
        tomorrow = datetime.now(pacific_tz).date()
        tomorrow = tomorrow.replace(day=tomorrow.day + 1)
        tomorrow_str = tomorrow.isoformat()
        
        formatted = format_date_with_relative(tomorrow_str)
        print(f"Tomorrow's date formatted: {formatted}")
        
        if "tomorrow" in formatted:
            print("✅ Date formatting uses correct timezone")
            return True
        else:
            print("❌ Date formatting timezone issue")
            return False
            
    except Exception as e:
        print(f"❌ Date formatting test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_booking_url_generation():
    """Test booking URL generation with real data"""
    try:
        from index import generate_booking_url, load_campground_config
        
        config = load_campground_config()
        
        # Test 1: ReserveCalifornia URL generation by campground_id
        test_site1 = {
            'campground_id': 766,  # Steep Ravine Cabin Area
            'facility_name': 'S Rav Cabin Area',
            'booking_url': 'https://www.reservecalifornia.com/CaliforniaWebHome/Facilities/AdvanceSearch.aspx'
        }
        
        url1 = generate_booking_url(test_site1, config)
        print(f"Test 1 - By ID: {url1}")
        
        # Test 2: ReserveCalifornia URL generation by facility name fallback
        test_site2 = {
            'campground_id': None,  # No ID, should use facility name
            'facility_name': 'S Rav Cabin Area',
            'booking_url': 'https://www.reservecalifornia.com/CaliforniaWebHome/Facilities/AdvanceSearch.aspx'
        }
        
        url2 = generate_booking_url(test_site2, config)
        print(f"Test 2 - By Name: {url2}")
        
        # Check if URLs have correct format
        expected_format = "https://reservecalifornia.com/park/"
        success = True
        
        if expected_format not in url1:
            print(f"❌ Test 1 failed. Expected: {expected_format}, Got: {url1}")
            success = False
        else:
            print("✅ Test 1 passed - URL by ID correct")
            
        if expected_format not in url2:
            print(f"❌ Test 2 failed. Expected: {expected_format}, Got: {url2}")
            success = False
        else:
            print("✅ Test 2 passed - URL by name correct")
            
        return success
            
    except Exception as e:
        print(f"❌ Booking URL test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("🧪 Running local Lambda tests...\n")
    
    tests = [
        test_function_definitions,
        test_config_loading,
        test_date_formatting,
        test_booking_url_generation,
    ]
    
    passed = 0
    for test in tests:
        if test():
            passed += 1
        print()
    
    print(f"📊 Results: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("🎉 All tests passed! Safe to deploy.")
        return 0
    else:
        print("⚠️  Some tests failed. Fix issues before deploying.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
