"""
Email configuration parser utility for handling multiple email recipients.

This module provides functionality to parse and validate email addresses from
environment variables, supporting both single email addresses and comma-separated
multiple email addresses for backward compatibility.
"""

import os
import re
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class EmailConfigParser:
    """
    Utility class for parsing and validating email configuration from environment variables.

    Supports both single email addresses and comma-separated multiple email addresses
    while maintaining backward compatibility with existing single email format.
    """

    # RFC 5322 compliant email regex pattern (simplified but robust)
    # Ensures proper domain structure and prevents consecutive dots
    EMAIL_PATTERN = re.compile(
        r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}$'
    )

    def __init__(self, env_var_name: str = 'EMAIL_TO_ADDRESS'):
        """
        Initialize the email config parser.

        Args:
            env_var_name: Name of the environment variable containing email addresses
        """
        self.env_var_name = env_var_name

    def parse_email_addresses(self) -> List[str]:
        """
        Parse email addresses from the configured environment variable.

        Supports both formats:
        - Single email: "user@example.com"
        - Multiple emails: "user1@example.com,user2@example.com,user3@example.com"

        Returns:
            List of validated email addresses

        Raises:
            ValueError: If no valid email addresses are found or environment variable is missing
        """
        email_config = os.environ.get(self.env_var_name)

        if not email_config:
            raise ValueError(f"Environment variable {self.env_var_name} is not set")

        # Split by comma and clean up whitespace
        raw_emails = [email.strip() for email in email_config.split(',')]

        # Filter out empty strings and validate emails
        valid_emails = []
        invalid_emails = []

        for email in raw_emails:
            if email:  # Skip empty strings
                if self.is_valid_email(email):
                    valid_emails.append(email)
                else:
                    invalid_emails.append(email)

        if invalid_emails:
            logger.warning(f"Invalid email addresses found and skipped: {invalid_emails}")

        if not valid_emails:
            raise ValueError(f"No valid email addresses found in {self.env_var_name}")

        logger.info(f"Parsed {len(valid_emails)} valid email address(es) from {self.env_var_name}")
        return valid_emails

    def is_valid_email(self, email: str) -> bool:
        """
        Validate an email address using RFC 5322 compliant regex.

        Args:
            email: Email address to validate

        Returns:
            True if email is valid, False otherwise
        """
        if not email or not isinstance(email, str):
            return False

        return bool(self.EMAIL_PATTERN.match(email.strip()))

    def get_primary_email(self) -> Optional[str]:
        """
        Get the first (primary) email address from the configuration.

        Useful for backward compatibility where only one email is needed.

        Returns:
            First valid email address or None if no valid emails found
        """
        try:
            emails = self.parse_email_addresses()
            return emails[0] if emails else None
        except ValueError:
            return None

    def validate_email_config(self) -> dict:
        """
        Validate the email configuration and return detailed results.

        Returns:
            Dictionary containing validation results:
            - 'valid': bool - Whether configuration is valid
            - 'emails': List[str] - List of valid email addresses
            - 'count': int - Number of valid emails
            - 'errors': List[str] - List of validation errors
        """
        result = {
            'valid': False,
            'emails': [],
            'count': 0,
            'errors': []
        }

        try:
            emails = self.parse_email_addresses()
            result['valid'] = True
            result['emails'] = emails
            result['count'] = len(emails)
        except ValueError as e:
            result['errors'].append(str(e))
        except Exception as e:
            result['errors'].append(f"Unexpected error: {str(e)}")

        return result


def get_email_addresses(env_var_name: str = 'EMAIL_TO_ADDRESS') -> List[str]:
    """
    Convenience function to get email addresses from environment variable.

    Args:
        env_var_name: Name of the environment variable containing email addresses

    Returns:
        List of validated email addresses

    Raises:
        ValueError: If no valid email addresses are found
    """
    parser = EmailConfigParser(env_var_name)
    return parser.parse_email_addresses()


def get_primary_email(env_var_name: str = 'EMAIL_TO_ADDRESS') -> Optional[str]:
    """
    Convenience function to get the primary (first) email address.

    Args:
        env_var_name: Name of the environment variable containing email addresses

    Returns:
        First valid email address or None if no valid emails found
    """
    parser = EmailConfigParser(env_var_name)
    return parser.get_primary_email()
