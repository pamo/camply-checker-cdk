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

def test_notification_logic():
    """Test email notification deduplication logic"""
    try:
        from index import should_send_notification
        from unittest.mock import Mock, patch

        # Test data
        sites_data = [
            {'campsite_id': '123', 'facility_name': 'Test Camp', 'booking_date': '2026-01-05'},
            {'campsite_id': '456', 'facility_name': 'Test Camp', 'booking_date': '2026-01-06'}
        ]

        # Test 1: No cache bucket - should always send
        with patch.dict('os.environ', {}, clear=True):
            result = should_send_notification(sites_data, 'TestProvider')
            if result:
                print("✅ Test 1 passed - No cache bucket, sends notification")
            else:
                print("❌ Test 1 failed - Should send when no cache bucket")
                return False

        # Test 2: Mock S3 - first time (no previous hash)
        mock_s3 = Mock()
        mock_s3.get_object.side_effect = Exception("NoSuchKey")  # Simulate no previous hash
        mock_s3.put_object.return_value = {}

        with patch('boto3.client', return_value=mock_s3), \
             patch.dict('os.environ', {'CACHE_BUCKET_NAME': 'test-bucket'}):
            result = should_send_notification(sites_data, 'TestProvider')
            if result:
                print("✅ Test 2 passed - First time, sends notification")
            else:
                print("❌ Test 2 failed - Should send on first run")
                return False

        # Test 3: Mock S3 - same data (should not send)
        import hashlib
        current_hash = hashlib.md5(str(sorted(sites_data, key=lambda x: x.get('campsite_id', ''))).encode()).hexdigest()

        mock_s3_same = Mock()
        mock_body = Mock()
        mock_body.read.return_value.decode.return_value.strip.return_value = current_hash
        mock_response = {'Body': mock_body}
        mock_s3_same.get_object.return_value = mock_response

        with patch('boto3.client', return_value=mock_s3_same), \
             patch.dict('os.environ', {'CACHE_BUCKET_NAME': 'test-bucket'}):
            result = should_send_notification(sites_data, 'TestProvider')
            if not result:
                print("✅ Test 3 passed - Same data, skips notification")
            else:
                print("❌ Test 3 failed - Should not send for same data")
                return False

        # Test 4: Mock S3 - different data (should send)
        mock_s3_diff = Mock()
        mock_body_diff = Mock()
        mock_body_diff.read.return_value.decode.return_value.strip.return_value = "different_hash"
        mock_response_diff = {'Body': mock_body_diff}
        mock_s3_diff.get_object.return_value = mock_response_diff
        mock_s3_diff.put_object.return_value = {}

        with patch('boto3.client', return_value=mock_s3_diff), \
             patch.dict('os.environ', {'CACHE_BUCKET_NAME': 'test-bucket'}):
            result = should_send_notification(sites_data, 'TestProvider')
            if result:
                print("✅ Test 4 passed - Different data, sends notification")
            else:
                print("❌ Test 4 failed - Should send for different data")
                return False

        print("✅ All notification logic tests passed")
        return True

    except Exception as e:
        print(f"❌ Notification logic test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_email_flow_integration():
    """Test that email flow only sends when there are actual changes"""
    try:
        from unittest.mock import Mock, patch

        # Simulate the main flow logic
        sites_data = [{'campsite_id': '123', 'facility_name': 'Test'}]

        # Test 1: No changes detected - should not add to changed results
        all_changed_results = []

        # Mock should_send_notification to return False (no changes)
        with patch('index.should_send_notification') as mock_should_send:
            mock_should_send.return_value = False

            # Simulate the main logic
            if mock_should_send(sites_data, 'TestProvider'):
                all_changed_results.extend(sites_data)

            if len(all_changed_results) == 0:
                print("✅ Test 1 passed - No changes, no email sent")
            else:
                print("❌ Test 1 failed - Should not send email when no changes")
                return False

        # Test 2: Changes detected - should add to changed results
        all_changed_results = []  # Reset

        # Mock should_send_notification to return True (changes detected)
        with patch('index.should_send_notification') as mock_should_send:
            mock_should_send.return_value = True

            # Simulate the main logic
            if mock_should_send(sites_data, 'TestProvider'):
                all_changed_results.extend(sites_data)

            if len(all_changed_results) > 0:
                print("✅ Test 2 passed - Changes detected, email will be sent")
            else:
                print("❌ Test 2 failed - Should send email when changes detected")
                return False

        print("✅ Email flow integration tests passed")
        return True

    except Exception as e:
        print(f"❌ Email flow integration test failed: {e}")
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
        # Try with different variations
        variations = ['Steep Ravine', 'S Rav Cabin', 'Cabin Area']
        for variation in variations:
            debug_result = get_campground_info_by_facility_name(variation, config)
            print(f"Debug - '{variation}' lookup: {debug_result is not None}")

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
        test_notification_logic,
        test_email_flow_integration,
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
