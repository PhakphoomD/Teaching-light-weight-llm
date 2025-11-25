"""
Simplified Teaching Loop Components

This package contains simplified, focused implementations for:
- Student: Minimal prompts for TinyLlama
- Metrics: Multi-metric scoring system (deterministic + LLM-based judges)
- Teacher: Feedback generation only (separated from scoring)
- Memory: FAISS-based smart retrieval
- Early Stopping: Patience-based (from round 2+)
- Logger: Fixed-width debug output
- Monitor: Performance tracking

Key separation:
- MetricsEvaluator: Scoring/evaluation (blind_judge, comparison_judge, exact_match, rouge_l, semantic_sim)
- TeacherFeedback: Teaching/feedback generation (CoT-based, actionable guidance)
"""

__all__ = [
    'StudentClient',
    'MetricsEvaluator',
    'TeacherFeedback',
    'FAISSMemory',
    'EarlyStopping',
    'RoundLogger',
    'PerformanceMonitor'
]
