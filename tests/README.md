# Test Structure

This project follows a structured approach to testing with clear separation between different test types.

## Directory Structure

```
tests/
├── unit/           # Unit tests - fast, isolated tests with mocked dependencies
├── integration/    # Integration tests - test component interactions
├── e2e/           # End-to-end tests - full workflow and user journey tests
├── helpers/       # Test utilities and helper functions
├── conftest.py    # Shared pytest fixtures
└── README.md      # This file
```

## Test Categories

### Unit Tests (`tests/unit/`)
- **Purpose**: Test individual functions, methods, and classes in isolation
- **Characteristics**: Fast execution, no external dependencies, heavily mocked
- **Examples**: Model validation, utility functions, business logic
- **Marker**: `@pytest.mark.unit`

### Integration Tests (`tests/integration/`)
- **Purpose**: Test interactions between multiple components
- **Characteristics**: Test API endpoints, database interactions, service integrations
- **Examples**: API endpoint tests, database CRUD operations, service layer tests
- **Marker**: `@pytest.mark.integration`

### End-to-End Tests (`tests/e2e/`)
- **Purpose**: Test complete user workflows and system behavior
- **Characteristics**: Slower execution, test full application stack
- **Examples**: User registration flow, complete API workflows, complex business processes
- **Marker**: `@pytest.mark.e2e`

## Running Tests

### Run All Tests
```bash
pytest
```

### Run by Category
```bash
# Unit tests only (fast)
pytest -m unit

# Integration tests only
pytest -m integration

# End-to-end tests only
pytest -m e2e
```

### Run by Directory
```bash
# Unit tests
pytest tests/unit/

# Integration tests
pytest tests/integration/

# End-to-end tests
pytest tests/e2e/
```

### Run with Coverage
```bash
# All tests with coverage
pytest --cov=src/app

# Unit tests with coverage
pytest tests/unit/ --cov=src/app
```

### Run Specific Test Types
```bash
# Authentication tests
pytest -m auth

# Database tests
pytest -m database

# API tests
pytest -m api

# Slow tests
pytest -m slow
```

## Test Markers

The following pytest markers are available:

- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.e2e` - End-to-end tests
- `@pytest.mark.api` - API endpoint tests
- `@pytest.mark.auth` - Authentication tests
- `@pytest.mark.database` - Database-related tests
- `@pytest.mark.cache` - Cache-related tests
- `@pytest.mark.external` - Tests with external service mocks
- `@pytest.mark.slow` - Tests that take longer to run
- `@pytest.mark.error` - Error scenario tests

## Best Practices

### Unit Tests
- Mock all external dependencies
- Test one thing at a time
- Use descriptive test names
- Keep tests fast (< 100ms each)

### Integration Tests
- Test realistic scenarios
- Use test database/fixtures
- Test error conditions
- Verify side effects

### End-to-End Tests
- Test complete user journeys
- Use realistic data
- Test critical business flows
- Keep minimal but comprehensive

### General Guidelines
- Follow the AAA pattern (Arrange, Act, Assert)
- Use meaningful test data
- Clean up after tests
- Write tests that are independent of each other
- Use fixtures for common setup

## CI/CD Integration

The test structure integrates with our CI/CD pipeline:

- **Pull Requests**: Run unit and integration tests
- **Main Branch**: Run all tests including e2e
- **Nightly Builds**: Run comprehensive test suite with performance tests

## Adding New Tests

1. **Determine test type**: Unit, Integration, or E2E
2. **Place in correct directory**: `tests/unit/`, `tests/integration/`, or `tests/e2e/`
3. **Add appropriate markers**: Use `@pytest.mark.unit`, `@pytest.mark.integration`, or `@pytest.mark.e2e`
4. **Follow naming convention**: `test_*.py` for files, `test_*` for functions
5. **Use existing fixtures**: Leverage `conftest.py` fixtures when possible
6. **Document complex tests**: Add docstrings for complex test scenarios

## Troubleshooting

### Common Issues

1. **Import errors**: Ensure `__init__.py` files exist in test directories
2. **Fixture not found**: Check if fixture is defined in `conftest.py` or imported correctly
3. **Database tests failing**: Ensure test database is properly set up and cleaned
4. **Slow tests**: Consider moving to integration or e2e category, or add `@pytest.mark.slow`

### Debug Commands

```bash
# Run with verbose output
pytest -v

# Run with debug output
pytest -s

# Run specific test
pytest tests/unit/test_models.py::TestUserModel::test_user_creation

# Run with pdb debugger
pytest --pdb
```
