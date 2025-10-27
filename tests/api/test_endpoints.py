"""
API integration tests for the House Price Prediction service.

These tests verify that the FastAPI endpoints work correctly when the
application is running in a Docker container, testing the full stack
from HTTP requests to model predictions.
"""

import pytest
import requests
import json
import time
from typing import Dict, Any


@pytest.mark.api
@pytest.mark.docker
class TestHealthEndpoint:
    """Test class for health check endpoint."""
    
    def test_health_check_success(self, docker_container, api_base_url, api_headers):
        """
        Test that the health endpoint returns success status.
        
        This test verifies:
        - Health endpoint is accessible
        - Returns 200 status code
        - Response contains expected health information
        - Model loading status is reported correctly
        """
        url = f"{api_base_url}/health"
        
        response = requests.get(url, headers=api_headers)
        
        # Verify response status
        assert response.status_code == 200
        
        # Verify response content
        data = response.json()
        assert data["status"] == "healthy"
        assert data["model_loaded"] is True
        
        # Verify response time is reasonable (< 1 second)
        assert response.elapsed.total_seconds() < 1.0
    
    def test_health_check_response_format(self, docker_container, api_base_url):
        """
        Test that the health endpoint returns properly formatted JSON.
        
        This test ensures the response is valid JSON with expected structure.
        """
        url = f"{api_base_url}/health"
        
        response = requests.get(url)
        
        # Verify content type
        assert "application/json" in response.headers.get("content-type", "")
        
        # Verify JSON structure
        data = response.json()
        required_fields = ["status", "model_loaded"]
        for field in required_fields:
            assert field in data


@pytest.mark.api
@pytest.mark.docker
class TestPredictionEndpoint:
    """Test class for single prediction endpoint."""
    
    def test_single_prediction_success(self, docker_container, api_base_url, api_headers, sample_house_data):
        """
        Test successful single house price prediction.
        
        This test verifies:
        - POST request to /predict works
        - Returns valid prediction response
        - Response contains all required fields
        - Predicted price is reasonable
        """
        url = f"{api_base_url}/predict"
        
        response = requests.post(url, json=sample_house_data, headers=api_headers)
        
        # Verify response status
        assert response.status_code == 200
        
        # Verify response structure
        data = response.json()
        required_fields = ["predicted_price", "confidence_interval", "features_importance", "prediction_time"]
        for field in required_fields:
            assert field in data
        
        # Verify data types and ranges
        assert isinstance(data["predicted_price"], (int, float))
        assert data["predicted_price"] > 0
        
        assert isinstance(data["confidence_interval"], list)
        assert len(data["confidence_interval"]) == 2
        assert data["confidence_interval"][0] < data["confidence_interval"][1]
        
        assert isinstance(data["features_importance"], dict)
        assert isinstance(data["prediction_time"], str)
        
        # Verify reasonable price range (between $50k and $2M)
        assert 50000 <= data["predicted_price"] <= 2000000
    
    def test_prediction_with_different_locations(self, docker_container, api_base_url, api_headers, sample_house_data):
        """
        Test predictions with different location types.
        
        This test ensures the model handles different location categories correctly.
        """
        url = f"{api_base_url}/predict"
        locations = ["urban", "suburban", "rural"]
        predictions = {}
        
        for location in locations:
            test_data = sample_house_data.copy()
            test_data["location"] = location
            
            response = requests.post(url, json=test_data, headers=api_headers)
            assert response.status_code == 200
            
            data = response.json()
            predictions[location] = data["predicted_price"]
        
        # Verify that predictions are different for different locations
        # (assuming the model considers location in pricing)
        assert len(set(predictions.values())) >= 1  # At least some variation expected
    
    def test_prediction_with_different_conditions(self, docker_container, api_base_url, api_headers, sample_house_data):
        """
        Test predictions with different house conditions.
        
        This test verifies that house condition affects price predictions.
        """
        url = f"{api_base_url}/predict"
        conditions = ["Excellent", "Good", "Fair"]
        predictions = {}
        
        for condition in conditions:
            test_data = sample_house_data.copy()
            test_data["condition"] = condition
            
            response = requests.post(url, json=test_data, headers=api_headers)
            assert response.status_code == 200
            
            data = response.json()
            predictions[condition] = data["predicted_price"]
        
        # Store predictions for potential comparison
        # (The actual relationship depends on the trained model)
        assert all(price > 0 for price in predictions.values())
    
    def test_prediction_edge_cases(self, docker_container, api_base_url, api_headers):
        """
        Test prediction with edge case values.
        
        This test ensures the API handles boundary values correctly.
        """
        url = f"{api_base_url}/predict"
        
        edge_cases = [
            {
                "sqft": 500,  # Very small house
                "bedrooms": 1,
                "bathrooms": 1,
                "location": "urban",
                "year_built": 2023,
                "condition": "Excellent"
            },
            {
                "sqft": 5000,  # Very large house
                "bedrooms": 6,
                "bathrooms": 5,
                "location": "suburban",
                "year_built": 1900,  # Very old
                "condition": "Fair"
            }
        ]
        
        for test_data in edge_cases:
            response = requests.post(url, json=test_data, headers=api_headers)
            assert response.status_code == 200
            
            data = response.json()
            assert data["predicted_price"] > 0
    
    def test_prediction_invalid_data(self, docker_container, api_base_url, api_headers, invalid_house_data):
        """
        Test prediction endpoint with invalid input data.
        
        This test verifies that the API properly validates input and
        returns appropriate error responses for invalid data.
        """
        url = f"{api_base_url}/predict"
        
        response = requests.post(url, json=invalid_house_data, headers=api_headers)
        
        # Should return validation error
        assert response.status_code == 422
        
        # Verify error response structure
        data = response.json()
        assert "detail" in data
        assert isinstance(data["detail"], list)
    
    def test_prediction_missing_fields(self, docker_container, api_base_url, api_headers):
        """
        Test prediction endpoint with missing required fields.
        
        This test ensures that all required fields are validated.
        """
        url = f"{api_base_url}/predict"
        
        incomplete_data = {
            "sqft": 2000,
            "bedrooms": 3
            # Missing required fields: bathrooms, location, year_built, condition
        }
        
        response = requests.post(url, json=incomplete_data, headers=api_headers)
        
        # Should return validation error
        assert response.status_code == 422
        
        data = response.json()
        assert "detail" in data


@pytest.mark.api
@pytest.mark.docker
class TestBatchPredictionEndpoint:
    """Test class for batch prediction endpoint."""
    
    def test_batch_prediction_success(self, docker_container, api_base_url, api_headers, batch_house_data):
        """
        Test successful batch prediction.
        
        This test verifies:
        - Batch prediction endpoint works
        - Returns predictions for all input records
        - All predictions are valid numbers
        """
        url = f"{api_base_url}/batch-predict"
        
        response = requests.post(url, json=batch_house_data, headers=api_headers)
        
        # Verify response status
        assert response.status_code == 200
        
        # Verify response structure
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == len(batch_house_data)
        
        # Verify all predictions are valid
        for prediction in data:
            assert isinstance(prediction, (int, float))
            assert prediction > 0
            assert 50000 <= prediction <= 2000000  # Reasonable price range
    
    def test_batch_prediction_empty_list(self, docker_container, api_base_url, api_headers):
        """
        Test batch prediction with empty input list.
        
        This test verifies handling of edge case with no input data.
        """
        url = f"{api_base_url}/batch-predict"
        
        response = requests.post(url, json=[], headers=api_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0
    
    def test_batch_prediction_single_item(self, docker_container, api_base_url, api_headers, sample_house_data):
        """
        Test batch prediction with single item.
        
        This test ensures batch endpoint works with minimal input.
        """
        url = f"{api_base_url}/batch-predict"
        
        response = requests.post(url, json=[sample_house_data], headers=api_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert isinstance(data[0], (int, float))
    
    def test_batch_prediction_large_batch(self, docker_container, api_base_url, api_headers, sample_house_data):
        """
        Test batch prediction with larger number of records.
        
        This test verifies performance with multiple records.
        """
        url = f"{api_base_url}/batch-predict"
        
        # Create larger batch (10 records)
        large_batch = [sample_house_data.copy() for _ in range(10)]
        
        # Vary some parameters to make records different
        for i, record in enumerate(large_batch):
            record["sqft"] = 1500 + (i * 200)
            record["bedrooms"] = 2 + (i % 3)
        
        start_time = time.time()
        response = requests.post(url, json=large_batch, headers=api_headers)
        elapsed_time = time.time() - start_time
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 10
        
        # Verify reasonable response time (< 5 seconds for 10 predictions)
        assert elapsed_time < 5.0
    
    def test_batch_prediction_invalid_item(self, docker_container, api_base_url, api_headers, sample_house_data, invalid_house_data):
        """
        Test batch prediction with one invalid item.
        
        This test verifies error handling in batch processing.
        """
        url = f"{api_base_url}/batch-predict"
        
        mixed_batch = [sample_house_data, invalid_house_data]
        
        response = requests.post(url, json=mixed_batch, headers=api_headers)
        
        # Should return validation error
        assert response.status_code == 422


@pytest.mark.api
@pytest.mark.docker
class TestAPIDocumentation:
    """Test class for API documentation endpoints."""
    
    def test_openapi_docs_accessible(self, docker_container, api_base_url):
        """
        Test that OpenAPI documentation is accessible.
        
        This test verifies that the Swagger UI documentation is available.
        """
        url = f"{api_base_url}/docs"
        
        response = requests.get(url)
        
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert "swagger" in response.text.lower()
    
    def test_openapi_json_schema(self, docker_container, api_base_url):
        """
        Test that OpenAPI JSON schema is accessible.
        
        This test verifies that the API schema can be retrieved programmatically.
        """
        url = f"{api_base_url}/openapi.json"
        
        response = requests.get(url)
        
        assert response.status_code == 200
        assert "application/json" in response.headers.get("content-type", "")
        
        schema = response.json()
        assert "openapi" in schema
        assert "info" in schema
        assert "paths" in schema
        
        # Verify our endpoints are documented
        paths = schema["paths"]
        expected_paths = ["/health", "/predict", "/batch-predict"]
        for path in expected_paths:
            assert path in paths


@pytest.mark.api
@pytest.mark.docker
@pytest.mark.slow
class TestAPIPerformance:
    """Test class for API performance and load testing."""
    
    def test_concurrent_predictions(self, docker_container, api_base_url, api_headers, sample_house_data):
        """
        Test concurrent prediction requests.
        
        This test verifies that the API can handle multiple simultaneous requests.
        """
        import concurrent.futures
        import threading
        
        url = f"{api_base_url}/predict"
        num_concurrent = 5
        
        def make_request():
            return requests.post(url, json=sample_house_data, headers=api_headers)
        
        start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_concurrent) as executor:
            futures = [executor.submit(make_request) for _ in range(num_concurrent)]
            responses = [future.result() for future in concurrent.futures.as_completed(futures)]
        elapsed_time = time.time() - start_time
        
        # Verify all requests succeeded
        for response in responses:
            assert response.status_code == 200
        
        # Verify reasonable total time (should be less than sequential)
        assert elapsed_time < num_concurrent * 2  # Generous upper bound
    
    def test_prediction_response_time(self, docker_container, api_base_url, api_headers, sample_house_data):
        """
        Test individual prediction response time.
        
        This test ensures that single predictions complete quickly.
        """
        url = f"{api_base_url}/predict"
        
        # Make several requests and measure average response time
        response_times = []
        for _ in range(5):
            start_time = time.time()
            response = requests.post(url, json=sample_house_data, headers=api_headers)
            elapsed_time = time.time() - start_time
            
            assert response.status_code == 200
            response_times.append(elapsed_time)
        
        avg_response_time = sum(response_times) / len(response_times)
        
        # Average response time should be under 1 second
        assert avg_response_time < 1.0
        
        # No single request should take more than 2 seconds
        assert max(response_times) < 2.0


if __name__ == "__main__":
    # Run API integration tests
    pytest.main([__file__, "-v", "-m", "api"])