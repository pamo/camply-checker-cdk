import pytest
from result_comparator import ResultComparator


class TestResultComparatorIntegration:
    """Integration tests demonstrating ResultComparator meets requirements"""

    def setup_method(self):
        """Set up test fixtures"""
        self.comparator = ResultComparator()

    def test_requirement_1_1_compare_current_with_previous(self):
        """
        Requirement 1.1: WHEN the system performs a campsite search
        THEN it SHALL compare the current results with the previous search results
        """
        current_results = {
            "campground_id": "766",
            "available_sites": [{"site_id": "123", "dates": ["2025-01-15"]}],
            "total_available_nights": 1
        }

        previous_results = {
            "campground_id": "766",
            "available_sites": [{"site_id": "124", "dates": ["2025-01-16"]}],
            "total_available_nights": 1
        }

        # Should perform comparison and detect difference
        result = self.comparator.compare_results(current_results, previous_results)
        assert result is True  # Results are different

        # Should also work with identical results
        identical_previous = current_results.copy()
        result = self.comparator.compare_results(current_results, identical_previous)
        assert result is False  # Results are identical

    def test_requirement_1_2_identical_results_no_notification(self):
        """
        Requirement 1.2: WHEN the current search results are identical to the previous results
        THEN the system SHALL NOT send any email notifications
        """
        current_results = {
            "campground_id": "766",
            "available_sites": [
                {"site_id": "123", "site_name": "Site A", "dates": ["2025-01-15", "2025-01-16"]}
            ],
            "total_available_nights": 2,
            "timestamp": "2025-01-08T10:30:00Z"  # This should be ignored
        }

        previous_results = current_results.copy()
        previous_results["timestamp"] = "2025-01-07T09:15:00Z"  # Different timestamp

        # Should return False (no notification needed) because results are identical
        # except for timestamp which should be ignored
        result = self.comparator.compare_results(current_results, previous_results)
        assert result is False

    def test_requirement_1_3_different_results_send_notification(self):
        """
        Requirement 1.3: WHEN the current search results differ from the previous results
        THEN the system SHALL send email notifications and update the stored results
        """
        current_results = {
            "campground_id": "766",
            "available_sites": [
                {"site_id": "123", "dates": ["2025-01-15", "2025-01-16"]},
                {"site_id": "124", "dates": ["2025-01-17"]}  # New site available
            ],
            "total_available_nights": 3
        }

        previous_results = {
            "campground_id": "766",
            "available_sites": [
                {"site_id": "123", "dates": ["2025-01-15", "2025-01-16"]}
            ],
            "total_available_nights": 2
        }

        # Should return True (notification needed) because results differ
        result = self.comparator.compare_results(current_results, previous_results)
        assert result is True

    def test_requirement_1_4_no_previous_results_send_notification(self):
        """
        Requirement 1.4: WHEN no previous search results exist
        THEN the system SHALL send notifications for any available campsites found
        """
        current_results = {
            "campground_id": "766",
            "available_sites": [{"site_id": "123", "dates": ["2025-01-15"]}],
            "total_available_nights": 1
        }

        # Should return True (notification needed) when no previous results
        result = self.comparator.compare_results(current_results, None)
        assert result is True

    def test_requirement_1_5_corrupted_previous_results_send_notification(self):
        """
        Requirement 1.5: IF the offline search file cannot be read or is corrupted
        THEN the system SHALL treat it as if no previous results exist and send notifications
        """
        current_results = {
            "campground_id": "766",
            "available_sites": [{"site_id": "123", "dates": ["2025-01-15"]}],
            "total_available_nights": 1
        }

        # Test with various forms of corrupted/malformed previous results
        corrupted_cases = [
            "invalid_string",  # Not a dictionary
            123,  # Wrong type
            [],  # Wrong type (list instead of dict)
            {"malformed": object()},  # Contains non-serializable data
        ]

        for corrupted_previous in corrupted_cases:
            result = self.comparator.compare_results(current_results, corrupted_previous)
            assert result is True  # Should treat as changed/send notification

    def test_normalization_handles_edge_cases(self):
        """Test that normalization properly handles various edge cases"""
        # Test case-insensitive comparison
        current = {"CampgroundName": "STEEP RAVINE", "sites": [{"name": "SITE A"}]}
        previous = {"campgroundname": "steep ravine", "sites": [{"name": "site a"}]}

        result = self.comparator.compare_results(current, previous)
        assert result is False  # Should be considered identical after normalization

        # Test with different key ordering
        current = {"a": 1, "b": 2, "c": 3}
        previous = {"c": 3, "a": 1, "b": 2}

        result = self.comparator.compare_results(current, previous)
        assert result is False  # Should be considered identical

        # Test with sorted lists
        current = {"dates": ["2025-01-17", "2025-01-15", "2025-01-16"]}
        previous = {"dates": ["2025-01-15", "2025-01-16", "2025-01-17"]}

        result = self.comparator.compare_results(current, previous)
        assert result is False  # Should be considered identical after sorting

    def test_hash_based_comparison_efficiency(self):
        """Test that hash-based comparison works efficiently"""
        # Create large, complex data structures
        large_current = {
            "campground_id": "766",
            "sites": [
                {
                    "site_id": f"site_{i}",
                    "dates": [f"2025-01-{15+j}" for j in range(5)],
                    "amenities": ["water", "electric", "sewer"]
                }
                for i in range(100)
            ]
        }

        import copy
        large_previous = copy.deepcopy(large_current)

        # Should efficiently determine they're identical using hashes
        result = self.comparator.compare_results(large_current, large_previous)
        assert result is False

        # Make a small change and verify it's detected
        large_previous["sites"][0]["site_id"] = "modified_site"
        result = self.comparator.compare_results(large_current, large_previous)
        assert result is True

    def test_comparison_summary_provides_debugging_info(self):
        """Test that comparison summary provides useful debugging information"""
        current = {"campground_id": "766", "sites": 5}
        previous = {"campground_id": "766", "sites": 3}

        summary = self.comparator.get_comparison_summary(current, previous)

        assert summary["has_previous_results"] is True
        assert summary["results_changed"] is True
        assert "current_hash" in summary
        assert "previous_hash" in summary
        assert summary["current_hash"] != summary["previous_hash"]
        assert isinstance(summary["normalization_errors"], list)
