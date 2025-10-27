# House Price Prediction - Testing Framework

## Overview

This comprehensive testing framework ensures the reliability, performance, and correctness of the House Price Prediction MLOps system. The test suite covers all aspects from individual functions to full Docker deployment scenarios.

## Test Structure

```
tests/
├── conftest.py                 # Shared fixtures and test configuration
├── pytest.ini                 # Pytest configuration
├── unit/                      # Unit tests for individual components
│   └── test_inference.py      # Tests for prediction logic
├── integration/               # Integration tests for system components
│   └── test_docker_api.py     # Docker container integration tests
├── api/                       # API endpoint tests
│   └── test_endpoints.py      # FastAPI endpoint testing
└── run_tests.py              # Master test runner script
```

## Test Categories

### 1. Unit Tests (`tests/unit/`)
**Purpose**: Test individual functions and classes in isolation
**Scope**: Core business logic, data processing, model inference
**Dependencies**: Mocked external dependencies

**Key Test Areas:**
- Model loading and validation
- Feature engineering functions
- Input data validation
- Prediction logic accuracy
- Error handling for edge cases

**Example Usage:**
```bash
# Run all unit tests
pytest tests/unit/ -v

# Run specific unit test file
pytest tests/unit/test_inference.py -v

# Run unit tests with coverage
pytest tests/unit/ --cov=src --cov-report=html
```

### 2. Integration Tests (`tests/integration/`)
**Purpose**: Test interactions between system components
**Scope**: Docker container lifecycle, API integration, database connections
**Dependencies**: Actual Docker containers and services

**Key Test Areas:**
- Container startup and shutdown
- Health monitoring and recovery
- Resource usage and limits
- File system structure verification
- Environment variable configuration
- Security configurations

**Example Usage:**
```bash
# Run integration tests (requires Docker)
pytest tests/integration/ -v -m integration

# Run with slow tests included
pytest tests/integration/ -v -m "integration or slow"
```

### 3. API Tests (`tests/api/`)
**Purpose**: Test HTTP API endpoints and request/response handling
**Scope**: FastAPI application, endpoint validation, error responses
**Dependencies**: Running Docker container

**Key Test Areas:**
- Health check endpoint
- Single prediction endpoint
- Batch prediction endpoint
- Input validation and error handling
- Response format verification
- Performance and load testing
- API documentation accessibility

**Example Usage:**
```bash
# Run API tests (requires running container)
pytest tests/api/ -v -m api

# Run API tests excluding slow performance tests
pytest tests/api/ -v -m "api and not slow"
```

## Test Fixtures and Configuration

### Shared Fixtures (`conftest.py`)
The `conftest.py` file provides reusable test fixtures that are shared across all test modules:

**Docker Fixtures:**
- `docker_client`: Docker client for container management
- `docker_container`: Pre-configured test container
- `api_base_url`: Base URL for API testing
- `api_headers`: Standard headers for API requests

**Test Data Fixtures:**
- `sample_house_data`: Valid house data for testing
- `invalid_house_data`: Invalid data for validation testing
- `batch_house_data`: Multiple house records for batch testing

**Configuration:**
- Automatic container cleanup after tests
- Health check validation
- Port management for parallel test execution

### Pytest Configuration (`pytest.ini`)
Comprehensive pytest configuration including:

- **Test Discovery**: Automatic test file and function detection
- **Markers**: Test categorization (unit, integration, api, docker, slow)
- **Coverage**: Code coverage reporting with 80% minimum threshold
- **Output**: Detailed reporting with JUnit XML and HTML coverage reports
- **Timeouts**: Prevent hanging tests with 5-minute timeout
- **Logging**: Structured logging for test debugging

## Master Test Runner (`run_tests.py`)

The master test runner orchestrates the complete testing pipeline:

### Features:
- **Automated Docker Management**: Builds images, starts containers, handles cleanup
- **Selective Test Execution**: Run specific test suites or all tests
- **Health Monitoring**: Verifies container health before running tests
- **Comprehensive Reporting**: Detailed test results and performance metrics
- **Error Handling**: Graceful failure recovery and resource cleanup

### Usage Examples:

```bash
# Run complete test suite
python run_tests.py --mode all --verbose

# Run only unit tests (no Docker required)
python run_tests.py --mode unit

# Run integration tests with cleanup
python run_tests.py --mode integration --cleanup

# Run API tests in verbose mode
python run_tests.py --mode api --verbose

# Run Docker-specific tests
python run_tests.py --mode docker
```

### Command Line Options:
- `--mode`: Test mode (all, unit, integration, api, docker)
- `--verbose`: Enable detailed logging
- `--cleanup`: Clean up Docker resources after tests (default: true)
- `--no-cleanup`: Leave Docker resources for debugging

## Test Data and Mocking

### Sample Data
All tests use realistic but safe test data that represents typical house characteristics:

```python
sample_house_data = {
    "sqft": 2000,
    "bedrooms": 3,
    "bathrooms": 2,
    "location": "suburban",
    "year_built": 2010,
    "condition": "Good"
}
```

### Mocking Strategy
Unit tests use comprehensive mocking to isolate components:

- **Model Loading**: Mock joblib.load() to avoid file system dependencies
- **External APIs**: Mock any external service calls
- **Time Dependencies**: Mock datetime for consistent testing
- **Random Components**: Mock random number generation for reproducible tests

### Invalid Data Testing
Comprehensive validation testing with various invalid input scenarios:

- Negative values (sqft, bedrooms, bathrooms)
- Invalid categorical values (location, condition)
- Missing required fields
- Wrong data types
- Out-of-range values (future year_built)

## Performance Testing

### Load Testing
API tests include concurrent request testing:

```python
# Test concurrent predictions
def test_concurrent_predictions():
    # Execute 10 simultaneous requests
    # Verify all succeed within reasonable time
    # Check response consistency
```

### Response Time Testing
Performance benchmarks for different operations:

- Single prediction: < 1 second
- Batch prediction (10 items): < 5 seconds
- Health check: < 0.5 seconds
- Container startup: < 30 seconds

### Resource Monitoring
Container resource usage verification:

- Memory usage: < 1GB
- CPU utilization monitoring
- Container log analysis
- Error detection and reporting

## CI/CD Integration

### GitHub Actions Ready
The test framework is designed for easy CI/CD integration:

```yaml
# Example GitHub Actions workflow
- name: Run Tests
  run: |
    python run_tests.py --mode all --verbose
    
- name: Upload Coverage Reports
  uses: codecov/codecov-action@v1
  with:
    file: tests/coverage.xml
```

### Test Artifacts
Generated test artifacts include:

- **JUnit XML**: `tests/test_results.xml` (for CI integration)
- **Coverage HTML**: `tests/coverage_html/` (detailed coverage report)
- **Coverage XML**: `tests/coverage.xml` (for coverage services)
- **Test Report**: `tests/test_report.txt` (human-readable summary)
- **Logs**: `tests/test_results.log` (detailed execution logs)

## Debugging and Troubleshooting

### Common Issues and Solutions

**1. Docker Connection Errors**
```bash
# Verify Docker is running
docker info

# Check for port conflicts
netstat -an | grep 8000

# Clean up stuck containers
docker ps -a | grep house-price
docker rm -f <container_id>
```

**2. Test Failures**
```bash
# Run with maximum verbosity
python run_tests.py --mode all --verbose

# Keep Docker resources for debugging
python run_tests.py --mode integration --no-cleanup

# Check container logs
docker logs <container_name>
```

**3. Import Errors**
```bash
# Verify Python path
export PYTHONPATH="${PYTHONPATH}:${PWD}/src"

# Install test dependencies
pip install -r requirements.txt
pip install pytest pytest-cov pytest-mock requests docker
```

### Test Development Guidelines

**1. Writing New Tests**
- Use descriptive test names that explain the scenario
- Include comprehensive docstrings with test purpose
- Follow AAA pattern: Arrange, Act, Assert
- Use appropriate pytest markers for categorization

**2. Test Isolation**
- Each test should be independent and idempotent
- Use fixtures for shared setup and teardown
- Mock external dependencies in unit tests
- Clean up resources in integration tests

**3. Assertion Best Practices**
- Use specific assertions that clearly indicate failures
- Include helpful error messages
- Test both positive and negative scenarios
- Verify data types and ranges, not just values

## Test Coverage Goals

Current coverage targets and areas for improvement:

### Current Coverage
- **src/api/**: 95%+ (well covered with API tests)
- **src/models/**: 85%+ (covered with unit tests)
- **src/features/**: 80%+ (feature engineering tests)
- **Overall Target**: 80%+ with room for improvement

### Coverage Improvement Areas
- Error handling edge cases
- Configuration validation
- Performance optimization paths
- Logging and monitoring code

### Continuous Improvement
The test suite is designed for continuous expansion:

- Add new test cases for bug fixes
- Expand performance benchmarks
- Include security testing
- Add chaos engineering tests
- Implement contract testing for API changes

This comprehensive testing framework provides confidence in the system's reliability and facilitates safe, rapid development and deployment of the House Price Prediction service.