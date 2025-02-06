import json
import subprocess
import sys
import os
import logging

# Set up logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def install_dependencies():
    try:
        logger.info("Installing camply and its dependencies")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "camply", "-t", "/tmp/"])
        sys.path.insert(0, '/tmp')
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to install dependencies: {e}")
        raise

def search_campgrounds(campgrounds):
    from camply.cli import camply_command_line

    for campground in campgrounds:
        logger.info(f"Searching for {campground['name']}")

        os.environ['EMAIL_SUBJECT_LINE'] = f"Camply: {campground['name']} Availability Update"
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

def lambda_handler(event, context):
    logger.info("Starting camply search")

    install_dependencies()

    campgrounds = [
        {'id': '766', 'name': 'Steep Ravine', 'provider': 'ReserveCalifornia'},
        {'id': '518', 'name': 'Julia Pfeiffer Burns', 'provider': 'ReserveCalifornia'},
        {'id': '252037', 'name': 'Sardine Peak Lookout', 'provider': 'RecreationDotGov'}
    ]

    search_campgrounds(campgrounds)

    logger.info("Camply searches completed")

    return {
        'statusCode': 200,
        'body': json.dumps('Camply check completed')
    }
