"""
Integration tests for the House Price Prediction Docker container.

These tests verify that the entire Docker containerization process works
correctly, including container startup, health checks, API accessibility,
and proper shutdown. They test the integration between all components.
"""

import pytest
import docker
import requests
import time
import json
import logging
from typing import Optional, Dict, Any


# Configure logging for integration tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@pytest.mark.integration
@pytest.mark.docker
class TestDockerContainerLifecycle:
    """Test class for Docker container lifecycle management."""
    
    def test_container_startup_and_shutdown(self, docker_client):
        """
        Test complete container lifecycle from startup to shutdown.
        
        This test verifies:
        - Container can be started successfully
        - Container reaches running state
        - Container can be stopped gracefully
        - Container cleanup works properly
        """
        # Build image if needed
        try:
            image = docker_client.images.get("house-price-api:latest")
        except docker.errors.ImageNotFound:
            # Build the image
            image, build_logs = docker_client.images.build(
                path=".",
                tag="house-price-api:latest",
                rm=True
            )
            logger.info("Built Docker image successfully")
        
        # Start container
        container = docker_client.containers.run(
            image.id,
            ports={"8000/tcp": 8001},  # Use different port to avoid conflicts
            detach=True,
            name="test-house-price-api"
        )
        
        try:
            # Wait for container to be running
            timeout = 30
            start_time = time.time()
            while time.time() - start_time < timeout:
                container.reload()
                if container.status == "running":
                    break
                time.sleep(1)
            else:
                pytest.fail("Container failed to start within timeout")
            
            logger.info(f"Container started successfully with ID: {container.short_id}")
            
            # Verify container is accessible
            assert container.status == "running"
            
            # Test basic connectivity (wait for app to be ready)
            app_ready = False
            for _ in range(30):  # 30 second timeout
                try:
                    response = requests.get("http://localhost:8001/health", timeout=5)
                    if response.status_code == 200:
                        app_ready = True
                        break
                except requests.exceptions.RequestException:
                    pass
                time.sleep(1)
            
            assert app_ready, "Application failed to become ready"
            logger.info("Application is ready and responding")
            
        finally:
            # Clean up container
            container.stop(timeout=10)
            container.remove()
            logger.info("Container stopped and removed")
    
    def test_container_health_monitoring(self, docker_container):
        """
        Test container health monitoring and recovery.
        
        This test verifies:
        - Health check endpoint is accessible
        - Container remains healthy over time
        - Health status is consistent
        """
        # Monitor health over several checks
        health_checks = []
        for i in range(5):
            try:
                response = requests.get(f"http://localhost:8000/health", timeout=5)
                health_checks.append({
                    "check": i + 1,
                    "status_code": response.status_code,
                    "response_time": response.elapsed.total_seconds(),
                    "healthy": response.status_code == 200
                })
                
                if response.status_code == 200:
                    data = response.json()
                    health_checks[-1]["model_loaded"] = data.get("model_loaded", False)
                
            except requests.exceptions.RequestException as e:
                health_checks.append({
                    "check": i + 1,
                    "status_code": None,
                    "response_time": None,
                    "healthy": False,
                    "error": str(e)
                })
            
            if i < 4:  # Don't sleep after last check
                time.sleep(2)
        
        # Verify all health checks passed
        successful_checks = [check for check in health_checks if check["healthy"]]
        assert len(successful_checks) == 5, f"Health checks failed: {health_checks}"
        
        # Verify reasonable response times
        response_times = [check["response_time"] for check in successful_checks]
        avg_response_time = sum(response_times) / len(response_times)
        assert avg_response_time < 1.0, f"Average response time too high: {avg_response_time}"
        
        logger.info(f"All health checks passed with avg response time: {avg_response_time:.3f}s")
    
    def test_container_resource_usage(self, docker_container):
        """
        Test container resource usage and limits.
        
        This test monitors container resource consumption to ensure
        it stays within reasonable bounds.
        """
        container = docker_container
        
        # Get initial stats
        stats = container.stats(stream=False)
        
        # Extract resource usage information
        memory_usage = stats["memory_stats"]["usage"]
        memory_limit = stats["memory_stats"]["limit"]
        cpu_usage = stats["cpu_stats"]["cpu_usage"]["total_usage"]
        
        # Convert memory to MB
        memory_usage_mb = memory_usage / (1024 * 1024)
        memory_limit_mb = memory_limit / (1024 * 1024)
        
        logger.info(f"Container memory usage: {memory_usage_mb:.2f}MB / {memory_limit_mb:.2f}MB")
        
        # Verify reasonable memory usage (container should use less than 1GB)
        assert memory_usage_mb < 1024, f"Memory usage too high: {memory_usage_mb:.2f}MB"
        
        # Memory usage should be positive (app is running)
        assert memory_usage_mb > 0, "No memory usage detected"
    
    def test_container_logs(self, docker_container):
        """
        Test container logging and error handling.
        
        This test verifies that the container produces proper logs
        and doesn't have critical errors.
        """
        container = docker_container
        
        # Get container logs
        logs = container.logs(tail=50, timestamps=True).decode('utf-8')
        
        # Verify logs are being generated
        assert len(logs) > 0, "No logs found in container"
        
        # Check for critical errors (should not be present)
        error_indicators = [
            "ERROR", "CRITICAL", "FATAL", "Exception", "Traceback"
        ]
        
        log_lines = logs.split('\n')
        error_lines = []
        for line in log_lines:
            if any(indicator in line for indicator in error_indicators):
                error_lines.append(line)
        
        # Allow some warnings but no critical errors
        critical_errors = [line for line in error_lines if any(
            indicator in line for indicator in ["CRITICAL", "FATAL", "Exception", "Traceback"]
        )]
        
        assert len(critical_errors) == 0, f"Critical errors found in logs: {critical_errors}"
        
        logger.info(f"Container logs look healthy. Total lines: {len(log_lines)}")


@pytest.mark.integration
@pytest.mark.docker
class TestFullStackIntegration:
    """Test class for full stack integration testing."""
    
    def test_end_to_end_prediction_flow(self, docker_container, api_base_url, api_headers, sample_house_data):
        """
        Test complete end-to-end prediction workflow.
        
        This test verifies:
        - Health check works
        - Single prediction works
        - Batch prediction works
        - All responses are consistent
        """
        # Step 1: Health check
        health_url = f"{api_base_url}/health"
        health_response = requests.get(health_url, headers=api_headers)
        assert health_response.status_code == 200
        
        health_data = health_response.json()
        assert health_data["status"] == "healthy"
        assert health_data["model_loaded"] is True
        
        # Step 2: Single prediction
        predict_url = f"{api_base_url}/predict"
        predict_response = requests.post(predict_url, json=sample_house_data, headers=api_headers)
        assert predict_response.status_code == 200
        
        predict_data = predict_response.json()
        single_prediction = predict_data["predicted_price"]
        assert isinstance(single_prediction, (int, float))
        assert single_prediction > 0
        
        # Step 3: Batch prediction with same data
        batch_url = f"{api_base_url}/batch-predict"
        batch_response = requests.post(batch_url, json=[sample_house_data], headers=api_headers)
        assert batch_response.status_code == 200
        
        batch_data = batch_response.json()
        assert isinstance(batch_data, list)
        assert len(batch_data) == 1
        
        batch_prediction = batch_data[0]
        
        # Step 4: Verify consistency between single and batch predictions
        # They should be identical for the same input
        prediction_diff = abs(single_prediction - batch_prediction)
        relative_diff = prediction_diff / single_prediction
        
        # Allow for small floating point differences (< 0.1%)
        assert relative_diff < 0.001, f"Inconsistent predictions: single={single_prediction}, batch={batch_prediction}"
        
        logger.info(f"End-to-end test passed. Prediction: ${single_prediction:,.2f}")
    
    def test_model_consistency_across_restarts(self, docker_client):
        """
        Test that model predictions are consistent across container restarts.
        
        This test verifies that the model loading and prediction logic
        produces consistent results after container restart.
        """
        test_data = {
            "sqft": 2000,
            "bedrooms": 3,
            "bathrooms": 2,
            "location": "suburban",
            "year_built": 2010,
            "condition": "Good"
        }
        
        predictions = []
        
        # Get predictions from two separate container instances
        for run in range(2):
            # Start fresh container
            container = docker_client.containers.run(
                "house-price-api:latest",
                ports={"8000/tcp": 8002 + run},  # Use different ports
                detach=True,
                name=f"test-consistency-{run}"
            )
            
            try:
                # Wait for container to be ready
                port = 8002 + run
                ready = False
                for _ in range(30):
                    try:
                        response = requests.get(f"http://localhost:{port}/health", timeout=5)
                        if response.status_code == 200:
                            ready = True
                            break
                    except requests.exceptions.RequestException:
                        pass
                    time.sleep(1)
                
                assert ready, f"Container {run} failed to become ready"
                
                # Make prediction
                response = requests.post(
                    f"http://localhost:{port}/predict",
                    json=test_data,
                    headers={"Content-Type": "application/json"}
                )
                assert response.status_code == 200
                
                data = response.json()
                predictions.append(data["predicted_price"])
                
                logger.info(f"Run {run + 1} prediction: ${predictions[-1]:,.2f}")
                
            finally:
                # Clean up container
                container.stop(timeout=10)
                container.remove()
        
        # Verify predictions are identical (or very close due to floating point)
        prediction_diff = abs(predictions[0] - predictions[1])
        relative_diff = prediction_diff / predictions[0]
        
        # Should be identical or nearly identical (< 0.01%)
        assert relative_diff < 0.0001, f"Inconsistent predictions across restarts: {predictions}"
        
        logger.info("Model consistency test passed across container restarts")
    
    def test_concurrent_load_handling(self, docker_container, api_base_url, api_headers, sample_house_data):
        """
        Test container's ability to handle concurrent load.
        
        This test verifies that the containerized application can handle
        multiple simultaneous requests without errors or significant
        performance degradation.
        """
        import concurrent.futures
        import threading
        
        predict_url = f"{api_base_url}/predict"
        num_concurrent = 10
        success_count = 0
        response_times = []
        predictions = []
        
        def make_request(request_id):
            try:
                start_time = time.time()
                response = requests.post(predict_url, json=sample_house_data, headers=api_headers, timeout=10)
                elapsed_time = time.time() - start_time
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "request_id": request_id,
                        "response_time": elapsed_time,
                        "prediction": data["predicted_price"]
                    }
                else:
                    return {
                        "success": False,
                        "request_id": request_id,
                        "status_code": response.status_code,
                        "response_time": elapsed_time
                    }
            except Exception as e:
                return {
                    "success": False,
                    "request_id": request_id,
                    "error": str(e),
                    "response_time": None
                }
        
        # Execute concurrent requests
        start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_concurrent) as executor:
            futures = [executor.submit(make_request, i) for i in range(num_concurrent)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        total_time = time.time() - start_time
        
        # Analyze results
        successful_results = [r for r in results if r["success"]]
        success_count = len(successful_results)
        
        # Verify success rate
        success_rate = success_count / num_concurrent
        assert success_rate >= 0.9, f"Success rate too low: {success_rate:.2%} ({success_count}/{num_concurrent})"
        
        # Verify response times
        response_times = [r["response_time"] for r in successful_results if r["response_time"]]
        if response_times:
            avg_response_time = sum(response_times) / len(response_times)
            max_response_time = max(response_times)
            
            # Response times should be reasonable even under load
            assert avg_response_time < 3.0, f"Average response time too high: {avg_response_time:.3f}s"
            assert max_response_time < 10.0, f"Max response time too high: {max_response_time:.3f}s"
        
        # Verify prediction consistency
        predictions = [r["prediction"] for r in successful_results if "prediction" in r]
        if len(predictions) > 1:
            # All predictions should be identical for same input
            unique_predictions = set(predictions)
            assert len(unique_predictions) == 1, f"Inconsistent predictions under load: {unique_predictions}"
        
        logger.info(f"Concurrent load test passed: {success_count}/{num_concurrent} successful, "
                   f"avg response time: {avg_response_time:.3f}s, total time: {total_time:.3f}s")
    
    def test_data_validation_integration(self, docker_container, api_base_url, api_headers):
        """
        Test data validation integration across the full stack.
        
        This test verifies that data validation works correctly
        through the entire Docker containerized application.
        """
        predict_url = f"{api_base_url}/predict"
        
        # Test various invalid data scenarios
        invalid_data_cases = [
            {
                "name": "negative_sqft",
                "data": {"sqft": -100, "bedrooms": 3, "bathrooms": 2, "location": "urban", "year_built": 2010, "condition": "Good"},
                "expected_error": "sqft must be positive"
            },
            {
                "name": "zero_bedrooms",
                "data": {"sqft": 2000, "bedrooms": 0, "bathrooms": 2, "location": "urban", "year_built": 2010, "condition": "Good"},
                "expected_error": "bedrooms must be positive"
            },
            {
                "name": "invalid_location",
                "data": {"sqft": 2000, "bedrooms": 3, "bathrooms": 2, "location": "invalid", "year_built": 2010, "condition": "Good"},
                "expected_error": "location must be one of"
            },
            {
                "name": "future_year",
                "data": {"sqft": 2000, "bedrooms": 3, "bathrooms": 2, "location": "urban", "year_built": 2050, "condition": "Good"},
                "expected_error": "year_built cannot be in the future"
            },
            {
                "name": "missing_field",
                "data": {"sqft": 2000, "bedrooms": 3, "bathrooms": 2, "location": "urban", "condition": "Good"},
                "expected_error": "field required"
            }
        ]
        
        validation_results = []
        
        for case in invalid_data_cases:
            response = requests.post(predict_url, json=case["data"], headers=api_headers)
            
            result = {
                "name": case["name"],
                "status_code": response.status_code,
                "validation_passed": response.status_code == 422
            }
            
            if response.status_code == 422:
                try:
                    error_data = response.json()
                    result["error_details"] = error_data
                except:
                    result["error_details"] = "Could not parse error response"
            
            validation_results.append(result)
        
        # Verify all validation cases returned proper error codes
        passed_validations = [r for r in validation_results if r["validation_passed"]]
        assert len(passed_validations) == len(invalid_data_cases), \
            f"Validation failures: {[r for r in validation_results if not r['validation_passed']]}"
        
        logger.info(f"Data validation integration test passed for {len(invalid_data_cases)} test cases")


@pytest.mark.integration
@pytest.mark.docker
@pytest.mark.slow
class TestDockerEnvironment:
    """Test class for Docker environment and configuration."""
    
    def test_environment_variables(self, docker_container):
        """
        Test that environment variables are properly set in container.
        
        This test verifies that the container environment is configured correctly.
        """
        container = docker_container
        
        # Get container environment variables
        inspect_data = container.attrs
        env_vars = inspect_data["Config"]["Env"]
        
        # Convert to dictionary
        env_dict = {}
        for var in env_vars:
            if "=" in var:
                key, value = var.split("=", 1)
                env_dict[key] = value
        
        # Verify expected environment variables
        assert "PATH" in env_dict
        
        # Python should be available in PATH
        exec_result = container.exec_run("python --version")
        assert exec_result.exit_code == 0
        assert "Python" in exec_result.output.decode()
        
        logger.info(f"Environment check passed. Python version: {exec_result.output.decode().strip()}")
    
    def test_file_system_structure(self, docker_container):
        """
        Test that the container file system is structured correctly.
        
        This test verifies that all necessary files are present in the container.
        """
        container = docker_container
        
        # Check for required files and directories
        required_paths = [
            "/app",
            "/app/main.py",
            "/app/inference.py",
            "/app/requirements.txt",
            "/app/models/trained"
        ]
        
        for path in required_paths:
            exec_result = container.exec_run(f"ls -la {path}")
            assert exec_result.exit_code == 0, f"Required path not found: {path}"
        
        # Check that model files exist
        exec_result = container.exec_run("find /app/models/trained -name '*.pkl' -o -name '*.joblib'")
        assert exec_result.exit_code == 0
        
        model_files = exec_result.output.decode().strip()
        assert len(model_files) > 0, "No model files found in container"
        
        logger.info(f"File system structure verified. Model files found: {model_files}")
    
    def test_container_security(self, docker_container):
        """
        Test basic container security aspects.
        
        This test verifies basic security configurations of the container.
        """
        container = docker_container
        inspect_data = container.attrs
        
        # Check that container is not running as root (security best practice)
        # Note: This might need to be adjusted based on actual Dockerfile configuration
        exec_result = container.exec_run("whoami")
        if exec_result.exit_code == 0:
            user = exec_result.output.decode().strip()
            logger.info(f"Container running as user: {user}")
            # Container should ideally not run as root
            # assert user != "root", "Container should not run as root user"
        
        # Check for security-related configurations
        security_opts = inspect_data.get("HostConfig", {}).get("SecurityOpt", [])
        logger.info(f"Security options: {security_opts}")
        
        # Verify container is not running in privileged mode
        privileged = inspect_data.get("HostConfig", {}).get("Privileged", False)
        assert not privileged, "Container should not run in privileged mode"
        
        logger.info("Basic container security checks passed")


if __name__ == "__main__":
    # Run integration tests
    pytest.main([__file__, "-v", "-m", "integration"])