"""
Unit tests for multi_email_notifier module.

Tests cover multi-email notification functionality, SMTP handling, error handling,
and integration with the email configuration parser.
"""

import os
import unittest
from unittest.mock import patch, MagicMock, call
import smtplib
from multi_email_notifier import MultiEmailNotifier, send_multi_email_notification


class TestMultiEmailNotifier(unittest.TestCase):
    """Test cases for MultiEmailNotifier class."""

    def setUp(self):
        """Set up test environment before each test."""
        # Set up required environment variables
        self.test_env_vars = {
            'EMAIL_TO_ADDRESS': 'user1@example.com,user2@example.com',
            'EMAIL_USERNAME': 'test@example.com',
            'EMAIL_PASSWORD': 'test_password',
            'EMAIL_SMTP_SERVER': 'smtp.test.com',
            'EMAIL_SMTP_PORT': '587',
            'EMAIL_FROM_ADDRESS': 'sender@example.com'
        }

        # Clean up environment variables
        for key in self.test_env_vars.keys():
            if key in os.environ:
                del os.environ[key]

        # Set test environment variables
        for key, value in self.test_env_vars.items():
            os.environ[key] = value

    def tearDown(self):
        """Clean up after each test."""
        # Clean up environment variables
        for key in self.test_env_vars.keys():
            if key in os.environ:
                del os.environ[key]

    def test_initialization_success(self):
        """Test successful initialization with all required environment variables."""
        notifier = MultiEmailNotifier()

        self.assertEqual(notifier.smtp_server, 'smtp.test.com')
        self.assertEqual(notifier.smtp_port, 587)
        self.assertEqual(notifier.username, 'test@example.com')
        self.assertEqual(notifier.password, 'test_password')
        self.assertEqual(notifier.from_address, 'sender@example.com')

    def test_initialization_missing_credentials(self):
        """Test initialization failure when required credentials are missing."""
        del os.environ['EMAIL_USERNAME']

        with self.assertRaises(ValueError) as context:
            MultiEmailNotifier()

        self.assertIn('Missing required email credentials', str(context.exception))

    def test_initialization_default_values(self):
        """Test initialization with default SMTP server and port values."""
        del os.environ['EMAIL_SMTP_SERVER']
        del os.environ['EMAIL_SMTP_PORT']

        notifier = MultiEmailNotifier()

        self.assertEqual(notifier.smtp_server, 'smtp.gmail.com')
        self.assertEqual(notifier.smtp_port, 465)

    def test_get_email_addresses_success(self):
        """Test successful retrieval of email addresses."""
        notifier = MultiEmailNotifier()
        addresses = notifier.get_email_addresses()

        self.assertEqual(len(addresses), 2)
        self.assertIn('user1@example.com', addresses)
        self.assertIn('user2@example.com', addresses)

    def test_get_email_addresses_failure(self):
        """Test email address retrieval failure."""
        del os.environ['EMAIL_TO_ADDRESS']

        notifier = MultiEmailNotifier()

        with self.assertRaises(ValueError):
            notifier.get_email_addresses()

    @patch('multi_email_notifier.smtplib.SMTP_SSL')
    def test_send_individual_email_success(self, mock_smtp_ssl):
        """Test successful individual email sending."""
        # Mock SMTP server
        mock_server = MagicMock()
        mock_smtp_ssl.return_value.__enter__.return_value = mock_server

        notifier = MultiEmailNotifier()

        # Should not raise an exception
        notifier._send_individual_email(
            'test@example.com',
            'Test Subject',
            'Test Body'
        )

        # Verify SMTP calls
        mock_smtp_ssl.assert_called_once_with('smtp.test.com', 587)
        mock_server.login.assert_called_once_with('test@example.com', 'test_password')
        mock_server.send_message.assert_called_once()

    @patch('multi_email_notifier.smtplib.SMTP_SSL')
    def test_send_individual_email_with_html(self, mock_smtp_ssl):
        """Test individual email sending with HTML body."""
        mock_server = MagicMock()
        mock_smtp_ssl.return_value.__enter__.return_value = mock_server

        notifier = MultiEmailNotifier()

        notifier._send_individual_email(
            'test@example.com',
            'Test Subject',
            'Test Body',
            '<html><body>Test HTML Body</body></html>'
        )

        # Verify the message was sent
        mock_server.send_message.assert_called_once()

    @patch('multi_email_notifier.smtplib.SMTP_SSL')
    def test_send_individual_email_smtp_error(self, mock_smtp_ssl):
        """Test individual email sending with SMTP error."""
        mock_server = MagicMock()
        mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, 'Authentication failed')
        mock_smtp_ssl.return_value.__enter__.return_value = mock_server

        notifier = MultiEmailNotifier()

        with self.assertRaises(Exception) as context:
            notifier._send_individual_email('test@example.com', 'Subject', 'Body')

        self.assertIn('SMTP error', str(context.exception))

    @patch('multi_email_notifier.smtplib.SMTP_SSL')
    def test_send_individual_email_connection_error(self, mock_smtp_ssl):
        """Test individual email sending with connection error."""
        mock_smtp_ssl.side_effect = ConnectionError('Connection failed')

        notifier = MultiEmailNotifier()

        with self.assertRaises(Exception) as context:
            notifier._send_individual_email('test@example.com', 'Subject', 'Body')

        self.assertIn('Email sending error', str(context.exception))

    @patch('multi_email_notifier.smtplib.SMTP_SSL')
    def test_send_notifications_all_success(self, mock_smtp_ssl):
        """Test sending notifications to multiple recipients with all successes."""
        mock_server = MagicMock()
        mock_smtp_ssl.return_value.__enter__.return_value = mock_server

        notifier = MultiEmailNotifier()
        result = notifier.send_notifications('Test Subject', 'Test Body')

        self.assertEqual(result['success_count'], 2)
        self.assertEqual(result['failure_count'], 0)
        self.assertEqual(len(result['results']), 2)
        self.assertEqual(len(result['errors']), 0)

        # Verify all results are successful
        for res in result['results']:
            self.assertEqual(res['status'], 'success')
            self.assertIsNone(res['error'])

    @patch('multi_email_notifier.smtplib.SMTP_SSL')
    def test_send_notifications_partial_failure(self, mock_smtp_ssl):
        """Test sending notifications with some failures."""
        mock_server = MagicMock()

        # First call succeeds, second call fails
        mock_server.send_message.side_effect = [None, smtplib.SMTPException('Send failed')]
        mock_smtp_ssl.return_value.__enter__.return_value = mock_server

        notifier = MultiEmailNotifier()
        result = notifier.send_notifications('Test Subject', 'Test Body')

        self.assertEqual(result['success_count'], 1)
        self.assertEqual(result['failure_count'], 1)
        self.assertEqual(len(result['results']), 2)
        self.assertEqual(len(result['errors']), 1)

        # Check individual results
        success_result = next(r for r in result['results'] if r['status'] == 'success')
        failure_result = next(r for r in result['results'] if r['status'] == 'failure')

        self.assertIsNone(success_result['error'])
        self.assertIsNotNone(failure_result['error'])

    @patch('multi_email_notifier.smtplib.SMTP_SSL')
    def test_send_notifications_all_failure(self, mock_smtp_ssl):
        """Test sending notifications with all failures."""
        mock_server = MagicMock()
        mock_server.send_message.side_effect = smtplib.SMTPException('Send failed')
        mock_smtp_ssl.return_value.__enter__.return_value = mock_server

        notifier = MultiEmailNotifier()
        result = notifier.send_notifications('Test Subject', 'Test Body')

        self.assertEqual(result['success_count'], 0)
        self.assertEqual(result['failure_count'], 2)
        self.assertEqual(len(result['results']), 2)
        self.assertEqual(len(result['errors']), 2)

    def test_send_notifications_email_config_error(self):
        """Test sending notifications when email configuration is invalid."""
        del os.environ['EMAIL_TO_ADDRESS']

        notifier = MultiEmailNotifier()
        result = notifier.send_notifications('Test Subject', 'Test Body')

        self.assertEqual(result['success_count'], 0)
        self.assertEqual(result['failure_count'], 0)
        self.assertEqual(len(result['results']), 0)
        self.assertEqual(len(result['errors']), 1)
        self.assertIn('Email configuration error', result['errors'][0])

    @patch('multi_email_notifier.smtplib.SMTP_SSL')
    def test_test_connection_success(self, mock_smtp_ssl):
        """Test successful SMTP connection test."""
        mock_server = MagicMock()
        mock_smtp_ssl.return_value.__enter__.return_value = mock_server

        notifier = MultiEmailNotifier()
        result = notifier.test_connection()

        self.assertTrue(result)
        mock_server.login.assert_called_once_with('test@example.com', 'test_password')

    @patch('multi_email_notifier.smtplib.SMTP_SSL')
    def test_test_connection_failure(self, mock_smtp_ssl):
        """Test failed SMTP connection test."""
        mock_smtp_ssl.side_effect = smtplib.SMTPAuthenticationError(535, 'Authentication failed')

        notifier = MultiEmailNotifier()
        result = notifier.test_connection()

        self.assertFalse(result)

    def test_validate_configuration_success(self):
        """Test successful configuration validation."""
        notifier = MultiEmailNotifier()
        result = notifier.validate_configuration()

        self.assertTrue(result['valid'])
        self.assertTrue(result['email_config']['valid'])
        self.assertTrue(result['smtp_config']['valid'])
        self.assertEqual(len(result['errors']), 0)

    def test_validate_configuration_missing_smtp_config(self):
        """Test configuration validation with missing SMTP configuration."""
        del os.environ['EMAIL_USERNAME']
        del os.environ['EMAIL_PASSWORD']

        with self.assertRaises(ValueError) as context:
            MultiEmailNotifier()

        self.assertIn('Missing required email credentials', str(context.exception))

    def test_validate_configuration_invalid_email_addresses(self):
        """Test configuration validation with invalid email addresses."""
        os.environ['EMAIL_TO_ADDRESS'] = 'invalid-email,@invalid.com'

        notifier = MultiEmailNotifier()
        result = notifier.validate_configuration()

        self.assertFalse(result['valid'])
        self.assertFalse(result['email_config']['valid'])

    @patch('multi_email_notifier.smtplib.SMTP_SSL')
    def test_convenience_function(self, mock_smtp_ssl):
        """Test the convenience function for sending multi-email notifications."""
        mock_server = MagicMock()
        mock_smtp_ssl.return_value.__enter__.return_value = mock_server

        result = send_multi_email_notification('Test Subject', 'Test Body')

        self.assertEqual(result['success_count'], 2)
        self.assertEqual(result['failure_count'], 0)

    @patch('multi_email_notifier.smtplib.SMTP_SSL')
    def test_convenience_function_with_html(self, mock_smtp_ssl):
        """Test the convenience function with HTML body."""
        mock_server = MagicMock()
        mock_smtp_ssl.return_value.__enter__.return_value = mock_server

        result = send_multi_email_notification(
            'Test Subject',
            'Test Body',
            '<html><body>HTML Body</body></html>'
        )

        self.assertEqual(result['success_count'], 2)
        self.assertEqual(result['failure_count'], 0)

    @patch('multi_email_notifier.smtplib.SMTP_SSL')
    def test_convenience_function_custom_env_var(self, mock_smtp_ssl):
        """Test the convenience function with custom environment variable."""
        os.environ['CUSTOM_EMAIL_VAR'] = 'custom@example.com'
        mock_server = MagicMock()
        mock_smtp_ssl.return_value.__enter__.return_value = mock_server

        result = send_multi_email_notification(
            'Test Subject',
            'Test Body',
            email_env_var='CUSTOM_EMAIL_VAR'
        )

        self.assertEqual(result['success_count'], 1)
        self.assertEqual(result['failure_count'], 0)


if __name__ == '__main__':
    unittest.main()
