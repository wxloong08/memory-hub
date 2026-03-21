# Testing Documentation

## Overview

Comprehensive test suite for Claude Memory System with >80% code coverage.

## Test Structure

```
tests/
├── conftest.py                      # Shared fixtures and utilities
├── test_database.py                 # Basic database tests
├── test_database_comprehensive.py   # Comprehensive database tests
├── test_models.py                   # Pydantic model validation tests
├── test_api.py                      # Basic API tests
├── test_api_comprehensive.py        # Comprehensive API tests
├── test_hooks.py                    # Claude Code hook tests
└── test_e2e.py                      # End-to-end integration tests
```

## Running Tests

### Run All Tests
```bash
cd "D:\python project\claude-memory-system"
pytest tests/ -v
```

### Run Specific Test Files
```bash
# Database tests
pytest tests/test_database_comprehensive.py -v

# API tests
pytest tests/test_api_comprehensive.py -v

# Model tests
pytest tests/test_models.py -v

# Hook tests
pytest tests/test_hooks.py -v

# End-to-end tests
pytest tests/test_e2e.py -v
```

### Run Tests by Category
```bash
# Integration tests only
pytest tests/ -v -m integration

# End-to-end tests only
pytest tests/ -v -m e2e

# Skip slow tests
pytest tests/ -v -m "not slow"

# Performance tests only
pytest tests/ -v -m performance
```

### Run with Coverage
```bash
pytest tests/ --cov=backend --cov-report=html --cov-report=term
```

## Test Categories

### 1. Unit Tests

#### Database Tests (`test_database_comprehensive.py`)
- Schema creation and validation
- CRUD operations
- Query filtering (time, importance, working_dir)
- Edge cases (empty DB, special characters, large content)
- Data integrity and uniqueness
- Concurrent operations
- Platform support

#### Model Tests (`test_models.py`)
- Pydantic model validation
- Required vs optional fields
- Type validation
- Serialization/deserialization
- Default values
- Special character handling

### 2. Integration Tests

#### API Tests (`test_api_comprehensive.py`)
- Health check endpoint
- POST /api/conversations
  - Minimal and full payloads
  - Multiple messages
  - Validation errors
  - Special characters
- GET /api/context
  - Empty database
  - Time filtering
  - Importance filtering
  - Working directory filtering
- CORS configuration
- Error handling
- End-to-end workflows

#### Hook Tests (`test_hooks.py`)
- Hook script existence and permissions
- Memory Hub connectivity handling
- Directory creation
- CLAUDE.md preservation
- Environment variable usage
- Error handling
- Installation script validation

### 3. End-to-End Tests (`test_e2e.py`)
- Full workflow: add conversation → retrieve context
- Multiple conversation tracking
- Cross-platform conversation tracking
- Importance scoring validation
- Context filtering
- Working directory isolation
- Concurrent request handling
- Performance benchmarks

## Test Fixtures

### Database Fixtures
- `test_db`: Isolated test database instance
- `temp_db_path`: Temporary database file path
- `temp_test_dir`: Temporary directory for testing

### Data Fixtures
- `sample_messages_short`: 2-message conversation
- `sample_messages_medium`: 6-message conversation
- `sample_messages_long`: 100-message conversation
- `sample_conversation_data`: Complete conversation structure

### Platform Fixtures
- `claude_web_conversation`: Claude Web conversation
- `claude_code_conversation`: Claude Code conversation
- `antigravity_conversation`: Antigravity conversation

### Time Fixtures
- `old_timestamp`: 48 hours ago
- `recent_timestamp`: 1 hour ago
- `current_timestamp`: Now

## Helper Classes

### DatabaseTestHelper
```python
# Count conversations
count = DatabaseTestHelper.count_conversations(db, working_dir="/project")

# Find by content
conv = DatabaseTestHelper.get_conversation_by_content(db, "search term")

# Clear all
DatabaseTestHelper.clear_all_conversations(db)
```

### APITestHelper
```python
# Add conversation
response = APITestHelper.add_conversation(client, platform="claude_web")

# Get context
response = APITestHelper.get_context(client, hours=24)

# Assert success
data = APITestHelper.assert_api_success(response)
```

### PerformanceTestHelper
```python
# Measure execution time
result, elapsed = PerformanceTestHelper.measure_time(func, *args)

# Assert performance
PerformanceTestHelper.assert_performance(elapsed, 2.0, "Database query")
```

## Test Coverage Goals

- **Database Layer**: >90% coverage
- **API Endpoints**: >85% coverage
- **Models**: >95% coverage
- **Hooks**: >70% coverage (bash scripts)
- **Overall**: >80% coverage

## Prerequisites

### Install Test Dependencies
```bash
pip install pytest pytest-cov httpx
```

### Start Memory Hub (for integration tests)
```bash
cd backend
uvicorn main:app --port 8765
```

## Writing New Tests

### Test Naming Convention
- Test files: `test_*.py`
- Test classes: `Test*`
- Test functions: `test_*`

### Example Test
```python
def test_feature_name():
    """Clear description of what is being tested"""
    # Arrange
    data = create_test_data()

    # Act
    result = function_under_test(data)

    # Assert
    assert result == expected_value
```

### Using Fixtures
```python
def test_with_fixture(test_db, sample_messages_short):
    """Test using fixtures"""
    conv_id = test_db.add_conversation(
        platform="claude_web",
        timestamp=datetime.now(),
        full_content=str(sample_messages_short)
    )
    assert conv_id is not None
```

## Continuous Integration

### GitHub Actions (Future)
```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Install dependencies
        run: pip install -r backend/requirements.txt
      - name: Run tests
        run: pytest tests/ --cov=backend --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

## Troubleshooting

### Tests Fail to Import Backend
```bash
# Add project root to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:D:\python project\claude-memory-system"
```

### Database Lock Errors
- Ensure previous test databases are cleaned up
- Check that connections are properly closed
- Use isolated test databases

### API Tests Fail
- Ensure Memory Hub is running on port 8765
- Check that test database is isolated
- Verify CORS configuration

### Hook Tests Fail on Windows
- Some bash-specific tests may not work on Windows
- Use Git Bash or WSL for running hook tests
- Skip platform-specific tests with markers

## Test Markers

```python
@pytest.mark.slow
def test_long_running_operation():
    """Mark slow tests"""
    pass

@pytest.mark.integration
def test_api_integration():
    """Mark integration tests"""
    pass

@pytest.mark.e2e
def test_full_workflow():
    """Mark end-to-end tests"""
    pass

@pytest.mark.performance
def test_performance_benchmark():
    """Mark performance tests"""
    pass
```

## Best Practices

1. **Isolation**: Each test should be independent
2. **Cleanup**: Always clean up test data and resources
3. **Clarity**: Use descriptive test names and docstrings
4. **Coverage**: Aim for both positive and negative test cases
5. **Speed**: Keep unit tests fast, mark slow tests appropriately
6. **Fixtures**: Reuse fixtures to reduce duplication
7. **Assertions**: Use specific assertions with clear messages
8. **Documentation**: Document complex test scenarios

## Next Steps

1. Implement remaining API endpoints (main.py)
2. Run tests and achieve >80% coverage
3. Set up CI/CD pipeline
4. Add performance benchmarks
5. Create test data generators for realistic scenarios
6. Add mutation testing for test quality validation
