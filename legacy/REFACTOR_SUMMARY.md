# Refactoring Summary: Separation of Concerns

## Date: 2025-11-15

## Objective
แยก **Scoring (Metrics)** ออกจาก **Teaching (Feedback)** ให้ชัดเจน

---

## Changes Made

### 1. ✅ Created `src/simplified/metrics.py` (NEW)
**Purpose:** Scoring system only

**Responsibilities:**
- Deterministic metrics: `exact_match`, `rouge_l`, `semantic_sim`
- LLM-based metrics: `blind_judge`, `comparison_judge`
- Final score calculation (weighted average)

**Key Methods:**
- `evaluate(question, student_answer, ground_truth)` → returns scores + passed + debug_info

**Import statement:**
```python
from src.simplified.metrics import MetricsEvaluator
```

---

### 2. ✅ Created `src/simplified/teacher_feedback.py` (NEW)
**Purpose:** Feedback generation only

**Responsibilities:**
- Generate teaching feedback (CoT-based)
- No scoring/evaluation logic
- Focus on helping student improve

**Key Methods:**
- `generate_feedback(question, student_answer, ground_truth, previous_feedback, round_num)` → returns feedback string

**Import statement:**
```python
from src.simplified.teacher_feedback import TeacherFeedback
```

---

### 3. ✅ Updated `simplified_teaching_loop.py`
**Changes:**
- Import `MetricsEvaluator` and `TeacherFeedback` instead of `TeacherEvaluator`
- Initialize both: `self.metrics = MetricsEvaluator(...)` and `self.teacher = TeacherFeedback(...)`
- Use `self.metrics.evaluate()` for scoring
- Use `self.teacher.generate_feedback()` for teaching
- Use `self.metrics.encoder` for similarity calculations
- Updated debug log variable names: `metrics_input_combined`, `metrics_responses_combined`

**Lines changed:**
- Line 47: Import statements
- Line 86-87: Initialize metrics + teacher
- Line 133: `self.metrics.encoder`
- Line 225: `self.metrics.encoder`
- Line 274: `self.metrics.evaluate()`
- Line 281-283: `metrics_debug`, `metrics_input_combined`, `metrics_responses_combined`
- Line 327-329: Use `metrics_input_combined` and `metrics_responses_combined` in debug log
- Line 407: `self.teacher.generate_feedback()`
- Line 467: `self.metrics.evaluate()`

---

### 4. ✅ Updated `src/simplified/__init__.py`
**Changes:**
- Updated docstring to reflect separation
- Exported `MetricsEvaluator` and `TeacherFeedback` instead of `TeacherEvaluator`

---

## Old File Status

### ⚠️ `src/simplified/teacher.py` (OLD - Can be deleted)
**Current status:** Not used anywhere in the codebase

**Verification:**
```bash
# No imports found:
grep -r "from src.simplified.teacher import TeacherEvaluator" .
# Output: No matches

# Only used in old __init__.py (now updated):
grep -r "TeacherEvaluator" .
# Output: Only in teacher.py itself and old __init__.py
```

**Safe to delete:** ✅ YES
- No files import `TeacherEvaluator` anymore
- All functionality moved to `metrics.py` + `teacher_feedback.py`
- Debug logging still captures all necessary information

---

## Debug Log Structure (After Refactoring)

### Before:
```json
{
  "teacher": {
    "input": "[blind_judge]\n...\n[comparison_judge]\n...",  // Evaluation prompts
    "output": { "scores": {...}, "final_score": 0.94 }
  }
}
```

### After (Same structure, clarified meaning):
```json
{
  "teacher": {
    "input": "[blind_judge]\n...\n[comparison_judge]\n...",  // Metrics evaluation prompts (NOT feedback)
    "output": { "scores": {...}, "final_score": 0.94 }
  }
}
```

**Note:** 
- "teacher.input" field now contains **metrics evaluation prompts** (blind_judge + comparison_judge)
- Teacher feedback generation is separate (captured in `generated_feedback` field)
- This is intentional to maintain backward compatibility with existing debug logs

---

## Benefits

### 1. **Clear Separation of Concerns**
- **Metrics:** Objective scoring (how good is the answer?)
- **Teacher:** Subjective teaching (how to improve?)

### 2. **Easier to Debug**
- Scoring issues → Check `metrics.py`
- Feedback issues → Check `teacher_feedback.py`

### 3. **More Maintainable**
- Each module has single responsibility
- Changes to scoring don't affect teaching logic
- Changes to teaching don't affect scoring logic

### 4. **Better Architecture**
```
Before:
teacher.py (838 lines)
├── evaluate() → scoring
└── generate_feedback() → teaching

After:
metrics.py (412 lines) → scoring only
teacher_feedback.py (380 lines) → teaching only
```

---

## Testing Checklist

- [x] No compile errors in refactored files
- [x] No imports of old `TeacherEvaluator`
- [ ] Run test: `python test_simplified.py --questions 2`
- [ ] Verify debug log structure unchanged
- [ ] Verify metrics scores are correct
- [ ] Verify teacher feedback generation works
- [ ] Verify memory system still functions

---

## Next Steps

1. **Test the refactored system:**
   ```bash
   conda activate tlw
   python test_simplified.py --questions 2
   ```

2. **Verify debug logs:**
   - Check `logs/simplified/debug/*.json`
   - Confirm "teacher.input" contains metrics evaluation prompts
   - Confirm "generated_feedback" contains teaching feedback

3. **If tests pass, delete old file:**
   ```bash
   # Backup first (optional)
   mv src/simplified/teacher.py src/simplified/teacher.py.backup
   
   # Or delete directly
   rm src/simplified/teacher.py
   ```

---

## Files Summary

### ✅ NEW Files
- `src/simplified/metrics.py` (412 lines)
- `src/simplified/teacher_feedback.py` (380 lines)

### ✅ MODIFIED Files
- `simplified_teaching_loop.py` (imports, initialization, method calls)
- `src/simplified/__init__.py` (exports)

### ⚠️ OLD File (Safe to delete after testing)
- `src/simplified/teacher.py` (838 lines) - No longer used

---

## Rollback Plan (If needed)

If anything goes wrong:

1. **Restore old import:**
   ```python
   from src.simplified.teacher import TeacherEvaluator
   ```

2. **Revert initialization:**
   ```python
   self.teacher = TeacherEvaluator(self.config['teacher'])
   ```

3. **Revert method calls:**
   ```python
   evaluation = self.teacher.evaluate(...)
   feedback = self.teacher.generate_feedback(...)
   ```

4. **Delete new files:**
   ```bash
   rm src/simplified/metrics.py
   rm src/simplified/teacher_feedback.py
   ```
