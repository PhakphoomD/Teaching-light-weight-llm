# Utility Scripts

This directory contains utility scripts for various tasks.

## Available Scripts

### Analysis and Visualization

#### `analyze_token_usage.py`
Analyze API token usage and costs.
```bash
python scripts/analyze_token_usage.py
```
- Reads token tracking data from `results/tokens/`
- Calculates total usage and costs
- Provides breakdown by model and experiment

#### `visualize_experiments.py`
Legacy visualization tool for creating charts.
```bash
python scripts/visualize_experiments.py --output analysis_reports
```
Note: Consider using `create_analysis_report.py` (in root) for more comprehensive reports.

#### `demo_visualization.py`
Demo script showing visualization examples.
```bash
python scripts/demo_visualization.py
```
- Demonstrates different chart types
- Shows sample data visualization
- Useful for learning matplotlib techniques

### Dataset Management

#### `check_dataset.py`
Validate dataset files and check format.
```bash
python scripts/check_dataset.py data/alpaca_100.jsonl
```
- Verifies JSONL format
- Checks for required fields
- Reports any issues

### Token Tracking

#### `example_token_tracking.py`
Example of how to track token usage in custom code.
```bash
python scripts/example_token_tracking.py
```
- Shows token tracking API
- Demonstrates usage in code
- Useful for development

## Running Scripts

All scripts can be run from the project root:
```bash
# From project root
python scripts/script_name.py [arguments]
```

Or from within the scripts directory:
```bash
cd scripts
python script_name.py [arguments]
```

## Adding New Scripts

When adding utility scripts:
1. Place them in this directory
2. Add appropriate documentation header
3. Update this README with description
4. Include usage examples

## See Also
- [Main Documentation](../docs/README.md)
- [Visualization Guide](../docs/visualization.md)
- [Analysis Summary Guide](../docs/analysis_summary.md)
