"""
Phase 0 - Environment Readiness Test
Tests that both TinyLlama (local) and GeminiClient (API) can be imported and initialized.
"""

from dotenv import load_dotenv
load_dotenv()

from src.providers.local_client import LocalTinyLlama
from src.providers.gemini_client import GeminiClient

print("=" * 70)
print("Phase 0 - Environment Readiness Test")
print("=" * 70)

# Test 1: Import and initialize LocalTinyLlama
print("\n[1/2] Testing LocalTinyLlama (TinyLlama local inference)...")
try:
    local_client = LocalTinyLlama(model="TinyLlama/TinyLlama-1.1B-Chat-v1.0")
    print(f"    [OK] LocalTinyLlama initialized")
    print(f"    [OK] Model: {local_client.model_id}")
    print(f"    [OK] Device: {local_client.device}")
except Exception as e:
    print(f"    [FAIL] Error: {e}")
    exit(1)

# Test 2: Import and initialize GeminiClient
print("\n[2/2] Testing GeminiClient (Google Gemini API)...")
try:
    gemini_client = GeminiClient(model="gemini-2.0-flash-lite")
    print(f"    [OK] GeminiClient initialized")
    print(f"    [OK] Model: {gemini_client.model_name}")
    print(f"    [OK] Rate limits: RPM={gemini_client.limits['RPM']}, TPM={gemini_client.limits['TPM']}, RPD={gemini_client.limits['RPD']}")
except Exception as e:
    print(f"    [FAIL] Error: {e}")
    exit(1)

print("\n" + "=" * 70)
print("[OK] All tests passed! Environment is ready for Phase 1.")
print("=" * 70)
