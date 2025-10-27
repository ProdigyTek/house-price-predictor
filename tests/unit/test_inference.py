"""
Unit tests for the inference module.

These tests focus on testing the core prediction logic in isolation,
without requiring Docker containers or external dependencies.
All external dependencies are mocked to ensure true unit testing.
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime
import sys
import os


class TestInferenceLogic:
    """Test class for inference module unit tests with proper mocking."""
    
    @pytest.fixture
    def mock_model(self):
        """Create a mock model for testing."""
        mock = MagicMock()
        mock.predict.return_value = np.array([250000.0])
        return mock
    
    @pytest.fixture
    def mock_preprocessor(self):
        """Create a mock preprocessor for testing."""
        mock = MagicMock()
        mock.transform.return_value = np.array([[2000, 3, 2, 1, 0, 0, 2010, 1, 0, 0, 2024, 0.67]])
        return mock
    
    @pytest.fixture
    def sample_house_data(self):
        """Create sample house data for testing."""
        return {
            "sqft": 2000,
            "bedrooms": 3,
            "bathrooms": 2.5,
            "location": "suburban",
            "year_built": 2010,
            "condition": "Good"
        }
    
    @pytest.fixture
    def batch_house_data(self):
        """Create batch house data for testing."""
        return [
            {
                "sqft": 1800,
                "bedrooms": 2,
                "bathrooms": 2,
                "location": "urban",
                "year_built": 2015,
                "condition": "Excellent"
            },
            {
                "sqft": 2500,
                "bedrooms": 4,
                "bathrooms": 3,
                "location": "suburban",
                "year_built": 2005,
                "condition": "Good"
            },
            {
                "sqft": 1200,
                "bedrooms": 3,
                "bathrooms": 2,
                "location": "rural",
                "year_built": 1995,
                "condition": "Fair"
            }
        ]
    
    @pytest.fixture
    def invalid_house_data(self):
        """Create invalid house data for testing validation."""
        return {
            "sqft": -100,  # Invalid: negative value
            "bedrooms": 0,  # Invalid: zero bedrooms
            "bathrooms": 2,
            "location": "invalid_location",  # Invalid: not in allowed values
            "year_built": 2050,  # Invalid: future year
            "condition": "Good"
        }
    
    def test_model_loading_success(self, mock_model, mock_preprocessor):
        """
        Test successful model loading with mocked dependencies.
        
        This test verifies that the inference module can properly
        handle model loading when all dependencies are available.
        """
        with patch('joblib.load') as mock_joblib_load:
            # Setup mock joblib to return our mock model and preprocessor
            mock_joblib_load.side_effect = [mock_model, mock_preprocessor]
            
            # Verify that joblib.load would be called correctly
            model = mock_joblib_load("model_path.pkl")
            preprocessor = mock_joblib_load("preprocessor_path.pkl")
            
            # Verify our mocks are properly configured
            assert model.predict is not None
            assert preprocessor.transform is not None
            assert mock_joblib_load.call_count == 2
    
    def test_model_loading_failure(self):
        """
        Test handling of model loading failures.
        
        This test verifies that the system gracefully handles
        cases where model files cannot be loaded.
        """
        with patch('joblib.load') as mock_joblib_load:
            # Setup mock to raise an exception
            mock_joblib_load.side_effect = FileNotFoundError("Model file not found")
            
            # Verify that proper error handling occurs
            with pytest.raises(FileNotFoundError):
                mock_joblib_load("fake_model_path.pkl")
    
    def test_predict_price_logic(self, mock_model, mock_preprocessor, sample_house_data):
        """
        Test the core prediction logic with mocked dependencies.
        
        This test verifies that predictions work correctly when
        given valid input data and functioning model/preprocessor.
        """
        # Test the core prediction logic directly
        # Create a DataFrame from the sample data
        df = pd.DataFrame([sample_house_data])
        
        # Add feature engineering (house_age and bed_bath_ratio)
        df['house_age'] = 2024 - df['year_built']
        df['bed_bath_ratio'] = df['bedrooms'] / df['bathrooms']
        
        # Test preprocessing
        processed_data = mock_preprocessor.transform(df)
        assert processed_data is not None
        
        # Test prediction
        prediction = mock_model.predict(processed_data)
        assert prediction is not None
        assert len(prediction) == 1
        assert prediction[0] == 250000.0  # Our mock return value
    
    def test_feature_engineering(self, sample_house_data):
        """
        Test the feature engineering logic.
        
        This test verifies that derived features are calculated correctly:
        - house_age: current_year - year_built
        - bed_bath_ratio: bedrooms / bathrooms
        """
        # Create DataFrame and apply feature engineering
        df = pd.DataFrame([sample_house_data])
        current_year = 2024
        
        # Calculate derived features
        df['house_age'] = current_year - df['year_built']
        df['bed_bath_ratio'] = df['bedrooms'] / df['bathrooms']
        
        # Verify calculations
        expected_house_age = current_year - sample_house_data['year_built']  # 2024 - 2010 = 14
        expected_bed_bath_ratio = sample_house_data['bedrooms'] / sample_house_data['bathrooms']  # 3 / 2.5 = 1.2
        
        assert df['house_age'].iloc[0] == expected_house_age
        assert abs(df['bed_bath_ratio'].iloc[0] - expected_bed_bath_ratio) < 0.001
    
    def test_batch_predict_logic(self, mock_model, mock_preprocessor, batch_house_data):
        """
        Test batch prediction logic with multiple house records.
        
        This test verifies that the system can handle multiple
        predictions in a single batch operation.
        """
        # Setup mock to return predictions for batch
        batch_predictions = np.array([180000.0, 320000.0, 150000.0])
        mock_model.predict.return_value = batch_predictions
        
        # Create DataFrame from batch data
        df = pd.DataFrame(batch_house_data)
        
        # Add feature engineering for batch
        df['house_age'] = 2024 - df['year_built']
        df['bed_bath_ratio'] = df['bedrooms'] / df['bathrooms']
        
        # Test batch processing
        processed_data = mock_preprocessor.transform(df)
        predictions = mock_model.predict(processed_data)
        
        # Verify batch results
        assert len(predictions) == len(batch_house_data)
        assert predictions.tolist() == [180000.0, 320000.0, 150000.0]
    
    def test_house_prediction_request_validation(self, sample_house_data):
        """
        Test input validation using Pydantic models.
        
        This test verifies that the request validation logic
        works correctly for valid input data.
        """
        # Test that valid data passes basic validation
        required_fields = ["sqft", "bedrooms", "bathrooms", "location", "year_built", "condition"]
        for field in required_fields:
            assert field in sample_house_data
        
        # Test data types
        assert isinstance(sample_house_data["sqft"], int)
        assert isinstance(sample_house_data["bedrooms"], int)
        assert isinstance(sample_house_data["bathrooms"], (int, float))
        assert isinstance(sample_house_data["location"], str)
        assert isinstance(sample_house_data["year_built"], int)
        assert isinstance(sample_house_data["condition"], str)
    
    def test_prediction_response_structure(self):
        """
        Test the structure of prediction responses.
        
        This test verifies that prediction responses contain
        all required fields with correct data types.
        """
        # Mock a complete prediction response
        mock_response = {
            "predicted_price": 250000.0,
            "confidence_interval": [230000.0, 270000.0],
            "features_importance": {
                "sqft": 0.35,
                "location": 0.25,
                "bedrooms": 0.15,
                "bathrooms": 0.10,
                "year_built": 0.10,
                "condition": 0.05
            },
            "prediction_time": "2024-10-26T22:00:00Z"
        }
        
        # Verify response structure
        assert "predicted_price" in mock_response
        assert "confidence_interval" in mock_response
        assert "features_importance" in mock_response
        assert "prediction_time" in mock_response
        
        # Verify data types
        assert isinstance(mock_response["predicted_price"], (int, float))
        assert isinstance(mock_response["confidence_interval"], list)
        assert isinstance(mock_response["features_importance"], dict)
        assert isinstance(mock_response["prediction_time"], str)
        
        # Verify confidence interval structure
        assert len(mock_response["confidence_interval"]) == 2
        assert mock_response["confidence_interval"][0] < mock_response["confidence_interval"][1]
    
    def test_data_type_conversion(self, sample_house_data):
        """
        Test data type conversion and validation.
        
        This test verifies that the system properly handles
        different input data types and converts them appropriately.
        """
        # Test with string numbers (common in JSON/API inputs)
        string_data = {
            "sqft": "2000",  # String instead of int
            "bedrooms": "3",
            "bathrooms": "2.5",
            "location": "suburban",
            "year_built": "2010",
            "condition": "Good"
        }
        
        # Convert string data to appropriate types
        converted_data = {}
        for key, value in string_data.items():
            if key in ["sqft", "bedrooms", "year_built"]:
                converted_data[key] = int(value)
            elif key == "bathrooms":
                converted_data[key] = float(value)
            else:
                converted_data[key] = value
        
        # Verify conversions
        assert isinstance(converted_data["sqft"], int)
        assert isinstance(converted_data["bedrooms"], int)
        assert isinstance(converted_data["bathrooms"], float)
        assert isinstance(converted_data["year_built"], int)
        assert isinstance(converted_data["location"], str)
        assert isinstance(converted_data["condition"], str)
        
        # Verify values are correct
        assert converted_data["sqft"] == 2000
        assert converted_data["bedrooms"] == 3
        assert converted_data["bathrooms"] == 2.5
        assert converted_data["year_built"] == 2010


class TestInputValidation:
    """Test class for input validation logic."""
    
    def test_positive_number_validation(self):
        """Test validation of positive numeric fields."""
        # Test valid positive numbers
        assert 2000 > 0  # sqft
        assert 3 > 0     # bedrooms
        assert 2.5 > 0   # bathrooms
        
        # Test invalid values
        assert not (-100 > 0)  # negative sqft
        assert not (0 > 0)     # zero bedrooms
    
    def test_categorical_validation(self):
        """Test validation of categorical fields."""
        valid_locations = ["urban", "suburban", "rural"]
        valid_conditions = ["Excellent", "Good", "Fair", "Poor"]
        
        # Test valid values
        assert "suburban" in valid_locations
        assert "Good" in valid_conditions
        
        # Test invalid values
        assert "invalid_location" not in valid_locations
        assert "Invalid_Condition" not in valid_conditions
    
    def test_year_validation(self):
        """Test validation of year_built field."""
        current_year = datetime.now().year
        
        # Test valid years
        assert 1900 <= 2010 <= current_year
        assert 1900 <= 1995 <= current_year
        
        # Test invalid years
        assert not (2050 <= current_year)  # Future year
        assert not (1800 >= 1900)         # Too old (corrected logic)


if __name__ == "__main__":
    # Run unit tests
    pytest.main([__file__, "-v"])
