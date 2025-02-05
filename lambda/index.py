import json
import subprocess
import sys
import os
import logging

# Set up logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    logger.info("Starting camply search")

    # Install camply and its dependencies
    subprocess.check_call([sys.executable, "-m", "pip", "install", "camply", "-t", "/tmp/"])

    # Add /tmp to Python path so we can import installed modules
    sys.path.insert(0, '/tmp')

    from camply.cli import camply_command_line

    steep_ravine = {'id': '766', 'name': 'Steep Ravine', 'provider': 'ReserveCalifornia'}
    big_sur = {'id': '518', 'name': 'Julia Pfeiffer Burns', 'provider': 'ReserveCalifornia'}
    sardine_peak = {'id': '252037', 'name': 'Sardine Peak Lookout', 'provider': 'RecreationDotGov'}
    campgrounds = [steep_ravine, sardine_peak, big_sur]

    for campground in campgrounds:
        logger.info(f"Searching for {campground['name']}")

        # Set the EMAIL_SUBJECT_LINE environment variable
        os.environ['EMAIL_SUBJECT_LINE'] = f"Camply: {campground['name']} Availability Update"
        # Create a unique offline search file for each campground
        offline_search_file = f"/tmp/camply_{campground['id']}.json"

        command = [
            'campsites',
            '--provider', campground['provider'],
            '--campground', campground['id'],
            '--start-date', '2025-01-01',
            '--end-date', '2025-12-31',
            '--notifications', 'email',
            '--search-once',
            '--offline-search',
            '--offline-search-path', offline_search_file
        ]

        try:
            camply_command_line(command)
            logger.info(f"Search completed for {campground['name']}")
        except Exception as e:
            logger.error(f"Error during camply search for {campground['name']}: {str(e)}")
            raise

    logger.info("Camply searches completed")

    return {
        'statusCode': 200,
        'body': json.dumps('Camply check completed')
    }
