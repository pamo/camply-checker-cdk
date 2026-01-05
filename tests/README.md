# Tests

This directory contains all tests for the camply-checker project.

## Structure

```
tests/
├── unit/                    # Unit tests for individual components
│   └── test_lambda.py      # Lambda function unit tests
├── integration/            # Integration tests for workflows  
│   └── test_lambda_workflow.py  # End-to-end Lambda workflow tests
├── infrastructure/         # CDK infrastructure tests
│   ├── camply.test.ts     # CDK stack tests
│   └── setup.ts           # Test setup
└── run_tests.py           # Test runner for all Lambda tests
```

## Running Tests

### All Lambda Tests
```bash
python tests/run_tests.py
```

### Individual Test Suites
```bash
# Unit tests only
python tests/unit/test_lambda.py

# Integration tests only  
python tests/integration/test_lambda_workflow.py
```

### Infrastructure Tests
```bash
npm test
```

## Test Categories

- **Unit Tests**: Test individual functions and components in isolation
- **Integration Tests**: Test complete workflows and component interactions
- **Infrastructure Tests**: Test CDK stack configuration and resources

## Requirements

Lambda tests require:
- Python 3.11+
- Virtual environment with boto3, camply==0.33.1, pytz

Infrastructure tests require:
- Node.js 18+
- AWS CDK dependencies
