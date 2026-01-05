#!/usr/bin/env python3
"""
Unit tests for Lambda function components
"""
import sys
import os
import json
from unittest.mock import Mock, patch

# Add lambda directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../lambda'))

def test_function_definitions():
    """Test that all required functions are properly defined"""
    try:
        import index
        
        # Check critical functions exist
        assert hasattr(index, 'lambda_handler'), "lambda_handler function missing"
        assert hasattr(index, 'load_campground_config'), "load_campground_config function missing"
        assert hasattr(index, 'get_campground_info_by_facility_name'), "get_campground_info_by_facility_name function missing"
        assert hasattr(index, 'generate_booking_url'), "generate_booking_url function missing"
        assert hasattr(index, 'should_send_notification'), "should_send_notification function missing"
        
        print("✅ All functions properly defined")
        return True
    except Exception as e:
        print(f"❌ Function definition test failed: {e}")
        return False

def test_config_loading():
    """Test campground configuration loading"""
    try:
        from index import load_campground_config
        
        config = load_campground_config()
        assert config is not None, "Config should not be None"
        assert 'campgrounds' in config, "Config should have campgrounds key"
        assert isinstance(config['campgrounds'], list), "Campgrounds should be a list"
        assert len(config['campgrounds']) > 0, "Should have at least one campground"
        
        print("✅ Config loading test passed")
        return True
    except Exception as e:
        print(f"❌ Config loading test failed: {e}")
        return False

def test_facility_name_matching():
    """Test facility name pattern matching"""
    try:
        from index import get_campground_info_by_facility_name, load_campground_config
        
        config = load_campground_config()
        
        # Test cases with expected matches
        test_cases = [
            ("Steep Ravine Cabin 001", "Steep Ravine Cabins"),
            ("S Rav Cabin Area", "Steep Ravine Cabins"),
            ("S Rav Camp Area Site 1", "Steep Ravine Campsites"),
            ("Unknown Facility", None)
        ]
        
        for facility_name, expected_name in test_cases:
            result = get_campground_info_by_facility_name(facility_name, config)
            if expected_name:
                assert result is not None, f"Should find match for {facility_name}"
                assert result['name'] == expected_name, f"Expected {expected_name}, got {result['name']}"
            else:
                assert result is None, f"Should not find match for {facility_name}"
        
        print("✅ Facility name matching test passed")
        return True
    except Exception as e:
        print(f"❌ Facility name matching test failed: {e}")
        return False

def run_unit_tests():
    """Run all unit tests"""
    print("🧪 Running Lambda unit tests...\n")
    
    tests = [
        test_function_definitions,
        test_config_loading,
        test_facility_name_matching
    ]
    
    passed = 0
    for test in tests:
        if test():
            passed += 1
        print()
    
    print(f"📊 Results: {passed}/{len(tests)} unit tests passed")
    return passed == len(tests)

if __name__ == "__main__":
    success = run_unit_tests()
    sys.exit(0 if success else 1)
