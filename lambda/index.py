import json
import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
import boto3

# Set up logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    Simplified Lambda handler for camply campsite checking
    """
    try:
        # Set up writable directories for camply BEFORE importing
        import tempfile
        import sys
        temp_dir = tempfile.mkdtemp(prefix='camply_', dir='/tmp')

        # Set environment variables that camply uses
        os.environ['HOME'] = temp_dir
        os.environ['XDG_CACHE_HOME'] = os.path.join(temp_dir, '.cache')
        os.environ['XDG_DATA_HOME'] = os.path.join(temp_dir, '.local', 'share')
        os.environ['XDG_CONFIG_HOME'] = os.path.join(temp_dir, '.config')
        os.environ['TMPDIR'] = temp_dir
        os.environ['TEMP'] = temp_dir
        os.environ['TMP'] = temp_dir

        # Create all necessary directories
        for env_var in ['XDG_CACHE_HOME', 'XDG_DATA_HOME', 'XDG_CONFIG_HOME']:
            os.makedirs(os.environ[env_var], exist_ok=True)

        # Create camply-specific cache directories
        camply_dirs = [
            os.path.join(temp_dir, '.cache', 'camply'),
            os.path.join(temp_dir, '.local', 'share', 'camply'),
            os.path.join(temp_dir, 'camply_cache'),
        ]
        for dir_path in camply_dirs:
            os.makedirs(dir_path, exist_ok=True)

        # Monkey patch Path operations to redirect read-only filesystem writes
        from pathlib import Path
        original_mkdir = Path.mkdir
        original_write_text = Path.write_text

        def safe_mkdir(self, mode=0o777, parents=False, exist_ok=False):
            path_str = str(self)
            if '/usr/local/lib/python3.11/site-packages/camply' in path_str:
                # Redirect to temp directory
                relative_path = path_str.split('site-packages/camply/')[-1] if 'camply/' in path_str else 'cache'
                new_path = Path(os.path.join(temp_dir, 'camply_cache', relative_path))
                return original_mkdir(new_path, mode, parents, exist_ok)
            return original_mkdir(self, mode, parents, exist_ok)

        def safe_write_text(self, data, encoding=None, errors=None, newline=None):
            path_str = str(self)
            if '/usr/local/lib/python3.11/site-packages/camply' in path_str:
                # Redirect to temp directory
                relative_path = path_str.split('site-packages/camply/')[-1] if 'camply/' in path_str else 'cache'
                new_path = Path(os.path.join(temp_dir, 'camply_cache', relative_path))
                new_path.parent.mkdir(parents=True, exist_ok=True)
                return original_write_text(new_path, data, encoding, errors, newline)
            return original_write_text(self, data, encoding, errors, newline)

        # Apply patches
        Path.mkdir = safe_mkdir
        Path.write_text = safe_write_text

        # Import camply here to avoid import issues during cold start
        from camply.containers import SearchWindow
        from camply.search import SearchRecreationDotGov, SearchReserveCalifornia

        logger.info("Starting campsite availability check")

        # Configuration
        search_window_days = int(os.environ.get('SEARCH_WINDOW_DAYS', '14'))
        start_date = datetime.now().date()
        end_date = start_date + timedelta(days=search_window_days)

        search_window = SearchWindow(start_date=start_date, end_date=end_date)

        # Simplified campground configuration
        campgrounds = [
            # Recreation.gov campgrounds
            {'provider': 'RecreationDotGov', 'campgrounds': [252037, 233359]},  # Sardine Peak Lookout, Point Reyes

            # ReserveCalifornia campgrounds
            {'provider': 'ReserveCalifornia', 'campgrounds': [766, 590, 2009, 589, 2008, 518]},  # Your campgrounds
        ]

        all_results = []

        for config in campgrounds:
            try:
                if config['provider'] == 'RecreationDotGov':
                    searcher = SearchRecreationDotGov(
                        search_window=search_window,
                        campgrounds=config['campgrounds'],
                        nights=1
                    )
                elif config['provider'] == 'ReserveCalifornia':
                    searcher = SearchReserveCalifornia(
                        search_window=search_window,
                        recreation_area=[1],  # Required for UseDirect providers
                        campgrounds=config['campgrounds'],
                        nights=1
                    )
                else:
                    logger.warning(f"Unknown provider: {config['provider']}")
                    continue

                # Get available campsites
                available_sites = searcher.get_matching_campsites(log=False, verbose=False)

                if available_sites:
                    logger.info(f"Found {len(available_sites)} available sites for {config['provider']}")

                    # Convert to serializable format
                    sites_data = []
                    for site in available_sites:
                        sites_data.append({
                            'campsite_id': site.campsite_id,
                            'booking_date': site.booking_date.isoformat() if site.booking_date else None,
                            'campsite_site_name': site.campsite_site_name,
                            'facility_name': site.facility_name,
                            'booking_url': site.booking_url,
                            'recreation_area': site.recreation_area,
                            'campsite_type': site.campsite_type
                        })

                    all_results.extend(sites_data)

                    # Send notification only if results have changed
                    if sites_data:
                        if should_send_notification(sites_data, config['provider']):
                            send_notification(sites_data, config['provider'])
                        else:
                            logger.info(f"No changes in availability for {config['provider']}, skipping notification")
                else:
                    logger.info(f"No availability found for {config['provider']}")

            except Exception as e:
                logger.error(f"Error searching {config['provider']}: {str(e)}")
                continue

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Search completed. Found {len(all_results)} available sites.',
                'sites_found': len(all_results)
            })
        }

    except Exception as e:
        logger.error(f"Lambda execution failed: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def format_date_with_relative(date_str: str) -> str:
    """
    Format date as 'Wed, Dec 24th, 2025 (in x days/weeks/months)'
    """
    try:
        from datetime import datetime, timedelta

        # Parse the date
        if 'T' in date_str:
            date_obj = datetime.fromisoformat(date_str.split('T')[0])
        else:
            date_obj = datetime.strptime(date_str.split(' ')[0], '%Y-%m-%d')

        # Format the date
        day_suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(date_obj.day % 10, 'th')
        if 10 <= date_obj.day % 100 <= 20:  # Special case for 11th, 12th, 13th
            day_suffix = 'th'

        formatted_date = date_obj.strftime(f'%a, %b {date_obj.day}{day_suffix}, %Y')

        # Calculate relative time
        today = datetime.now().date()
        days_diff = (date_obj.date() - today).days

        if days_diff == 0:
            relative = "today"
        elif days_diff == 1:
            relative = "tomorrow"
        elif days_diff < 7:
            relative = f"in {days_diff} days"
        elif days_diff < 30:
            weeks = days_diff // 7
            relative = f"in {weeks} week{'s' if weeks != 1 else ''}"
        elif days_diff < 365:
            months = days_diff // 30
            relative = f"in {months} month{'s' if months != 1 else ''}"
        else:
            years = days_diff // 365
            relative = f"in {years} year{'s' if years != 1 else ''}"

        return f"{formatted_date} ({relative})"

    except Exception as e:
        return date_str  # Fallback to original if parsing fails


def should_send_notification(sites: List[Dict[str, Any]], provider: str) -> bool:
    """
    Check if notification should be sent by comparing with last sent results
    """
    try:
        import boto3
        import hashlib

        s3 = boto3.client('s3')
        bucket_name = os.environ.get('CACHE_BUCKET_NAME')

        if not bucket_name:
            logger.warning("No cache bucket configured, sending notification")
            return True

        # Create hash of current results
        sites_key = f"{provider}_sites"
        current_hash = hashlib.md5(str(sorted(sites, key=lambda x: x.get('campsite_id', ''))).encode()).hexdigest()

        try:
            # Get last sent hash from S3
            response = s3.get_object(Bucket=bucket_name, Key=f"last_sent_{sites_key}.txt")
            last_hash = response['Body'].read().decode('utf-8').strip()

            if current_hash == last_hash:
                return False  # No changes, don't send

        except s3.exceptions.NoSuchKey:
            # First time running, no previous hash exists
            pass
        except Exception as e:
            logger.warning(f"Error reading last sent hash: {str(e)}")

        # Store current hash for next comparison
        try:
            s3.put_object(
                Bucket=bucket_name,
                Key=f"last_sent_{sites_key}.txt",
                Body=current_hash,
                ContentType='text/plain'
            )
        except Exception as e:
            logger.warning(f"Error storing current hash: {str(e)}")

        return True  # Send notification

    except Exception as e:
        logger.error(f"Error in deduplication check: {str(e)}")
        return True  # Default to sending on error


def send_notification(sites: List[Dict[str, Any]], provider: str):
    """
    Send email notification for available campsites
    """
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        from collections import defaultdict

        # Email configuration from environment variables
        smtp_server = os.environ.get('EMAIL_SMTP_SERVER')
        smtp_port = int(os.environ.get('EMAIL_SMTP_PORT', '587'))
        username = os.environ.get('EMAIL_USERNAME')
        password = os.environ.get('EMAIL_PASSWORD')
        from_addr = os.environ.get('EMAIL_FROM_ADDRESS')
        to_addr = os.environ.get('EMAIL_TO_ADDRESS')
        subject_line = os.environ.get('EMAIL_SUBJECT_LINE', f'⛺️ Camply Update - {provider} ⛺️')

        if not all([smtp_server, username, password, from_addr, to_addr]):
            logger.warning("Email configuration incomplete, skipping notification")
            return

        # Group sites by recreation area, then by facility
        sites_by_rec_area = defaultdict(lambda: defaultdict(list))
        for site in sites:
            rec_area = site.get('recreation_area', site['facility_name'].split(' - ')[0] if ' - ' in site['facility_name'] else site['facility_name'])
            facility_name = site['facility_name']  # Use full facility name instead of campsite_site_name
            sites_by_rec_area[rec_area][facility_name].append(site)

        # Create HTML email content
        html_body = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 15px; line-height: 1.3; }}
                h1 {{ color: #2E8B57; margin: 10px 0; font-size: 20px; }}
                h2 {{ color: #4682B4; margin: 15px 0 8px 0; font-size: 16px; }}
                table {{ border-collapse: collapse; width: 100%; margin: 8px 0 20px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; font-size: 14px; }}
                th {{ background-color: #f2f2f2; font-weight: bold; }}
                tr:nth-child(even) {{ background-color: #f9f9f9; }}
                .book-link {{ background-color: #4CAF50; color: white; padding: 6px 12px;
                            text-decoration: none; border-radius: 3px; display: inline-block; font-size: 12px; }}
                .book-link:hover {{ background-color: #45a049; }}
                .summary {{ background-color: #e8f5e8; padding: 10px; border-radius: 4px; margin-bottom: 15px; font-size: 14px; }}
                .rec-area-header {{ color: #2E8B57; border-bottom: 2px solid #2E8B57; padding-bottom: 5px; margin: 20px 0 10px 0; }}
            </style>
        </head>
        <body>
            <h1>🏕️ Campsite Availability Alert</h1>
            <div class="summary">
                <strong>Found {len(sites)} available campsites on {provider}</strong>
            </div>
        """

        # Add tables grouped by recreation area
        for rec_area, facilities in sites_by_rec_area.items():
            html_body += f"""
            <h1 class="rec-area-header">
                🏞️ {rec_area}
            </h1>
            """

            for facility_name, facility_sites in facilities.items():
                html_body += f"""
                <h2>{facility_name}</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Available Date</th>
                            <th>Nights</th>
                            <th>Book Now</th>
                        </tr>
                    </thead>
                    <tbody>
                """

                # Sort sites by date
                facility_sites.sort(key=lambda x: x['booking_date'])

                for site in facility_sites:
                    # Format date with relative time
                    booking_date = site['booking_date'].split('T')[0] if 'T' in site['booking_date'] else site['booking_date'].split(' ')[0]
                    formatted_date = format_date_with_relative(booking_date)
                    nights = site.get('num_nights', 1)
                    booking_url = site['booking_url']

                    html_body += f"""
                        <tr>
                            <td>{formatted_date}</td>
                            <td>{nights} night{'s' if nights != 1 else ''}</td>
                            <td><a href="{booking_url}" class="book-link">Book Now</a></td>
                        </tr>
                    """

                html_body += """
                    </tbody>
                </table>
                """

        html_body += """
            <p style="margin-top: 20px; color: #666; font-size: 11px; line-height: 1.4;">
                This is an automated notification from your Camply checker.
                Book quickly as availability changes frequently!
            </p>
        </body>
        </html>
        """

        # Count unique recreation areas
        unique_rec_areas = len(sites_by_rec_area)

        # Send individual emails to each recipient
        recipients = [addr.strip() for addr in to_addr.split(',')]

        for recipient in recipients:
            msg = MIMEMultipart('alternative')
            msg['From'] = f"Campground Monitor <{from_addr}>"
            msg['To'] = recipient
            msg['Subject'] = f"Availability alert for {unique_rec_areas} area{'s' if unique_rec_areas != 1 else ''}"

            # Add HTML content
            html_part = MIMEText(html_body, 'html')
            msg.attach(html_part)

            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(username, password)
                server.send_message(msg)

        logger.info(f"Notification sent for {len(sites)} sites")

    except Exception as e:
        logger.error(f"Failed to send notification: {str(e)}")
