import json
import os
import logging
import tempfile
from datetime import datetime, timedelta

# Set up logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def setup_camply_temp_dirs():
    """Set up temporary directories for camply using Python's tempfile module"""
    # Create a temporary directory for camply operations
    temp_dir = tempfile.mkdtemp(prefix='camply_', dir='/tmp')
    logger.info(f"Created temporary directory for camply: {temp_dir}")

    # Set environment variables to redirect camply to use temp directories
    os.environ['HOME'] = temp_dir
    os.environ['XDG_CACHE_HOME'] = os.path.join(temp_dir, '.cache')
    os.environ['XDG_DATA_HOME'] = os.path.join(temp_dir, '.local', 'share')
    os.environ['XDG_CONFIG_HOME'] = os.path.join(temp_dir, '.config')

    # Create the XDG directories
    for env_var in ['XDG_CACHE_HOME', 'XDG_DATA_HOME', 'XDG_CONFIG_HOME']:
        os.makedirs(os.environ[env_var], exist_ok=True)

    return temp_dir

# Set up temporary directories for camply
TEMP_DIR = setup_camply_temp_dirs()

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


def search_campgrounds():
    from camply.cli import camply_command_line

    start_date = datetime.now().strftime('%Y-%m-%d')
    end_date = (datetime.now() + timedelta(days=SEARCH_WINDOW_DAYS)).strftime('%Y-%m-%d')

    for campground in CAMPGROUNDS:
        logger.info(f"Searching for {campground.name}")

        # Set dynamic email subject for this campground
        os.environ['EMAIL_SUBJECT_LINE'] = f"Camply: {campground.name} Availability Update"

        # Use offline search with file in temp directory
        offline_search_file = os.path.join(TEMP_DIR, f"camply_{campground.id}_{start_date}_{end_date}.json")

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
            logger.info(f"Running camply command: {' '.join(command)}")
            camply_command_line(command)
            logger.info(f"Search completed for {campground.name}")
        except Exception as e:
            logger.error(f"Error during camply search for {campground.name}: {str(e)}")
            raise

def lambda_handler(event, context):
    logger.info("Starting camply search")

    try:
        search_campgrounds()
        logger.info("Camply searches completed")

        return {
            'statusCode': 200,
            'body': json.dumps('Camply check completed')
        }
    except Exception as e:
        logger.error(f"Lambda execution failed: {str(e)}")
        raise
    finally:
        # Clean up temporary directory
        try:
            import shutil
            shutil.rmtree(TEMP_DIR, ignore_errors=True)
            logger.info(f"Cleaned up temporary directory: {TEMP_DIR}")
        except Exception as cleanup_error:
            logger.warning(f"Failed to clean up temp directory: {cleanup_error}")
