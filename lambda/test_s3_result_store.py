import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError, NoCredentialsError, BotoCoreError
from s3_result_store import S3ResultStore


class TestS3ResultStore:
    """Test suite for S3ResultStore class"""

    def setup_method(self):
        """Set up test fixtures"""
        self.bucket_name = "test-cache-bucket"
        self.mock_s3_client = Mock()
        self.store = S3ResultStore(self.bucket_name, self.mock_s3_client)
        self.sample_results = {
            "available_sites": [
                {"site_id": "123", "site_name": "Site A", "dates": ["2025-01-15"]}
            ],
            "total_available_nights": 1
        }
        self.campground_id = "766"

    def test_generate_key(self):
        """Test S3 key generation"""
        key = self.store.generate_key(self.campground_id)
        expected_key = f"search-results/{self.campground_id}/latest.json"
        assert key == expected_key

    def test_store_results_success(self):
        """Test successful result storage"""
        self.mock_s3_client.put_object.return_value = {}

        result = self.store.store_results(self.campground_id, self.sample_results)

        assert result is True
        self.mock_s3_client.put_object.assert_called_once()

        # Verify the call arguments
        call_args = self.mock_s3_client.put_object.call_args
        assert call_args[1]['Bucket'] == self.bucket_name
        assert call_args[1]['Key'] == f"search-results/{self.campground_id}/latest.json"
        assert call_args[1]['ContentType'] == 'application/json'

        # Verify the stored data structure
        stored_data = json.loads(call_args[1]['Body'])
        assert stored_data['campground_id'] == self.campground_id
        assert 'timestamp' in stored_data
        assert stored_data['results'] == self.sample_results
        assert 'result_hash' in stored_data

    def test_store_results_client_error(self):
        """Test storage failure due to S3 client error"""
        self.mock_s3_client.put_object.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
            'PutObject'
        )

        result = self.store.store_results(self.campground_id, self.sample_results)

        assert result is False

    def test_store_results_no_credentials_error(self):
        """Test storage failure due to missing credentials"""
        self.mock_s3_client.put_object.side_effect = NoCredentialsError()

        result = self.store.store_results(self.campground_id, self.sample_results)

        assert result is False

    def test_store_results_json_error(self):
        """Test storage failure due to JSON serialization error"""
        # Create non-serializable data
        non_serializable_results = {"func": lambda x: x}

        result = self.store.store_results(self.campground_id, non_serializable_results)

        assert result is False

    def test_retrieve_results_success(self):
        """Test successful result retrieval"""
        stored_data = {
            "campground_id": self.campground_id,
            "timestamp": "2025-01-08T10:30:00Z",
            "results": self.sample_results,
            "result_hash": "test_hash"
        }

        mock_response = {
            'Body': Mock()
        }
        mock_response['Body'].read.return_value = json.dumps(stored_data).encode('utf-8')
        self.mock_s3_client.get_object.return_value = mock_response

        result = self.store.retrieve_results(self.campground_id)

        assert result == stored_data
        self.mock_s3_client.get_object.assert_called_once_with(
            Bucket=self.bucket_name,
            Key=f"search-results/{self.campground_id}/latest.json"
        )

    def test_retrieve_results_no_such_key(self):
        """Test retrieval when no previous results exist"""
        self.mock_s3_client.get_object.side_effect = ClientError(
            {'Error': {'Code': 'NoSuchKey', 'Message': 'Key not found'}},
            'GetObject'
        )

        result = self.store.retrieve_results(self.campground_id)

        assert result is None

    def test_retrieve_results_client_error(self):
        """Test retrieval failure due to S3 client error"""
        self.mock_s3_client.get_object.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
            'GetObject'
        )

        result = self.store.retrieve_results(self.campground_id)

        assert result is None

    def test_retrieve_results_json_decode_error(self):
        """Test retrieval failure due to malformed JSON"""
        mock_response = {
            'Body': Mock()
        }
        mock_response['Body'].read.return_value = b"invalid json"
        self.mock_s3_client.get_object.return_value = mock_response

        result = self.store.retrieve_results(self.campground_id)

        assert result is None

    def test_generate_result_hash(self):
        """Test result hash generation"""
        hash1 = self.store._generate_result_hash(self.sample_results)
        hash2 = self.store._generate_result_hash(self.sample_results)

        # Same input should produce same hash
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 produces 64-character hex string

        # Different input should produce different hash
        different_results = {"different": "data"}
        hash3 = self.store._generate_result_hash(different_results)
        assert hash1 != hash3

    def test_generate_result_hash_with_error(self):
        """Test result hash generation with error handling"""
        # Mock json.dumps to raise an exception
        with patch('s3_result_store.json.dumps', side_effect=TypeError("Mock error")):
            hash_result = self.store._generate_result_hash(self.sample_results)

            # Should still return a hash (fallback behavior)
            assert len(hash_result) == 64

    def test_has_results_changed_no_previous_results(self):
        """Test comparison when no previous results exist"""
        self.mock_s3_client.get_object.side_effect = ClientError(
            {'Error': {'Code': 'NoSuchKey', 'Message': 'Key not found'}},
            'GetObject'
        )

        result = self.store.has_results_changed(self.campground_id, self.sample_results)

        assert result is True

    def test_has_results_changed_results_identical(self):
        """Test comparison when results are identical"""
        # Mock retrieve_results to return data with same hash
        current_hash = self.store._generate_result_hash(self.sample_results)
        stored_data = {
            "campground_id": self.campground_id,
            "timestamp": "2025-01-08T10:30:00Z",
            "results": self.sample_results,
            "result_hash": current_hash
        }

        mock_response = {
            'Body': Mock()
        }
        mock_response['Body'].read.return_value = json.dumps(stored_data).encode('utf-8')
        self.mock_s3_client.get_object.return_value = mock_response

        result = self.store.has_results_changed(self.campground_id, self.sample_results)

        assert result is False

    def test_has_results_changed_results_different(self):
        """Test comparison when results are different"""
        # Mock retrieve_results to return data with different hash
        stored_data = {
            "campground_id": self.campground_id,
            "timestamp": "2025-01-08T10:30:00Z",
            "results": {"different": "results"},
            "result_hash": "different_hash"
        }

        mock_response = {
            'Body': Mock()
        }
        mock_response['Body'].read.return_value = json.dumps(stored_data).encode('utf-8')
        self.mock_s3_client.get_object.return_value = mock_response

        result = self.store.has_results_changed(self.campground_id, self.sample_results)

        assert result is True

    def test_has_results_changed_comparison_error(self):
        """Test comparison with error handling (fail-safe approach)"""
        # Mock retrieve_results to raise an exception
        with patch.object(self.store, 'retrieve_results', side_effect=Exception("Mock error")):
            result = self.store.has_results_changed(self.campground_id, self.sample_results)

            # Should default to True (fail-safe approach)
            assert result is True

    def test_initialization_with_default_client(self):
        """Test initialization with default boto3 client"""
        with patch('s3_result_store.boto3.client') as mock_boto3_client:
            mock_client = Mock()
            mock_boto3_client.return_value = mock_client

            store = S3ResultStore("test-bucket")

            assert store.bucket_name == "test-bucket"
            assert store.s3_client == mock_client
            mock_boto3_client.assert_called_once_with('s3')

    def test_hash_consistency_with_key_order(self):
        """Test that hash is consistent regardless of dictionary key order"""
        results1 = {"a": 1, "b": 2, "c": 3}
        results2 = {"c": 3, "a": 1, "b": 2}

        hash1 = self.store._generate_result_hash(results1)
        hash2 = self.store._generate_result_hash(results2)

        assert hash1 == hash2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
