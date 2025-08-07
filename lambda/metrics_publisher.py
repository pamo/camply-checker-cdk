import boto3
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

class MetricsPublisher:
    """
    Publishes CloudWatch metrics for email delivery and system monitoring.
    """

    def __init__(self):
        self.cloudwatch = boto3.client('cloudwatch')
        self.namespace = 'CamplySiteCheck/Notifications'

    def publish_email_delivery_metrics(self, campground_id: str, campground_name: str,
                                     success_count: int, failure_count: int,
                                     email_addresses: List[str]) -> None:
        """
        Publish email delivery success/failure metrics to CloudWatch.

        Args:
            campground_id: ID of the campground being monitored
            campground_name: Name of the campground
            success_count: Number of successful email deliveries
            failure_count: Number of failed email deliveries
            email_addresses: List of email addresses (for individual metrics)
        """
        try:
            metrics_data = []
            timestamp = datetime.now(timezone.utc)

            # Overall success/failure metrics
            if success_count > 0:
                metrics_data.append({
                    'MetricName': 'EmailDeliverySuccess',
                    'Dimensions': [
                        {'Name': 'CampgroundId', 'Value': campground_id},
                        {'Name': 'CampgroundName', 'Value': campground_name}
                    ],
                    'Value': success_count,
                    'Unit': 'Count',
                    'Timestamp': timestamp
                })

            if failure_count > 0:
                metrics_data.append({
                    'MetricName': 'EmailDeliveryFailure',
                    'Dimensions': [
                        {'Name': 'CampgroundId', 'Value': campground_id},
                        {'Name': 'CampgroundName', 'Value': campground_name}
                    ],
                    'Value': failure_count,
                    'Unit': 'Count',
                    'Timestamp': timestamp
                })

            # Success rate metric
            total_attempts = success_count + failure_count
            if total_attempts > 0:
                success_rate = (success_count / total_attempts) * 100
                metrics_data.append({
                    'MetricName': 'EmailDeliverySuccessRate',
                    'Dimensions': [
                        {'Name': 'CampgroundId', 'Value': campground_id},
                        {'Name': 'CampgroundName', 'Value': campground_name}
                    ],
                    'Value': success_rate,
                    'Unit': 'Percent',
                    'Timestamp': timestamp
                })

            # Individual email metrics (masked for privacy)
            for i, email in enumerate(email_addresses):
                masked_email = self._mask_email(email)
                # Assume success for now - this will be updated when integrated with actual email sending
                metrics_data.append({
                    'MetricName': 'IndividualEmailDelivery',
                    'Dimensions': [
                        {'Name': 'CampgroundId', 'Value': campground_id},
                        {'Name': 'EmailAddress', 'Value': masked_email}
                    ],
                    'Value': 1 if i < success_count else 0,
                    'Unit': 'Count',
                    'Timestamp': timestamp
                })

            # Publish metrics in batches (CloudWatch limit is 20 metrics per call)
            self._publish_metrics_batch(metrics_data)

            logger.info(f"Published email delivery metrics for {campground_name}: "
                       f"{success_count} successes, {failure_count} failures")

        except Exception as e:
            logger.error(f"Failed to publish email delivery metrics: {str(e)}")
            # Don't raise - metrics publishing failure shouldn't break the main flow

    def publish_secret_retrieval_failure(self, secret_name: str, error_message: str) -> None:
        """
        Publish metrics when secret retrieval fails.

        Args:
            secret_name: Name of the secret that failed to retrieve
            error_message: Error message from the failure
        """
        try:
            metrics_data = [{
                'MetricName': 'SecretRetrievalFailure',
                'Dimensions': [
                    {'Name': 'SecretName', 'Value': secret_name}
                ],
                'Value': 1,
                'Unit': 'Count',
                'Timestamp': datetime.now(timezone.utc)
            }]

            self._publish_metrics_batch(metrics_data)
            logger.info(f"Published secret retrieval failure metric for {secret_name}")

        except Exception as e:
            logger.error(f"Failed to publish secret retrieval failure metric: {str(e)}")

    def publish_s3_operation_failure(self, operation: str, bucket: str, key: str) -> None:
        """
        Publish metrics when S3 operations fail.

        Args:
            operation: Type of S3 operation (get, put, delete)
            bucket: S3 bucket name
            key: S3 object key
        """
        try:
            metrics_data = [{
                'MetricName': 'S3OperationFailure',
                'Dimensions': [
                    {'Name': 'Operation', 'Value': operation},
                    {'Name': 'Bucket', 'Value': bucket}
                ],
                'Value': 1,
                'Unit': 'Count',
                'Timestamp': datetime.now(timezone.utc)
            }]

            self._publish_metrics_batch(metrics_data)
            logger.info(f"Published S3 operation failure metric for {operation} on {bucket}/{key}")

        except Exception as e:
            logger.error(f"Failed to publish S3 operation failure metric: {str(e)}")

    def publish_notification_skipped(self, campground_id: str, campground_name: str, reason: str) -> None:
        """
        Publish metrics when notifications are skipped (e.g., no changes in results).

        Args:
            campground_id: ID of the campground
            campground_name: Name of the campground
            reason: Reason why notification was skipped
        """
        try:
            metrics_data = [{
                'MetricName': 'NotificationSkipped',
                'Dimensions': [
                    {'Name': 'CampgroundId', 'Value': campground_id},
                    {'Name': 'CampgroundName', 'Value': campground_name},
                    {'Name': 'Reason', 'Value': reason}
                ],
                'Value': 1,
                'Unit': 'Count',
                'Timestamp': datetime.now(timezone.utc)
            }]

            self._publish_metrics_batch(metrics_data)
            logger.info(f"Published notification skipped metric for {campground_name}: {reason}")

        except Exception as e:
            logger.error(f"Failed to publish notification skipped metric: {str(e)}")

    def _publish_metrics_batch(self, metrics_data: List[Dict]) -> None:
        """
        Publish metrics to CloudWatch in batches.

        Args:
            metrics_data: List of metric data dictionaries
        """
        if not metrics_data:
            return

        # CloudWatch allows up to 20 metrics per put_metric_data call
        batch_size = 20
        for i in range(0, len(metrics_data), batch_size):
            batch = metrics_data[i:i + batch_size]

            try:
                self.cloudwatch.put_metric_data(
                    Namespace=self.namespace,
                    MetricData=batch
                )
                logger.debug(f"Published batch of {len(batch)} metrics to CloudWatch")

            except ClientError as e:
                logger.error(f"Failed to publish metrics batch: {str(e)}")
                raise

    def _mask_email(self, email: str) -> str:
        """
        Mask email address for privacy in metrics.

        Args:
            email: Email address to mask

        Returns:
            Masked email address (e.g., "u***@example.com")
        """
        if '@' not in email:
            return 'invalid_email'

        local, domain = email.split('@', 1)
        if len(local) <= 1:
            masked_local = local
        else:
            masked_local = local[0] + '*' * (len(local) - 1)

        return f"{masked_local}@{domain}"
