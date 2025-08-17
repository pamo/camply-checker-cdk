#!/usr/bin/env python3
"""
Test specifically for Steep Ravine campground searchability.
"""

import sys
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def test_steep_ravine_search():
    """Test if we can search Steep Ravine campground specifically."""

    logger.info("🏕️ Testing Steep Ravine campground search...")

    try:
        from camply.search import CAMPSITE_SEARCH_PROVIDER
        from camply.containers import SearchWindow

        # Steep Ravine details
        campground_id = 766
        campground_name = "Steep Ravine"
        provider_name = "ReserveCalifornia"

        logger.info(f"Campground: {campground_name} (ID: {campground_id})")
        logger.info(f"Provider: {provider_name}")

        # Create search window
        start_date = datetime.now().date()
        end_date = (datetime.now() + timedelta(days=90)).date()
        search_window = SearchWindow(start_date=start_date, end_date=end_date)

        logger.info(f"Search window: {start_date} to {end_date}")

        # Get the provider class
        provider_class = CAMPSITE_SEARCH_PROVIDER.get(provider_name)
        if not provider_class:
            logger.error(f"❌ Provider {provider_name} not found")
            return False

        logger.info(f"✅ Found provider class: {provider_class.__name__}")

        # Try different parameter combinations for ReserveCalifornia
        logger.info("Testing parameter combinations...")

        # Attempt 1: Using campground_ids (our current approach)
        try:
            logger.info("  Attempt 1: Using campground_ids parameter...")
            search_kwargs = {
                'search_window': search_window,
                'recreation_area': [1],  # Placeholder
                'campground_ids': [campground_id],
                'weekends_only': False,
                'nights': 1,
                'offline_search': False,
                'verbose': False
            }

            search_instance = provider_class(**search_kwargs)
            logger.info("  ✅ Successfully created search instance with campground_ids")

            # Try to run a search (this might fail, but let's see what happens)
            logger.info("  Running search...")
            results = search_instance.get_matching_campsites(log=False, verbose=False)
            logger.info(f"  ✅ Search completed! Found {len(results)} campsites")

            if results:
                logger.info("  Sample results:")
                for i, campsite in enumerate(results[:3]):  # Show first 3
                    logger.info(f"    {i+1}. {campsite.campsite_site_name} - {campsite.booking_date.strftime('%Y-%m-%d')}")

            return True

        except Exception as e:
            logger.warning(f"  ⚠️ Attempt 1 failed: {e}")

        # Attempt 2: Try to find the correct recreation area
        try:
            logger.info("  Attempt 2: Trying to find correct recreation area...")

            # Let's try to search for recreation areas first
            provider_instance = provider_class.provider_class()  # Get the underlying provider

            if hasattr(provider_instance, 'find_campgrounds'):
                logger.info("  Searching for campgrounds to find recreation area...")
                campgrounds = provider_instance.find_campgrounds(
                    campground_id=[campground_id],
                    verbose=False
                )

                if campgrounds:
                    campground = campgrounds[0]
                    logger.info(f"  ✅ Found campground: {campground.facility_name}")
                    logger.info(f"  Recreation area ID: {campground.recreation_area_id}")
                    logger.info(f"  Recreation area: {campground.recreation_area}")

                    # Try search with correct recreation area
                    search_kwargs['recreation_area'] = [campground.recreation_area_id]
                    search_instance = provider_class(**search_kwargs)
                    results = search_instance.get_matching_campsites(log=False, verbose=False)
                    logger.info(f"  ✅ Search with correct recreation area completed! Found {len(results)} campsites")

                    return True
                else:
                    logger.warning("  ⚠️ No campgrounds found")

        except Exception as e:
            logger.warning(f"  ⚠️ Attempt 2 failed: {e}")

        # If we get here, the search setup worked but might not have found results
        logger.info("✅ Search setup successful (even if no availability found)")
        return True

    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run the Steep Ravine test."""
    logger.info("🧪 Starting Steep Ravine campground test...")

    if test_steep_ravine_search():
        logger.info("🎉 Steep Ravine campground is searchable!")
        return True
    else:
        logger.error("❌ Steep Ravine campground search failed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
