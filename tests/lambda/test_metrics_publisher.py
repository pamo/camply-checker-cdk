import unittest
from unittest.mock import Mock, patch, call
import boto3
from datetime import datetime, timezone
from botocore.exceptions import ClientError

from metrics_publisher import MetricsPublisher


class TestMetricsPublisher(unittest.TestCase):

    def setUp(self):
        self.publisher = MetricsPublisher()

    def test_publish_email_delivery_metrics_success_only(self):
        """Test publishing metrics when all emails succeed."""
        campground_id = '766'
        campground_name = 'Steep Ravine'
        success_count = 3
        failure_count = 0
        email_addresses = ['user1@example.com', 'user2@example.com', 'user3@example.com']

        with patch.object(self.publisher, '_publish_metrics_batch') as mock_publish:
            self.publisher.publish_email_delivery_metrics(
                campground_id, campground_name, success_count, failure_count, email_addresses
            )

            # Verify the method was called
            mock_publish.assert_called_once()

            # Get the metrics data that was passed
            metrics_data = mock_publish.call_args[0][0]

            # Should have: EmailDeliverySuccess, EmailDeliverySuccessRate, and 3 IndividualEmailDelivery metrics
            self.assertEqual(len(metrics_data), 5)

            # Check success metric
            success_metric = next(m for m in metrics_data if m['MetricName'] == 'EmailDeliverySuccess')
            self.assertEqual(success_metric['Value'], 3)
            self.assertEqual(success_metric['Unit'], 'Count')

            # Check success rate metric
            rate_metric = next(m for m in metrics_data if m['MetricName'] == 'EmailDeliverySuccessRate')
            self.assertEqual(rate_metric['Value'], 100.0)
            self.assertEqual(rate_metric['Unit'], 'Percent')

            # Check individual email metrics
            individual_metrics = [m for m in metrics_data if m['MetricName'] == 'IndividualEmailDelivery']
            self.assertEqual(len(individual_metrics), 3)
            for metric in individual_metrics:
                self.assertEqual(metric['Value'], 1)  # All should be successful

    def test_publish_email_delivery_metrics_mixed_results(self):
        """Test publishing metrics with both successes and failures."""
        campground_id = '766'
        campground_name = 'Steep Ravine'
        success_count = 2
        failure_count = 1
        email_addresses = ['user1@example.com', 'user2@example.com', 'user3@example.com']

        with patch.object(self.publisher, '_publish_metrics_batch') as mock_publish:
            self.publisher.publish_email_delivery_metrics(
                campground_id, campground_name, success_count, failure_count, email_addresses
            )

            metrics_data = mock_publish.call_args[0][0]

            # Should have: EmailDeliverySuccess, EmailDeliveryFailure, EmailDeliverySuccessRate, and 3 IndividualEmailDelivery
            self.assertEqual(len(metrics_data), 6)

            # Check success metric
            success_metric = next(m for m in metrics_data if m['MetricName'] == 'EmailDeliverySuccess')
            self.assertEqual(success_metric['Value'], 2)

            # Check failure metric
            failure_metric = next(m for m in metrics_data if m['MetricName'] == 'EmailDeliveryFailure')
            self.assertEqual(failure_metric['Value'], 1)

            # Check success rate (2/3 = 66.67%)
            rate_metric = next(m for m in metrics_data if m['MetricName'] == 'EmailDeliverySuccessRate')
            self.assertAlmostEqual(rate_metric['Value'], 66.67, places=1)

    def test_publish_email_delivery_metrics_no_attempts(self):
        """Test publishing metrics when no email attempts were made."""
        campground_id = '766'
        campground_name = 'Steep Ravine'
        success_count = 0
        failure_count = 0
        email_addresses = []

        with patch.object(self.publisher, '_publish_metrics_batch') as mock_publish:
            self.publisher.publish_email_delivery_metrics(
                campground_id, campground_name, success_count, failure_count, email_addresses
            )

            metrics_data = mock_publish.call_args[0][0]

            # Should have no metrics when no attempts were made
            self.assertEqual(len(metrics_data), 0)

    def test_publish_secret_retrieval_failure(self):
        """Test publishing secret retrieval failure metrics."""
        secret_name = 'camply-alert-email'
        error_message = 'Secret not found'

        with patch.object(self.publisher, '_publish_metrics_batch') as mock_publish:
            self.publisher.publish_secret_retrieval_failure(secret_name, error_message)

            metrics_data = mock_publish.call_args[0][0]

            self.assertEqual(len(metrics_data), 1)
            metric = metrics_data[0]
            self.assertEqual(metric['MetricName'], 'SecretRetrievalFailure')
            self.assertEqual(metric['Value'], 1)
            self.assertEqual(metric['Unit'], 'Count')

            # Check dimensions
            dimensions = {d['Name']: d['Value'] for d in metric['Dimensions']}
            self.assertEqual(dimensions['SecretName'], secret_name)

    def test_publish_s3_operation_failure(self):
        """Test publishing S3 operation failure metrics."""
        operation = 'get'
        bucket = 'camply-cache-bucket'
        key = 'results/766.json'

        with patch.object(self.publisher, '_publish_metrics_batch') as mock_publish:
            self.publisher.publish_s3_operation_failure(operation, bucket, key)

            metrics_data = mock_publish.call_args[0][0]

            self.assertEqual(len(metrics_data), 1)
            metric = metrics_data[0]
            self.assertEqual(metric['MetricName'], 'S3OperationFailure')
            self.assertEqual(metric['Value'], 1)
            self.assertEqual(metric['Unit'], 'Count')

            # Check dimensions
            dimensions = {d['Name']: d['Value'] for d in metric['Dimensions']}
            self.assertEqual(dimensions['Operation'], operation)
            self.assertEqual(dimensions['Bucket'], bucket)

    def test_publish_notification_skipped(self):
        """Test publishing notification skipped metrics."""
        campground_id = '766'
        campground_name = 'Steep Ravine'
        reason = 'no_changes'

        with patch.object(self.publisher, '_publish_metrics_batch') as mock_publish:
            self.publisher.publish_notification_skipped(campground_id, campground_name, reason)

            metrics_data = mock_publish.call_args[0][0]

            self.assertEqual(len(metrics_data), 1)
            metric = metrics_data[0]
            self.assertEqual(metric['MetricName'], 'NotificationSkipped')
            self.assertEqual(metric['Value'], 1)
            self.assertEqual(metric['Unit'], 'Count')

            # Check dimensions
            dimensions = {d['Name']: d['Value'] for d in metric['Dimensions']}
            self.assertEqual(dimensions['CampgroundId'], campground_id)
            self.assertEqual(dimensions['CampgroundName'], campground_name)
            self.assertEqual(dimensions['Reason'], reason)

    def test_publish_metrics_batch_single_batch(self):
        """Test publishing a single batch of metrics."""
        metrics_data = [
            {
                'MetricName': 'TestMetric',
                'Value': 1,
                'Unit': 'Count',
                'Timestamp': datetime.now(timezone.utc)
            }
        ]

        with patch.object(self.publisher.cloudwatch, 'put_metric_data') as mock_put:
            self.publisher._publish_metrics_batch(metrics_data)

            mock_put.assert_called_once_with(
                Namespace='CamplySiteCheck/Notifications',
                MetricData=metrics_data
            )

    def test_publish_metrics_batch_multiple_batches(self):
        """Test publishing multiple batches when exceeding CloudWatch limit."""
        # Create 25 metrics (should be split into 2 batches of 20 and 5)
        metrics_data = []
        for i in range(25):
            metrics_data.append({
                'MetricName': f'TestMetric{i}',
                'Value': 1,
                'Unit': 'Count',
                'Timestamp': datetime.now(timezone.utc)
            })

        with patch.object(self.publisher.cloudwatch, 'put_metric_data') as mock_put:
            self.publisher._publish_metrics_batch(metrics_data)

            # Should be called twice
            self.assertEqual(mock_put.call_count, 2)

            # First call should have 20 metrics
            first_call_data = mock_put.call_args_list[0][1]['MetricData']
            self.assertEqual(len(first_call_data), 20)

            # Second call should have 5 metrics
            second_call_data = mock_put.call_args_list[1][1]['MetricData']
            self.assertEqual(len(second_call_data), 5)

    def test_publish_metrics_batch_empty_list(self):
        """Test publishing empty metrics list."""
        with patch.object(self.publisher.cloudwatch, 'put_metric_data') as mock_put:
            self.publisher._publish_metrics_batch([])

            # Should not call CloudWatch API
            mock_put.assert_not_called()

    def test_publish_metrics_batch_client_error(self):
        """Test handling CloudWatch client errors."""
        metrics_data = [
            {
                'MetricName': 'TestMetric',
                'Value': 1,
                'Unit': 'Count',
                'Timestamp': datetime.now(timezone.utc)
            }
        ]

        with patch.object(self.publisher.cloudwatch, 'put_metric_data') as mock_put:
            mock_put.side_effect = ClientError(
                error_response={'Error': {'Code': 'InvalidParameterValue', 'Message': 'Invalid parameter'}},
                operation_name='PutMetricData'
            )

            with self.assertRaises(ClientError):
                self.publisher._publish_metrics_batch(metrics_data)

    def test_mask_email_normal_email(self):
        """Test email masking for normal email addresses."""
        test_cases = [
            ('user@example.com', 'u***@example.com'),
            ('a@example.com', 'a@example.com'),
            ('longusername@example.com', 'l***********@example.com'),
            ('test.user@subdomain.example.com', 't********@subdomain.example.com')
        ]

        for email, expected in test_cases:
            with self.subTest(email=email):
                result = self.publisher._mask_email(email)
                self.assertEqual(result, expected)

    def test_mask_email_invalid_email(self):
        """Test email masking for invalid email addresses."""
        result = self.publisher._mask_email('invalid-email')
        self.assertEqual(result, 'invalid_email')

    @patch('metrics_publisher.logger')
    def test_publish_email_delivery_metrics_exception_handling(self, mock_logger):
        """Test that exceptions in metrics publishing are handled gracefully."""
        with patch.object(self.publisher, '_publish_metrics_batch') as mock_publish:
            mock_publish.side_effect = Exception('CloudWatch error')

            # Should not raise exception
            self.publisher.publish_email_delivery_metrics(
                '766', 'Steep Ravine', 1, 0, ['user@example.com']
            )

            # Should log the error
            mock_logger.error.assert_called_once()

    @patch('metrics_publisher.logger')
    def test_publish_secret_retrieval_failure_exception_handling(self, mock_logger):
        """Test that exceptions in secret failure metrics are handled gracefully."""
        with patch.object(self.publisher, '_publish_metrics_batch') as mock_publish:
            mock_publish.side_effect = Exception('CloudWatch error')

            # Should not raise exception
            self.publisher.publish_secret_retrieval_failure('test-secret', 'error')

            # Should log the error
            mock_logger.error.assert_called_once()


if __name__ == '__main__':
    unittest.main()
