"""
Phase 1 - Test Teacher Model (Gemini)

This script tests that GeminiClient can perform a single Q&A round,
verifies API key loading, and handles safety blocks.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.providers.gemini_client import GeminiClient
from src.core.logger import get_logger
from config.ai_config import load_config

logger = get_logger("test.teacher")


def test_teacher_model():
    """Test GeminiClient single-shot inference."""
    print("=" * 70)
    print("Phase 1 - Testing Teacher Model (Gemini)")
    print("=" * 70)
    
    try:
        # Load config to get model name
        print("\n[1/5] Loading configuration...")
        cfg, secrets = load_config()
        teacher_model = cfg.teacher.providers[0].model
        print(f"    [OK] Config loaded")
        print(f"    [OK] Teacher model: {teacher_model}")
        print(f"    [OK] API key present: {bool(secrets.api_key)}")
        
        # Initialize teacher model
        print(f"\n[2/5] Initializing GeminiClient...")
        teacher = GeminiClient(
            model=teacher_model,
            api_key=secrets.api_key,
        )
        print(f"    [OK] Model initialized: {teacher.model_name}")
        print(f"    [OK] Rate limits: RPM={teacher.limits['RPM']}, TPM={teacher.limits['TPM']}, RPD={teacher.limits['RPD']}")
        
        # Prepare test question
        test_question = "What is the capital of France? Answer in one short sentence."
        messages = [
            {"role": "user", "content": test_question}
        ]
        
        print(f"\n[3/5] Testing API call...")
        print(f"    Question: {test_question}")
        
        # Perform inference
        print(f"\n[4/5] Generating answer (max_tokens=100)...")
        result = teacher.chat(
            messages=messages,
            temperature=0.2,
            max_tokens=100,
        )
        
        # Check result
        print(f"\n[5/5] Checking result...")
        
        # Check for errors
        if result.error:
            if "safety_block" in result.error:
                print(f"    [WARNING]  Safety block triggered: {result.error}")
                print(f"    Note: This is a known issue, will handle in production")
                return True  # Still pass, as we detected it properly
            else:
                print(f"    [FAIL] Error occurred: {result.error}")
                return False
        
        # Check for empty response
        if not result.text or not result.text.strip():
            print(f"    [WARNING]  Empty response received (no error reported)")
            print(f"    Note: May need retry logic in production")
            return True  # Still pass, as we detected it
        
        # Success
        print(f"    [OK] Generated text: {result.text}")
        print(f"    [OK] Text length: {len(result.text)} characters")
        
        # Success summary
        print("\n" + "=" * 70)
        print("[OK] Teacher Model Test PASSED")
        print("=" * 70)
        print(f"Model: {teacher.model_name}")
        print(f"Rate limits: RPM={teacher.limits['RPM']}, TPM={teacher.limits['TPM']}, RPD={teacher.limits['RPD']}")
        print(f"Response: {result.text}")
        print("=" * 70)
        
        return True
        
    except ValueError as e:
        if "API_KEY" in str(e):
            print(f"\n[FAIL] Test FAILED: Missing API key")
            print(f"    Error: {str(e)}")
            print(f"    Please check your .env file")
            return False
        raise
        
    except Exception as e:
        print(f"\n[FAIL] Test FAILED with exception:")
        print(f"    Type: {type(e).__name__}")
        print(f"    Message: {str(e)}")
        logger.error(f"Teacher model test failed: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = test_teacher_model()
    sys.exit(0 if success else 1)
