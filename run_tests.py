"""
Master Test Runner for House Price Prediction MLOps Project

This script orchestrates the complete testing pipeline including:
1. Docker image building
2. Container startup and health checks  
3. Unit tests execution
4. Integration tests execution
5. API tests execution
6. Performance benchmarking
7. Cleanup and reporting

Usage:
    python run_tests.py [--mode all|unit|integration|api|docker] [--verbose] [--cleanup]
    
Examples:
    python run_tests.py --mode all --verbose
    python run_tests.py --mode unit
    python run_tests.py --mode docker --cleanup
"""

import argparse
import docker
import pytest
import time
import logging
import sys
import os
import subprocess
import requests
from typing import Dict, List, Optional, Tuple
from pathlib import Path


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('tests/test_results.log')
    ]
)
logger = logging.getLogger(__name__)


class TestRunner:
    """
    Orchestrates the complete testing pipeline for the House Price Prediction service.
    
    This class manages Docker containers, runs test suites, and provides
    comprehensive reporting of test results and system health.
    """
    
    def __init__(self, cleanup: bool = True, verbose: bool = False):
        """
        Initialize the test runner.
        
        Args:
            cleanup: Whether to clean up Docker resources after tests
            verbose: Whether to enable verbose logging
        """
        self.cleanup = cleanup
        self.verbose = verbose
        self.docker_client = None
        self.test_container = None
        self.image_name = "house-price-api:test"
        self.container_name = "house-price-test"
        self.container_port = 8000
        self.host_port = 8000
        
        # Test results tracking
        self.test_results = {
            "unit": {"status": "not_run", "duration": 0, "details": {}},
            "integration": {"status": "not_run", "duration": 0, "details": {}},
            "api": {"status": "not_run", "duration": 0, "details": {}},
            "docker": {"status": "not_run", "duration": 0, "details": {}},
            "overall": {"status": "not_run", "start_time": None, "end_time": None}
        }
        
        if verbose:
            logging.getLogger().setLevel(logging.DEBUG)
    
    def setup_docker(self) -> bool:
        """
        Set up Docker client and verify Docker is available.
        
        Returns:
            bool: True if Docker setup successful, False otherwise
        """
        try:
            self.docker_client = docker.from_env()
            
            # Test Docker connection
            self.docker_client.ping()
            logger.info("Docker client connected successfully")
            
            # Check if Docker daemon is running
            docker_info = self.docker_client.info()
            logger.info(f"Docker info: {docker_info['ServerVersion']} on {docker_info['OperatingSystem']}")
            
            return True
            
        except docker.errors.DockerException as e:
            logger.error(f"Docker setup failed: {e}")
            logger.error("Please ensure Docker is installed and running")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during Docker setup: {e}")
            return False
    
    def build_docker_image(self) -> bool:
        """
        Build the Docker image for testing.
        
        Returns:
            bool: True if build successful, False otherwise
        """
        try:
            logger.info("Building Docker image for testing...")
            start_time = time.time()
            
            # Build image
            image, build_logs = self.docker_client.images.build(
                path=".",
                tag=self.image_name,
                rm=True,
                forcerm=True
            )
            
            build_time = time.time() - start_time
            
            if self.verbose:
                logger.debug("Build logs:")
                for log in build_logs:
                    if 'stream' in log:
                        logger.debug(log['stream'].strip())
            
            logger.info(f"Docker image built successfully in {build_time:.2f} seconds")
            logger.info(f"Image ID: {image.short_id}")
            
            return True
            
        except docker.errors.BuildError as e:
            logger.error(f"Docker build failed: {e}")
            if self.verbose:
                for log in e.build_log:
                    if 'stream' in log:
                        logger.error(log['stream'].strip())
            return False
        except Exception as e:
            logger.error(f"Unexpected error during Docker build: {e}")
            return False
    
    def start_test_container(self) -> bool:
        """
        Start the test container and wait for it to be ready.
        
        Returns:
            bool: True if container started successfully, False otherwise
        """
        try:
            # Remove existing container if it exists
            self.cleanup_container()
            
            logger.info("Starting test container...")
            
            # Start container
            self.test_container = self.docker_client.containers.run(
                self.image_name,
                ports={f"{self.container_port}/tcp": self.host_port},
                detach=True,
                name=self.container_name,
                environment={
                    "ENV": "test",
                    "LOG_LEVEL": "DEBUG" if self.verbose else "INFO"
                }
            )
            
            logger.info(f"Container started with ID: {self.test_container.short_id}")
            
            # Wait for container to be running
            timeout = 30
            start_time = time.time()
            while time.time() - start_time < timeout:
                self.test_container.reload()
                if self.test_container.status == "running":
                    break
                time.sleep(1)
            else:
                logger.error("Container failed to start within timeout")
                return False
            
            # Wait for application to be ready
            logger.info("Waiting for application to be ready...")
            app_ready = False
            health_url = f"http://localhost:{self.host_port}/health"
            
            for attempt in range(30):  # 30 second timeout
                try:
                    response = requests.get(health_url, timeout=5)
                    if response.status_code == 200:
                        health_data = response.json()
                        if health_data.get("status") == "healthy" and health_data.get("model_loaded"):
                            app_ready = True
                            break
                except requests.exceptions.RequestException:
                    pass
                
                time.sleep(1)
                if self.verbose and attempt % 5 == 0:
                    logger.debug(f"Waiting for app readiness... attempt {attempt + 1}/30")
            
            if not app_ready:
                logger.error("Application failed to become ready")
                self.log_container_status()
                return False
            
            logger.info("Test container is ready and healthy")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start test container: {e}")
            return False
    
    def log_container_status(self):
        """Log detailed container status for debugging."""
        if self.test_container:
            try:
                self.test_container.reload()
                logger.info(f"Container status: {self.test_container.status}")
                
                # Get container logs
                logs = self.test_container.logs(tail=20).decode('utf-8')
                logger.info("Recent container logs:")
                for line in logs.split('\n')[-10:]:  # Last 10 lines
                    if line.strip():
                        logger.info(f"  {line}")
                        
            except Exception as e:
                logger.error(f"Failed to get container status: {e}")
    
    def run_unit_tests(self) -> bool:
        """
        Run unit tests.
        
        Returns:
            bool: True if tests passed, False otherwise
        """
        logger.info("Running unit tests...")
        start_time = time.time()
        
        try:
            # Use the virtual environment's Python executable
            python_exe = sys.executable
            
            # Run pytest for unit tests
            cmd = [
                python_exe, "-m", "pytest",
                "tests/unit/",
                "-v" if self.verbose else "-q",
                "--tb=short",
                "-m", "not slow",
                "--junitxml=tests/unit_test_results.xml"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=".")
            duration = time.time() - start_time
            
            self.test_results["unit"]["duration"] = duration
            self.test_results["unit"]["details"] = {
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
            
            if result.returncode == 0:
                self.test_results["unit"]["status"] = "passed"
                logger.info(f"Unit tests passed in {duration:.2f} seconds")
                return True
            else:
                self.test_results["unit"]["status"] = "failed"
                logger.error(f"Unit tests failed (exit code: {result.returncode})")
                if self.verbose:
                    logger.error(f"STDOUT: {result.stdout}")
                    logger.error(f"STDERR: {result.stderr}")
                return False
                
        except Exception as e:
            self.test_results["unit"]["status"] = "error"
            logger.error(f"Error running unit tests: {e}")
            return False
    
    def run_integration_tests(self) -> bool:
        """
        Run integration tests.
        
        Returns:
            bool: True if tests passed, False otherwise
        """
        logger.info("Running integration tests...")
        start_time = time.time()
        
        try:
            # Use the virtual environment's Python executable
            python_exe = sys.executable
            
            # Run pytest for integration tests
            cmd = [
                python_exe, "-m", "pytest",
                "tests/integration/",
                "-v" if self.verbose else "-q",
                "--tb=short",
                "-m", "integration",
                "--junitxml=tests/integration_test_results.xml"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=".")
            duration = time.time() - start_time
            
            self.test_results["integration"]["duration"] = duration
            self.test_results["integration"]["details"] = {
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
            
            if result.returncode == 0:
                self.test_results["integration"]["status"] = "passed"
                logger.info(f"Integration tests passed in {duration:.2f} seconds")
                return True
            else:
                self.test_results["integration"]["status"] = "failed"
                logger.error(f"Integration tests failed (exit code: {result.returncode})")
                if self.verbose:
                    logger.error(f"STDOUT: {result.stdout}")
                    logger.error(f"STDERR: {result.stderr}")
                return False
                
        except Exception as e:
            self.test_results["integration"]["status"] = "error"
            logger.error(f"Error running integration tests: {e}")
            return False
    
    def run_api_tests(self) -> bool:
        """
        Run API tests.
        
        Returns:
            bool: True if tests passed, False otherwise
        """
        logger.info("Running API tests...")
        start_time = time.time()
        
        try:
            # Use the virtual environment's Python executable
            python_exe = sys.executable
            
            # Run pytest for API tests
            cmd = [
                python_exe, "-m", "pytest",
                "tests/api/",
                "-v" if self.verbose else "-q",
                "--tb=short",
                "-m", "api",
                "--junitxml=tests/api_test_results.xml"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=".")
            duration = time.time() - start_time
            
            self.test_results["api"]["duration"] = duration
            self.test_results["api"]["details"] = {
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
            
            if result.returncode == 0:
                self.test_results["api"]["status"] = "passed"
                logger.info(f"API tests passed in {duration:.2f} seconds")
                return True
            else:
                self.test_results["api"]["status"] = "failed"
                logger.error(f"API tests failed (exit code: {result.returncode})")
                if self.verbose:
                    logger.error(f"STDOUT: {result.stdout}")
                    logger.error(f"STDERR: {result.stderr}")
                return False
                
        except Exception as e:
            self.test_results["api"]["status"] = "error"
            logger.error(f"Error running API tests: {e}")
            return False
    
    def run_docker_tests(self) -> bool:
        """
        Run Docker-specific tests.
        
        Returns:
            bool: True if tests passed, False otherwise
        """
        logger.info("Running Docker tests...")
        start_time = time.time()
        
        try:
            # Use the virtual environment's Python executable
            python_exe = sys.executable
            
            # Run pytest for Docker-specific tests
            cmd = [
                python_exe, "-m", "pytest",
                "tests/",
                "-v" if self.verbose else "-q",
                "--tb=short",
                "-m", "docker",
                "--junitxml=tests/docker_test_results.xml"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=".")
            duration = time.time() - start_time
            
            self.test_results["docker"]["duration"] = duration
            self.test_results["docker"]["details"] = {
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
            
            if result.returncode == 0:
                self.test_results["docker"]["status"] = "passed"
                logger.info(f"Docker tests passed in {duration:.2f} seconds")
                return True
            else:
                self.test_results["docker"]["status"] = "failed"
                logger.error(f"Docker tests failed (exit code: {result.returncode})")
                if self.verbose:
                    logger.error(f"STDOUT: {result.stdout}")
                    logger.error(f"STDERR: {result.stderr}")
                return False
                
        except Exception as e:
            self.test_results["docker"]["status"] = "error"
            logger.error(f"Error running Docker tests: {e}")
            return False
    
    def cleanup_container(self):
        """Clean up test container."""
        try:
            if self.test_container:
                self.test_container.stop(timeout=10)
                self.test_container.remove()
                self.test_container = None
                logger.info("Test container cleaned up")
        except Exception as e:
            logger.warning(f"Error cleaning up container: {e}")
        
        # Also try to remove any existing container with the same name
        try:
            existing_container = self.docker_client.containers.get(self.container_name)
            existing_container.stop(timeout=10)
            existing_container.remove()
            logger.info("Existing container removed")
        except docker.errors.NotFound:
            pass  # Container doesn't exist, which is fine
        except Exception as e:
            logger.warning(f"Error removing existing container: {e}")
    
    def cleanup_resources(self):
        """Clean up all Docker resources created during testing."""
        if not self.cleanup:
            logger.info("Cleanup disabled, leaving resources intact")
            return
        
        logger.info("Cleaning up Docker resources...")
        
        # Clean up container
        self.cleanup_container()
        
        # Clean up image
        try:
            image = self.docker_client.images.get(self.image_name)
            self.docker_client.images.remove(image.id, force=True)
            logger.info("Test image removed")
        except docker.errors.ImageNotFound:
            pass  # Image doesn't exist, which is fine
        except Exception as e:
            logger.warning(f"Error removing test image: {e}")
    
    def generate_report(self) -> str:
        """
        Generate a comprehensive test report.
        
        Returns:
            str: Formatted test report
        """
        total_duration = sum(result["duration"] for result in self.test_results.values() if isinstance(result, dict) and "duration" in result)
        
        passed_tests = [name for name, result in self.test_results.items() 
                       if isinstance(result, dict) and result.get("status") == "passed"]
        failed_tests = [name for name, result in self.test_results.items() 
                       if isinstance(result, dict) and result.get("status") == "failed"]
        error_tests = [name for name, result in self.test_results.items() 
                      if isinstance(result, dict) and result.get("status") == "error"]
        
        report = f"""
========================================
House Price Prediction Test Report
========================================

Overall Status: {'PASSED' if not failed_tests and not error_tests else 'FAILED'}
Total Duration: {total_duration:.2f} seconds

Test Results Summary:
--------------------
✓ Passed: {len(passed_tests)} ({', '.join(passed_tests) if passed_tests else 'none'})
✗ Failed: {len(failed_tests)} ({', '.join(failed_tests) if failed_tests else 'none'})
⚠ Errors: {len(error_tests)} ({', '.join(error_tests) if error_tests else 'none'})

Detailed Results:
----------------
"""
        
        for test_name, result in self.test_results.items():
            if isinstance(result, dict) and "status" in result:
                status_icon = "✓" if result["status"] == "passed" else "✗" if result["status"] == "failed" else "⚠"
                report += f"{status_icon} {test_name.upper()} Tests: {result['status'].upper()}"
                if "duration" in result:
                    report += f" ({result['duration']:.2f}s)"
                report += "\n"
        
        return report
    
    def save_report(self, report: str):
        """Save the test report to file."""
        report_file = "tests/test_report.txt"
        try:
            os.makedirs(os.path.dirname(report_file), exist_ok=True)
            with open(report_file, 'w') as f:
                f.write(report)
            logger.info(f"Test report saved to {report_file}")
        except Exception as e:
            logger.error(f"Failed to save test report: {e}")
    
    def run_all_tests(self) -> bool:
        """
        Run the complete test suite.
        
        Returns:
            bool: True if all tests passed, False otherwise
        """
        self.test_results["overall"]["start_time"] = time.time()
        
        logger.info("Starting complete test suite...")
        
        # Setup phase
        if not self.setup_docker():
            return False
        
        if not self.build_docker_image():
            return False
        
        if not self.start_test_container():
            return False
        
        # Testing phase
        success = True
        
        # Run unit tests (don't require container)
        if not self.run_unit_tests():
            success = False
        
        # Run integration tests (require container)
        if not self.run_integration_tests():
            success = False
        
        # Run API tests (require container)
        if not self.run_api_tests():
            success = False
        
        # Run Docker tests (require container)
        if not self.run_docker_tests():
            success = False
        
        self.test_results["overall"]["end_time"] = time.time()
        self.test_results["overall"]["status"] = "passed" if success else "failed"
        
        return success
    
    def run_specific_tests(self, mode: str) -> bool:
        """
        Run specific test suite based on mode.
        
        Args:
            mode: Test mode ('unit', 'integration', 'api', 'docker')
            
        Returns:
            bool: True if tests passed, False otherwise
        """
        self.test_results["overall"]["start_time"] = time.time()
        
        success = True
        
        if mode == "unit":
            success = self.run_unit_tests()
        elif mode in ["integration", "api", "docker"]:
            # These modes require Docker container
            if not self.setup_docker():
                return False
            if not self.build_docker_image():
                return False
            if not self.start_test_container():
                return False
            
            if mode == "integration":
                success = self.run_integration_tests()
            elif mode == "api":
                success = self.run_api_tests()
            elif mode == "docker":
                success = self.run_docker_tests()
        
        self.test_results["overall"]["end_time"] = time.time()
        self.test_results["overall"]["status"] = "passed" if success else "failed"
        
        return success


def main():
    """Main entry point for the test runner."""
    parser = argparse.ArgumentParser(
        description="Master Test Runner for House Price Prediction MLOps Project",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_tests.py --mode all --verbose
  python run_tests.py --mode unit
  python run_tests.py --mode docker --cleanup
        """
    )
    
    parser.add_argument(
        "--mode",
        choices=["all", "unit", "integration", "api", "docker"],
        default="all",
        help="Test mode to run (default: all)"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    parser.add_argument(
        "--cleanup",
        action="store_true",
        default=True,
        help="Clean up Docker resources after tests (default: True)"
    )
    
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Don't clean up Docker resources after tests"
    )
    
    args = parser.parse_args()
    
    # Handle cleanup flag
    cleanup = args.cleanup and not args.no_cleanup
    
    # Create test runner
    runner = TestRunner(cleanup=cleanup, verbose=args.verbose)
    
    try:
        # Run tests based on mode
        if args.mode == "all":
            success = runner.run_all_tests()
        else:
            success = runner.run_specific_tests(args.mode)
        
        # Generate and display report
        report = runner.generate_report()
        print(report)
        runner.save_report(report)
        
        # Exit with appropriate code
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        logger.info("Test execution interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error during test execution: {e}")
        sys.exit(1)
    finally:
        # Always try to clean up
        try:
            runner.cleanup_resources()
        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")


if __name__ == "__main__":
    main()