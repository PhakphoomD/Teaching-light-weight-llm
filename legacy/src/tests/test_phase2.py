"""
Phase 2 - Test Critic Logic and Hint Distillation

This script tests the complete teacher-student interaction:
1. Student (TinyLlama) answers a question (potentially wrong)
2. Teacher (Gemini) evaluates and provides feedback
3. Hint distillation filters out direct answers
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from src.providers.local_client import LocalTinyLlama
from src.critic.model import TeacherCritic
from src.critic.hints import distil_hint, filter_answer_leakage
from src.prompts.student import build_student_prompt_simple
from src.core.logger import get_logger

logger = get_logger("test.phase2")


def test_critic_and_hints():
    """Test the complete critic workflow."""
    print("=" * 70)
    print("Phase 2 - Testing Critic Logic and Hint Distillation")
    print("=" * 70)
    
    # Test question
    question = "What is the capital of France?"
    correct_answer = "Paris"
    
    try:
        # Step 1: Get student's (wrong) answer
        print("\n[1/5] Getting student answer...")
        print(f"    Question: {question}")
        
        # For testing, we'll use a deliberately wrong answer
        # In real scenarios, we'd get this from TinyLlama
        student_answer = "London"  # Wrong answer for testing
        
        print(f"    Student answer: {student_answer}")
        print(f"    Expected: {correct_answer}")
        
        # Step 2: Initialize teacher critic
        print("\n[2/5] Initializing teacher critic...")
        teacher = TeacherCritic(
            provider="gemini",
            model_name="gemini-2.0-flash-lite",
            temperature=0.2,
            max_tokens=512
        )
        print(f"    [OK] Teacher initialized")
        
        # Step 3: Evaluate student answer
        print("\n[3/5] Teacher evaluating student answer...")
        result = teacher.evaluate(
            question=question,
            student_answer=student_answer,
            correct_answer=correct_answer
        )
        
        print(f"\n    Evaluation: {result.evaluation}")
        print(f"    Reasoning: {result.reasoning[:100]}...")
        print(f"    Hint: {result.hint[:100]}...")
        
        if result.error:
            print(f"    [WARNING]  Warning: {result.error}")
        
        # Check parsing
        if not result.evaluation or result.evaluation == "unknown":
            print(f"    [FAIL] Failed to parse evaluation")
            return False
        
        if not result.reasoning:
            print(f"    [WARNING]  No reasoning found")
        
        if not result.hint:
            print(f"    [WARNING]  No hint found")
        
        print(f"    [OK] Teacher evaluation complete")
        
        # Step 4: Distill hint from reasoning
        print("\n[4/5] Distilling hint from reasoning...")
        distilled_hint = distil_hint(result.reasoning)
        
        print(f"    Original reasoning length: {len(result.reasoning)} chars")
        print(f"    Distilled hint length: {len(distilled_hint)} chars")
        print(f"    Distilled hint: {distilled_hint[:150]}...")
        
        # Step 5: Check for answer leakage
        print("\n[5/5] Checking for answer leakage...")
        
        # Check if correct answer appears in hint
        hint_to_check = result.hint
        filtered_hint, has_leakage = filter_answer_leakage(
            hint=hint_to_check,
            known_answer=correct_answer
        )
        
        if has_leakage:
            print(f"    [WARNING]  Answer leakage detected!")
            print(f"    Original hint: {hint_to_check}")
            print(f"    Filtered hint: {filtered_hint}")
        else:
            print(f"    [OK] No answer leakage detected")
            print(f"    Hint is safe: {hint_to_check}")
        
        # Also check distilled hint
        _, distilled_leakage = filter_answer_leakage(
            hint=distilled_hint,
            known_answer=correct_answer
        )
        
        if distilled_leakage:
            print(f"    [WARNING]  Distilled hint contains answer!")
        else:
            print(f"    [OK] Distilled hint is clean")
        
        # Summary
        print("\n" + "=" * 70)
        print("Phase 2 Test Results")
        print("=" * 70)
        print(f"Question: {question}")
        print(f"Student Answer: {student_answer}")
        print(f"Teacher Evaluation: {result.evaluation}")
        print(f"")
        print(f"Full Response:")
        print(f"---")
        print(result.raw_text)
        print(f"---")
        print(f"")
        print(f"Parsed Fields:")
        print(f"  Evaluation: {result.evaluation}")
        print(f"  Reasoning: {result.reasoning}")
        print(f"  Hint: {result.hint}")
        print(f"")
        print(f"Hint Safety:")
        print(f"  Original hint safe: {'[OK]' if not has_leakage else '[FAIL]'}")
        print(f"  Distilled hint safe: {'[OK]' if not distilled_leakage else '[FAIL]'}")
        print("=" * 70)
        
        # Determine pass/fail
        if result.evaluation == "incorrect":
            print("\n[OK] Test PASSED - Teacher correctly identified wrong answer")
            
            if has_leakage:
                print("[WARNING]  Note: Hint contains answer - needs improvement")
                return True  # Pass but with warning
            
            return True
        else:
            print("\n[FAIL] Test FAILED - Expected 'incorrect' evaluation")
            return False
        
    except Exception as e:
        print(f"\n[FAIL] Test FAILED with exception:")
        print(f"    Type: {type(e).__name__}")
        print(f"    Message: {str(e)}")
        logger.error(f"Phase 2 test failed: {e}", exc_info=True)
        return False


def test_with_real_student():
    """Test with actual TinyLlama student answer."""
    print("\n" + "=" * 70)
    print("Bonus Test: Using Real Student Model")
    print("=" * 70)
    
    question = "What is the capital of France?"
    
    try:
        # Get real answer from TinyLlama
        print("\n[1/3] Getting answer from TinyLlama...")
        student = LocalTinyLlama(model="TinyLlama/TinyLlama-1.1B-Chat-v1.0")
        
        prompt = build_student_prompt_simple(question)
        result = student.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=50
        )
        
        student_answer = result.text.strip()
        print(f"    Student answer: {student_answer}")
        
        # Evaluate
        print("\n[2/3] Teacher evaluating...")
        teacher = TeacherCritic()
        eval_result = teacher.evaluate(question, student_answer)
        
        print(f"    Evaluation: {eval_result.evaluation}")
        print(f"    Hint: {eval_result.hint}")
        
        # Check hint
        print("\n[3/3] Checking hint safety...")
        _, has_leakage = filter_answer_leakage(eval_result.hint, "Paris")
        
        print(f"    Hint safe: {'[OK]' if not has_leakage else '[FAIL]'}")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] Bonus test failed: {e}")
        return False


if __name__ == "__main__":
    # Run main test
    success = test_critic_and_hints()
    
    # Run bonus test if main test passed
    if success:
        print("\n" + "=" * 70)
        test_with_real_student()
    
    sys.exit(0 if success else 1)
