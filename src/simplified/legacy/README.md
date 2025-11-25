# Legacy Files

This directory contains old implementations that have been replaced by newer, refactored versions.

## Files

### `teacher.py` (Moved on 2025-11-15)

**Original Purpose:** Combined evaluation (scoring) and feedback generation in one class.

**Why Replaced:** 
- Mixed two concerns: scoring (objective) and teaching (subjective)
- Hard to debug and maintain (838 lines)
- Confusing for users (is teacher scoring or teaching?)

**Replaced By:**
- `src/simplified/metrics.py` - Scoring system only (blind_judge, comparison_judge, deterministic metrics)
- `src/simplified/teacher_feedback.py` - Feedback generation only (CoT-based teaching)

**Verification:**
- ✅ Prompts identical (no changes to evaluation logic)
- ✅ Scores identical (same results)
- ✅ Debug logs compatible (same structure)
- ✅ Tests passing (100% success rate)

**Status:** Safe to keep as reference, but not used in production code.

---

## Restoration

If you need to restore the old implementation:

```python
# In simplified_teaching_loop.py, change:
from src.simplified.metrics import MetricsEvaluator
from src.simplified.teacher_feedback import TeacherFeedback

# Back to:
from src.simplified.legacy.teacher import TeacherEvaluator

# And change:
self.metrics = MetricsEvaluator(self.config['teacher'])
self.teacher = TeacherFeedback(self.config['teacher'])

# Back to:
self.teacher = TeacherEvaluator(self.config['teacher'])

# And change all:
self.metrics.evaluate() → self.teacher.evaluate()
self.metrics.encoder → self.teacher.encoder
```

But you probably don't want to do this. The new version is cleaner! 😊
