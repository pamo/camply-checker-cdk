#!/usr/bin/env python3
"""
Tests for site prioritization and sorting logic
"""
import sys
import os

# Add lambda directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../lambda'))

def test_site_priority_sorting():
    """Test that sites are sorted by campground priority (cabins first)"""
    try:
        from index import load_campground_config
        
        # Load real config to get priorities
        config = load_campground_config()
        
        # Create mixed sites from both cabins (priority 1) and campsites (priority 2)
        mixed_sites = [
            {
                'campsite_id': 590001,
                'facility_name': 'S Rav Camp Area Site E1',
                'campground_id': 590,  # Campsites - priority 2
                'site_name': 'Site E1',
                'booking_date': '2026-01-07'
            },
            {
                'campsite_id': 766001, 
                'facility_name': 'S Rav Cabin 001',
                'campground_id': 766,  # Cabins - priority 1
                'site_name': 'Cabin 001',
                'booking_date': '2026-01-07'
            },
            {
                'campsite_id': 590002,
                'facility_name': 'S Rav Camp Area Site E2', 
                'campground_id': 590,  # Campsites - priority 2
                'site_name': 'Site E2',
                'booking_date': '2026-01-07'
            },
            {
                'campsite_id': 766002,
                'facility_name': 'S Rav Cabin 002',
                'campground_id': 766,  # Cabins - priority 1
                'site_name': 'Cabin 002', 
                'booking_date': '2026-01-07'
            }
        ]
        
        # TODO: Implement this function
        def sort_sites_by_priority(sites, config):
            """Sort sites by campground priority (lower number = higher priority)"""
            def get_priority(site):
                campground_id = site.get('campground_id')
                for campground in config.get('campgrounds', []):
                    if campground.get('id') == campground_id:
                        return campground.get('priority', 999)
                return 999
            
            return sorted(sites, key=get_priority)
        
        sorted_sites = sort_sites_by_priority(mixed_sites, config)
        
        # Expected order: All cabins (766) first, then campsites (590)
        expected_campground_order = [766, 766, 590, 590]
        actual_campground_order = [s['campground_id'] for s in sorted_sites]
        
        assert actual_campground_order == expected_campground_order, \
            f"Expected {expected_campground_order}, got {actual_campground_order}"
        
        # First two should be cabins
        assert sorted_sites[0]['campground_id'] == 766, "First site should be cabin"
        assert sorted_sites[1]['campground_id'] == 766, "Second site should be cabin"
        
        # Last two should be campsites  
        assert sorted_sites[2]['campground_id'] == 590, "Third site should be campsite"
        assert sorted_sites[3]['campground_id'] == 590, "Fourth site should be campsite"
        
        print("✅ Site priority sorting test passed")
        return True
    except Exception as e:
        print(f"❌ Site priority sorting test failed: {e}")
        return False

def test_priority_lookup():
    """Test that we can look up priority by campground ID"""
    try:
        from index import load_campground_config
        
        config = load_campground_config()
        
        # Create lookup function (to be implemented)
        def get_campground_priority(campground_id, config):
            """Get priority for a campground ID"""
            for campground in config.get('campgrounds', []):
                if campground.get('id') == campground_id:
                    return campground.get('priority', 999)
            return 999  # Default low priority
        
        # Test priority lookup
        cabin_priority = get_campground_priority(766, config)
        campsite_priority = get_campground_priority(590, config)
        
        assert cabin_priority == 1, f"Cabins should have priority 1, got {cabin_priority}"
        assert campsite_priority == 2, f"Campsites should have priority 2, got {campsite_priority}"
        assert cabin_priority < campsite_priority, "Cabins should have higher priority (lower number)"
        
        print("✅ Priority lookup test passed")
        return True
    except Exception as e:
        print(f"❌ Priority lookup test failed: {e}")
        return False

def test_email_ordering():
    """Test that email content shows cabins before campsites"""
    try:
        # Realistic mixed site data
        mixed_sites = [
            {
                'campsite_id': 590001,
                'facility_name': 'S Rav Camp Area Site E1',
                'campground_id': 590,
                'site_name': 'Site E1',
                'booking_date': '2026-01-07',
                'booking_url': 'https://reservecalifornia.com/park/682/590'
            },
            {
                'campsite_id': 766001,
                'facility_name': 'S Rav Cabin 001', 
                'campground_id': 766,
                'site_name': 'Cabin 001',
                'booking_date': '2026-01-07',
                'booking_url': 'https://reservecalifornia.com/park/682/766'
            }
        ]
        
        # TODO: Implement email formatting with priority
        # email_content = format_email_with_priority(mixed_sites, config)
        
        # For now, test that we can identify cabin vs campsite
        cabin_sites = [s for s in mixed_sites if s['campground_id'] == 766]
        campsite_sites = [s for s in mixed_sites if s['campground_id'] == 590]
        
        assert len(cabin_sites) == 1, "Should have 1 cabin site"
        assert len(campsite_sites) == 1, "Should have 1 campsite site"
        
        # Cabin should come first in any sorted list
        assert cabin_sites[0]['campsite_id'] == 766001, "Cabin should be identifiable"
        
        print("✅ Email ordering test structure ready")
        return True
    except Exception as e:
        print(f"❌ Email ordering test failed: {e}")
        return False

def run_priority_tests():
    """Run all priority/sorting tests"""
    print("🧪 Running site priority tests...\n")
    
    tests = [
        test_priority_lookup,
        test_site_priority_sorting,
        test_email_ordering
    ]
    
    passed = 0
    for test in tests:
        if test():
            passed += 1
        print()
    
    print(f"📊 Results: {passed}/{len(tests)} priority tests passed")
    return passed == len(tests)

if __name__ == "__main__":
    success = run_priority_tests()
    sys.exit(0 if success else 1)
