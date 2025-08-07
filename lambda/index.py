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
    # CampgroundConfig('518', 'Julia Pfeiffer Burns', 'ReserveCalifornia'),
    CampgroundConfig('252037', 'Sardine Peak Lookout', 'RecreationDotGov')
]
SEARCH_WINDOW_DAYS = int(os.environ['SEARCH_WINDOW_DAYS'])
S3_CACHE_BUCKET = os.environ.get('S3_CACHE_BUCKET', '')

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
    from camply.cli import camply_command_line
    import sys
    from io import StringIO
    import contextlib

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

        except Exception as e:
            logger.error(f"Error processing {campground.name}: {str(e)}")
            # Continue with other campgrounds even if one fails
            continue


def capture_camply_results(campground: CampgroundConfig, start_date: str, end_date: str) -> dict:
    """
    Capture camply search results without sending notifications.

    Args:
        campground: Campground configuration
        start_date: Search start date
        end_date: Search end date

    Returns:
        Dictionary containing search results
    """
    from camply.cli import camply_command_line
    import sys
    from io import StringIO
    import contextlib

    # Build camply command without notifications to capture results
    command = [
        'campsites',
        '--provider', campground.provider,
        '--campground', campground.id,
        '--start-date', start_date,
        '--end-date', end_date,
        '--search-once'
    ]

    logger.info(f"Running camply command: {' '.join(command)}")

    # Capture stdout to get camply results
    captured_output = StringIO()

    try:
        with contextlib.redirect_stdout(captured_output):
            camply_command_line(command)

        # Get the captured output
        output = captured_output.getvalue()
        logger.debug(f"Camply output for {campground.name}: {output}")

        # Parse camply output into structured results
        results = parse_camply_output(output, campground)

        logger.info(f"Captured results for {campground.name}: found {len(results.get('available_sites', []))} available sites")
        return results

    except Exception as e:
        logger.error(f"Error capturing camply results for {campground.name}: {str(e)}")
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


def parse_camply_output(output: str, campground: CampgroundConfig) -> dict:
    """
    Parse camply text output into structured results.

    Args:
        output: Raw camply output text
        campground: Campground configuration

    Returns:
        Structured results dictionary
    """
    # Initialize results structure
    results = {
        'campground_id': campground.id,
        'campground_name': campground.name,
        'provider': campground.provider,
        'available_sites': [],
        'total_available_nights': 0
    }

    try:
        # Parse camply output - this is a simplified parser
        # Camply typically outputs information about available sites
        lines = output.strip().split('\n')

        available_sites = []
        current_site = None

        for line in lines:
            line = line.strip()

            # Look for site information patterns in camply output
            # This is a basic parser - may need adjustment based on actual camply output format
            if 'Site' in line and ('available' in line.lower() or 'found' in line.lower()):
                # Extract site information
                site_info = {
                    'site_name': line,
                    'dates': []
                }
                available_sites.append(site_info)
            elif line and available_sites:
                # Add additional information to the last site
                if 'date' in line.lower() or any(char.isdigit() for char in line):
                    available_sites[-1]['dates'].append(line)

        results['available_sites'] = available_sites

        # Count total available nights
        total_nights = 0
        for site in available_sites:
            total_nights += len(site.get('dates', []))
        results['total_available_nights'] = total_nights

        # If no structured data found, create a summary from the output
        if not available_sites and output.strip():
            # Create a single entry with the full output as summary
            results['available_sites'] = [{
                'site_name': 'Search Results',
                'summary': output.strip()
            }]
            # Consider any non-empty output as having availability
            results['total_available_nights'] = 1 if 'available' in output.lower() else 0

        logger.debug(f"Parsed {len(available_sites)} sites for {campground.name}")

    except Exception as e:
        logger.warning(f"Error parsing camply output for {campground.name}: {str(e)}")
        # Include raw output in results for debugging
        results['raw_output'] = output
        results['parse_error'] = str(e)

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
        # Check total available nights
        total_nights = results.get('total_available_nights', 0)
        if total_nights > 0:
            return True

        # Check available sites
        available_sites = results.get('available_sites', [])
        if not available_sites:
            return False

        # Check if any sites have actual availability data
        for site in available_sites:
            # If site has dates, it has availability
            if site.get('dates') and len(site.get('dates', [])) > 0:
                return True

            # Check summary for availability indicators
            summary = site.get('summary', '').lower()
            if summary and any(indicator in summary for indicator in ['available', 'found', 'booking']):
                # But exclude negative indicators
                if not any(negative in summary for negative in ['no available', 'not found', '0 total', 'no sites']):
                    return True

        # Check raw output for availability indicators (fallback)
        raw_output = results.get('raw_output', '').lower()
        if raw_output:
            # Look for positive availability indicators
            positive_indicators = ['available', 'found', 'booking', 'reservable']
            negative_indicators = ['no available', 'not found', '0 total', 'no sites', 'no reservable']

            has_positive = any(indicator in raw_output for indicator in positive_indicators)
            has_negative = any(indicator in raw_output for indicator in negative_indicators)

            # Only consider it available if we have positive indicators without negative ones
            return has_positive and not has_negative

        return False

    except Exception as e:
        logger.warning(f"Error checking availability: {str(e)}")
        # Default to False to avoid false positive notifications
        return False


def send_campground_notifications(campground: CampgroundConfig, results: dict):
    """
    Send notifications for campground availability using multi-email system.

    Args:
        campground: Campground configuration
        results: Search results to include in notification
    """
    try:
        # Initialize multi-email notifier
        notifier = MultiEmailNotifier()

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
        logger.error(f"Error sending notifications for {campground.name}: {str(e)}")
        # Publish failure metrics
        metrics_publisher.publish_email_delivery_metrics(
            campground.id,
            campground.name,
            0,  # success_count
            1,  # failure_count (assume at least one recipient would have failed)
            []  # no email addresses available due to error
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
            "Search Results:",
            ""
        ]

        available_sites = results.get('available_sites', [])

        if available_sites:
            for site in available_sites:
                site_name = site.get('site_name', 'Unknown Site')
                body_lines.append(f"• {site_name}")

                # Add dates if available
                dates = site.get('dates', [])
                if dates:
                    for date in dates[:5]:  # Limit to first 5 dates to keep email concise
                        body_lines.append(f"  - {date}")
                    if len(dates) > 5:
                        body_lines.append(f"  - ... and {len(dates) - 5} more dates")

                # Add summary if available
                summary = site.get('summary', '')
                if summary and len(summary) < 200:  # Only include short summaries
                    body_lines.append(f"  Summary: {summary}")

                body_lines.append("")

            total_nights = results.get('total_available_nights', 0)
            if total_nights > 0:
                body_lines.append(f"Total available nights found: {total_nights}")
        else:
            body_lines.append("No available campsites found in this search.")

        # Add search parameters
        search_params = results.get('search_parameters', {})
        if search_params:
            body_lines.extend([
                "",
                "Search Parameters:",
                f"Start Date: {search_params.get('start_date', 'N/A')}",
                f"End Date: {search_params.get('end_date', 'N/A')}"
            ])

        # Add error information if present
        if 'error' in results:
            body_lines.extend([
                "",
                "Note: There was an error during the search:",
                results['error']
            ])

        # Add raw output for debugging if parsing failed
        if 'raw_output' in results and results.get('parse_error'):
            body_lines.extend([
                "",
                "Raw search output (for debugging):",
                results['raw_output'][:500] + "..." if len(results['raw_output']) > 500 else results['raw_output']
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
        logger.warning("S3_CACHE_BUCKET not configured - result comparison will be disabled")

    try:
        # Validate multi-email configuration
        try:
            notifier = MultiEmailNotifier()
            config_validation = notifier.validate_configuration()
            if not config_validation['valid']:
                logger.error(f"Email configuration validation failed: {config_validation['errors']}")
                return {
                    'statusCode': 500,
                    'body': json.dumps({
                        'error': 'Email configuration validation failed',
                        'details': config_validation['errors']
                    })
                }
            logger.info(f"Email configuration validated: {config_validation['email_config']['count']} recipients configured")
        except Exception as e:
            logger.error(f"Failed to validate email configuration: {str(e)}")
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'error': 'Email configuration error',
                    'details': str(e)
                })
            }

        # Run campground searches
        search_campgrounds()
        logger.info("Enhanced camply searches completed successfully")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Camply check completed successfully',
                'campgrounds_processed': len(CAMPGROUNDS),
                's3_enabled': bool(S3_CACHE_BUCKET)
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
