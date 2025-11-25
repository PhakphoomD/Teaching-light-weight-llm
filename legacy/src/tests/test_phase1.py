"""
Phase 1 - Comprehensive Integration Test

This script runs all Phase 1 tests:
1. Local Student Model (TinyLlama)
2. Teacher Model (Gemini)  
3. Gemini-2.5 Models Support
4. Configuration Verification
5. .env Loader
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import subprocess


def run_test(test_name: str, script_path: str) -> bool:
    """Run a test script and return success status."""
    print(f"\n{'='*70}")
    print(f"Running: {test_name}")
    print(f"{'='*70}\n")
    
    result = subprocess.run(
        [sys.executable, script_path],
        capture_output=False,
        text=True
    )
    
    return result.returncode == 0


def main():
    """Run all Phase 1 tests."""
    print("=" * 70)
    print("PHASE 1 - COMPREHENSIVE INTEGRATION TEST")
    print("=" * 70)
    
    tests = [
        ("Test 1: Local Student Model", "src/tests/test_student.py"),
        ("Test 2: Teacher Model", "src/tests/test_teacher.py"),
        ("Test 3: Gemini-2.5 Support", "src/tests/test_gemini25.py"),
        ("Test 4: Configuration", "src/tests/test_config.py"),
        ("Test 5: .env Loader", "src/tests/test_env_loader.py"),
    ]
    
    results = {}
    
    for test_name, script_path in tests:
        success = run_test(test_name, script_path)
        results[test_name] = success
    
    # Print summary
    print("\n" + "=" * 70)
    print("PHASE 1 TEST SUMMARY")
    print("=" * 70)
    
    all_passed = True
    for test_name, success in results.items():
        status = "[OK] PASSED" if success else "[FAIL] FAILED"
        print(f"{status} - {test_name}")
        if not success:
            all_passed = False
    
    print("=" * 70)
    
    if all_passed:
        print("\n  ALL PHASE 1 TESTS PASSED!  ")
        print("\nPhase 1 Complete - Baseline Integration Verified")
        print("\nReady for Phase 2:")
        print("  - Data pipeline implementation")
        print("  - Teacher-Student interaction loop")
        print("  - Hints generation & distillation")
        print("\n" + "=" * 70)
        return 0
    else:
        print("\n[FAIL] SOME TESTS FAILED")
        print("\nPlease review failed tests above")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
