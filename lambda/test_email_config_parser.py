"""
Unit tests for email_config_parser module.

Tests cover email parsing, validation, backward compatibility,
and error handling scenarios.
"""

import os
import pytest
import unittest
from unittest.mock import patch
from email_config_parser import EmailConfigParser, get_email_addresses, get_primary_email


class TestEmailConfigParser(unittest.TestCase):
    """Test cases for EmailConfigParser class."""

    def setUp(self):
        """Set up test fixtures."""
        self.parser = EmailConfigParser()
        # Clean up environment variable before each test
        if 'EMAIL_TO_ADDRESS' in os.environ:
            del os.environ['EMAIL_TO_ADDRESS']

    def tearDown(self):
        """Clean up after each test."""
        # Clean up environment variable after each test
        if 'EMAIL_TO_ADDRESS' in os.environ:
            del os.environ['EMAIL_TO_ADDRESS']

    def test_single_email_parsing(self):
        """Test parsing a single email address."""
        os.environ['EMAIL_TO_ADDRESS'] = 'user@example.com'
        emails = self.parser.parse_email_addresses()

        self.assertEqual(len(emails), 1)
        self.assertEqual(emails[0], 'user@example.com')

    def test_multiple_email_parsing(self):
        """Test parsing multiple comma-separated email addresses."""
        os.environ['EMAIL_TO_ADDRESS'] = 'user1@example.com,user2@example.com,user3@example.com'
        emails = self.parser.parse_email_addresses()

        self.assertEqual(len(emails), 3)
        self.assertIn('user1@example.com', emails)
        self.assertIn('user2@example.com', emails)
        self.assertIn('user3@example.com', emails)

    def test_email_parsing_with_whitespace(self):
        """Test parsing emails with extra whitespace."""
        os.environ['EMAIL_TO_ADDRESS'] = ' user1@example.com , user2@example.com , user3@example.com '
        emails = self.parser.parse_email_addresses()

        self.assertEqual(len(emails), 3)
        self.assertEqual(emails[0], 'user1@example.com')
        self.assertEqual(emails[1], 'user2@example.com')
        self.assertEqual(emails[2], 'user3@example.com')

    def test_email_parsing_with_empty_entries(self):
        """Test parsing emails with empty entries between commas."""
        os.environ['EMAIL_TO_ADDRESS'] = 'user1@example.com,,user2@example.com, ,user3@example.com'
        emails = self.parser.parse_email_addresses()

        self.assertEqual(len(emails), 3)
        self.assertIn('user1@example.com', emails)
        self.assertIn('user2@example.com', emails)
        self.assertIn('user3@example.com', emails)

    def test_missing_environment_variable(self):
        """Test behavior when environment variable is not set."""
        with self.assertRaises(ValueError) as context:
            self.parser.parse_email_addresses()

        self.assertIn('EMAIL_TO_ADDRESS is not set', str(context.exception))

    def test_empty_environment_variable(self):
        """Test behavior when environment variable is empty."""
        os.environ['EMAIL_TO_ADDRESS'] = ''

        with self.assertRaises(ValueError) as context:
            self.parser.parse_email_addresses()

        self.assertIn('EMAIL_TO_ADDRESS is not set', str(context.exception))

    def test_custom_environment_variable_name(self):
        """Test using a custom environment variable name."""
        os.environ['CUSTOM_EMAIL_VAR'] = 'custom@example.com'
        parser = EmailConfigParser('CUSTOM_EMAIL_VAR')
        emails = parser.parse_email_addresses()

        self.assertEqual(len(emails), 1)
        self.assertEqual(emails[0], 'custom@example.com')

    def test_email_validation_valid_emails(self):
        """Test email validation with valid email addresses."""
        valid_emails = [
            'user@example.com',
            'test.email@domain.co.uk',
            'user+tag@example.org',
            'user123@test-domain.com',
            'a@b.co'
        ]

        for email in valid_emails:
            with self.subTest(email=email):
                self.assertTrue(self.parser.is_valid_email(email))

    def test_email_validation_invalid_emails(self):
        """Test email validation with invalid email addresses."""
        invalid_emails = [
            'invalid-email',
            '@example.com',
            'user@',
            'user@.com',
            'user@domain',
            'user space@example.com',
            '',
            None,
            123,
            'user@domain..com'
        ]

        for email in invalid_emails:
            with self.subTest(email=email):
                self.assertFalse(self.parser.is_valid_email(email))

    def test_mixed_valid_invalid_emails(self):
        """Test parsing with mix of valid and invalid email addresses."""
        os.environ['EMAIL_TO_ADDRESS'] = 'valid@example.com,invalid-email,another@example.com,@invalid.com'

        with patch('email_config_parser.logger') as mock_logger:
            emails = self.parser.parse_email_addresses()

            self.assertEqual(len(emails), 2)
            self.assertIn('valid@example.com', emails)
            self.assertIn('another@example.com', emails)

            # Check that warning was logged for invalid emails
            mock_logger.warning.assert_called_once()
            warning_call = mock_logger.warning.call_args[0][0]
            self.assertIn('Invalid email addresses found', warning_call)

    def test_all_invalid_emails(self):
        """Test behavior when all emails are invalid."""
        os.environ['EMAIL_TO_ADDRESS'] = 'invalid-email,@invalid.com,another-invalid'

        with self.assertRaises(ValueError) as context:
            self.parser.parse_email_addresses()

        self.assertIn('No valid email addresses found', str(context.exception))

    def test_get_primary_email_single(self):
        """Test getting primary email with single email."""
        os.environ['EMAIL_TO_ADDRESS'] = 'primary@example.com'
        primary = self.parser.get_primary_email()

        self.assertEqual(primary, 'primary@example.com')

    def test_get_primary_email_multiple(self):
        """Test getting primary email with multiple emails."""
        os.environ['EMAIL_TO_ADDRESS'] = 'first@example.com,second@example.com,third@example.com'
        primary = self.parser.get_primary_email()

        self.assertEqual(primary, 'first@example.com')

    def test_get_primary_email_none(self):
        """Test getting primary email when no valid emails exist."""
        primary = self.parser.get_primary_email()
        self.assertIsNone(primary)

    def test_validate_email_config_valid(self):
        """Test email configuration validation with valid config."""
        os.environ['EMAIL_TO_ADDRESS'] = 'user1@example.com,user2@example.com'
        result = self.parser.validate_email_config()

        self.assertTrue(result['valid'])
        self.assertEqual(result['count'], 2)
        self.assertEqual(len(result['emails']), 2)
        self.assertEqual(len(result['errors']), 0)
        self.assertIn('user1@example.com', result['emails'])
        self.assertIn('user2@example.com', result['emails'])

    def test_validate_email_config_invalid(self):
        """Test email configuration validation with invalid config."""
        result = self.parser.validate_email_config()

        self.assertFalse(result['valid'])
        self.assertEqual(result['count'], 0)
        self.assertEqual(len(result['emails']), 0)
        self.assertGreater(len(result['errors']), 0)
        self.assertIn('EMAIL_TO_ADDRESS is not set', result['errors'][0])

    def test_validate_email_config_mixed(self):
        """Test email configuration validation with mixed valid/invalid emails."""
        os.environ['EMAIL_TO_ADDRESS'] = 'valid@example.com,invalid-email'

        with patch('email_config_parser.logger'):
            result = self.parser.validate_email_config()

        self.assertTrue(result['valid'])
        self.assertEqual(result['count'], 1)
        self.assertEqual(len(result['emails']), 1)
        self.assertEqual(result['emails'][0], 'valid@example.com')


class TestConvenienceFunctions(unittest.TestCase):
    """Test cases for convenience functions."""

    def setUp(self):
        """Set up test fixtures."""
        # Clean up environment variable before each test
        if 'EMAIL_TO_ADDRESS' in os.environ:
            del os.environ['EMAIL_TO_ADDRESS']

    def tearDown(self):
        """Clean up after each test."""
        # Clean up environment variable after each test
        if 'EMAIL_TO_ADDRESS' in os.environ:
            del os.environ['EMAIL_TO_ADDRESS']

    def test_get_email_addresses_function(self):
        """Test get_email_addresses convenience function."""
        os.environ['EMAIL_TO_ADDRESS'] = 'user1@example.com,user2@example.com'
        emails = get_email_addresses()

        self.assertEqual(len(emails), 2)
        self.assertIn('user1@example.com', emails)
        self.assertIn('user2@example.com', emails)

    def test_get_email_addresses_custom_var(self):
        """Test get_email_addresses with custom environment variable."""
        os.environ['CUSTOM_EMAIL'] = 'custom@example.com'
        emails = get_email_addresses('CUSTOM_EMAIL')

        self.assertEqual(len(emails), 1)
        self.assertEqual(emails[0], 'custom@example.com')

    def test_get_primary_email_function(self):
        """Test get_primary_email convenience function."""
        os.environ['EMAIL_TO_ADDRESS'] = 'primary@example.com,secondary@example.com'
        primary = get_primary_email()

        self.assertEqual(primary, 'primary@example.com')

    def test_get_primary_email_custom_var(self):
        """Test get_primary_email with custom environment variable."""
        os.environ['CUSTOM_EMAIL'] = 'custom@example.com'
        primary = get_primary_email('CUSTOM_EMAIL')

        self.assertEqual(primary, 'custom@example.com')

    def test_get_primary_email_none(self):
        """Test get_primary_email when no emails are configured."""
        primary = get_primary_email()
        self.assertIsNone(primary)


class TestBackwardCompatibility(unittest.TestCase):
    """Test cases for backward compatibility scenarios."""

    def setUp(self):
        """Set up test fixtures."""
        if 'EMAIL_TO_ADDRESS' in os.environ:
            del os.environ['EMAIL_TO_ADDRESS']

    def tearDown(self):
        """Clean up after each test."""
        if 'EMAIL_TO_ADDRESS' in os.environ:
            del os.environ['EMAIL_TO_ADDRESS']

    def test_existing_single_email_format(self):
        """Test that existing single email format continues to work."""
        # Simulate existing configuration
        os.environ['EMAIL_TO_ADDRESS'] = 'existing@example.com'

        parser = EmailConfigParser()
        emails = parser.parse_email_addresses()
        primary = parser.get_primary_email()

        # Should work exactly as before
        self.assertEqual(len(emails), 1)
        self.assertEqual(emails[0], 'existing@example.com')
        self.assertEqual(primary, 'existing@example.com')

    def test_gmail_format_compatibility(self):
        """Test compatibility with Gmail addresses (common in existing configs)."""
        os.environ['EMAIL_TO_ADDRESS'] = 'user@gmail.com'

        parser = EmailConfigParser()
        emails = parser.parse_email_addresses()

        self.assertEqual(len(emails), 1)
        self.assertEqual(emails[0], 'user@gmail.com')
        self.assertTrue(parser.is_valid_email('user@gmail.com'))

    def test_multiple_emails_new_format(self):
        """Test that new multiple email format works correctly."""
        os.environ['EMAIL_TO_ADDRESS'] = 'admin@example.com,user@example.com,backup@example.com'

        parser = EmailConfigParser()
        emails = parser.parse_email_addresses()
        primary = parser.get_primary_email()

        # New functionality should work
        self.assertEqual(len(emails), 3)
        self.assertEqual(primary, 'admin@example.com')  # First email is primary
        self.assertIn('admin@example.com', emails)
        self.assertIn('user@example.com', emails)
        self.assertIn('backup@example.com', emails)


if __name__ == '__main__':
    unittest.main()
