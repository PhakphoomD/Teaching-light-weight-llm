# Visualization Guide

This guide explains how to visualize experiment results and generate analysis reports.

## Quick Start

### Generate Analysis Report (Recommended)
```bash
python create_analysis_report.py
```

This interactive tool will:
1. List all available experiments
2. Let you select experiments to analyze
3. Generate organized report with graphs and data

### Legacy Visualization Tool
```bash
python visualize_experiments.py --output analysis_reports
```

## Analysis Report Structure

Each report is saved in a dedicated folder:
```
analysis_reports/
└── tinyllama_1.1b_baseline_20251029_143022/
    ├── summary_table.csv           # Comparison table (Excel-friendly)
    ├── summary_table.txt           # Formatted text table
    ├── comparison_graphs.png       # Visual comparisons
    ├── detailed_report.txt         # Full experiment details
    └── experiments_analyzed.txt    # List of included experiments
```

## Using the Analysis Report Generator

### Interactive Mode (Default)
```bash
python create_analysis_report.py
```

Follow the prompts to:
1. View all available experiments
2. Select experiments by number (e.g., 1,3,5)
3. Or type "all" to analyze all experiments

### Command-Line Mode
```bash
# Analyze specific experiments
python create_analysis_report.py --experiments tinyllama_1.1b/baseline/run_20251028_212825 tinyllama_1.1b/multikey_tfidf/run_20251028_200210

# Custom output directory
python create_analysis_report.py --output-dir my_reports

# Custom results directory
python create_analysis_report.py --results-dir results
```

### Non-Interactive Mode
```bash
python create_analysis_report.py --non-interactive --experiments tinyllama_1.1b/baseline/run_20251028_212825
```

## Understanding the Graphs

### Success Rate Comparison
- Bar chart showing success rate percentage for each experiment
- Higher is better
- Compares effectiveness across different strategies

### Average Iterations Comparison
- Bar chart showing average number of iterations per task
- Lower values indicate faster convergence
- Helps identify efficiency of different approaches

## Reading the Summary Table

The summary table includes:
- **Model**: Student model used (e.g., tinyllama_1.1b)
- **Strategy**: Teaching strategy applied
- **Run**: Timestamp of the experiment
- **Success Rate**: Percentage of successfully completed tasks
- **Avg Iterations**: Average number of iterations needed
- **Total Tasks**: Number of tasks attempted
- **Successful**: Number of successful completions
- **Failed**: Number of failed tasks
- **Avg Score**: Average quality score (if available)

## Detailed Report Contents

The detailed report includes:
1. **Configuration**: All experiment parameters
2. **Summary Statistics**: Aggregate metrics
3. **Task Results**: Individual task outcomes
   - Success/failure status
   - Number of iterations
   - Quality scores
   - Question snippets

## Tips for Analysis

### Comparing Strategies
```bash
# Compare all runs of specific strategies
python create_analysis_report.py
# Then select all runs for strategies you want to compare
```

### Tracking Progress Over Time
```bash
# Select multiple runs of the same strategy to see improvements
python create_analysis_report.py
# Select runs ordered by timestamp
```

### Finding Best Configuration
1. Generate reports for different parameter combinations
2. Compare success rates and iteration counts
3. Review detailed reports for insights

## Exporting Data

All data is exported in multiple formats:
- **CSV**: Open in Excel or Google Sheets
- **TXT**: Human-readable formatted text
- **PNG**: High-resolution graphs (300 DPI)

## Advanced Usage

### Batch Analysis Script
Create a script to analyze multiple configurations:

```bash
# analyze_all.bat
python create_analysis_report.py --non-interactive --experiments tinyllama_1.1b/baseline/run_20251028_212825 --output-dir reports/baseline
python create_analysis_report.py --non-interactive --experiments tinyllama_1.1b/multikey_tfidf/run_20251028_200210 --output-dir reports/multikey
```

### Programmatic Access
You can also use the generator in your own scripts:

```python
from create_analysis_report import AnalysisReportGenerator

generator = AnalysisReportGenerator("results", "my_reports")
experiments = ["tinyllama_1.1b/baseline/run_20251028_212825"]
generator.generate_report(experiments)
```

## Troubleshooting

### No Experiments Found
- Check that `results/` directory exists
- Verify experiment structure: `model/strategy/run_YYYYMMDD_HHMMSS/`
- Ensure summary.json files are present

### Missing Graphs
- Install matplotlib: `pip install matplotlib`
- Check for sufficient data (at least 1 valid experiment)

### Encoding Issues with Thai Text
- All files use UTF-8 encoding
- CSV files use UTF-8-BOM for Excel compatibility

### Large File Sizes
- Graphs are saved at 300 DPI for publication quality
- Reduce DPI in code if file size is a concern

## See Also
- [Analysis Summary Guide](analysis_summary.md)
- [Running Experiments](execution.md)
- [Configuration Guide](configuration.md)
