# Teaching Lightweight LLM

An experimental framework for teaching and improving lightweight language models using various memory and retrieval strategies.

## Quick Start

### 1. Installation
```bash
# Create conda environment
conda env create -f environment.yml
conda activate tlw

# Install Python dependencies
pip install -r requirements.txt
```

### 2. Set API Keys
```bash
# Windows
set GROQ_API_KEY=your_groq_api_key
set GOOGLE_API_KEY=your_google_api_key

# Linux/Mac
export GROQ_API_KEY=your_groq_api_key
export GOOGLE_API_KEY=your_google_api_key
```

### 3. Run Your First Experiment
```bash
# Interactive mode (recommended)
python run_experiment.py

# Or command-line mode
python run_experiment.py --student tinyllama_1.1b --teacher gemini-1.5-flash --strategies baseline --dataset alpaca_20
```

### 4. Analyze Results
```bash
python create_analysis_report.py
```

## Project Structure

```
Teaching_lightweight_LLM/
├── config/                    # Configuration files
├── data/                      # Datasets
├── docs/                      # Complete documentation
│   ├── README.md             # Documentation index
│   ├── execution.md          # How to run experiments
│   ├── analysis_summary.md   # Analyzing results
│   ├── visualization.md      # Creating graphs
│   ├── configuration.md      # All settings
│   └── export.md             # Building executables
├── results/                   # Experiment outputs
├── scripts/                   # Utility scripts
├── src/                       # Source code
├── tests/                     # Test suite
├── run_experiment.py          # Main entry point
└── create_analysis_report.py  # Analysis tool
```

## Documentation

Complete documentation is available in the `docs/` folder:

- [Documentation Index](docs/README.md) - Start here
- [Execution Guide](docs/execution.md) - Running experiments
- [Configuration Guide](docs/configuration.md) - All settings
- [Analysis Guide](docs/analysis_summary.md) - Understanding results
- [Visualization Guide](docs/visualization.md) - Creating graphs
- [Export Guide](docs/export.md) - Building executables

## Key Features

- Multiple student models (TinyLlama, Llama2, Llama3)
- Various teaching strategies (baseline, reflection, memory-based)
- Organized analysis reports with graphs
- Comprehensive documentation
- Executable distribution support

## Common Tasks

### Run Experiment
```bash
python run_experiment.py --student tinyllama_1.1b --teacher gemini-1.5-flash --strategies multikey_tfidf --dataset alpaca_100
```

### Generate Analysis Report
```bash
python create_analysis_report.py
```

### Build Executable
```bash
pyinstaller --clean run_experiment.spec
```

## Platform-Specific Setup

### Windows (NVIDIA GPU)
1. Verify NVIDIA driver:
   ```powershell
   nvidia-smi
   ```
   If GPU not shown, install official NVIDIA Driver first.

2. Create Conda environment:
   ```bash
   conda env create -f environment.yml
   conda activate tlw
   ```

3. Install Python packages:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. Verify GPU:
   ```python
   import torch
   print("CUDA available:", torch.cuda.is_available())
   print("Device:", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU")
   ```

### MacOS (Apple Silicon: M1/M2/M3)
macOS uses MPS/Metal, not CUDA.

1. Create environment:
   ```bash
   conda env create -f environment.yml
   conda activate tlw
   ```

2. Install dependencies:
   ```bash
   pip install --upgrade pip
   pip install torch torchvision torchaudio
   pip install -r requirements.txt
   ```

3. Verify MPS:
   ```python
   import torch
   print("MPS available:", torch.backends.mps.is_available())
   ```

### Google Colab
```bash
pip install --upgrade pip
pip install torch torchvision torchaudio
pip install -r requirements.txt
```

## Repository Files

- `environment.yml` - Conda environment for GPU/CUDA packages
- `requirements.txt` - Python dependencies
- `config/` - Configuration files
- `data/` - Datasets
- `docs/` - Complete documentation
- `results/` - Experiment outputs
- `scripts/` - Utility scripts
- `src/` - Source code
- `tests/` - Test suite

## Troubleshooting

### GPU Not Detected (Windows)
1. Install official NVIDIA Driver
2. Reboot system
3. Run `nvidia-smi` to verify

### CUDA Not Available
1. Ensure Conda environment is activated
2. Reinstall: `pip install -r requirements.txt`

### macOS CUDA Error
macOS doesn't support CUDA. Use MPS (Metal) instead.

### Import Errors
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

## Contributing

1. Create feature branch
2. Make changes
3. Run tests: `python -m pytest tests/`
4. Submit pull request

## License

See LICENSE file for details.

## Citation

If you use this work, please cite:
```
@software{teaching_lightweight_llm,
  title = {Teaching Lightweight LLM},
  year = {2025},
  url = {https://github.com/Kosakiri/Teaching-light-weight-llm}
}
```

## Support

- Documentation: [docs/README.md](docs/README.md)
- Issues: GitHub Issues
- Questions: GitHub Discussions

### Generating Datasets

```powershell
# Generate full Alpaca dataset
python -m src.experiments.prepare_alpaca

# Generate 100-sample subset
$env:ALPACA_SAMPLE_SIZE="100"
$env:ALPACA_OUT="data/datasets/alpaca_100.jsonl"
python -m src.experiments.prepare_alpaca
```

## Notes

- Memory files use JSON format with task-based and rule-based indexing
- Datasets use JSONL format (one JSON object per line)
- All paths in code default to this structure
- Archived results are stored in `logs/experiments/`
