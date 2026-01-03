import json
import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
import boto3
import re

# Set up logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def load_campground_config():
    """Load campground configuration from JSON file"""
    try:
        config_path = '/var/task/config/campgrounds.json'
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # Filter only enabled campgrounds and sort by priority
        enabled_campgrounds = [c for c in config['campgrounds'] if c.get('enabled', True)]
        enabled_campgrounds.sort(key=lambda x: x.get('priority', 999))
        
        logger.info(f"Loaded {len(enabled_campgrounds)} enabled campgrounds")
        return enabled_campgrounds
    except Exception as e:
        logger.error(f"Failed to load campground config: {str(e)}")
        # Fallback to hardcoded config
        return [
            {'id': 766, 'name': 'Steep Ravine', 'provider': 'ReserveCalifornia', 'priority': 1, 'enabled': True},
            {'id': 590, 'name': 'Steep Ravine Campgrounds', 'provider': 'ReserveCalifornia', 'priority': 2, 'enabled': True},
            {'id': 233359, 'name': 'Point Reyes National Seashore', 'provider': 'RecreationDotGov', 'priority': 3, 'enabled': True, 'filter': 'hike-in'},
            {'id': 252037, 'name': 'Sardine Peak Lookout', 'provider': 'RecreationDotGov', 'priority': 4, 'enabled': True}
        ]

def group_campgrounds_by_provider(campgrounds_config):
    """Group campgrounds by provider for camply search"""
    providers = {}
    for campground in campgrounds_config:
        provider = campground['provider']
        if provider not in providers:
            providers[provider] = []
        providers[provider].append(campground['id'])
    
    return [{'provider': provider, 'campgrounds': ids} for provider, ids in providers.items()]

def get_campground_metadata(campground_id, campgrounds_config):
    """Get metadata for a specific campground ID"""
    for campground in campgrounds_config:
        if campground['id'] == campground_id:
            return campground
    return None

def extract_site_name(site_name, campground_config):
    """Extract and format site name based on campground configuration"""
    if not site_name or not campground_config:
        return site_name or 'Unknown'
    
    display_format = campground_config.get('display_format', 'simple')
    
    if display_format == 'site_and_loop':
        # Handle "Site: 010, Loop: Sky" format (Point Reyes)
        site_match = re.search(r'Site:\s*(\w+)', site_name, re.IGNORECASE)
        loop_match = re.search(r'Loop:\s*(\w+)', site_name, re.IGNORECASE)
        
        if site_match and loop_match:
            return f"Site {site_match.group(1)}, Loop {loop_match.group(1)}"
        elif site_match:
            return f"Site {site_match.group(1)}"
        
        # Handle "Cabin (5 People) #CB06" format (Steep Ravine)
        cabin_match = re.search(r'Cabin.*?#(\w+)', site_name, re.IGNORECASE)
        if cabin_match:
            return f"Cabin {cabin_match.group(1)}"
    
    return site_name

def lambda_handler(event, context):
    """
    Simplified Lambda handler for campground checking
    """
    # Version marker for deployment verification
    logger.info("=== CAMPLY CHECKER v3.2 - URL FIX & CABIN PRIORITY - 2026-01-02 ===")
    
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
        logger.info(f"Config version: {os.environ.get('CONFIG_VERSION', 'unknown')}")

        # Configuration
        search_window_days = int(os.environ.get('SEARCH_WINDOW_DAYS', '14'))
        start_date = datetime.now().date()
        end_date = start_date + timedelta(days=search_window_days)

        search_window = SearchWindow(start_date=start_date, end_date=end_date)

        # Load campground configuration
        campgrounds_config = load_campground_config()
        campgrounds = group_campgrounds_by_provider(campgrounds_config)

        all_results = []
        all_changed_results = []

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

                    # Convert to serializable format and add metadata
                    sites_data = []
                    for site in available_sites:
                        # Get campground metadata
                        campground_meta = get_campground_metadata(getattr(site, 'campground_id', None), campgrounds_config)
                        
                        # Filter Point Reyes to only include hike-in campgrounds
                        if site.facility_name == "Point Reyes National Seashore Campground":
                            if site.campsite_type and "HIKE TO" in site.campsite_type:
                                pass  # Include this site
                            else:
                                continue  # Skip boat-in and other types

                        # Extract and format site name
                        formatted_site_name = extract_site_name(site.campsite_site_name, campground_meta)

                        sites_data.append({
                            'campsite_id': site.campsite_id,
                            'booking_date': site.booking_date.isoformat() if site.booking_date else None,
                            'campsite_site_name': formatted_site_name,
                            'facility_name': site.facility_name,
                            'campground_name': campground_meta['name'] if campground_meta else site.facility_name,
                            'campsite_use_type': getattr(site, 'campsite_use_type', None),
                            'campsite_loop_name': getattr(site, 'campsite_loop_name', None),
                            'booking_url': site.booking_url,
                            'recreation_area': site.recreation_area,
                            'campsite_type': site.campsite_type,
                            'campground_id': getattr(site, 'campground_id', None),
                            'priority': campground_meta['priority'] if campground_meta else 999
                        })

                    # Sort by priority (lower numbers first)
                    sites_data.sort(key=lambda x: x.get('priority', 999))
                    all_results.extend(sites_data)

                    # Only add to changed results if there are actual changes
                    if should_send_notification(sites_data, config['provider']):
                        all_changed_results.extend(sites_data)
                        logger.info(f"Changes detected for {config['provider']}, added {len(sites_data)} sites")
                    else:
                        logger.info(f"No changes for {config['provider']}, skipping notification")
                else:
                    logger.info(f"No availability found for {config['provider']}")

            except Exception as e:
                logger.error(f"Error searching {config['provider']}: {str(e)}")
                continue

        # Send single notification with all changed results
        if all_changed_results:
            send_notification(all_changed_results, "Multiple Providers")
        else:
            logger.info("No changes in availability across all providers, skipping notification")

        # Only generate dashboard if there are changes or it's been a while
        should_update_dashboard = bool(all_changed_results) or should_force_dashboard_update()

        if should_update_dashboard:
            generate_dashboard(all_results)
        else:
            logger.info("No changes detected, skipping dashboard update")

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


def should_force_dashboard_update():
    """Check if dashboard should be updated even without changes (every 6 hours)"""
    try:
        import boto3
        from datetime import datetime, timedelta

        s3 = boto3.client('s3')
        bucket_name = os.environ.get('CACHE_BUCKET_NAME')

        if not bucket_name:
            return True

        try:
            response = s3.head_object(Bucket=bucket_name, Key='dashboard_last_updated.txt')
            last_modified = response['LastModified'].replace(tzinfo=None)
            six_hours_ago = datetime.utcnow() - timedelta(hours=6)
            return last_modified < six_hours_ago
        except:
            return True  # Force update if we can't check
    except:
        return True


_template_cache = None

def get_template():
    """Get template with caching"""
    global _template_cache
    if _template_cache is None:
        try:
            with open('/var/task/template.html', 'r') as f:
                _template_cache = f.read()
        except FileNotFoundError:
            _template_cache = """<!DOCTYPE html>
<html><head><title>Campground Dashboard</title></head>
<body><h1>Dashboard</h1><div id="sites">{{SITES_JSON}}</div></body></html>"""
    return _template_cache


def generate_dashboard(all_sites):
    """Generate and upload dashboard to S3 using template"""
    try:
        import boto3
        from datetime import datetime
        import json

        s3 = boto3.client('s3')
        bucket_name = os.environ.get('CACHE_BUCKET_NAME')

        if not bucket_name:
            logger.warning('No cache bucket configured')
            return

        template = get_template()

        sites_data = []
        areas = set()
        for site in all_sites:
            area = site.get('recreation_area', 'Unknown')
            areas.add(area)

            formatted_date = format_date_with_relative(site.get('booking_date')) if site.get('booking_date') else 'No date'

            # Fix ReserveCalifornia URLs for dashboard
            booking_url = site.get('booking_url', '#')
            campground_id = site.get('campground_id')
            if campground_id and campground_id in [766, 590, 2009, 589, 2008, 518]:
                park_id_map = {
                    766: 682,   # Steep Ravine Cabins
                    590: 682,   # Steep Ravine Campsites  
                    2009: 682,  # Pantoll Campground
                    589: 682,   # Frank Valley Horse Campground
                    2008: 682,  # Bootjack Campground
                    518: 661    # Julia Pfeiffer Burns
                }
                park_id = park_id_map.get(campground_id)
                if park_id:
                    booking_url = f"https://reservecalifornia.com/park/{park_id}/{campground_id}"

            sites_data.append({
                'name': site.get('facility_name', 'Unknown'),
                'site_name': site.get('campsite_site_name', 'Unknown'),
                'campground_name': site.get('campground_name', site.get('facility_name', 'Unknown')),
                'booking_date': site.get('booking_date'),
                'formatted_date': formatted_date,
                'url': booking_url,
                'recreation_area': area,
                'campground_id': campground_id,
                'priority': site.get('priority', 999),
                'num_nights': site.get('num_nights', 1)
            })

        area_options = ''.join(f'<option value="{area}">{area}</option>' for area in sorted(areas))

        html_content = template.replace('{{LAST_UPDATED}}', datetime.utcnow().isoformat() + 'Z')
        html_content = html_content.replace('{{TOTAL_SITES}}', str(len(sites_data)))
        html_content = html_content.replace('{{TOTAL_AREAS}}', str(len(areas)))
        html_content = html_content.replace('{{SITES_DATA}}', json.dumps(sites_data))
        html_content = html_content.replace('{{EMAIL_CONTENT}}', '<h1>Campsite Availability Alert</h1><p>Dashboard with filtering available above.</p>')

        s3.put_object(
            Bucket=bucket_name,
            Key='dashboard.html',
            Body=html_content,
            ContentType='text/html'
        )

        s3.put_object(
            Bucket=bucket_name,
            Key='dashboard_last_updated.txt',
            Body=datetime.utcnow().isoformat(),
            ContentType='text/plain'
        )

        logger.info(f'Dashboard updated with {len(sites_data)} sites')

    except Exception as e:
        logger.error(f'Failed to generate dashboard: {str(e)}')

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
        subject_line = os.environ.get('EMAIL_SUBJECT_LINE', f' Campground Update - {provider} ')

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
                .browser-link {{ color: #888; font-size: 11px; text-align: center; margin-bottom: 15px; }}
                .browser-link a {{ color: #888; text-decoration: none; }}
                .browser-link a:hover {{ text-decoration: underline; }}
                h1 {{ color: #2E8B57; margin: 10px 0; font-size: 20px; }}
                h2 {{ color: #4682B4; margin: 15px 0 8px 0; font-size: 16px; }}
                table {{ border-collapse: collapse; width: 100%; margin: 8px 0 20px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; font-size: 14px; }}
                th {{ background-color: #f2f2f2; font-weight: bold; }}
                tr:nth-child(even) {{ background-color: #f9f9f9; }}
                .book-link {{ background-color: #4CAF50; color: #e8f5e8 !important; padding: 6px 12px;
                            text-decoration: none; border-radius: 3px; display: inline-block; font-size: 12px; }}
                .book-link:hover {{ background-color: #45a049; }}
                .summary {{ background-color: #e8f5e8; padding: 10px; border-radius: 4px; margin-bottom: 15px; font-size: 14px; }}
                .rec-area-header {{ color: #2E8B57; border-bottom: 2px solid #2E8B57; padding-bottom: 5px; margin: 20px 0 10px 0; }}
            </style>
        </head>
        <body>
            <div class="browser-link">
                <a href="https://{os.environ.get('CACHE_BUCKET_NAME', 'bucket')}.s3.{os.environ.get('AWS_REGION', 'us-west-1')}.amazonaws.com/dashboard.html">View this in your browser</a>
            </div>
            <h1> Campsite Availability Alert</h1>
            <div class="summary">
                <strong>Found {len(sites)} available campsites on {provider}</strong>
            </div>
        """

        # Sort recreation areas by priority (lowest priority number of any site in that area)
        def sort_rec_areas(item):
            rec_area, facilities = item
            min_priority = 999
            for facility_sites in facilities.values():
                for site in facility_sites:
                    min_priority = min(min_priority, site.get('priority', 999))
            return min_priority

        sorted_rec_areas = sorted(sites_by_rec_area.items(), key=sort_rec_areas)

        for rec_area, facilities in sorted_rec_areas:
            html_body += f"""
            <h1 class="rec-area-header">
                 {rec_area}
            </h1>
            """

            for facility_name, facility_sites in facilities.items():
                html_body += f"""
                <h2>{facility_name}</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Campground</th>
                            <th>Site Name</th>
                            <th>Available Date</th>
                            <th>Nights</th>
                            <th>Book Now</th>
                        </tr>
                    </thead>
                    <tbody>
                """

                # Sort sites by priority first, then by date
                facility_sites.sort(key=lambda x: (x.get('priority', 999), x['booking_date']))

                for site in facility_sites:
                    # Format date with relative time
                    booking_date = site['booking_date'].split('T')[0] if 'T' in site['booking_date'] else site['booking_date'].split(' ')[0]
                    formatted_date = format_date_with_relative(booking_date)
                    nights = site.get('num_nights', 1)
                    campground_name = site.get('campground_name', site.get('facility_name', 'Unknown'))
                    site_name = site.get('campsite_site_name', 'Unknown')
                    booking_url = site['booking_url']

                    campground_id = site.get('campground_id')
                    if campground_id and campground_id in [766, 590, 2009, 589, 2008, 518]:
                        park_id_map = {
                            766: 682,   # Steep Ravine Cabins
                            590: 682,   # Steep Ravine Campsites  
                            2009: 682,  # Pantoll Campground
                            589: 682,   # Frank Valley Horse Campground
                            2008: 682,  # Bootjack Campground
                            518: 661    # Julia Pfeiffer Burns
                        }
                        park_id = park_id_map.get(campground_id)
                        if park_id:
                            booking_url = f"https://reservecalifornia.com/park/{park_id}/{campground_id}"

                    html_body += f"""
                        <tr>
                            <td>{campground_name}</td>
                            <td>{site_name}</td>
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
                This is an automated notification from your Campground checker.
                Book quickly as availability changes frequently!
            </p>
        </body>
        </html>
        """

        # Count unique recreation areas
        unique_rec_areas = len(sites_by_rec_area)

        # Send single email with BCC to avoid duplicate emails
        recipients = [addr.strip() for addr in to_addr.split(',')]

        msg = MIMEMultipart('alternative')
        msg['From'] = f"Campground Monitor <{from_addr}>"
        msg['To'] = from_addr  # Send to self to hide recipients
        msg['Bcc'] = ', '.join(recipients)  # Use BCC for actual recipients
        msg['Subject'] = f"Availability alert for {unique_rec_areas} area{'s' if unique_rec_areas != 1 else ''}"

        # Add HTML content
        html_part = MIMEText(html_body, 'html')
        msg.attach(html_part)

        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
                server.login(username, password)
                server.send_message(msg, to_addrs=recipients)
        else:
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(username, password)
                server.send_message(msg, to_addrs=recipients)

        logger.info(f"Notification sent for {len(sites)} sites")

    except Exception as e:
        logger.error(f"Failed to send notification: {str(e)}")
