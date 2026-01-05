#!/usr/bin/env python3
"""
Integration tests for complete Lambda workflow
"""
import sys
import os
import json
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
import pytz

# Add lambda directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../lambda'))

def test_notification_logic():
    """Test email notification deduplication logic"""
    try:
        from index import should_send_notification
        
        # Mock boto3.client to simulate no cache bucket (should always send)
        with patch('index.boto3.client') as mock_boto3:
            mock_s3 = Mock()
            mock_boto3.return_value = mock_s3
            
            # Test: No cache bucket - should send
            mock_s3.head_object.side_effect = Exception("NoSuchBucket")
            result = should_send_notification([{'site': 'test'}], 'TestProvider')
            assert result == True, "Should send when no cache bucket"
            
            # Test: First time (no existing cache) - should send  
            mock_s3.head_object.side_effect = Exception("NoSuchKey")
            mock_s3.get_object.side_effect = Exception("NoSuchKey")
            result = should_send_notification([{'site': 'test'}], 'TestProvider')
            assert result == True, "Should send first time"
        
        print("✅ Notification logic tests passed")
        return True
    except Exception as e:
        print(f"❌ Notification logic test failed: {e}")
        return False

def test_url_generation():
    """Test booking URL generation"""
    try:
        from index import generate_booking_url, load_campground_config
        
        config = load_campground_config()
        
        # Test ID-based URL
        site_with_id = {
            'campground_id': 766,
            'facility_name': 'S Rav Cabin Area'
        }
        url = generate_booking_url(site_with_id, config)
        assert url.startswith("https://reservecalifornia.com/park/"), f"Expected ReserveCalifornia URL, got {url}"
        
        # Test facility name fallback
        site_without_id = {
            'campground_id': None,
            'facility_name': 'S Rav Cabin Area'
        }
        url = generate_booking_url(site_without_id, config)
        assert url.startswith("https://reservecalifornia.com/park/"), f"Expected fallback URL, got {url}"
        
        print("✅ URL generation tests passed")
        return True
    except Exception as e:
        print(f"❌ URL generation test failed: {e}")
        return False

def test_date_formatting():
    """Test timezone-aware date formatting"""
    try:
        from index import format_date_with_relative
        
        # Test tomorrow's date
        pacific = pytz.timezone('US/Pacific')
        now = datetime.now(pacific)
        tomorrow = now + timedelta(days=1)
        
        formatted = format_date_with_relative(tomorrow.strftime('%Y-%m-%d'))
        assert "tomorrow" in formatted.lower(), f"Expected 'tomorrow' in {formatted}"
        
        print("✅ Date formatting test passed")
        return True
    except Exception as e:
        print(f"❌ Date formatting test failed: {e}")
        return False

def run_integration_tests():
    """Run all integration tests"""
    print("🧪 Running Lambda integration tests...\n")
    
    tests = [
        test_notification_logic,
        test_url_generation,
        test_date_formatting
    ]
    
    passed = 0
    for test in tests:
        if test():
            passed += 1
        print()
    
    print(f"📊 Results: {passed}/{len(tests)} integration tests passed")
    return passed == len(tests)

if __name__ == "__main__":
    success = run_integration_tests()
    sys.exit(0 if success else 1)
