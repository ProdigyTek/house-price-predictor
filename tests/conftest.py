"""
Test configuration and shared fixtures for the House Price Predictor API tests.

This module provides pytest fixtures and configurations used across all test modules.
It includes Docker container management, test data generation, and API client setup.
"""

import pytest
import docker
import time
import requests
import subprocess
import json
from typing import Dict, Any, Generator
from pathlib import Path


# Test Data Fixtures
@pytest.fixture
def sample_house_data() -> Dict[str, Any]:
    """
    Provides sample house data for testing single predictions.
    
    Returns:
        Dict containing valid house features for API testing
    """
    return {
        "sqft": 2000,
        "bedrooms": 3,
        "bathrooms": 2.5,
        "location": "suburban",
        "year_built": 2010,
        "condition": "Good"
    }


@pytest.fixture
def batch_house_data() -> list[Dict[str, Any]]:
    """
    Provides multiple house records for batch prediction testing.
    
    Returns:
        List of house feature dictionaries for batch testing
    """
    return [
        {
            "sqft": 1500,
            "bedrooms": 2,
            "bathrooms": 2,
            "location": "urban",
            "year_built": 2015,
            "condition": "Excellent"
        },
        {
            "sqft": 3000,
            "bedrooms": 4,
            "bathrooms": 3,
            "location": "suburban",
            "year_built": 2005,
            "condition": "Good"
        },
        {
            "sqft": 2500,
            "bedrooms": 3,
            "bathrooms": 2,
            "location": "rural",
            "year_built": 2020,
            "condition": "Excellent"
        }
    ]


@pytest.fixture
def invalid_house_data() -> Dict[str, Any]:
    """
    Provides invalid house data for error testing.
    
    Returns:
        Dict containing invalid house features that should trigger validation errors
    """
    return {
        "sqft": -100,  # Negative square footage (invalid)
        "bedrooms": 0,  # Zero bedrooms (invalid)
        "bathrooms": -1,  # Negative bathrooms (invalid)
        "location": "",  # Empty location (invalid)
        "year_built": 1700,  # Too old (invalid)
        "condition": "Unknown"  # Unknown condition
    }


# Docker Container Management Fixtures
@pytest.fixture(scope="session")
def docker_client():
    """
    Provides Docker client for container management.
    
    Returns:
        Docker client instance for managing containers during tests
    """
    try:
        client = docker.from_env()
        # Test if Docker is running
        client.ping()
        return client
    except Exception as e:
        pytest.skip(f"Docker not available: {e}")


@pytest.fixture(scope="session")
def docker_image(docker_client):
    """
    Builds the Docker image for testing if it doesn't exist.
    
    Args:
        docker_client: Docker client fixture
        
    Returns:
        Docker image object for the house price predictor
    """
    image_name = "housepricepredictor:test"
    project_root = Path(__file__).parent.parent
    
    try:
        # Try to get existing image
        image = docker_client.images.get(image_name)
        print(f"Using existing Docker image: {image_name}")
        return image
    except docker.errors.ImageNotFound:
        # Build image if it doesn't exist
        print(f"Building Docker image: {image_name}")
        image, build_logs = docker_client.images.build(
            path=str(project_root),
            tag=image_name,
            rm=True
        )
        return image


@pytest.fixture(scope="session")
def docker_container(docker_client, docker_image):
    """
    Starts a Docker container for API testing and ensures it's healthy.
    
    Args:
        docker_client: Docker client fixture
        docker_image: Built Docker image fixture
        
    Yields:
        Running container instance for testing
        
    Note:
        This fixture automatically starts the container before tests
        and stops it after all tests complete.
    """
    container = None
    try:
        # Start container
        container = docker_client.containers.run(
            docker_image.id,
            ports={'8000/tcp': 8000},
            detach=True,
            name="house-api-test",
            remove=True
        )
        
        # Wait for container to be healthy
        max_retries = 30
        for i in range(max_retries):
            try:
                response = requests.get("http://localhost:8000/health", timeout=2)
                if response.status_code == 200:
                    print("✅ Container is healthy and ready for testing")
                    break
            except requests.exceptions.RequestException:
                pass
            
            if i == max_retries - 1:
                raise Exception("Container failed to become healthy")
            
            time.sleep(1)
        
        yield container
        
    finally:
        # Clean up container
        if container:
            try:
                container.stop()
                print("🧹 Container stopped and cleaned up")
            except Exception as e:
                print(f"⚠️ Error stopping container: {e}")


@pytest.fixture
def api_base_url() -> str:
    """
    Provides the base URL for API testing.
    
    Returns:
        Base URL string for making API requests
    """
    return "http://localhost:8000"


@pytest.fixture
def api_headers() -> Dict[str, str]:
    """
    Provides common headers for API requests.
    
    Returns:
        Dictionary of HTTP headers for API testing
    """
    return {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }


# Test Markers Configuration
def pytest_configure(config):
    """
    Configure custom pytest markers.
    
    Args:
        config: Pytest configuration object
    """
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests (deselect with '-m \"not unit\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (deselect with '-m \"not integration\"')"
    )
    config.addinivalue_line(
        "markers", "api: marks tests as API tests (deselect with '-m \"not api\"')"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "docker: marks tests that require Docker (deselect with '-m \"not docker\"')"
    )


# Test Collection Hook
def pytest_collection_modifyitems(config, items):
    """
    Automatically mark tests based on their location.
    
    Args:
        config: Pytest configuration
        items: List of collected test items
    """
    for item in items:
        # Add markers based on test file path
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "api" in str(item.fspath):
            item.add_marker(pytest.mark.api)
        
        # Mark Docker-related tests
        if "docker" in str(item.fspath) or "container" in item.name:
            item.add_marker(pytest.mark.docker)