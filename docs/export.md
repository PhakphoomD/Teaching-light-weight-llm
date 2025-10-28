# Export and Distribution Guide

This guide explains how to export your experiment and create distributable packages.

## Building Standalone Executable

### Overview
You can create a standalone `.exe` file that runs without Python installed.

### Prerequisites
```bash
pip install pyinstaller
```

### Build Process

#### Option 1: Using Spec File (Recommended)
```bash
pyinstaller --clean run_experiment.spec
```

#### Option 2: Command Line
```bash
pyinstaller --onefile --console --name run_experiment --add-data "config;config" --add-data "data;data" --add-data "src;src" --hidden-import groq --hidden-import google.generativeai --hidden-import yaml --hidden-import jsonlines run_experiment.py
```

### Output
The executable will be created in:
```
dist/run_experiment.exe
```

### File Size
- Typical size: 50-200 MB
- Includes all Python dependencies
- Compressed internally

## Creating Distribution Package

### Complete Package Structure
```
Teaching_LLM_Package/
├── run_experiment.exe          # Main executable
├── create_analysis_report.exe  # Analysis tool (optional)
├── visualize_experiments.exe   # Visualization tool (optional)
├── config/
│   ├── config.yaml
│   ├── models.yaml
│   ├── strategies.yaml
│   └── canonical_concepts.json
├── data/
│   ├── alpaca_20.jsonl
│   ├── alpaca_100.jsonl
│   └── alpaca_questions.jsonl
├── docs/
│   └── (all documentation files)
├── README.txt                  # Quick start guide
└── LICENSE.txt                 # License information
```

### Build Additional Tools
```bash
# Build analysis report generator
pyinstaller --onefile --console --name create_analysis_report --hidden-import matplotlib --hidden-import pandas create_analysis_report.py

# Build visualization tool
pyinstaller --onefile --console --name visualize_experiments --hidden-import matplotlib visualize_experiments.py
```

## Distribution Package Creation

### Windows
```bash
# Create package directory
mkdir Teaching_LLM_Package
cd Teaching_LLM_Package

# Copy executables
copy ..\dist\run_experiment.exe .
copy ..\dist\create_analysis_report.exe .

# Copy configuration and data
xcopy ..\config config\ /E /I
xcopy ..\data data\ /E /I
xcopy ..\docs docs\ /E /I

# Create README
echo Quick Start Guide > README.txt
```

### Linux/Mac
```bash
# Create package directory
mkdir -p Teaching_LLM_Package
cd Teaching_LLM_Package

# Copy executables
cp ../dist/run_experiment ./
cp ../dist/create_analysis_report ./

# Copy configuration and data
cp -r ../config ./
cp -r ../data ./
cp -r ../docs ./

# Create README
echo "Quick Start Guide" > README.txt
```

## User Installation Instructions

### For End Users (No Python)

1. **Extract Package**
   - Unzip the distribution package
   - No installation needed

2. **Set API Keys**
   ```bash
   # Windows
   set GROQ_API_KEY=your_groq_api_key
   set GOOGLE_API_KEY=your_google_api_key
   
   # Linux/Mac
   export GROQ_API_KEY=your_groq_api_key
   export GOOGLE_API_KEY=your_google_api_key
   ```

3. **Run Experiments**
   ```bash
   # Interactive mode
   run_experiment.exe
   
   # Command line mode
   run_experiment.exe --student tinyllama_1.1b --teacher gemini-1.5-flash --strategies baseline --dataset alpaca_20
   ```

4. **Analyze Results**
   ```bash
   create_analysis_report.exe
   ```

### First Run Behavior
- May take 5-10 seconds to start (extraction)
- Subsequent runs are faster
- Creates `results/` folder for output

## What the Executable Can Do

### Full Functionality
- Run all teaching experiments
- Use all strategies
- Load all datasets
- Generate results
- Save configurations
- Track progress

### Limitations
- **Requires API Keys**: Must set environment variables
- **Internet Required**: For API calls to teacher models
- **No Code Editing**: Cannot modify source code
- **Fixed Models**: Student models must be included in package
- **Large Size**: 50-200 MB download

### What's Included
- Python interpreter (embedded)
- All Python libraries
- Configuration files
- Dataset files
- Source code (compiled)

### What's NOT Included
- Model weight files (too large)
- API keys
- Previous results
- Custom datasets (unless added to package)

## Advanced Distribution

### Creating Installer

#### Using Inno Setup (Windows)
```iss
[Setup]
AppName=Teaching Lightweight LLM
AppVersion=1.0
DefaultDirName={pf}\Teaching_LLM
OutputDir=installer
OutputBaseFilename=Teaching_LLM_Setup

[Files]
Source: "dist\run_experiment.exe"; DestDir: "{app}"
Source: "config\*"; DestDir: "{app}\config"; Flags: recursesubdirs
Source: "data\*"; DestDir: "{app}\data"; Flags: recursesubdirs
```

#### Using PyInstaller with NSIS (Windows)
```bash
makensis installer.nsi
```

### Docker Container
```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

ENV GROQ_API_KEY=""
ENV GOOGLE_API_KEY=""

CMD ["python", "run_experiment.py"]
```

Build and run:
```bash
docker build -t teaching-llm .
docker run -e GROQ_API_KEY=$GROQ_API_KEY -e GOOGLE_API_KEY=$GOOGLE_API_KEY teaching-llm
```

### Cloud Deployment

#### AWS Lambda
Package as Lambda function:
```bash
# Create deployment package
pip install -r requirements.txt -t package/
cp -r src package/
cp run_experiment.py package/
cd package && zip -r ../lambda.zip . && cd ..
```

#### Google Cloud Run
```yaml
# cloudbuild.yaml
steps:
- name: 'gcr.io/cloud-builders/docker'
  args: ['build', '-t', 'gcr.io/$PROJECT_ID/teaching-llm', '.']
- name: 'gcr.io/cloud-builders/docker'
  args: ['push', 'gcr.io/$PROJECT_ID/teaching-llm']
```

## Updating Distributions

### Version Management
```python
# version.py
VERSION = "1.0.0"
BUILD_DATE = "2025-01-29"
```

Include in executable:
```bash
python run_experiment.py --version
```

### Update Process
1. Make code changes
2. Update version number
3. Test thoroughly
4. Rebuild executable
5. Create new distribution package
6. Document changes in CHANGELOG
7. Distribute to users

## Troubleshooting Distribution

### Executable Won't Run
- **Anti-virus**: May block unsigned executables
- **Permissions**: Ensure execute permissions
- **Dependencies**: Check all files included

### Missing Files
```
Error: config.yaml not found
```
**Solution**: Ensure config folder is next to executable

### API Errors
```
Error: GROQ_API_KEY not set
```
**Solution**: Set environment variables before running

### Size Too Large
- Remove unnecessary dependencies
- Exclude unused models
- Use UPX compression:
  ```bash
  pyinstaller --upx-dir=/path/to/upx run_experiment.py
  ```

## Best Practices

### For Developers
1. Test executable before distributing
2. Include all necessary files
3. Document requirements clearly
4. Version your releases
5. Provide changelog

### For Distribution
1. Use clear folder structure
2. Include comprehensive README
3. Provide example commands
4. Test on clean system
5. Consider installer for ease of use

### For Users
1. Keep API keys secure
2. Backup results regularly
3. Check for updates
4. Report issues with version info
5. Read documentation

## Security Considerations

### API Keys
- Never include API keys in distributed files
- Users must provide their own keys
- Document key setup clearly

### Code Protection
- Executable is somewhat obfuscated
- Not fully protected from reverse engineering
- Consider licensing terms

### Data Privacy
- Results stay on user's machine
- No telemetry by default
- Users control all data

## See Also
- [Execution Guide](execution.md)
- [Configuration Guide](configuration.md)
- BUILD_EXECUTABLE.md (technical details)
