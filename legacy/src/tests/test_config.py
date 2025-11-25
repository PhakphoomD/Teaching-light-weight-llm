"""
Phase 1 - Verify Configuration Values

This script verifies all config values are correctly set:
- Teacher providers
- Student device selection
- Memory encoder and k value
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from config.ai_config import load_config
from src.core.logger import get_logger

logger = get_logger("test.config")


def verify_config():
    """Verify all configuration values."""
    print("=" * 70)
    print("Phase 1 - Configuration Verification")
    print("=" * 70)
    
    try:
        # Load config
        print("\n[1/5] Loading configuration...")
        cfg, secrets = load_config()
        print("    [OK] Config loaded successfully")
        
        # Verify teacher configuration
        print("\n[2/5] Verifying teacher configuration...")
        print(f"    Provider: {cfg.teacher.providers[0].provider}")
        print(f"    Model: {cfg.teacher.providers[0].model}")
        print(f"    Timeout: {cfg.teacher.providers[0].timeout_s}s")
        print(f"    Temperature: {cfg.teacher.temperature}")
        print(f"    Max tokens: {cfg.teacher.max_tokens}")
        print(f"    Top-p: {cfg.teacher.top_p}")
        print(f"    Rate limit: {cfg.teacher.rate_limit_rps} RPS")
        
        # Check expected values
        if cfg.teacher.providers[0].provider != "gemini":
            print("    [WARNING]  Expected provider to be 'gemini'")
            return False
        
        if "gemini-2" not in cfg.teacher.providers[0].model:
            print(f"    [WARNING]  Expected Gemini-2.x model, got: {cfg.teacher.providers[0].model}")
            return False
        
        print("    [OK] Teacher configuration correct")
        
        # Verify student configuration
        print("\n[3/5] Verifying student configuration...")
        print(f"    Mode: {cfg.student.mode}")
        print(f"    Model: {cfg.student.model}")
        print(f"    Device: {cfg.student.device}")
        print(f"    Max new tokens: {cfg.student.max_new_tokens}")
        print(f"    Temperature: {cfg.student.temperature}")
        print(f"    Top-p: {cfg.student.top_p}")
        
        # Check expected values
        if cfg.student.mode != "local":
            print(f"    [WARNING]  Expected mode to be 'local', got: {cfg.student.mode}")
            return False
        
        if "TinyLlama" not in cfg.student.model:
            print(f"    [WARNING]  Expected TinyLlama model, got: {cfg.student.model}")
            return False
        
        if cfg.student.device not in ["auto", "cuda", "cpu"]:
            print(f"    [WARNING]  Unexpected device: {cfg.student.device}")
            return False
        
        print("    [OK] Student configuration correct")
        
        # Verify memory configuration
        print("\n[4/5] Verifying memory configuration...")
        print(f"    Encoder: {cfg.memory.encoder}")
        print(f"    Dimension: {cfg.memory.dim}")
        print(f"    Index path: {cfg.memory.index_path}")
        print(f"    Store path: {cfg.memory.store_path}")
        print(f"    K (top-k): {cfg.memory.k}")
        
        # Check expected values
        if cfg.memory.encoder != "all-MiniLM-L6-v2":
            print(f"    [WARNING]  Expected encoder to be 'all-MiniLM-L6-v2', got: {cfg.memory.encoder}")
            return False
        
        if cfg.memory.k != 5:
            print(f"    [WARNING]  Expected k=5, got: {cfg.memory.k}")
            return False
        
        if cfg.memory.dim != 384:
            print(f"    [WARNING]  Expected dimension=384, got: {cfg.memory.dim}")
            return False
        
        print("    [OK] Memory configuration correct")
        
        # Verify secrets
        print("\n[5/5] Verifying secrets/API keys...")
        print(f"    Provider: {secrets.provider}")
        print(f"    API key present: {bool(secrets.api_key)}")
        if secrets.base_url:
            print(f"    Base URL: {secrets.base_url}")
        
        if not secrets.api_key:
            print("    [FAIL] API key is missing!")
            return False
        
        if secrets.provider != cfg.teacher.providers[0].provider:
            print(f"    [WARNING]  Secret provider ({secrets.provider}) doesn't match teacher provider ({cfg.teacher.providers[0].provider})")
            return False
        
        print("    [OK] Secrets configured correctly")
        
        # Success summary
        print("\n" + "=" * 70)
        print("[OK] Configuration Verification PASSED")
        print("=" * 70)
        print("Summary:")
        print(f"  Teacher: {cfg.teacher.providers[0].provider}/{cfg.teacher.providers[0].model}")
        print(f"  Student: {cfg.student.mode}/{cfg.student.model} on {cfg.student.device}")
        print(f"  Memory: {cfg.memory.encoder} (k={cfg.memory.k})")
        print(f"  API Key: Present for {secrets.provider}")
        print("=" * 70)
        
        return True
        
    except Exception as e:
        print(f"\n[FAIL] Verification FAILED with exception:")
        print(f"    Type: {type(e).__name__}")
        print(f"    Message: {str(e)}")
        logger.error(f"Config verification failed: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = verify_config()
    sys.exit(0 if success else 1)
