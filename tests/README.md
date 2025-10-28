# Test Suite

This directory contains all test files for the Teaching Lightweight LLM project.

## Test Categories

### System Tests
- `test_phase1_4_features.py` - Phase 1-4 feature integration tests

### Component Tests
- `test_batch_summary.py` - Batch summary functionality tests
- `test_experiment_summary.py` - Experiment summary generation tests
- `test_metrics_verification.py` - Metrics calculation and verification tests

### Display Tests
- `test_console_display.py` - Console output display tests
- `test_console_display_new.py` - Updated console display tests

## Running Tests

### Run all tests
```bash
python -m pytest tests/
```

### Run specific test file
```bash
python -m pytest tests/test_metrics_verification.py
```

### Run with verbose output
```bash
python -m pytest tests/ -v
```

### Run specific test function
```bash
python -m pytest tests/test_metrics_verification.py::test_function_name -v
```

## Test Requirements

Make sure all dependencies are installed:
```bash
pip install -r requirements.txt
pip install pytest  # If not already included
```

