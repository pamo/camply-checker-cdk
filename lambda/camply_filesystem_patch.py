"""
Filesystem redirection utilities for camply in AWS Lambda environments.

This module provides targeted redirection of file operations from read-only
package directories to writable temporary directories in AWS Lambda.
"""

import os
import logging
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


def setup_camply_filesystem():
    """
    Set up filesystem redirection for camply in Lambda environments.

    Returns:
        str: The temporary directory path for cleanup.
    """
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

    # Create camply cache structure in temp directory
    camply_cache_dir = os.path.join(temp_dir, 'camply_cache', 'providers', 'usedirect', 'ReserveCalifornia')
    os.makedirs(camply_cache_dir, exist_ok=True)

    # Apply targeted patches for read-only paths
    apply_filesystem_patches(temp_dir)

    return temp_dir


def apply_filesystem_patches(temp_dir):
    """Apply targeted monkey patches to Path methods for read-only paths."""

    # Store original Path methods
    original_mkdir = Path.mkdir
    original_open = Path.open
    original_write_text = Path.write_text
    original_read_text = Path.read_text
    original_exists = Path.exists

    def redirect_if_readonly(path_str):
        """Check if path is in read-only camply package directory and redirect."""
        readonly_patterns = [
            '/usr/local/lib/python3.11/site-packages/camply',
            '/var/lang/lib/python3.11/site-packages/camply'
        ]

        for pattern in readonly_patterns:
            if pattern in path_str:
                if 'camply/' in path_str:
                    relative_path = path_str.split('camply/')[-1]
                    redirected = os.path.join(temp_dir, 'camply_cache', relative_path)
                    logger.debug(f"Redirecting read-only path: {path_str} -> {redirected}")
                    return redirected
        return path_str

    # Targeted monkey patches
    def safe_mkdir(self, mode=0o777, parents=False, exist_ok=False):
        redirected = redirect_if_readonly(str(self))
        if redirected != str(self):
            return original_mkdir(Path(redirected), mode, parents, exist_ok)
        return original_mkdir(self, mode, parents, exist_ok)

    def safe_open(self, mode='r', buffering=-1, encoding=None, errors=None, newline=None):
        redirected = redirect_if_readonly(str(self))
        if redirected != str(self):
            if 'w' in mode or 'a' in mode:
                Path(redirected).parent.mkdir(parents=True, exist_ok=True)
            return original_open(Path(redirected), mode, buffering, encoding, errors, newline)
        return original_open(self, mode, buffering, encoding, errors, newline)

    def safe_write_text(self, data, encoding=None, errors=None, newline=None):
        redirected = redirect_if_readonly(str(self))
        if redirected != str(self):
            Path(redirected).parent.mkdir(parents=True, exist_ok=True)
            return original_write_text(Path(redirected), data, encoding, errors, newline)
        return original_write_text(self, data, encoding, errors, newline)

    def safe_read_text(self, encoding=None, errors=None):
        redirected = redirect_if_readonly(str(self))
        if redirected != str(self):
            redirected_path = Path(redirected)
            if redirected_path.exists():
                return original_read_text(redirected_path, encoding, errors)
            # Try to copy from original if it exists
            if original_exists(self):
                logger.info(f"Copying original file to writable location: {self} -> {redirected}")
                redirected_path.parent.mkdir(parents=True, exist_ok=True)
                content = original_read_text(self, encoding, errors)
                original_write_text(redirected_path, content, encoding)
                return content
        return original_read_text(self, encoding, errors)

    def safe_exists(self):
        redirected = redirect_if_readonly(str(self))
        if redirected != str(self):
            return Path(redirected).exists() or original_exists(self)
        return original_exists(self)

    # Apply patches
    Path.mkdir = safe_mkdir
    Path.open = safe_open
    Path.write_text = safe_write_text
    Path.read_text = safe_read_text
    Path.exists = safe_exists

    logger.info("Applied filesystem patches for camply")


def cleanup_temp_dir(temp_dir):
    """Clean up the temporary directory."""
    try:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        logger.info(f"Cleaned up temporary directory: {temp_dir}")
    except Exception as e:
        logger.warning(f"Failed to clean up temp directory: {e}")
