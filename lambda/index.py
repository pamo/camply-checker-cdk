import json
import subprocess
import sys
import os
import logging
from datetime import datetime, timedelta

# Set up logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

class CampgroundConfig:
    def __init__(self, id: str, name: str, provider: str):
        self.id = id
        self.name = name
        self.provider = provider

CAMPGROUNDS = [
    CampgroundConfig('766', 'Steep Ravine', 'ReserveCalifornia'),
    CampgroundConfig('518', 'Julia Pfeiffer Burns', 'ReserveCalifornia'),
    CampgroundConfig('252037', 'Sardine Peak Lookout', 'RecreationDotGov')
]
SEARCH_WINDOW_DAYS = int(os.environ['SEARCH_WINDOW_DAYS'])

def install_dependencies():
    try:
        logger.info("Installing camply and its dependencies")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "camply", "-t", "/tmp/"])
        sys.path.insert(0, '/tmp')
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to install dependencies: {e}")
        raise

def search_campgrounds():
    from camply.cli import camply_command_line
    start_date = datetime.now().strftime('%Y-%m-%d')
    end_date = (datetime.now() + timedelta(days=SEARCH_WINDOW_DAYS)).strftime('%Y-%m-%d')

    for campground in CAMPGROUNDS:
        logger.info(f"Searching for {campground.name}")

        os.environ['EMAIL_SUBJECT_LINE'] = f"Camply: {campground.name} Availability Update"
        offline_search_file = f"/tmp/camply_{campground.id}.json"

        command = [
            'campsites',
            '--provider', campground.provider,
            '--campground', campground.id,
            '--start-date', start_date,
            '--end-date', end_date,
            '--notifications', 'email',
            '--search-once',
            '--offline-search',
            '--offline-search-path', offline_search_file
        ]

        try:
            camply_command_line(command)
            logger.info(f"Search completed for {campground.name}")
        except Exception as e:
            logger.error(f"Error during camply search for {campground.name}: {str(e)}")
            raise

def lambda_handler(event, context):
    logger.info("Starting camply search")

    install_dependencies()

    search_campgrounds()

    logger.info("Camply searches completed")

    return {
        'statusCode': 200,
        'body': json.dumps('Camply check completed')
    }
