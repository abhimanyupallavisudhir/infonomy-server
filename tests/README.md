# Testing Guide for Infonomy Server

This directory contains comprehensive tests for the Infonomy information market server. The testing strategy follows best practices for testing applications with database dependencies.

## Testing Philosophy

### Why Database Testing is NOT Bad

Contrary to common misconceptions, testing with databases is not inherently bad. The key is to do it **correctly**:

1. **Isolation**: Each test runs in its own database transaction or separate database
2. **Speed**: Use in-memory databases for fast test execution
3. **Reliability**: Tests should be deterministic and not depend on external state
4. **Coverage**: Test both business logic and database interactions

## Test Structure

### Test Categories

- **Unit Tests** (`test_models.py`, `test_business_logic.py`): Test individual components without database dependencies
- **Integration Tests** (`test_database_operations.py`): Test database operations with proper isolation
- **API Tests** (`test_api_endpoints.py`): Test API endpoints using FastAPI test client

### Test Markers

Tests are organized using pytest markers:

- `@pytest.mark.unit`: Fast tests without database
- `@pytest.mark.integration`: Tests with database operations
- `@pytest.mark.api`: API endpoint tests
- `@pytest.mark.slow`: Tests that take more than a few seconds

## Running Tests

### Run All Tests
```bash
pytest
```

### Run Specific Test Categories
```bash
# Unit tests only (fast)
pytest -m unit

# Integration tests only
pytest -m integration

# API tests only
pytest -m api

# Skip slow tests
pytest -m "not slow"
```

### Run Specific Test Files
```bash
pytest tests/test_models.py
pytest tests/test_database_operations.py
pytest tests/test_api_endpoints.py
```

### Run with Coverage
```bash
pytest --cov=infonomy_server --cov-report=html
```

## Test Database Strategy

### In-Memory Database
- Each test gets a fresh in-memory SQLite database
- Complete isolation between tests
- Fast execution
- No cleanup required

### Fixtures
- `test_db`: Provides a database session for each test
- `test_client`: Provides a FastAPI test client with database override
- `sample_*`: Pre-created test data for common scenarios

## Writing New Tests

### Unit Tests
```python
@pytest.mark.unit
def test_user_creation():
    """Test basic user creation without database."""
    user = User(username="testuser", email="test@example.com")
    assert user.username == "testuser"
    assert user.is_active is True
```

### Integration Tests
```python
@pytest.mark.integration
def test_user_creation_and_retrieval(test_db):
    """Test creating and retrieving users from database."""
    user = User(username="testuser", email="test@example.com")
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    
    retrieved_user = test_db.get(User, user.id)
    assert retrieved_user.username == "testuser"
```

### API Tests
```python
@pytest.mark.api
def test_get_users(test_client):
    """Test getting all users via API."""
    response = test_client.get("/api/users/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
```

## Best Practices

### 1. Test Isolation
- Each test should be independent
- Use fixtures for common setup
- Don't rely on test execution order

### 2. Meaningful Assertions
- Test behavior, not implementation
- Use descriptive test names
- Include both positive and negative test cases

### 3. Database Testing
- Use transactions for isolation
- Test both success and failure scenarios
- Verify data integrity

### 4. API Testing
- Test authentication and authorization
- Test error handling
- Test request/response formats

## Common Patterns

### Testing Business Logic
```python
def test_balance_deduction_logic():
    """Test balance deduction without database."""
    user = User(balance=100.0, available_balance=100.0)
    user.available_balance -= 25.0
    assert user.available_balance == 75.0
    assert user.balance == 100.0
```

### Testing Database Operations
```python
def test_user_creation(test_db):
    """Test user creation in database."""
    user = User(username="testuser", email="test@example.com")
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    
    assert user.id is not None
    assert user.username == "testuser"
```

### Testing API Endpoints
```python
def test_create_user(test_client):
    """Test user creation via API."""
    user_data = {
        "username": "newuser",
        "email": "newuser@example.com",
        "password": "password123"
    }
    
    response = test_client.post("/auth/register", json=user_data)
    assert response.status_code == 201
```

## Debugging Tests

### Verbose Output
```bash
pytest -v
```

### Stop on First Failure
```bash
pytest -x
```

### Debug Specific Test
```bash
pytest tests/test_models.py::TestUserModel::test_user_creation -v
```

### Print Debug Information
```python
def test_debug_example(test_db):
    user = User(username="testuser")
    test_db.add(user)
    test_db.commit()
    
    print(f"Created user with ID: {user.id}")  # This will show in test output
    assert user.id is not None
```

## Continuous Integration

The test suite is designed to run in CI environments:

- No external dependencies (Redis, etc.) required for most tests
- Fast execution with in-memory databases
- Clear markers for different test types
- Comprehensive coverage of critical functionality

## Troubleshooting

### Common Issues

1. **Import Errors**: Make sure the `infonomy_server` package is in your Python path
2. **Database Errors**: Ensure you're using the test database fixtures
3. **Authentication Errors**: Use the `authenticated_headers` fixture for API tests
4. **Slow Tests**: Use markers to skip slow tests during development

### Getting Help

- Check existing test files for examples
- Use `pytest --collect-only` to see available tests
- Use `pytest -k "test_name"` to run specific tests
- Check the FastAPI testing documentation for API test patterns