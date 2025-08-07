import pytest
from unittest.mock import patch, MagicMock
import json
from result_comparator import ResultComparator


class TestResultComparator:
    """Test suite for ResultComparator class"""

    def setup_method(self):
        """Set up test fixtures before each test method"""
        self.comparator = ResultComparator()

        # Sample search results for testing
        self.sample_current_results = {
            "campground_id": "766",
            "campground_name": "Steep Ravine",
            "available_sites": [
                {
                    "site_id": "123",
                    "site_name": "Site A",
                    "dates": ["2025-01-15", "2025-01-16"]
                },
                {
                    "site_id": "124",
                    "site_name": "Site B",
                    "dates": ["2025-01-17"]
                }
            ],
            "total_available_nights": 3,
            "timestamp": "2025-01-08T10:30:00Z"
        }

        self.sample_previous_results = {
            "campground_id": "766",
            "campground_name": "Steep Ravine",
            "available_sites": [
                {
                    "site_id": "123",
                    "site_name": "Site A",
                    "dates": ["2025-01-15", "2025-01-16"]
                },
                {
                    "site_id": "124",
                    "site_name": "Site B",
                    "dates": ["2025-01-17"]
                }
            ],
            "total_available_nights": 3,
            "timestamp": "2025-01-07T09:15:00Z"  # Different timestamp
        }

    def test_compare_results_no_previous_results(self):
        """Test comparison when no previous results exist"""
        result = self.comparator.compare_results(self.sample_current_results, None)
        assert result is True

    def test_compare_results_identical_results(self):
        """Test comparison when results are identical (ignoring timestamps)"""
        result = self.comparator.compare_results(
            self.sample_current_results,
            self.sample_previous_results
        )
        assert result is False  # Should be identical after normalization

    def test_compare_results_different_results(self):
        """Test comparison when results are different"""
        different_previous = self.sample_previous_results.copy()
        different_previous["total_available_nights"] = 2  # Different value

        result = self.comparator.compare_results(
            self.sample_current_results,
            different_previous
        )
        assert result is True

    def test_compare_results_malformed_previous(self):
        """Test comparison with malformed previous results"""
        # Test with non-dictionary previous results
        result = self.comparator.compare_results(self.sample_current_results, "invalid")
        assert result is True

        # Test with None values in previous results
        malformed_previous = None
        result = self.comparator.compare_results(self.sample_current_results, malformed_previous)
        assert result is True

    def test_compare_results_with_exception(self):
        """Test comparison when an exception occurs during processing"""
        with patch.object(self.comparator, 'normalize_results', side_effect=Exception("Mock error")):
            result = self.comparator.compare_results(self.sample_current_results, self.sample_previous_results)
            assert result is True  # Should default to changed on error

    def test_normalize_results_basic(self):
        """Test basic result normalization"""
        test_results = {
            "CampgroundName": "  STEEP RAVINE  ",
            "TotalSites": 5,
            "AvailableSites": [
                {"SiteId": "123", "SiteName": "  Site A  "},
                {"SiteId": "124", "SiteName": "  Site B  "}
            ],
            "timestamp": "2025-01-08T10:30:00Z"  # Should be excluded
        }

        normalized = self.comparator.normalize_results(test_results)

        # Check that keys are normalized to lowercase
        assert "campgroundname" in normalized
        assert "totalsites" in normalized
        assert "availablesites" in normalized
        assert "timestamp" not in normalized  # Should be excluded

        # Check that string values are normalized
        assert normalized["campgroundname"] == "steep ravine"

        # Check that nested dictionaries are normalized
        sites = normalized["availablesites"]
        assert sites[0]["sitename"] == "site a"
        assert sites[1]["sitename"] == "site b"

    def test_normalize_results_with_lists(self):
        """Test normalization of results containing lists"""
        test_results = {
            "dates": ["2025-01-17", "2025-01-15", "2025-01-16"],  # Unsorted
            "site_types": ["RV", "tent", "Cabin"]  # Mixed case
        }

        normalized = self.comparator.normalize_results(test_results)

        # Lists of strings should be sorted
        assert normalized["dates"] == ["2025-01-15", "2025-01-16", "2025-01-17"]
        assert normalized["site_types"] == ["cabin", "rv", "tent"]

    def test_normalize_results_with_mixed_types(self):
        """Test normalization with mixed data types"""
        test_results = {
            "string_field": "  Test String  ",
            "int_field": 42,
            "float_field": 3.14,
            "bool_field": True,
            "none_field": None,
            "nested_dict": {
                "inner_string": "  INNER  ",
                "inner_int": 100
            }
        }

        normalized = self.comparator.normalize_results(test_results)

        assert normalized["string_field"] == "test string"
        assert normalized["int_field"] == 42
        assert normalized["float_field"] == 3.14
        assert normalized["bool_field"] is True
        assert normalized["none_field"] is None
        assert normalized["nested_dict"]["inner_string"] == "inner"
        assert normalized["nested_dict"]["inner_int"] == 100

    def test_normalize_results_invalid_input(self):
        """Test normalization with invalid input"""
        # Test with non-dictionary input
        result = self.comparator.normalize_results("invalid")
        assert result == {}

        # Test with None input
        result = self.comparator.normalize_results(None)
        assert result == {}

    def test_normalize_results_with_exception(self):
        """Test normalization when an exception occurs"""
        # Create a problematic input that might cause issues
        problematic_results = {"key": object()}  # Non-serializable object

        # Should handle the exception gracefully
        normalized = self.comparator.normalize_results(problematic_results)
        assert isinstance(normalized, dict)

    def test_normalize_value_edge_cases(self):
        """Test _normalize_value with various edge cases"""
        # Test with unsortable list (mixed types)
        mixed_list = [1, "string", {"dict": "value"}]
        normalized = self.comparator._normalize_value(mixed_list)
        assert len(normalized) == 3  # Should preserve all items

        # Test with empty containers
        assert self.comparator._normalize_value({}) == {}
        assert self.comparator._normalize_value([]) == []

        # Test with nested structures
        nested = {
            "level1": {
                "level2": {
                    "level3": ["c", "a", "b"]
                }
            }
        }
        normalized = self.comparator._normalize_value(nested)
        assert normalized["level1"]["level2"]["level3"] == ["a", "b", "c"]

    def test_generate_hash_consistency(self):
        """Test that hash generation is consistent"""
        data1 = {"a": 1, "b": 2, "c": 3}
        data2 = {"c": 3, "a": 1, "b": 2}  # Same data, different order

        hash1 = self.comparator._generate_hash(data1)
        hash2 = self.comparator._generate_hash(data2)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 produces 64-character hex string

    def test_generate_hash_different_data(self):
        """Test that different data produces different hashes"""
        data1 = {"a": 1, "b": 2}
        data2 = {"a": 1, "b": 3}

        hash1 = self.comparator._generate_hash(data1)
        hash2 = self.comparator._generate_hash(data2)

        assert hash1 != hash2

    def test_generate_hash_with_serialization_error(self):
        """Test hash generation when JSON serialization fails"""
        # Create data that can't be JSON serialized
        problematic_data = {"key": object()}

        # Should still return a hash (fallback behavior)
        hash_result = self.comparator._generate_hash(problematic_data)
        assert len(hash_result) == 64
        assert isinstance(hash_result, str)

    def test_generate_hash_with_complete_failure(self):
        """Test hash generation when JSON serialization fails and fallback is used"""
        with patch('json.dumps', side_effect=Exception("JSON error")):
            # Should use fallback method and still return a hash
            hash_result = self.comparator._generate_hash({"test": "data"})
            assert len(hash_result) == 64  # Should still return a hash
            assert isinstance(hash_result, str)

    def test_get_comparison_summary_basic(self):
        """Test basic comparison summary generation"""
        summary = self.comparator.get_comparison_summary(
            self.sample_current_results,
            self.sample_previous_results
        )

        assert "has_previous_results" in summary
        assert "results_changed" in summary
        assert "current_hash" in summary
        assert "previous_hash" in summary
        assert "normalization_errors" in summary

        assert summary["has_previous_results"] is True
        assert summary["results_changed"] is False  # Should be identical after normalization
        assert isinstance(summary["current_hash"], str)
        assert isinstance(summary["previous_hash"], str)
        assert isinstance(summary["normalization_errors"], list)

    def test_get_comparison_summary_no_previous(self):
        """Test comparison summary when no previous results exist"""
        summary = self.comparator.get_comparison_summary(
            self.sample_current_results,
            None
        )

        assert summary["has_previous_results"] is False
        assert summary["results_changed"] is True
        assert summary["current_hash"] is not None
        assert summary["previous_hash"] is None

    def test_get_comparison_summary_with_errors(self):
        """Test comparison summary when errors occur during processing"""
        with patch.object(self.comparator, 'normalize_results', side_effect=Exception("Mock error")):
            summary = self.comparator.get_comparison_summary(
                self.sample_current_results,
                self.sample_previous_results
            )

            assert "error" in summary or len(summary["normalization_errors"]) > 0
            assert summary["results_changed"] is True  # Should default to changed on error

    def test_real_world_campground_data_comparison(self):
        """Test with realistic campground data structures"""
        current_data = {
            "campground_id": "766",
            "campground_name": "Steep Ravine",
            "provider": "ReserveCalifornia",
            "search_parameters": {
                "start_date": "2025-01-08",
                "end_date": "2025-02-07"
            },
            "available_sites": [
                {
                    "site_id": "123",
                    "site_name": "Site A",
                    "site_type": "tent",
                    "dates": ["2025-01-15", "2025-01-16"],
                    "nightly_rate": 35.00
                }
            ],
            "total_available_nights": 2,
            "search_timestamp": "2025-01-08T10:30:00Z"
        }

        # Previous data with same content but different timestamp
        previous_data = current_data.copy()
        previous_data["search_timestamp"] = "2025-01-07T09:15:00Z"

        # Should be considered identical (timestamp ignored)
        result = self.comparator.compare_results(current_data, previous_data)
        assert result is False

        # Now test with actual difference
        different_previous = previous_data.copy()
        different_previous["total_available_nights"] = 1

        result = self.comparator.compare_results(current_data, different_previous)
        assert result is True

    def test_edge_case_empty_results(self):
        """Test comparison with empty or minimal results"""
        empty_current = {}
        empty_previous = {}

        result = self.comparator.compare_results(empty_current, empty_previous)
        assert result is False  # Empty results should be considered identical

        # Test empty current with non-empty previous
        result = self.comparator.compare_results(empty_current, self.sample_previous_results)
        assert result is True

    def test_edge_case_large_nested_structures(self):
        """Test with large, deeply nested data structures"""
        large_data = {
            "level1": {
                f"item_{i}": {
                    "level2": {
                        f"subitem_{j}": f"value_{i}_{j}"
                        for j in range(10)
                    }
                }
                for i in range(10)
            }
        }

        # Should handle large structures without issues
        normalized = self.comparator.normalize_results(large_data)
        assert isinstance(normalized, dict)

        hash_result = self.comparator._generate_hash(normalized)
        assert len(hash_result) == 64

        # Comparison should work
        result = self.comparator.compare_results(large_data, large_data.copy())
        assert result is False  # Should be identical
