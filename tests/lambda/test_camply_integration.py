#!/usr/bin/env python3
"""
Test script to verify camply integration works correctly.
"""

import sys
import os
import logging
from datetime import datetime, timedelta

# Add the lambda directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from index import CampgroundConfig, capture_camply_results, check_availability, convert_campsites_to_results

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_camply_integration():
    """Test camply integration with a known campground."""

    # Test with a Recreation.gov campground (Sardine Peak Lookout)
    campground = CampgroundConfig('252037', 'Sardine Peak Lookout', 'RecreationDotGov')

    # Search for next 30 days
    start_date = datetime.now().strftime('%Y-%m-%d')
    end_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')

    logger.info(f"Testing camply integration with {campground.name}")
    logger.info(f"Search window: {start_date} to {end_date}")

    try:
        # Test the capture function
        results = capture_camply_results(campground, start_date, end_date)

        logger.info(f"Results structure: {list(results.keys())}")
        logger.info(f"Available sites count: {len(results.get('available_sites', []))}")
        logger.info(f"Total available nights: {results.get('total_available_nights', 0)}")

        # Test availability checking
        has_availability = check_availability(results)
        logger.info(f"Has availability: {has_availability}")

        # Print first few sites if available
        available_sites = results.get('available_sites', [])
        if available_sites:
            logger.info("Sample available sites:")
            for i, site in enumerate(available_sites[:3]):  # Show first 3
                logger.info(f"  Site {i+1}: {site.get('site_name', 'Unknown')} - {site.get('booking_date', 'No date')}")

        # Test with ReserveCalifornia campground (Steep Ravine)
        logger.info("\n" + "="*50)
        campground2 = CampgroundConfig('766', 'Steep Ravine', 'ReserveCalifornia')
        logger.info(f"Testing camply integration with {campground2.name}")

        results2 = capture_camply_results(campground2, start_date, end_date)

        logger.info(f"Results structure: {list(results2.keys())}")
        logger.info(f"Available sites count: {len(results2.get('available_sites', []))}")
        logger.info(f"Total available nights: {results2.get('total_available_nights', 0)}")

        has_availability2 = check_availability(results2)
        logger.info(f"Has availability: {has_availability2}")

        available_sites2 = results2.get('available_sites', [])
        if available_sites2:
            logger.info("Sample available sites:")
            for i, site in enumerate(available_sites2[:3]):  # Show first 3
                logger.info(f"  Site {i+1}: {site.get('site_name', 'Unknown')} - {site.get('booking_date', 'No date')}")

        logger.info("\nTest completed successfully!")
        return True

    except Exception as e:
        logger.error(f"Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_camply_integration()
    sys.exit(0 if success else 1)
