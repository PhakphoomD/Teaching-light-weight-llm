"""
Phase 1 - Test Local Student Model (TinyLlama)

This script tests that LocalTinyLlama can perform a single Q&A round
and verifies hardware (CPU/GPU) compatibility.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.providers.local_client import LocalTinyLlama
from src.core.logger import get_logger

logger = get_logger("test.student")


def test_local_student():
    """Test LocalTinyLlama single-shot inference."""
    print("=" * 70)
    print("Phase 1 - Testing Local Student Model (TinyLlama)")
    print("=" * 70)
    
    try:
        # Initialize student model
        print("\n[1/4] Initializing LocalTinyLlama...")
        student = LocalTinyLlama(
            model="TinyLlama/TinyLlama-1.1B-Chat-v1.0",
            device=None,  # Auto-detect CUDA/CPU
        )
        print(f"    [OK] Model initialized: {student.model_id}")
        print(f"    [OK] Device: {student.device}")
        
        # Prepare test question
        test_question = "What is the capital of France?"
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": test_question}
        ]
        
        print(f"\n[2/4] Testing tokenization...")
        print(f"    Question: {test_question}")
        
        # Perform inference
        print(f"\n[3/4] Generating answer (max_tokens=50)...")
        result = student.chat(
            messages=messages,
            temperature=0.7,
            max_tokens=50,
        )
        
        # Check result
        print(f"\n[4/4] Checking result...")
        if result.error:
            print(f"    [FAIL] Error occurred: {result.error}")
            return False
        
        if not result.text or not result.text.strip():
            print(f"    [WARNING]  Empty response received")
            return False
        
        print(f"    [OK] Generated text: {result.text[:100]}...")
        print(f"    [OK] Text length: {len(result.text)} characters")
        
        # Success summary
        print("\n" + "=" * 70)
        print("[OK] Local Student Model Test PASSED")
        print("=" * 70)
        print(f"Model: {student.model_id}")
        print(f"Device: {student.device}")
        print(f"Response length: {len(result.text)} chars")
        print("=" * 70)
        
        return True
        
    except Exception as e:
        print(f"\n[FAIL] Test FAILED with exception:")
        print(f"    Type: {type(e).__name__}")
        print(f"    Message: {str(e)}")
        logger.error(f"Student model test failed: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = test_local_student()
    sys.exit(0 if success else 1)
