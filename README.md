# Teaching-light-weight-llm

## Set up guide
This repository separates **machine/runtime-specific** packages (installed with **Conda**) from **cross-platform Python libraries** (installed with **pip**).  
Follow the steps for your platform.

### Windows (NVIDIA)
Verify NVIDIA driver:
   ```powershell```
   nvidia-smi
If you don't see your GPU/driver, install the official NVIDIA Driver first.

Create Conda env (GPU runtime):

    conda env create -f environment.yml
    conda activate tlw```
Install Python packages with pip:

    pip install --upgrade pip
    pip install -r requirements.txt
Sanity check:

    import torch
    print("CUDA available:", torch.cuda.is_available())
    print("Device:", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU")

### MacOS (Apple Silicon: M1/M2/M3)
macOS uses MPS/Metal, not CUDA.
`` same as window without nvidia ``

    conda env create -f environment.yml
    conda activate tlw

    pip install --upgrade pip
    pip install torch torchvision torchaudio
    pip install -r requirements.txt

    
    import torch
    print("MPS available:", getattr(torch.backends, "mps", None) and torch.backends.m)
    is_available()
    print("CUDA available:", torch.cuda.is_available())
    


### Google Colab (pip-only)
    pip install --upgrade pip
    pip install torch torchvision torchaudio
    pip install -r requirements.txt

## Files in this repo

environment.yml — Conda environment for machine/runtime-specific packages (GPU/CUDA on Windows).

requirements.txt — pip requirements for cross-platform libs and LLM SDKs.

Optional: if you want to keep provider SDKs separate, create requirements-llm.txt with:
    openai>=1.40.0
    groq>=0.11.0
    google-generativeai>=0.7.2

## Set-up Troubleshooting
1. nvidia-smi not found / no GPU shown (Windows)
Install the official NVIDIA Driver (Studio/Game Ready), reboot, then re-run nvidia-smi.

2. Torch says CUDA available: False on Windows
Ensure you created/activated the Conda env from environment.yml (which installs pytorch-cuda).
Then reinstall pip packages: pip install -r requirements.txt.

3. FAISS GPU on Windows
Use CPU build (faiss-cpu) on Windows. If you need FAISS GPU, use Linux/WSL2.

4. macOS cannot use CUDA
Correct — use MPS (Metal) via pip install torch torchvision torchaudio.

After a successful setup:

    pip freeze > requirements-lock.txt
    conda env export > environment-lock.yml
this can help us to reproducibility next time.