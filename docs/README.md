# Documentation Index

Welcome to the Teaching Lightweight LLM documentation.

## Quick Start
New to the system? Start here:
1. [Execution Guide](execution.md) - Run your first experiment
2. [Configuration Guide](configuration.md) - Understand the settings
3. [Visualization Guide](visualization.md) - Analyze your results

## User Guides

### Running Experiments
- [Execution Guide](execution.md) - Complete guide to running experiments
  - Interactive and command-line modes
  - Available models and strategies
  - Performance tips
  - Troubleshooting

### Analyzing Results
- [Analysis Summary Guide](analysis_summary.md) - Understanding your results
  - Result file structure
  - Key metrics explained
  - Comparison techniques
  - Statistical analysis

- [Visualization Guide](visualization.md) - Creating graphs and reports
  - Analysis report generator
  - Graph interpretation
  - Data export options
  - Advanced usage

### Configuration
- [Configuration Guide](configuration.md) - All configuration options
  - Configuration files overview
  - Model settings
  - Strategy configuration
  - Parameter tuning
  - Adding custom components

### Distribution
- [Export Guide](export.md) - Creating distributable packages
  - Building executables
  - Distribution packages
  - User installation
  - Deployment options

## File Organization

### Project Structure
```
Teaching_lightweight_LLM/
├── config/                    # Configuration files
├── data/                      # Datasets
├── docs/                      # Documentation (this folder)
├── results/                   # Experiment results
├── src/                       # Source code
├── tests/                     # Test files
├── run_experiment.py          # Main entry point
├── create_analysis_report.py  # Analysis tool
└── requirements.txt           # Dependencies
```

### Key Directories

#### config/
System configuration and settings
- `config.yaml` - Main configuration
- `models.yaml` - Model definitions
- `strategies.yaml` - Strategy settings
- `canonical_concepts.json` - Concept definitions

#### data/
Training and evaluation datasets
- `alpaca_20.jsonl` - Small test set
- `alpaca_100.jsonl` - Standard evaluation
- `alpaca_questions.jsonl` - Full dataset

#### results/
Experiment outputs (auto-generated)
- Organized by model/strategy/run
- Contains configs, summaries, and detailed results

#### src/
Source code modules
- `core/` - Core system components
- `pipelines/` - Teaching pipelines
- `memory/` - Memory systems
- `evaluation/` - Metrics and evaluation
- `analysis/` - Analysis tools

#### tests/
Test suite
- Unit tests
- Integration tests
- System verification tests

#### docs/
Documentation (this folder)
- User guides
- Configuration references
- API documentation

## Common Workflows

### Workflow 1: First Experiment
```bash
# 1. Set API keys
set GROQ_API_KEY=your_key
set GOOGLE_API_KEY=your_key

# 2. Run quick test
python run_experiment.py --student tinyllama_1.1b --teacher gemini-1.5-flash --strategies baseline --dataset alpaca_20

# 3. View results
python create_analysis_report.py
```

### Workflow 2: Strategy Comparison
```bash
# 1. Run multiple strategies
python run_experiment.py --student tinyllama_1.1b --teacher gemini-1.5-flash --strategies baseline multikey_tfidf reflection --dataset alpaca_100

# 2. Generate comparison report
python create_analysis_report.py
# Select all three runs

# 3. Review graphs and tables in analysis_reports/
```

### Workflow 3: Full Evaluation
```bash
# 1. Test on small dataset first
python run_experiment.py --student tinyllama_1.1b --teacher gemini-1.5-flash --strategies multikey_tfidf --dataset alpaca_20

# 2. If good, run full evaluation
python run_experiment.py --student tinyllama_1.1b --teacher gemini-1.5-flash --strategies multikey_tfidf --dataset alpaca_100 --max-iters 5

# 3. Analyze and export
python create_analysis_report.py
```

### Workflow 4: Creating Distribution
```bash
# 1. Build executable
pyinstaller --clean run_experiment.spec

# 2. Test executable
dist\run_experiment.exe --help

# 3. Create package
# Copy dist/, config/, data/, docs/ to distribution folder

# 4. Zip and share
```

## Getting Help

### Documentation
- Read the relevant guide for your task
- Check troubleshooting sections
- Review examples and workflows

### Common Issues
- **API Errors**: Check environment variables
- **Model Not Found**: Verify paths in config/models.yaml
- **Import Errors**: Install requirements: `pip install -r requirements.txt`
- **Memory Errors**: Use smaller models or datasets

### Best Practices
1. Start with small datasets (alpaca_20)
2. Test incrementally
3. Keep notes on configuration changes
4. Backup important results
5. Use version control

## System Overview

### Components

#### 1. Experiment Runner
`run_experiment.py` - Main entry point
- Loads configuration
- Initializes models
- Runs teaching loops
- Saves results

#### 2. Teaching Pipeline
`src/pipelines/` - Core teaching logic
- Student-teacher interaction
- Strategy implementation
- Iteration management
- Feedback processing

#### 3. Memory System
`src/memory/` - Memory management
- Storage and retrieval
- Similarity matching
- Key generation
- Canonical concepts

#### 4. Evaluation
`src/evaluation/` - Quality assessment
- Metrics calculation
- Critic feedback
- Success criteria

#### 5. Analysis
`src/analysis/` - Result analysis
- Comparison tools
- Visualization
- Statistical analysis

### Data Flow
```
Dataset → Student Model → Teacher Evaluation → Feedback → Memory → Next Iteration
                ↓
           Results Saved
                ↓
         Analysis & Visualization
```

## Additional Resources

### External Documentation
- PyTorch: https://pytorch.org/docs/
- Transformers: https://huggingface.co/docs/transformers/
- Gemini API: https://ai.google.dev/docs
- Groq API: https://console.groq.com/docs/

### Related Papers
- Teaching techniques for LLMs
- Memory-augmented learning
- Retrieval strategies
- Quality metrics

### Community
- GitHub Issues: Report bugs
- Discussions: Ask questions
- Pull Requests: Contribute improvements

## Document Updates

This documentation is regularly updated. Check for:
- New features
- Configuration changes
- Best practices
- Bug fixes

Last updated: 2025-01-29

## Quick Reference

### Commands
```bash
# Run experiment
python run_experiment.py [options]

# Generate analysis
python create_analysis_report.py

# Visualize
python visualize_experiments.py

# Build executable
pyinstaller run_experiment.spec

# Run tests
python -m pytest tests/
```

### Key Files
- `run_experiment.py` - Main program
- `config/config.yaml` - Configuration
- `results/` - Output directory
- `docs/` - This documentation

### Environment Variables
```bash
GROQ_API_KEY      # Required for Groq models
GOOGLE_API_KEY    # Required for Gemini models
```

---

For detailed information on any topic, refer to the specific guide linked above.
