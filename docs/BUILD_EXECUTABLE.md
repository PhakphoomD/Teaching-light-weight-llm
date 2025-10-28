# Building Standalone Executable

This guide explains how to create a standalone `run_experiment.exe` that can run without Python installed.

## Prerequisites

Install PyInstaller:
```bash
pip install pyinstaller
```

## Build the Executable

### Option 1: Using the spec file (Recommended)
```bash
pyinstaller --clean run_experiment.spec
```

### Option 2: Using command line
```bash
pyinstaller --onefile --console --name run_experiment ^
    --add-data "config;config" ^
    --add-data "data;data" ^
    --add-data "src;src" ^
    --hidden-import groq ^
    --hidden-import google.generativeai ^
    --hidden-import yaml ^
    --hidden-import jsonlines ^
    run_experiment.py
```

## Output Location

The executable will be created in:
```
dist/run_experiment.exe
```

## Distribution Package

To distribute, create a folder with:
```
your-package/
├── run_experiment.exe      # The built executable
├── config/                 # Configuration files
│   ├── config.yaml
│   ├── models.yaml
│   ├── strategies.yaml
│   └── canonical_concepts.json
├── data/                   # Dataset files
│   ├── alpaca_100.jsonl
│   └── alpaca_20.jsonl
└── README.txt              # Usage instructions
```

## Usage (No Python Required!)

Users can run experiments directly:
```bash
# Interactive mode
run_experiment.exe

# Command line mode
run_experiment.exe --student tinyllama_1.1b --teacher gemini-1.5-flash ^
                   --strategies multikey_tfidf canonical_similarity ^
                   --dataset alpaca_100 --max-iters 3
```

## Visualization

For visualization, you can also build a separate executable:
```bash
pyinstaller --onefile --console --name visualize_experiments ^
    --hidden-import matplotlib ^
    visualize_experiments.py
```

Then users can run:
```bash
visualize_experiments.exe --output analysis_reports
```

## Notes

- **File Size**: The executable will be 50-200MB due to bundled libraries
- **First Run**: May take 5-10 seconds to extract and start
- **API Keys**: Users still need to set `GROQ_API_KEY` and `GOOGLE_API_KEY` environment variables
- **Results**: Created in `results/` directory next to the executable
- **Updates**: Rebuild the executable when code changes

## Testing the Executable

1. Copy `dist/run_experiment.exe` to a clean directory
2. Copy `config/` and `data/` folders
3. Run without Python:
   ```bash
   run_experiment.exe --student tinyllama_1.1b --teacher gemini-1.5-flash --strategies baseline --dataset alpaca_20
   ```

## Troubleshooting

**Error: "Module not found"**
- Add missing module to `hiddenimports` in `run_experiment.spec`

**Error: "Config file not found"**
- Ensure `config/` folder is in the same directory as the .exe

**Slow startup**
- Normal for first run; subsequent runs are faster
- Use `--onedir` instead of `--onefile` for faster startup (creates folder instead of single .exe)

## Advanced: Smaller Executable

To reduce file size:
```bash
# Use --onedir mode (creates folder with DLLs)
pyinstaller --onedir run_experiment.spec

# Or exclude unused modules
pyinstaller --clean --exclude-module tkinter --exclude-module PyQt5 run_experiment.spec
```
