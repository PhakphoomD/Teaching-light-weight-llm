"""
Phase 1 - Test Gemini-2.5 Models Support

This script verifies that GeminiClient can work with Gemini-2.5 models
and correctly reads limits from MODEL_LIMITS.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.providers.gemini_client import GeminiClient
from src.providers.constants import get_model_limits, list_available_models
from src.core.logger import get_logger
from dotenv import load_dotenv
import os

# Load .env before anything else
load_dotenv()

logger = get_logger("test.gemini25")


def test_gemini_25_support():
    """Test that GeminiClient supports Gemini-2.5 models."""
    print("=" * 70)
    print("Phase 1 - Testing Gemini-2.5 Models Support")
    print("=" * 70)
    
    try:
        # Check available models
        print("\n[1/4] Checking available models in constants...")
        available_models = list_available_models()
        print(f"    Available models: {available_models}")
        
        # Check Gemini-2.5 models
        gemini_25_models = [m for m in available_models if "2.5" in m]
        if not gemini_25_models:
            print("    [FAIL] No Gemini-2.5 models found in MODEL_LIMITS")
            return False
        
        print(f"    [OK] Found {len(gemini_25_models)} Gemini-2.5 models:")
        for model in gemini_25_models:
            limits = get_model_limits(model)
            print(f"       - {model}: RPM={limits['RPM']}, TPM={limits['TPM']}, RPD={limits['RPD']}")
        
        # Test initialization with each Gemini-2.5 model
        print(f"\n[2/4] Testing GeminiClient initialization...")
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            print("    [WARNING]  GOOGLE_API_KEY not found in environment")
            print("    Skipping actual API initialization")
            return True  # Still pass the limits check
        
        for model in gemini_25_models:
            print(f"\n    Testing {model}...")
            try:
                client = GeminiClient(model=model, api_key=api_key)
                print(f"       [OK] Client initialized successfully")
                print(f"       [OK] Model name: {client.model_name}")
                print(f"       [OK] Limits loaded: RPM={client.limits['RPM']}, TPM={client.limits['TPM']}, RPD={client.limits['RPD']}")
            except Exception as e:
                print(f"       [FAIL] Initialization failed: {e}")
                return False
        
        # Verify limits are correctly stored
        print(f"\n[3/4] Verifying limits are correctly stored...")
        test_model = "gemini-2.5-flash-lite"
        expected_limits = get_model_limits(test_model)
        client = GeminiClient(model=test_model, api_key=api_key)
        
        if client.limits != expected_limits:
            print(f"    [FAIL] Limits mismatch!")
            print(f"       Expected: {expected_limits}")
            print(f"       Got: {client.limits}")
            return False
        
        print(f"    [OK] Limits correctly stored in client instance")
        
        # Test that unknown models get default limits
        print(f"\n[4/4] Testing fallback for unknown models...")
        unknown_model = "gemini-unknown-model"
        client = GeminiClient(model=unknown_model, api_key=api_key)
        print(f"    [OK] Unknown model handled: {client.model_name}")
        print(f"    [OK] Default limits applied: RPM={client.limits['RPM']}, TPM={client.limits['TPM']}, RPD={client.limits['RPD']}")
        
        # Success summary
        print("\n" + "=" * 70)
        print("[OK] Gemini-2.5 Models Support Test PASSED")
        print("=" * 70)
        print(f"Supported Gemini-2.5 models: {len(gemini_25_models)}")
        for model in gemini_25_models:
            print(f"  - {model}")
        print("=" * 70)
        
        return True
        
    except Exception as e:
        print(f"\n[FAIL] Test FAILED with exception:")
        print(f"    Type: {type(e).__name__}")
        print(f"    Message: {str(e)}")
        logger.error(f"Gemini-2.5 support test failed: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = test_gemini_25_support()
    sys.exit(0 if success else 1)
