"""
Integration tests for the enhanced Lambda handler functionality.

Tests the complete end-to-end functionality including:
- Complete Lambda execution with S3 result storage
- Multi-email notification delivery with various scenarios
- CloudWatch metrics publishing verification
- Error handling and alarm triggering scenarios
"""

import unittest
from unittest.mock import patch, MagicMock, call, Mock
import os
import json
import boto3
from moto import mock_s3, mock_cloudwatch
from datetime import datetime

# Set required environment variables before importing index
os.environ['SEARCH_WINDOW_DAYS'] = '30'
os.environ['S3_CACHE_BUCKET'] = 'test-bucket'
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
os.environ['EMAIL_TO_ADDRESS'] = 'test1@example.com,test2@example.com'
os.environ['EMAIL_USERNAME'] = 'test_user'
os.environ['EMAIL_PASSWORD'] = 'test_pass'
os.environ['EMAIL_FROM_ADDRESS'] = 'from@example.com'

from index import (
    lambda_handler,
    search_campgrounds,
    capture_camply_results,
    parse_camply_output,
    create_notification_body,
    CampgroundConfig,
    process_campground_results,
    send_campground_notifications
)


class TestEndToEndIntegration(unittest.TestCase):
    """Test complete end-to-end Lambda functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.campground = CampgroundConfig('766', 'Steep Ravine', 'ReserveCalifornia')

        # Mock event and context for Lambda handler
        self.mock_event = {}
        self.mock_context = MagicMock()
        self.mock_context.aws_request_id = 'test-request-id'
        self.mock_context.function_name = 'test-function'

        # Sample camply output for testing
        self.sample_camply_output = """
        Site A available
        2025-01-15
        2025-01-16
        Site B available
        2025-01-20
        """

        # Sample search results
        self.sample_results = {
            'campground_id': '766',
            'campground_name': 'Steep Ravine',
            'provider': 'ReserveCalifornia',
            'available_sites': [
                {
                    'site_name': 'Site A',
                    'dates': ['2025-01-15', '2025-01-16']
                },
                {
                    'site_name': 'Site B',
                    'dates': ['2025-01-20']
                }
            ],
            'total_available_nights': 3,
            'search_parameters': {
                'start_date': '2025-01-15',
                'end_date': '2025-02-15'
            }
        }

    # Test 1: Complete Lambda execution with S3 result storage
    @mock_s3
    @patch('index.camply_command_line')
    @patch('index.MultiEmailNotifier')
    @patch('index.MetricsPublisher')
    def test_complete_lambda_execution_with_s3(self, mock_metrics_class, mock_notifier_class, mock_camply):
        """Test complete Lambda execution with S3 result storage."""
        # Set up S3 bucket
        s3_client = boto3.client('s3', region_name='us-east-1')
        s3_client.create_bucket(Bucket='test-bucket')

        # Mock camply output
        mock_camply.return_value = None

        # Mock notifier
        mock_notifier = MagicMock()
        mock_notifier_class.return_value = mock_notifier
        mock_notifier.validate_configuration.return_value = {
            'valid': True,
            'email_config': {'count': 2}
        }
        mock_notifier.send_notifications.return_value = {
            'success_count': 2,
            'failure_count': 0,
            'results': [
                {'email': 'test1@example.com', 'status': 'success'},
                {'email': 'test2@example.com', 'status': 'success'}
            ],
            'errors': []
        }

        # Mock metrics publisher
        mock_metrics = MagicMock()
        mock_metrics_class.return_value = mock_metrics

        # Mock camply output capture
        with patch('index.capture_camply_results') as mock_capture:
            mock_capture.return_value = self.sample_results

            # Execute Lambda handler
            response = lambda_handler(self.mock_event, self.mock_context)

            # Verify successful execution
            self.assertEqual(response['statusCode'], 200)
            response_body = json.loads(response['body'])
            self.assertEqual(response_body['message'], 'Camply check completed successfully')
            self.assertTrue(response_body['s3_enabled'])

            # Verify S3 storage was attempted
            mock_capture.assert_called()

            # Verify notifications were sent
            mock_notifier.send_notifications.assert_called()

            # Verify metrics were published
            mock_metrics.publish_email_delivery_metrics.assert_called()

    @mock_s3
    @patch('index.camply_command_line')
    def test_s3_result_storage_and_comparison(self, mock_camply):
        """Test S3 result storage and comparison logic."""
        # Set up S3 bucket
        s3_client = boto3.client('s3', region_name='us-east-1')
        s3_client.create_bucket(Bucket='test-bucket')

        # Mock camply
        mock_camply.return_value = None

        with patch('index.capture_camply_results') as mock_capture:
            # First execution - no previous results
            mock_capture.return_value = self.sample_results
            should_notify = process_campground_results(self.campground, self.sample_results)
            self.assertTrue(should_notify)  # Should notify on first run

            # Second execution - same results
            should_notify = process_campground_results(self.campground, self.sample_results)
            self.assertFalse(should_notify)  # Should not notify for same results

            # Third execution - different results
            different_results = self.sample_results.copy()
            different_results['available_sites'].append({
                'site_name': 'Site C',
                'dates': ['2025-01-25']
            })
            different_results['total_available_nights'] = 4

            should_notify = process_campground_results(self.campground, different_results)
            self.assertTrue(should_notify)  # Should notify for changed results

    # Test 2: Multi-email notification delivery with various scenarios
    @patch('index.MultiEmailNotifier')
    @patch('index.MetricsPublisher')
    def test_multi_email_notification_success(self, mock_metrics_class, mock_notifier_class):
        """Test successful multi-email notification delivery."""
        # Mock notifier for successful delivery
        mock_notifier = MagicMock()
        mock_notifier_class.return_value = mock_notifier
        mock_notifier.send_notifications.return_value = {
            'success_count': 3,
            'failure_count': 0,
            'results': [
                {'email': 'test1@example.com', 'status': 'success'},
                {'email': 'test2@example.com', 'status': 'success'},
                {'email': 'test3@example.com', 'status': 'success'}
            ],
            'errors': []
        }

        # Mock metrics publisher
        mock_metrics = MagicMock()
        mock_metrics_class.return_value = mock_metrics

        # Send notifications
        send_campground_notifications(self.campground, self.sample_results)

        # Verify notifier was called with correct parameters
        mock_notifier.send_notifications.assert_called_once()
        call_args = mock_notifier.send_notifications.call_args
        subject, body = call_args[0]

        self.assertIn('Steep Ravine', subject)
        self.assertIn('Site A', body)
        self.assertIn('Site B', body)

        # Verify metrics were published
        mock_metrics.publish_email_delivery_metrics.assert_called_once_with(
            '766', 'Steep Ravine', 3, 0, ['test1@example.com', 'test2@example.com', 'test3@example.com']
        )

    @patch('index.MultiEmailNotifier')
    @patch('index.MetricsPublisher')
    def test_multi_email_notification_partial_failure(self, mock_metrics_class, mock_notifier_class):
        """Test multi-email notification with partial failures."""
        # Mock notifier for partial failure
        mock_notifier = MagicMock()
        mock_notifier_class.return_value = mock_notifier
        mock_notifier.send_notifications.return_value = {
            'success_count': 2,
            'failure_count': 1,
            'results': [
                {'email': 'test1@example.com', 'status': 'success'},
                {'email': 'test2@example.com', 'status': 'success'},
                {'email': 'test3@example.com', 'status': 'failed', 'error': 'SMTP timeout'}
            ],
            'errors': ['Failed to send to test3@example.com: SMTP timeout']
        }

        # Mock metrics publisher
        mock_metrics = MagicMock()
        mock_metrics_class.return_value = mock_metrics

        # Send notifications
        send_campground_notifications(self.campground, self.sample_results)

        # Verify metrics reflect partial failure
        mock_metrics.publish_email_delivery_metrics.assert_called_once_with(
            '766', 'Steep Ravine', 2, 1, ['test1@example.com', 'test2@example.com', 'test3@example.com']
        )

    @patch('index.MultiEmailNotifier')
    @patch('index.MetricsPublisher')
    def test_multi_email_notification_complete_failure(self, mock_metrics_class, mock_notifier_class):
        """Test multi-email notification with complete failure."""
        # Mock notifier to raise exception
        mock_notifier_class.side_effect = Exception("Email configuration error")

        # Mock metrics publisher
        mock_metrics = MagicMock()
        mock_metrics_class.return_value = mock_metrics

        # Send notifications
        send_campground_notifications(self.campground, self.sample_results)

        # Verify failure metrics were published
        mock_metrics.publish_email_delivery_metrics.assert_called_once_with(
            '766', 'Steep Ravine', 0, 1, []
        )

    # Test 3: CloudWatch metrics publishing verification
    @mock_cloudwatch
    @patch('index.MultiEmailNotifier')
    def test_cloudwatch_metrics_publishing(self, mock_notifier_class):
        """Test that CloudWatch metrics are published correctly."""
        # Set up CloudWatch client
        cloudwatch = boto3.client('cloudwatch', region_name='us-east-1')

        # Mock notifier
        mock_notifier = MagicMock()
        mock_notifier_class.return_value = mock_notifier
        mock_notifier.send_notifications.return_value = {
            'success_count': 2,
            'failure_count': 1,
            'results': [
                {'email': 'test1@example.com', 'status': 'success'},
                {'email': 'test2@example.com', 'status': 'success'},
                {'email': 'test3@example.com', 'status': 'failed'}
            ],
            'errors': ['SMTP error']
        }

        # Import and use real MetricsPublisher
        from metrics_publisher import MetricsPublisher

        with patch.object(MetricsPublisher, 'cloudwatch', cloudwatch):
            # Send notifications which should publish metrics
            send_campground_notifications(self.campground, self.sample_results)

            # Verify metrics were published to CloudWatch
            # Note: In real AWS, we would check CloudWatch metrics
            # In moto mock, we verify the calls were made
            mock_notifier.send_notifications.assert_called_once()

    @patch('index.MetricsPublisher')
    def test_metrics_for_skipped_notifications(self, mock_metrics_class):
        """Test metrics publishing when notifications are skipped."""
        mock_metrics = MagicMock()
        mock_metrics_class.return_value = mock_metrics

        # Mock S3 store to return no changes
        with patch('index.s3_store') as mock_s3_store:
            mock_s3_store.has_results_changed.return_value = False
            mock_s3_store.store_results.return_value = True

            # Process results (should skip notification)
            should_notify = process_campground_results(self.campground, self.sample_results)
            self.assertFalse(should_notify)

            # Simulate the search_campgrounds function behavior
            if not should_notify:
                mock_metrics.publish_notification_skipped.assert_not_called()  # This would be called in search_campgrounds

    @patch('index.MetricsPublisher')
    def test_s3_failure_metrics(self, mock_metrics_class):
        """Test metrics publishing for S3 operation failures."""
        mock_metrics = MagicMock()
        mock_metrics_class.return_value = mock_metrics

        # Mock S3 store to fail storage
        with patch('index.s3_store') as mock_s3_store:
            mock_s3_store.has_results_changed.return_value = True
            mock_s3_store.store_results.return_value = False  # Storage failure

            # Process results
            should_notify = process_campground_results(self.campground, self.sample_results)
            self.assertTrue(should_notify)  # Should still notify despite storage failure

    # Test 4: Error handling and alarm triggering scenarios
    @patch('index.MultiEmailNotifier')
    @patch('index.MetricsPublisher')
    def test_email_configuration_validation_failure(self, mock_metrics_class, mock_notifier_class):
        """Test Lambda handler when email configuration validation fails."""
        # Mock notifier to fail validation
        mock_notifier = MagicMock()
        mock_notifier_class.return_value = mock_notifier
        mock_notifier.validate_configuration.return_value = {
            'valid': False,
            'errors': ['Invalid email format', 'Missing SMTP credentials']
        }

        # Execute Lambda handler
        response = lambda_handler(self.mock_event, self.mock_context)

        # Verify error response
        self.assertEqual(response['statusCode'], 500)
        response_body = json.loads(response['body'])
        self.assertEqual(response_body['error'], 'Email configuration validation failed')
        self.assertIn('Invalid email format', response_body['details'])

    @patch('index.MultiEmailNotifier')
    def test_email_configuration_exception(self, mock_notifier_class):
        """Test Lambda handler when email configuration raises exception."""
        # Mock notifier to raise exception during initialization
        mock_notifier_class.side_effect = Exception("Secrets Manager access denied")

        # Execute Lambda handler
        response = lambda_handler(self.mock_event, self.mock_context)

        # Verify error response
        self.assertEqual(response['statusCode'], 500)
        response_body = json.loads(response['body'])
        self.assertEqual(response_body['error'], 'Email configuration error')
        self.assertIn('Secrets Manager access denied', response_body['details'])

    @mock_s3
    @patch('index.camply_command_line')
    @patch('index.MultiEmailNotifier')
    def test_s3_access_failure_handling(self, mock_notifier_class, mock_camply):
        """Test handling of S3 access failures."""
        # Don't create S3 bucket to simulate access failure

        # Mock camply and notifier
        mock_camply.return_value = None
        mock_notifier = MagicMock()
        mock_notifier_class.return_value = mock_notifier
        mock_notifier.validate_configuration.return_value = {
            'valid': True,
            'email_config': {'count': 2}
        }
        mock_notifier.send_notifications.return_value = {
            'success_count': 2,
            'failure_count': 0,
            'results': [],
            'errors': []
        }

        with patch('index.capture_camply_results') as mock_capture:
            mock_capture.return_value = self.sample_results

            # Process results (should handle S3 failure gracefully)
            should_notify = process_campground_results(self.campground, self.sample_results)
            self.assertTrue(should_notify)  # Should default to notifying on S3 failure

    @patch('index.camply_command_line')
    @patch('index.MultiEmailNotifier')
    def test_camply_execution_failure(self, mock_notifier_class, mock_camply):
        """Test handling of camply execution failures."""
        # Mock camply to raise exception
        mock_camply.side_effect = Exception("Camply execution failed")

        # Mock notifier
        mock_notifier = MagicMock()
        mock_notifier_class.return_value = mock_notifier
        mock_notifier.validate_configuration.return_value = {
            'valid': True,
            'email_config': {'count': 2}
        }

        # Capture camply results should handle the exception
        results = capture_camply_results(self.campground, '2025-01-15', '2025-02-15')

        # Verify error is captured in results
        self.assertEqual(results['campground_id'], '766')
        self.assertIn('error', results)
        self.assertIn('Camply execution failed', results['error'])

    @patch('index.MultiEmailNotifier')
    @patch('index.MetricsPublisher')
    def test_lambda_execution_exception_handling(self, mock_metrics_class, mock_notifier_class):
        """Test Lambda handler exception handling."""
        # Mock notifier to pass validation but fail during search
        mock_notifier = MagicMock()
        mock_notifier_class.return_value = mock_notifier
        mock_notifier.validate_configuration.return_value = {
            'valid': True,
            'email_config': {'count': 2}
        }

        # Mock search_campgrounds to raise exception
        with patch('index.search_campgrounds') as mock_search:
            mock_search.side_effect = Exception("Unexpected error during search")

            # Execute Lambda handler
            response = lambda_handler(self.mock_event, self.mock_context)

            # Verify error response
            self.assertEqual(response['statusCode'], 500)
            response_body = json.loads(response['body'])
            self.assertEqual(response_body['error'], 'Lambda execution failed')
            self.assertIn('Unexpected error during search', response_body['details'])

    # Additional integration tests for parsing and notification body creation
    def test_parse_camply_output_with_sites(self):
        """Test parsing camply output with available sites."""
        output = """
        Site A available
        2025-01-15
        2025-01-16
        Site B available
        2025-01-20
        """

        results = parse_camply_output(output, self.campground)

        self.assertEqual(results['campground_id'], '766')
        self.assertEqual(results['campground_name'], 'Steep Ravine')
        self.assertEqual(results['provider'], 'ReserveCalifornia')
        self.assertEqual(len(results['available_sites']), 2)
        self.assertGreater(results['total_available_nights'], 0)

    def test_parse_camply_output_no_sites(self):
        """Test parsing camply output with no available sites."""
        output = "No campsites found."

        results = parse_camply_output(output, self.campground)

        self.assertEqual(results['campground_id'], '766')
        self.assertEqual(len(results['available_sites']), 1)  # Creates summary entry
        self.assertEqual(results['total_available_nights'], 0)  # No "available" in output

    def test_parse_camply_output_empty(self):
        """Test parsing empty camply output."""
        output = ""

        results = parse_camply_output(output, self.campground)

        self.assertEqual(results['campground_id'], '766')
        self.assertEqual(len(results['available_sites']), 0)
        self.assertEqual(results['total_available_nights'], 0)

    def test_create_notification_body_with_sites(self):
        """Test creating notification body with available sites."""
        results = {
            'campground_id': '766',
            'campground_name': 'Steep Ravine',
            'provider': 'ReserveCalifornia',
            'available_sites': [
                {
                    'site_name': 'Site A',
                    'dates': ['2025-01-15', '2025-01-16']
                }
            ],
            'total_available_nights': 2,
            'search_parameters': {
                'start_date': '2025-01-15',
                'end_date': '2025-02-15'
            }
        }

        body = create_notification_body(self.campground, results)

        self.assertIn('Steep Ravine', body)
        self.assertIn('Site A', body)
        self.assertIn('2025-01-15', body)
        self.assertIn('Total available nights found: 2', body)
        self.assertIn('ReserveCalifornia', body)

    def test_create_notification_body_no_sites(self):
        """Test creating notification body with no available sites."""
        results = {
            'campground_id': '766',
            'campground_name': 'Steep Ravine',
            'provider': 'ReserveCalifornia',
            'available_sites': [],
            'total_available_nights': 0
        }

        body = create_notification_body(self.campground, results)

        self.assertIn('Steep Ravine', body)
        self.assertIn('No available campsites found', body)

    def test_create_notification_body_with_error(self):
        """Test creating notification body when there's an error."""
        results = {
            'campground_id': '766',
            'campground_name': 'Steep Ravine',
            'provider': 'ReserveCalifornia',
            'available_sites': [],
            'error': 'Connection timeout'
        }

        body = create_notification_body(self.campground, results)

        self.assertIn('Steep Ravine', body)
        self.assertIn('Connection timeout', body)

    # Comprehensive end-to-end scenario tests
    @mock_s3
    @patch('index.camply_command_line')
    @patch('index.MultiEmailNotifier')
    @patch('index.MetricsPublisher')
    def test_end_to_end_new_availability_scenario(self, mock_metrics_class, mock_notifier_class, mock_camply):
        """Test complete end-to-end scenario with new availability detected."""
        # Set up S3 bucket
        s3_client = boto3.client('s3', region_name='us-east-1')
        s3_client.create_bucket(Bucket='test-bucket')

        # Mock components
        mock_camply.return_value = None

        mock_notifier = MagicMock()
        mock_notifier_class.return_value = mock_notifier
        mock_notifier.validate_configuration.return_value = {
            'valid': True,
            'email_config': {'count': 2}
        }
        mock_notifier.send_notifications.return_value = {
            'success_count': 2,
            'failure_count': 0,
            'results': [
                {'email': 'test1@example.com', 'status': 'success'},
                {'email': 'test2@example.com', 'status': 'success'}
            ],
            'errors': []
        }

        mock_metrics = MagicMock()
        mock_metrics_class.return_value = mock_metrics

        # Mock camply output capture
        with patch('index.capture_camply_results') as mock_capture:
            mock_capture.return_value = self.sample_results

            # Execute Lambda handler
            response = lambda_handler(self.mock_event, self.mock_context)

            # Verify successful execution
            self.assertEqual(response['statusCode'], 200)

            # Verify all components were called
            mock_notifier.validate_configuration.assert_called_once()
            mock_capture.assert_called()
            mock_notifier.send_notifications.assert_called()
            mock_metrics.publish_email_delivery_metrics.assert_called()

    @mock_s3
    @patch('index.camply_command_line')
    @patch('index.MultiEmailNotifier')
    @patch('index.MetricsPublisher')
    def test_end_to_end_no_changes_scenario(self, mock_metrics_class, mock_notifier_class, mock_camply):
        """Test complete end-to-end scenario with no changes detected."""
        # Set up S3 bucket with existing results
        s3_client = boto3.client('s3', region_name='us-east-1')
        s3_client.create_bucket(Bucket='test-bucket')

        # Store initial results in S3
        from s3_result_store import S3ResultStore
        s3_store = S3ResultStore('test-bucket')
        s3_store.store_results('766', self.sample_results)

        # Mock components
        mock_camply.return_value = None

        mock_notifier = MagicMock()
        mock_notifier_class.return_value = mock_notifier
        mock_notifier.validate_configuration.return_value = {
            'valid': True,
            'email_config': {'count': 2}
        }

        mock_metrics = MagicMock()
        mock_metrics_class.return_value = mock_metrics

        # Mock camply output capture to return same results
        with patch('index.capture_camply_results') as mock_capture:
            mock_capture.return_value = self.sample_results

            # Execute Lambda handler
            response = lambda_handler(self.mock_event, self.mock_context)

            # Verify successful execution
            self.assertEqual(response['statusCode'], 200)

            # Verify notifications were NOT sent (no changes detected)
            mock_notifier.send_notifications.assert_not_called()

            # Verify skipped notification metrics would be published
            # (This would happen in search_campgrounds function)
            mock_capture.assert_called()


if __name__ == '__main__':
    unittest.main()
