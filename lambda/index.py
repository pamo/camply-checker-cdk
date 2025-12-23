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
        # Set up writable directories for camply
        import tempfile
        temp_dir = tempfile.mkdtemp(prefix='camply_', dir='/tmp')
        os.environ['HOME'] = temp_dir
        os.environ['XDG_CACHE_HOME'] = os.path.join(temp_dir, '.cache')
        os.environ['XDG_DATA_HOME'] = os.path.join(temp_dir, '.local', 'share')
        os.environ['XDG_CONFIG_HOME'] = os.path.join(temp_dir, '.config')
        
        # Create directories
        for env_var in ['XDG_CACHE_HOME', 'XDG_DATA_HOME', 'XDG_CONFIG_HOME']:
            os.makedirs(os.environ[env_var], exist_ok=True)
        
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
            {'provider': 'RecreationDotGov', 'campgrounds': [252037]},  # Sardine Peak Lookout
            
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
                    
                    # Send notification if sites found
                    if sites_data:
                        send_notification(sites_data, config['provider'])
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

def send_notification(sites: List[Dict[str, Any]], provider: str):
    """
    Send email notification for available campsites
    """
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        # Email configuration from environment variables
        smtp_server = os.environ.get('EMAIL_SMTP_SERVER')
        smtp_port = int(os.environ.get('EMAIL_SMTP_PORT', '587'))
        username = os.environ.get('EMAIL_USERNAME')
        password = os.environ.get('EMAIL_PASSWORD')
        from_addr = os.environ.get('EMAIL_FROM_ADDRESS')
        to_addr = os.environ.get('EMAIL_TO_ADDRESS')
        
        if not all([smtp_server, username, password, from_addr, to_addr]):
            logger.warning("Email configuration incomplete, skipping notification")
            return
        
        # Create email content
        subject = f"Campsites Available - {provider}"
        
        body = f"Found {len(sites)} available campsites on {provider}:\n\n"
        for site in sites:
            body += f"• {site['facility_name']} - {site['campsite_site_name']}\n"
            body += f"  Date: {site['booking_date']}\n"
            body += f"  Book: {site['booking_url']}\n\n"
        
        # Send email
        msg = MIMEMultipart()
        msg['From'] = from_addr
        msg['To'] = to_addr
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(username, password)
            server.send_message(msg)
        
        logger.info(f"Notification sent for {len(sites)} sites")
        
    except Exception as e:
        logger.error(f"Failed to send notification: {str(e)}")
