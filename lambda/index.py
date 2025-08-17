import json
import os
import logging
from datetime import datetime, timedelta
from camply_filesystem_patch import setup_camply_filesystem, cleanup_temp_dir
from s3_result_store import S3ResultStore
from result_comparator import ResultComparator
from multi_email_notifier import MultiEmailNotifier
from metrics_publisher import MetricsPublisher

# Set up logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Set up filesystem redirection for camply
temp_dir = setup_camply_filesystem()

class CampgroundConfig:
    def __init__(self, id: str, name: str, provider: str):
        self.id = id
        self.name = name
        self.provider = provider

CAMPGROUNDS = [
    CampgroundConfig('766', 'Steep Ravine', 'ReserveCalifornia'),
    CampgroundConfig('590', 'Steep Ravine Campgrounds', 'ReserveCalifornia'),
    CampgroundConfig('2009', 'Pantoll Campground', 'ReserveCalifornia'),
    CampgroundConfig('589', 'Frank Valley Horse Campground', 'ReserveCalifornia'),
    CampgroundConfig('2008', 'Bootjack Campground', 'ReserveCalifornia'),

    CampgroundConfig('518', 'Julia Pfeiffer Burns', 'ReserveCalifornia'),
    CampgroundConfig('252037', 'Sardine Peak Lookout', 'RecreationDotGov')
]
SEARCH_WINDOW_DAYS = int(os.environ['SEARCH_WINDOW_DAYS'])
S3_CACHE_BUCKET = os.environ.get('CACHE_BUCKET_NAME', '')

# Initialize components
s3_store = S3ResultStore(S3_CACHE_BUCKET) if S3_CACHE_BUCKET else None
result_comparator = ResultComparator()
metrics_publisher = MetricsPublisher()


def search_campgrounds():
    """
    Enhanced campground search with result comparison and multi-email notifications.

    This function:
    1. Searches each campground using camply
    2. Stores results in S3 and compares with previous results
    3. Sends notifications only if results have changed
    4. Uses multi-email notification system
    5. Publishes CloudWatch metrics for monitoring
    """


    start_date = datetime.now().strftime('%Y-%m-%d')
    end_date = (datetime.now() + timedelta(days=SEARCH_WINDOW_DAYS)).strftime('%Y-%m-%d')

    for campground in CAMPGROUNDS:
        logger.info(f"Searching for {campground.name} (ID: {campground.id})")

        try:
            # Capture camply output to get search results
            current_results = capture_camply_results(campground, start_date, end_date)

            # Check if there's availability first
            has_availability = check_availability(current_results)

            if not has_availability:
                logger.info(f"No availability found for {campground.name}, skipping notification")
                metrics_publisher.publish_notification_skipped(
                    campground.id,
                    campground.name,
                    "no_availability"
                )
                continue

            # Process results and determine if notification is needed
            should_notify = process_campground_results(campground, current_results)

            if should_notify:
                logger.info(f"Availability found for {campground.name}, sending notifications")
                # Send notifications using multi-email system
                send_campground_notifications(campground, current_results)
            else:
                # Publish metrics for skipped notification
                metrics_publisher.publish_notification_skipped(
                    campground.id,
                    campground.name,
                    "no_changes_detected"
                )
                logger.info(f"Availability found for {campground.name} but no changes detected, skipping notifications")

        except SystemExit as e:
            logger.warning(f"Camply called sys.exit() while processing {campground.name} - continuing with next campground")
            # Continue with other campgrounds even if camply exits
            continue
        except Exception as e:
            logger.error(f"Error processing {campground.name}: {str(e)}")
            # Continue with other campgrounds even if one fails
            continue


def capture_camply_results(campground: CampgroundConfig, start_date: str, end_date: str) -> dict:
    """
    Capture camply search results using camply as a library.

    Args:
        campground: Campground configuration
        start_date: Search start date
        end_date: Search end date

    Returns:
        Dictionary containing search results
    """
    from camply.search import CAMPSITE_SEARCH_PROVIDER
    from camply.containers import SearchWindow
    from datetime import datetime

    try:
        # Convert string dates to datetime objects
        start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()

        # Create search window
        search_window = SearchWindow(start_date=start_dt, end_date=end_dt)

        # Get the appropriate search provider class
        provider_class = CAMPSITE_SEARCH_PROVIDER.get(campground.provider)
        if not provider_class:
            raise ValueError(f"Unknown provider: {campground.provider}")

        # Set up search parameters based on provider
        search_kwargs = {
            'search_window': search_window,
            'weekends_only': False,
            'nights': 1,
            'offline_search': False,
            'verbose': False  # Disable verbose logging to reduce noise
        }

        # Add provider-specific parameters based on the CLI parameter mapping
        if campground.provider == 'RecreationDotGov':
            # RecreationDotGov uses campgrounds parameter
            search_kwargs['campgrounds'] = [int(campground.id)]
        elif campground.provider in ['ReserveCalifornia', 'AlabamaStateParks', 'ArizonaStateParks',
                                     'FloridaStateParks', 'MinnesotaStateParks', 'MissouriStateParks',
                                     'OhioStateParks', 'VirginiaStateParks', 'NorthernTerritory',
                                     'FairfaxCountyParks', 'MaricopaCountyParks', 'OregonMetro']:
            # UseDirect-based providers need recreation_area and campground_ids
            # For now, we'll use a placeholder recreation_area - this might need to be configured per campground
            search_kwargs['recreation_area'] = [1]  # Placeholder - may need to be campground-specific
            search_kwargs['campground_ids'] = [int(campground.id)]
        elif campground.provider == 'GoingToCamp':
            # GoingToCamp uses recreation_area parameter
            search_kwargs['recreation_area'] = [1]  # Placeholder - needs to be configured
            search_kwargs['campgrounds'] = [int(campground.id)]
        else:
            # Default approach for unknown providers
            search_kwargs['campgrounds'] = [int(campground.id)]

        logger.info(f"Searching {campground.name} using camply library with provider {campground.provider}")
        logger.debug(f"Search parameters: {search_kwargs}")

        # Create search instance and get results
        search_instance = provider_class(**search_kwargs)
        available_campsites = search_instance.get_matching_campsites(
            log=False,  # Disable logging to avoid noise
            verbose=False
        )

        logger.debug(f"Camply returned {len(available_campsites)} AvailableCampsite objects")

        # Convert AvailableCampsite objects to structured results
        results = convert_campsites_to_results(available_campsites, campground, start_date, end_date)

        logger.info(f"Found {len(available_campsites)} available campsites for {campground.name}")
        return results

    except SystemExit as e:
        logger.warning(f"Camply called sys.exit() for {campground.name} - likely no results found")
        # Return empty results when camply exits (usually means no availability)
        return {
            'campground_id': campground.id,
            'campground_name': campground.name,
            'provider': campground.provider,
            'search_parameters': {
                'start_date': start_date,
                'end_date': end_date
            },
            'available_sites': [],
            'no_results_found': True
        }
    except Exception as e:
        logger.error(f"Error searching {campground.name} with camply library: {str(e)}")
        # Return empty results on error to allow processing to continue
        return {
            'campground_id': campground.id,
            'campground_name': campground.name,
            'provider': campground.provider,
            'search_parameters': {
                'start_date': start_date,
                'end_date': end_date
            },
            'available_sites': [],
            'error': str(e)
        }


def convert_campsites_to_results(available_campsites, campground: CampgroundConfig, start_date: str, end_date: str) -> dict:
    """
    Convert AvailableCampsite objects to our structured results format.

    Args:
        available_campsites: List of AvailableCampsite objects from camply
        campground: Campground configuration
        start_date: Search start date
        end_date: Search end date

    Returns:
        Structured results dictionary
    """
    results = {
        'campground_id': campground.id,
        'campground_name': campground.name,
        'provider': campground.provider,
        'search_parameters': {
            'start_date': start_date,
            'end_date': end_date
        },
        'available_sites': [],
        'total_available_nights': 0
    }

    try:
        available_sites = []
        total_nights = 0

        for campsite in available_campsites:
            # Validate that we have an AvailableCampsite object
            if not hasattr(campsite, 'campsite_id') or not hasattr(campsite, 'booking_date'):
                logger.warning(f"Invalid campsite object received: {type(campsite)}")
                continue

            # Convert AvailableCampsite to our format
            site_info = {
                'campsite_id': str(campsite.campsite_id),
                'site_name': campsite.campsite_site_name,
                'campsite_type': campsite.campsite_type,
                'loop_name': campsite.campsite_loop_name,
                'booking_date': campsite.booking_date.strftime('%Y-%m-%d'),
                'booking_end_date': campsite.booking_end_date.strftime('%Y-%m-%d'),
                'booking_nights': campsite.booking_nights,
                'availability_status': campsite.availability_status,
                'booking_url': campsite.booking_url,
                'facility_name': campsite.facility_name,
                'recreation_area': campsite.recreation_area,
                'occupancy': campsite.campsite_occupancy,
                'use_type': campsite.campsite_use_type
            }

            # Add location if available
            if campsite.location:
                site_info['location'] = {
                    'latitude': campsite.location.latitude,
                    'longitude': campsite.location.longitude
                }

            # Add equipment information if available
            if campsite.permitted_equipment:
                site_info['permitted_equipment'] = [
                    {
                        'equipment_name': eq.equipment_name,
                        'max_length': eq.max_length
                    }
                    for eq in campsite.permitted_equipment
                ]

            # Add attributes if available
            if campsite.campsite_attributes:
                site_info['attributes'] = [
                    {
                        'name': attr.attribute_name,
                        'value': attr.attribute_value
                    }
                    for attr in campsite.campsite_attributes
                ]

            available_sites.append(site_info)
            total_nights += campsite.booking_nights

        results['available_sites'] = available_sites
        results['total_available_nights'] = total_nights

        logger.debug(f"Converted {len(available_sites)} campsites for {campground.name}")

    except Exception as e:
        logger.warning(f"Error converting campsites for {campground.name}: {str(e)}")
        results['conversion_error'] = str(e)

    return results


def process_campground_results(campground: CampgroundConfig, current_results: dict) -> bool:
    """
    Process campground results and determine if notifications should be sent.

    Args:
        campground: Campground configuration
        current_results: Current search results

    Returns:
        True if notifications should be sent, False otherwise
    """
    try:
        # First check if there's any availability - don't notify if no sites available
        has_availability = check_availability(current_results)

        if not has_availability:
            logger.info(f"No availability found for {campground.name}, skipping notification")

            # Still store results in S3 for tracking
            if s3_store:
                storage_success = s3_store.store_results(campground.id, current_results)
                if not storage_success:
                    logger.warning(f"Failed to store results for {campground.name} in S3")
                    metrics_publisher.publish_s3_operation_failure('put', S3_CACHE_BUCKET, f"search-results/{campground.id}/latest.json")

            return False

        # If there's availability, check if results have changed (if S3 is available)
        if s3_store:
            # Check if results have changed
            results_changed = s3_store.has_results_changed(campground.id, current_results)

            # Store current results regardless of whether they changed
            storage_success = s3_store.store_results(campground.id, current_results)

            if not storage_success:
                logger.warning(f"Failed to store results for {campground.name} in S3")
                # Publish S3 failure metric
                metrics_publisher.publish_s3_operation_failure('put', S3_CACHE_BUCKET, f"search-results/{campground.id}/latest.json")

            # Only notify if results changed AND there's availability
            return results_changed
        else:
            logger.info("S3 store not available, notifying for any availability found")
            # Without S3, notify for any availability (since we can't track changes)
            return True

    except Exception as e:
        logger.error(f"Error processing results for {campground.name}: {str(e)}")
        # Default to not sending notifications on error to avoid spam
        return False


def check_availability(results: dict) -> bool:
    """
    Check if the search results contain any actual availability.

    Args:
        results: Search results dictionary

    Returns:
        True if availability is found, False otherwise
    """
    try:
        # Check if there was an error during search
        if 'error' in results:
            logger.warning(f"Search error detected: {results['error']}")
            return False

        # Check total available nights
        total_nights = results.get('total_available_nights', 0)
        if total_nights > 0:
            return True

        # Check available sites
        available_sites = results.get('available_sites', [])
        if not available_sites:
            return False

        # With the new structured format, any site in available_sites represents actual availability
        # since camply only returns AvailableCampsite objects for truly available sites
        for site in available_sites:
            # Check if site has valid booking information
            if site.get('booking_url') and site.get('campsite_id'):
                # Check availability status
                status = site.get('availability_status', '').lower()
                if status and 'available' in status:
                    return True

                # If no explicit status, but we have booking info, consider it available
                if site.get('booking_date') and site.get('booking_nights', 0) > 0:
                    return True

        return False

    except Exception as e:
        logger.warning(f"Error checking availability: {str(e)}")
        # Default to False to avoid false positive notifications
        return False


def send_campground_notifications(campground: CampgroundConfig, results: dict):
    """
    Send notifications for campground availability using multi-email system.
    If email is not configured, just log the availability details.

    Args:
        campground: Campground configuration
        results: Search results to include in notification
    """
    try:
        # Try to initialize multi-email notifier
        notifier = MultiEmailNotifier()
        config_validation = notifier.validate_configuration()

        if not config_validation['valid']:
            # Email not configured - just log the availability
            logger.info(f"Email not configured - logging availability for {campground.name}")
            body = create_notification_body(campground, results)
            logger.info(f"Availability details for {campground.name}:\n{body}")

            # Publish metrics indicating notification was skipped due to config
            metrics_publisher.publish_notification_skipped(
                campground.id,
                campground.name,
                "email_not_configured"
            )
            return

        # Create email subject and body
        subject = f"Camply: {campground.name} Availability Update"
        body = create_notification_body(campground, results)

        # Send notifications
        delivery_results = notifier.send_notifications(subject, body)

        # Publish metrics
        metrics_publisher.publish_email_delivery_metrics(
            campground.id,
            campground.name,
            delivery_results['success_count'],
            delivery_results['failure_count'],
            [result['email'] for result in delivery_results['results']]
        )

        # Log results
        logger.info(f"Notification delivery for {campground.name}: "
                   f"{delivery_results['success_count']} successful, "
                   f"{delivery_results['failure_count']} failed")

        if delivery_results['errors']:
            logger.warning(f"Notification errors for {campground.name}: {delivery_results['errors']}")

    except Exception as e:
        logger.warning(f"Email system not available for {campground.name}: {str(e)}")
        # Log the availability details instead
        try:
            body = create_notification_body(campground, results)
            logger.info(f"Availability details for {campground.name}:\n{body}")
        except Exception as body_error:
            logger.error(f"Error creating notification body: {str(body_error)}")

        # Publish failure metrics
        metrics_publisher.publish_notification_skipped(
            campground.id,
            campground.name,
            "email_system_error"
        )


def create_notification_body(campground: CampgroundConfig, results: dict) -> str:
    """
    Create email notification body from search results.

    Args:
        campground: Campground configuration
        results: Search results

    Returns:
        Formatted email body text
    """
    try:
        body_lines = [
            f"Campsite availability update for {campground.name}",
            f"Provider: {campground.provider}",
            f"Campground ID: {campground.id}",
            "",
            "Available Campsites:",
            ""
        ]

        available_sites = results.get('available_sites', [])

        if available_sites:
            for site in available_sites:
                site_name = site.get('site_name', 'Unknown Site')
                campsite_id = site.get('campsite_id', 'N/A')

                body_lines.append(f"🏕 {site_name} (ID: {campsite_id})")

                # Add booking details
                booking_date = site.get('booking_date')
                booking_end_date = site.get('booking_end_date')
                booking_nights = site.get('booking_nights', 1)

                if booking_date:
                    if booking_end_date and booking_end_date != booking_date:
                        body_lines.append(f"   📅 {booking_date} to {booking_end_date} ({booking_nights} night{'s' if booking_nights > 1 else ''})")
                    else:
                        body_lines.append(f"   📅 {booking_date} ({booking_nights} night{'s' if booking_nights > 1 else ''})")

                # Add campsite details
                campsite_type = site.get('campsite_type')
                if campsite_type:
                    body_lines.append(f"   🏕 Type: {campsite_type}")

                loop_name = site.get('loop_name')
                if loop_name:
                    body_lines.append(f"   📍 Loop: {loop_name}")

                occupancy = site.get('occupancy')
                if occupancy and isinstance(occupancy, (list, tuple)) and len(occupancy) == 2:
                    body_lines.append(f"   👥 Capacity: {occupancy[0]}-{occupancy[1]} people")

                # Add booking URL
                booking_url = site.get('booking_url')
                if booking_url:
                    body_lines.append(f"   🔗 Book now: {booking_url}")

                # Add equipment info if available
                equipment = site.get('permitted_equipment', [])
                if equipment:
                    equipment_names = [eq.get('equipment_name', 'Unknown') for eq in equipment[:3]]  # Limit to first 3
                    body_lines.append(f"   🚐 Equipment: {', '.join(equipment_names)}")
                    if len(equipment) > 3:
                        body_lines.append(f"       ... and {len(equipment) - 3} more")

                body_lines.append("")

            total_nights = results.get('total_available_nights', 0)
            body_lines.append(f"📊 Total available nights found: {total_nights}")
        else:
            body_lines.append("No available campsites found in this search.")

        # Add search parameters
        search_params = results.get('search_parameters', {})
        if search_params:
            body_lines.extend([
                "",
                "Search Parameters:",
                f"📅 Start Date: {search_params.get('start_date', 'N/A')}",
                f"📅 End Date: {search_params.get('end_date', 'N/A')}"
            ])

        # Add facility information if available
        if available_sites:
            first_site = available_sites[0]
            facility_name = first_site.get('facility_name')
            recreation_area = first_site.get('recreation_area')

            if facility_name or recreation_area:
                body_lines.extend([
                    "",
                    "Location Details:"
                ])
                if facility_name:
                    body_lines.append(f"🏕 Facility: {facility_name}")
                if recreation_area:
                    body_lines.append(f"⛰️ Recreation Area: {recreation_area}")

        # Add error information if present
        if 'error' in results:
            body_lines.extend([
                "",
                "⚠️ Note: There was an error during the search:",
                results['error']
            ])

        body_lines.extend([
            "",
            "---",
            "This is an automated notification from the Camply Site Checker.",
            f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"
        ])

        return "\n".join(body_lines)

    except Exception as e:
        logger.error(f"Error creating notification body: {str(e)}")
        # Return a basic notification on error
        return f"""
Campsite availability update for {campground.name}

There was an error formatting the detailed results, but availability was detected.

Error: {str(e)}

Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
"""

def lambda_handler(event, context):
    logger.info("Starting enhanced camply search with result comparison and multi-email notifications")

    # Validate required configuration
    if not S3_CACHE_BUCKET:
        logger.warning("CACHE_BUCKET_NAME not configured - result comparison will be disabled")

    # Check email configuration but don't fail if it's not configured
    email_configured = False
    try:
        notifier = MultiEmailNotifier()
        config_validation = notifier.validate_configuration()
        if config_validation['valid']:
            email_configured = True
            logger.info(f"Email configuration validated: {config_validation['email_config']['count']} recipients configured")
        else:
            logger.warning(f"Email configuration validation failed: {config_validation['errors']}")
            logger.warning("Continuing without email notifications - only logging results")
    except Exception as e:
        logger.warning(f"Email configuration not available: {str(e)}")
        logger.warning("Continuing without email notifications - only logging results")

    try:

        # Run campground searches
        search_campgrounds()
        logger.info("Enhanced camply searches completed successfully")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Camply check completed successfully',
                'campgrounds_processed': len(CAMPGROUNDS),
                's3_enabled': bool(S3_CACHE_BUCKET),
                'email_configured': email_configured
            })
        }
    except Exception as e:
        logger.error(f"Lambda execution failed: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Lambda execution failed',
                'details': str(e)
            })
        }
    finally:
        # Clean up temporary directory
        cleanup_temp_dir(temp_dir)
