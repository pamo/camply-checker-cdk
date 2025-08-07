import json
import logging
import hashlib
from datetime import datetime, timezone
from typing import Dict, Optional, Any
import boto3
from botocore.exceptions import ClientError, NoCredentialsError, BotoCoreError

logger = logging.getLogger(__name__)


class S3ResultStore:
    """
    Handles storing and retrieving campground search results from S3 cache bucket.
    Provides fallback behavior when S3 operations fail.
    """

    def __init__(self, bucket_name: str, s3_client=None):
        """
        Initialize S3ResultStore with bucket name and optional S3 client.

        Args:
            bucket_name: Name of the S3 bucket for caching results
            s3_client: Optional boto3 S3 client (for testing/mocking)
        """
        self.bucket_name = bucket_name
        self.s3_client = s3_client or boto3.client('s3')

    def generate_key(self, campground_id: str) -> str:
        """
        Generate S3 key for storing campground results.

        Args:
            campground_id: Unique identifier for the campground

        Returns:
            S3 key string for the campground results
        """
        return f"search-results/{campground_id}/latest.json"

    def store_results(self, campground_id: str, results: Dict[str, Any]) -> bool:
        """
        Store search results in S3 cache bucket.

        Args:
            campground_id: Unique identifier for the campground
            results: Dictionary containing search results data

        Returns:
            True if storage was successful, False otherwise
        """
        try:
            # Add metadata to results
            storage_data = {
                "campground_id": campground_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "results": results,
                "result_hash": self._generate_result_hash(results)
            }

            key = self.generate_key(campground_id)

            # Store in S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=json.dumps(storage_data, indent=2),
                ContentType='application/json'
            )

            logger.info(f"Successfully stored results for campground {campground_id} in S3")
            return True

        except (ClientError, NoCredentialsError, BotoCoreError) as e:
            logger.error(f"S3 error storing results for campground {campground_id}: {str(e)}")
            return False
        except TypeError as e:
            logger.error(f"JSON serialization error for campground {campground_id}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error storing results for campground {campground_id}: {str(e)}")
            return False

    def retrieve_results(self, campground_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve previous search results from S3 cache bucket.

        Args:
            campground_id: Unique identifier for the campground

        Returns:
            Dictionary containing previous results, or None if not found/error
        """
        try:
            key = self.generate_key(campground_id)

            # Retrieve from S3
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=key
            )

            # Parse JSON content
            content = response['Body'].read().decode('utf-8')
            data = json.loads(content)

            logger.info(f"Successfully retrieved results for campground {campground_id} from S3")
            return data

        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            if error_code == 'NoSuchKey':
                logger.info(f"No previous results found for campground {campground_id}")
            else:
                logger.error(f"S3 client error retrieving results for campground {campground_id}: {str(e)}")
            return None
        except (NoCredentialsError, BotoCoreError) as e:
            logger.error(f"S3 error retrieving results for campground {campground_id}: {str(e)}")
            return None
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.error(f"Data parsing error for campground {campground_id}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error retrieving results for campground {campground_id}: {str(e)}")
            return None

    def _generate_result_hash(self, results: Dict[str, Any]) -> str:
        """
        Generate SHA256 hash of normalized results for comparison.

        Args:
            results: Dictionary containing search results

        Returns:
            SHA256 hash string of the results
        """
        try:
            # Create a normalized string representation for hashing
            # Sort keys to ensure consistent hashing
            normalized_json = json.dumps(results, sort_keys=True, separators=(',', ':'))
            return hashlib.sha256(normalized_json.encode('utf-8')).hexdigest()
        except Exception as e:
            logger.error(f"Error generating result hash: {str(e)}")
            # Return a default hash if generation fails
            return hashlib.sha256(str(results).encode('utf-8')).hexdigest()

    def has_results_changed(self, campground_id: str, current_results: Dict[str, Any]) -> bool:
        """
        Check if current results differ from previously stored results.

        Args:
            campground_id: Unique identifier for the campground
            current_results: Current search results to compare

        Returns:
            True if results have changed or no previous results exist, False if identical
        """
        try:
            previous_data = self.retrieve_results(campground_id)

            # If no previous results exist, consider results as changed
            if previous_data is None:
                logger.info(f"No previous results for campground {campground_id}, treating as changed")
                return True

            # Compare result hashes
            current_hash = self._generate_result_hash(current_results)
            previous_hash = previous_data.get('result_hash', '')

            if current_hash != previous_hash:
                logger.info(f"Results changed for campground {campground_id}")
                return True
            else:
                logger.info(f"Results unchanged for campground {campground_id}")
                return False

        except Exception as e:
            logger.error(f"Error comparing results for campground {campground_id}: {str(e)}")
            # Default to treating as changed if comparison fails (fail-safe approach)
            return True
