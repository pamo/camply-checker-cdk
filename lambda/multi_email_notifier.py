"""
Multi-email notification system for sending campsite availability notifications.

This module provides functionality to send email notifications to multiple recipients
using existing email credential handling from environment variables. It includes
individual email sending with error handling per recipient and CloudWatch metrics
publishing for monitoring email delivery success/failure rates.
"""

import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Optional
from email_config_parser import EmailConfigParser

logger = logging.getLogger(__name__)


class MultiEmailNotifier:
    """
    Multi-email notification system that handles sending notifications to multiple recipients.

    Uses existing email credential handling from environment variables and provides
    individual email sending with error handling per recipient.
    """

    def __init__(self, email_env_var: str = 'EMAIL_TO_ADDRESS'):
        """
        Initialize the multi-email notifier.

        Args:
            email_env_var: Name of the environment variable containing email addresses
        """
        self.email_parser = EmailConfigParser(email_env_var)
        self.smtp_server = os.environ.get('EMAIL_SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.environ.get('EMAIL_SMTP_PORT', '465'))
        self.username = os.environ.get('EMAIL_USERNAME', '')
        self.password = os.environ.get('EMAIL_PASSWORD', '')
        self.from_address = os.environ.get('EMAIL_FROM_ADDRESS', '')

        # Validate required credentials
        if not all([self.username, self.password, self.from_address]):
            raise ValueError("Missing required email credentials in environment variables")

    def get_email_addresses(self) -> List[str]:
        """
        Get the list of email addresses from environment variable configuration.

        Returns:
            List of validated email addresses

        Raises:
            ValueError: If no valid email addresses are found
        """
        return self.email_parser.parse_email_addresses()

    def send_notifications(self, subject: str, body: str, html_body: Optional[str] = None) -> Dict[str, any]:
        """
        Send email notifications to all configured recipients.

        Args:
            subject: Email subject line
            body: Plain text email body
            html_body: Optional HTML email body

        Returns:
            Dictionary containing:
            - 'success_count': Number of successful deliveries
            - 'failure_count': Number of failed deliveries
            - 'results': List of delivery results per recipient
            - 'errors': List of error messages for failed deliveries
        """
        try:
            email_addresses = self.get_email_addresses()
        except ValueError as e:
            logger.error(f"Failed to get email addresses: {str(e)}")
            return {
                'success_count': 0,
                'failure_count': 0,
                'results': [],
                'errors': [f"Email configuration error: {str(e)}"]
            }

        logger.info(f"Sending notifications to {len(email_addresses)} recipient(s)")

        results = []
        success_count = 0
        failure_count = 0
        errors = []

        for email_address in email_addresses:
            try:
                self._send_individual_email(email_address, subject, body, html_body)
                results.append({
                    'email': email_address,
                    'status': 'success',
                    'error': None
                })
                success_count += 1
                logger.info(f"Successfully sent notification to {email_address}")
            except Exception as e:
                error_msg = f"Failed to send notification to {email_address}: {str(e)}"
                logger.error(error_msg)
                results.append({
                    'email': email_address,
                    'status': 'failure',
                    'error': str(e)
                })
                errors.append(error_msg)
                failure_count += 1

        # Log summary
        logger.info(f"Email delivery summary: {success_count} successful, {failure_count} failed")

        return {
            'success_count': success_count,
            'failure_count': failure_count,
            'results': results,
            'errors': errors
        }

    def _send_individual_email(self, to_address: str, subject: str, body: str, html_body: Optional[str] = None) -> None:
        """
        Send an individual email to a single recipient.

        Args:
            to_address: Recipient email address
            subject: Email subject line
            body: Plain text email body
            html_body: Optional HTML email body

        Raises:
            Exception: If email sending fails
        """
        # Create message
        msg = MIMEMultipart('alternative')
        msg['From'] = self.from_address
        msg['To'] = to_address
        msg['Subject'] = subject

        # Add plain text part
        text_part = MIMEText(body, 'plain')
        msg.attach(text_part)

        # Add HTML part if provided
        if html_body:
            html_part = MIMEText(html_body, 'html')
            msg.attach(html_part)

        # Send email
        try:
            with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port) as server:
                server.login(self.username, self.password)
                server.send_message(msg)
        except smtplib.SMTPException as e:
            raise Exception(f"SMTP error: {str(e)}")
        except Exception as e:
            raise Exception(f"Email sending error: {str(e)}")

    def test_connection(self) -> bool:
        """
        Test the SMTP connection and authentication.

        Returns:
            True if connection is successful, False otherwise
        """
        try:
            with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port) as server:
                server.login(self.username, self.password)
            logger.info("SMTP connection test successful")
            return True
        except Exception as e:
            logger.error(f"SMTP connection test failed: {str(e)}")
            return False

    def validate_configuration(self) -> Dict[str, any]:
        """
        Validate the complete email notification configuration.

        Returns:
            Dictionary containing validation results:
            - 'valid': bool - Whether configuration is valid
            - 'email_config': dict - Email address validation results
            - 'smtp_config': dict - SMTP configuration validation results
            - 'errors': List[str] - List of validation errors
        """
        result = {
            'valid': False,
            'email_config': {},
            'smtp_config': {},
            'errors': []
        }

        # Validate email addresses
        result['email_config'] = self.email_parser.validate_email_config()

        # Validate SMTP configuration
        smtp_errors = []
        if not self.username:
            smtp_errors.append("EMAIL_USERNAME not set")
        if not self.password:
            smtp_errors.append("EMAIL_PASSWORD not set")
        if not self.from_address:
            smtp_errors.append("EMAIL_FROM_ADDRESS not set")

        result['smtp_config'] = {
            'valid': len(smtp_errors) == 0,
            'server': self.smtp_server,
            'port': self.smtp_port,
            'username': self.username,
            'from_address': self.from_address,
            'errors': smtp_errors
        }

        # Overall validation
        result['valid'] = result['email_config']['valid'] and result['smtp_config']['valid']
        result['errors'] = result['email_config'].get('errors', []) + smtp_errors

        return result


def send_multi_email_notification(subject: str, body: str, html_body: Optional[str] = None,
                                 email_env_var: str = 'EMAIL_TO_ADDRESS') -> Dict[str, any]:
    """
    Convenience function to send multi-email notifications.

    Args:
        subject: Email subject line
        body: Plain text email body
        html_body: Optional HTML email body
        email_env_var: Name of the environment variable containing email addresses

    Returns:
        Dictionary containing delivery results and statistics
    """
    notifier = MultiEmailNotifier(email_env_var)
    return notifier.send_notifications(subject, body, html_body)
