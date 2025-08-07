import json
import hashlib
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class ResultComparator:
    """
    Handles comparison and normalization of campground search results.
    Provides hash-based comparison for efficient result matching with proper
    handling of edge cases like missing or malformed data.
    """

    def compare_results(self, current: Dict[str, Any], previous: Optional[Dict[str, Any]]) -> bool:
        """
        Compare current search results with previous results.

        Args:
            current: Current search results dictionary
            previous: Previous search results dictionary, or None if no previous results

        Returns:
            True if results have changed or no previous results exist, False if identical
        """
        try:
            # If no previous results exist, consider results as changed
            if previous is None:
                logger.info("No previous results found, treating as changed")
                return True

            # Handle malformed previous results
            if not isinstance(previous, dict):
                logger.warning("Previous results are malformed (not a dictionary), treating as changed")
                return True

            # Normalize both result sets for comparison
            normalized_current = self.normalize_results(current)
            normalized_previous = self.normalize_results(previous)

            # Generate hashes for comparison
            current_hash = self._generate_hash(normalized_current)
            previous_hash = self._generate_hash(normalized_previous)

            # Compare hashes
            results_changed = current_hash != previous_hash

            if results_changed:
                logger.info("Results have changed based on hash comparison")
            else:
                logger.info("Results are identical based on hash comparison")

            return results_changed

        except Exception as e:
            logger.error(f"Error during result comparison: {str(e)}")
            # Default to treating as changed if comparison fails (fail-safe approach)
            return True

    def normalize_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize search results for consistent comparison.

        This method handles:
        - Sorting of lists and dictionaries
        - Removal of timestamp-related fields that shouldn't affect comparison
        - Standardization of data types
        - Handling of missing or None values

        Args:
            results: Raw search results dictionary

        Returns:
            Normalized results dictionary suitable for comparison
        """
        try:
            if not isinstance(results, dict):
                logger.warning("Results are not a dictionary, returning empty dict for normalization")
                return {}

            normalized = {}

            for key, value in results.items():
                # Skip timestamp fields that shouldn't affect comparison
                if key.lower() in ['timestamp', 'last_updated', 'search_time', 'search_timestamp']:
                    continue

                normalized_key = str(key).strip().lower()
                normalized[normalized_key] = self._normalize_value(value)

            return normalized

        except Exception as e:
            logger.error(f"Error normalizing results: {str(e)}")
            # Return original results if normalization fails
            return results if isinstance(results, dict) else {}

    def _normalize_value(self, value: Any) -> Any:
        """
        Recursively normalize individual values within results.

        Args:
            value: Value to normalize

        Returns:
            Normalized value
        """
        try:
            if value is None:
                return None

            if isinstance(value, dict):
                # Recursively normalize dictionary values and sort keys
                normalized_dict = {}
                for k, v in value.items():
                    normalized_key = str(k).strip().lower()
                    normalized_dict[normalized_key] = self._normalize_value(v)
                return normalized_dict

            elif isinstance(value, list):
                # Normalize list items and sort if they're comparable
                normalized_list = [self._normalize_value(item) for item in value]
                try:
                    # Try to sort the list for consistent ordering
                    # This works for lists of strings, numbers, or simple comparable types
                    if normalized_list and all(type(item) == type(normalized_list[0]) for item in normalized_list):
                        if isinstance(normalized_list[0], (str, int, float)):
                            return sorted(normalized_list)
                except (TypeError, AttributeError):
                    # If sorting fails, return the list as-is
                    pass
                return normalized_list

            elif isinstance(value, str):
                # Normalize strings by stripping whitespace and converting to lowercase
                return value.strip().lower()

            elif isinstance(value, (int, float)):
                # Numbers are already normalized
                return value

            elif isinstance(value, bool):
                # Booleans are already normalized
                return value

            else:
                # For other types, convert to string and normalize
                return str(value).strip().lower()

        except Exception as e:
            logger.warning(f"Error normalizing value {value}: {str(e)}")
            # Return original value if normalization fails
            return value

    def _generate_hash(self, data: Dict[str, Any]) -> str:
        """
        Generate SHA256 hash of normalized data for comparison.

        Args:
            data: Normalized data dictionary

        Returns:
            SHA256 hash string of the data
        """
        try:
            # Create a consistent string representation for hashing
            # Sort keys to ensure consistent hashing regardless of insertion order
            normalized_json = json.dumps(data, sort_keys=True, separators=(',', ':'))
            return hashlib.sha256(normalized_json.encode('utf-8')).hexdigest()

        except (TypeError, ValueError) as e:
            logger.error(f"JSON serialization error during hash generation: {str(e)}")
            # Fallback to string representation if JSON serialization fails
            try:
                data_str = str(sorted(data.items()) if isinstance(data, dict) else data)
                return hashlib.sha256(data_str.encode('utf-8')).hexdigest()
            except Exception as fallback_error:
                logger.error(f"Fallback hash generation failed: {str(fallback_error)}")
                # Return a default hash based on the data type and length
                return hashlib.sha256(f"error_hash_{type(data).__name__}_{len(str(data))}".encode('utf-8')).hexdigest()

        except Exception as e:
            logger.error(f"Unexpected error during hash generation: {str(e)}")
            # Return a default error hash
            return hashlib.sha256("hash_generation_error".encode('utf-8')).hexdigest()

    def get_comparison_summary(self, current: Dict[str, Any], previous: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Get a detailed summary of the comparison between current and previous results.
        Useful for debugging and logging purposes.

        Args:
            current: Current search results dictionary
            previous: Previous search results dictionary, or None

        Returns:
            Dictionary containing comparison summary information
        """
        try:
            summary = {
                "has_previous_results": previous is not None,
                "results_changed": self.compare_results(current, previous),
                "current_hash": None,
                "previous_hash": None,
                "normalization_errors": []
            }

            # Generate hashes for summary
            try:
                normalized_current = self.normalize_results(current)
                summary["current_hash"] = self._generate_hash(normalized_current)
            except Exception as e:
                summary["normalization_errors"].append(f"Current results: {str(e)}")

            if previous is not None:
                try:
                    normalized_previous = self.normalize_results(previous)
                    summary["previous_hash"] = self._generate_hash(normalized_previous)
                except Exception as e:
                    summary["normalization_errors"].append(f"Previous results: {str(e)}")

            return summary

        except Exception as e:
            logger.error(f"Error generating comparison summary: {str(e)}")
            return {
                "has_previous_results": previous is not None,
                "results_changed": True,  # Default to changed on error
                "error": str(e)
            }
