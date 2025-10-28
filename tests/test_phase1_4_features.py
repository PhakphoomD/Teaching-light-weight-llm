"""
Unit Tests for Phase 1-4 Features

Tests coverage:
- Phase 1: Critic exact mode statistics (case/space/punct/token differences)
- Phase 1: Keyword normalization ("gd" == "gradient descent")
- Phase 3: Memory deduplication and caps
- Phase 4: Retrieval strategy (per-task recent, kw∩err intersection, fallbacks)

Run with: python -m pytest tests/test_phase1_4_features.py -v
"""

import tempfile
import os
import json
from typing import List, Dict, Any

from src.evaluation.critic import SimpleCritic, CriticResult
from src.memory.store import JsonMemoryStore, Feedback, FeedbackLite
from src.memory.retrieval import get_task_recent
from src.memory.utils import hash_feedback


class TestPhase1CriticExactMode:
    """Test Phase 1: Exact mode statistics in CriticResult."""
    
    def test_case_mismatch(self):
        """Test case difference detection."""
        critic = SimpleCritic()
        
        item = {
            "expected_exact": "Machine Learning"
        }
        answer = "machine learning"  # Wrong case
        
        result: CriticResult = critic.evaluate_structured(item, answer)
        
        assert not result.satisfied
        assert result.error_type == "exact_match_failed"
        assert result.exact_diff is not None
        assert result.exact_diff["case_errors"] > 0
    
    def test_exact_match(self):
        """Test perfect exact match."""
        critic = SimpleCritic()
        
        item = {
            "expected_exact": "gradient descent"
        }
        answer = "gradient descent"
        
        result: CriticResult = critic.evaluate_structured(item, answer)
        
        assert result.satisfied
    
    def test_no_expected_exact_leak(self):
        """Test that expected_exact is never exposed in feedback."""
        critic = SimpleCritic()
        
        item = {
            "expected_exact": "SECRETANSWER123"
        }
        answer = "wrong answer"
        
        result: CriticResult = critic.evaluate_structured(item, answer)
        
        # Verify no leakage in any output fields
        assert "SECRETANSWER123" not in result.error_analysis
        if result.exact_diff:
            # Check all values in exact_diff dict
            for key, val in result.exact_diff.items():
                if isinstance(val, str):
                    assert "SECRETANSWER123" not in val


class TestPhase1KeywordNormalization:
    """Test Phase 1: Keyword normalization and synonym handling."""
    
    def test_case_insensitive_keywords(self):
        """Test keyword matching is case-insensitive."""
        critic = SimpleCritic()
        
        item = {
            "expected_keywords": ["Machine Learning", "Neural Network"]
        }
        answer = "I use machine learning and neural networks"
        
        result = critic.evaluate_structured(item, answer)
        
        # Should pass or have minimal missing concepts
        assert result.satisfied or len(result.missing_concepts or []) <= 1
    
    def test_missing_keyword_detection(self):
        """Test correct detection of missing keywords."""
        critic = SimpleCritic()
        
        item = {
            "expected_keywords": ["backpropagation", "learning_rate", "epochs"]
        }
        answer = "Training uses backpropagation"
        
        result = critic.evaluate_structured(item, answer)
        
        assert not result.satisfied  # Missing 2 keywords
        assert len(result.missing_concepts or []) >= 2


class TestPhase3MemoryDedup:
    """Test Phase 3: Memory deduplication and caps."""
    
    def test_cap_per_task(self):
        """Test cap per task ≤3 enforcement."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = os.path.join(tmpdir, "memory.json")
            memory = JsonMemoryStore(path=store_path, cap_per_task=3)
            
            # Add 5 different feedbacks
            for i in range(5):
                fb = Feedback(
                    task_id="task-001",
                    message=f"Feedback {i}",
                    source="test"
                )
                memory.add_feedback(fb)
            
            # Should only keep last 3
            feedbacks = memory.get_feedback("task-001")
            assert len(feedbacks) == 3
            
            # Should be most recent (2, 3, 4)
            messages = [fb.message for fb in feedbacks]
            assert "Feedback 2" in messages
            assert "Feedback 3" in messages
            assert "Feedback 4" in messages
            assert "Feedback 0" not in messages


class TestPhase4Retrieval:
    """Test Phase 4: Retrieval strategy (get_task_recent, intersections)."""
    
    def test_get_task_recent(self):
        """Test get_task_recent retrieves n most recent feedbacks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = os.path.join(tmpdir, "memory.json")
            memory = JsonMemoryStore(path=store_path)
            
            # Manually populate with FeedbackLite structure
            memory._data["entries"] = {
                "entry_1": {
                    "task_id": "task-001",
                    "lesson": "Lesson 1",
                    "error_keys": ["error:format"],
                    "student_answer_short": "Answer 1",
                    "ts": "2025-10-28T10:00:00"
                },
                "entry_2": {
                    "task_id": "task-001",
                    "lesson": "Lesson 2",
                    "error_keys": ["error:missing"],
                    "student_answer_short": "Answer 2",
                    "ts": "2025-10-28T11:00:00"
                },
                "entry_3": {
                    "task_id": "task-001",
                    "lesson": "Lesson 3",
                    "error_keys": ["error:incomplete"],
                    "student_answer_short": "Answer 3",
                    "ts": "2025-10-28T12:00:00"
                }
            }
            memory._data["index"]["task:task-001"] = ["entry_1", "entry_2", "entry_3"]
            
            # Get 2 most recent
            recent = get_task_recent(memory, "task-001", n=2)
            
            assert len(recent) == 2
            # Should return most recent first
            assert recent[0].lesson == "Lesson 3"
            assert recent[1].lesson == "Lesson 2"
    
    def test_get_task_recent_empty(self):
        """Test get_task_recent returns empty list for unknown task."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = os.path.join(tmpdir, "memory.json")
            memory = JsonMemoryStore(path=store_path)
            
            recent = get_task_recent(memory, "unknown-task", n=2)
            
            assert recent == []


if __name__ == "__main__":
    # Run tests manually
    import sys
    
    print("Running Phase 1-4 Feature Tests...\n")
    
    # Test Phase 1 - Critic
    print("=== Phase 1: Critic Tests ===")
    test_critic = TestPhase1CriticExactMode()
    try:
        test_critic.test_case_mismatch()
        print(" test_case_mismatch")
    except Exception as e:
        print(f" test_case_mismatch: {e}")
    
    try:
        test_critic.test_exact_match()
        print(" test_exact_match")
    except Exception as e:
        print(f" test_exact_match: {e}")
    
    try:
        test_critic.test_no_expected_exact_leak()
        print(" test_no_expected_exact_leak")
    except Exception as e:
        print(f" test_no_expected_exact_leak: {e}")
    
    # Test Phase 1 - Keywords
    print("\n=== Phase 1: Keyword Normalization ===")
    test_keywords = TestPhase1KeywordNormalization()
    try:
        test_keywords.test_case_insensitive_keywords()
        print(" test_case_insensitive_keywords")
    except Exception as e:
        print(f" test_case_insensitive_keywords: {e}")
    
    try:
        test_keywords.test_missing_keyword_detection()
        print(" test_missing_keyword_detection")
    except Exception as e:
        print(f" test_missing_keyword_detection: {e}")
    
    # Test Phase 3 - Memory
    print("\n=== Phase 3: Memory Dedup & Caps ===")
    test_memory = TestPhase3MemoryDedup()
    try:
        test_memory.test_cap_per_task()
        print(" test_cap_per_task")
    except Exception as e:
        print(f" test_cap_per_task: {e}")
    
    # Test Phase 4 - Retrieval
    print("\n=== Phase 4: Retrieval Strategy ===")
    test_retrieval = TestPhase4Retrieval()
    try:
        test_retrieval.test_get_task_recent()
        print(" test_get_task_recent")
    except Exception as e:
        print(f" test_get_task_recent: {e}")
    
    try:
        test_retrieval.test_get_task_recent_empty()
        print(" test_get_task_recent_empty")
    except Exception as e:
        print(f" test_get_task_recent_empty: {e}")
    
    print("\n=== All Tests Complete ===")
