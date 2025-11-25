# 🔄 System Flow Analysis - Teaching LLM Project

## 📊 Overall Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         run_loop()                               │
│                    (refinement/loop.py)                          │
│                                                                   │
│  Main orchestrator - loops through refinement rounds            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Calls 3 stages in order:
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│ StudentStage  │    │ TeacherStage  │    │ MemoryStage   │
│               │    │               │    │               │
│ Generates     │───▶│ Evaluates &   │───▶│ Stores wrong  │
│ answer        │    │ Creates hint  │    │ attempts      │
└───────────────┘    └───────────────┘    └───────────────┘
```

---

## 🎓 STUDENT STAGE - Detail Flow

```
StudentStage.process()
    │
    ├─▶ 1. Retrieve context from memory (if not first round)
    │      │
    │      └─▶ MemoryRetrievalPlugin
    │            │
    │            ├─▶ Route by task & structure
    │            ├─▶ Search FAISS index (k=3)
    │            ├─▶ Filter by hard negatives
    │            └─▶ Return top-k relevant records
    │
    ├─▶ 2. Build prompt
    │      │
    │      └─▶ build_prompt() from prompts/student.py
    │            │
    │            ├─▶ First attempt:
    │            │   "Answer the following question directly..."
    │            │   [Question]
    │            │   ⚠️ Context DISABLED (commented out)
    │            │
    │            └─▶ Refinement (round 2+):
    │                "You are refining your answer..."
    │                "Your previous answer was: [previous_answer]"
    │                "Feedback: [hints combined]"
    │                [Question]
    │
    └─▶ 3. Generate answer
           │
           └─▶ GeneratorPlugin
                 │
                 ├─▶ Call LLM (Gemini/TinyLlama)
                 │   - temperature=0.0 (deterministic)
                 │   - max_tokens=128 (force brevity)
                 │
                 └─▶ Return: {answer, tokens, latency, context_used}
```

**Key Points:**
- ✅ `previous_answer` is passed and used in prompts
- ⚠️ Memory context is **DISABLED** (commented out in student.py line 101-107)
- 🔄 Hints are concatenated in prompt: "Feedback: hint1\n\nhint2\n\nhint3"

---

## 👨‍🏫 TEACHER STAGE - Detail Flow

```
TeacherStage.process()
    │
    ├─▶ 1. Evaluate & Generate Hint (COMBINED!)
    │      │
    │      └─▶ EvaluatorPlugin.evaluate_and_hint()
    │            │
    │            ├─▶ Call critic.evaluate() → CriticFeedback
    │            │     │
    │            │     └─▶ HybridCritic.evaluate()
    │            │           │
    │            │           ├─▶ 1. Rule-based evaluation
    │            │           │     │
    │            │           │     └─▶ Check:
    │            │           │         - Empty/too brief
    │            │           │         - Exact match
    │            │           │         - Token overlap (F1)
    │            │           │         - No punctuation
    │            │           │         └─▶ Returns: {score, error_keys}
    │            │           │
    │            │           ├─▶ 2. LLM evaluation (if enabled)
    │            │           │     │
    │            │           │     └─▶ LLMEvaluator.evaluate()
    │            │           │           │
    │            │           │           ├─▶ Build prompt with COT
    │            │           │           ├─▶ Call Gemini
    │            │           │           └─▶ Parse JSON response
    │            │           │                 → {issues, fixes, lesson}
    │            │           │
    │            │           ├─▶ 3. Merge feedback
    │            │           │     │
    │            │           │     └─▶ _merge_feedback()
    │            │           │           │
    │            │           │           ├─▶ If LLM available:
    │            │           │           │   - issues: rule_keys + LLM issues
    │            │           │           │   - fixes: LLM fixes (filtered)
    │            │           │           │   - lesson: LLM lesson (filtered)
    │            │           │           │
    │            │           │           └─▶ If LLM UNAVAILABLE:
    │            │           │               ❌ OLD: fixes = error_keys (raw)
    │            │           │               ✅ NEW: Map error_keys to readable
    │            │           │                   - "wrong_answer" → "Your answer is incorrect..."
    │            │           │                   - "no_punctuation" → "Add proper punctuation..."
    │            │           │                   - etc.
    │            │           │
    │            │           └─▶ 4. Calibrate stop_score
    │            │                 │
    │            │                 └─▶ sigmoid(a * combined_score + b)
    │            │                     → Returns: CriticFeedback
    │            │
    │            └─▶ ⚠️ BUILD HINT HERE (evaluator.py lines 117-135)
    │                  │
    │                  ├─▶ Build hint from CriticFeedback:
    │                  │   hint_parts = []
    │                  │   if issues:
    │                  │       "Your answer has issues:"
    │                  │       "  1. [issue1]"
    │                  │       "  2. [issue2]"
    │                  │   if fixes:
    │                  │       "How to improve:"
    │                  │       "  - [fix1]"
    │                  │       "  - [fix2]"
    │                  │
    │                  ├─▶ Filter leakage
    │                  ├─▶ Truncate if too long
    │                  └─▶ Return hint
    │
    └─▶ 2. Check early stopping (if incorrect)
           │
           └─▶ EarlyStoppingPlugin
                 │
                 ├─▶ Track stop_scores over rounds
                 ├─▶ Check patience (no improvement for N rounds)
                 └─▶ Return: should_stop
```

**🔥 CRITICAL ISSUE FOUND:**

```python
# ❌ PROBLEM: Hint is built in evaluator.py (lines 117-135)
# This uses eval_result.issues and eval_result.fixes
# BUT: These come from aggregator._merge_feedback()

# ✅ SOLUTION: The readable hints we added in aggregator.py
# ARE being used! They go into CriticFeedback.fixes
# Then evaluator.py formats them into the final hint
```

---

## 💾 MEMORY STAGE - Detail Flow

```
MemoryStage.process()
    │
    ├─▶ If answer CORRECT:
    │      └─▶ Skip storage (don't store correct answers)
    │
    └─▶ If answer INCORRECT:
           │
           ├─▶ 1. Store to memory
           │      │
           │      └─▶ StoragePlugin
           │            │
           │            ├─▶ Create compact record:
           │            │   - question, answer, feedback
           │            │   - task, structure, params
           │            │   - timestamp, score
           │            │
           │            ├─▶ Save to JSONL file
           │            │
           │            └─▶ Index in FAISS
           │                  │
           │                  ├─▶ Embed structure tokens
           │                  ├─▶ Add to vector index
           │                  └─▶ Save index to disk
           │
           └─▶ 2. Log iteration (optional)
                  │
                  └─▶ LoggerPlugin
                        │
                        └─▶ Save detailed JSON log
```

---

## 🔄 Complete Loop Flow (One Round)

```
ROUND 1:
┌─────────────────────────────────────────────────────────────┐
│ run_loop()                                                   │
│                                                              │
│ 1. StudentStage.process()                                   │
│    ├─▶ No context (first round)                            │
│    ├─▶ Prompt: "Answer this question..."                   │
│    └─▶ LLM generates: answer1                              │
│                                                              │
│ 2. TeacherStage.process()                                   │
│    ├─▶ HybridCritic.evaluate()                             │
│    │   ├─▶ Rules: score=0.61, errors=[wrong_answer]       │
│    │   ├─▶ LLM: (if available) issues, fixes, lesson      │
│    │   └─▶ Merge: fixes = ["Your answer is incorrect..."] │
│    │                                                        │
│    └─▶ EvaluatorPlugin builds hint:                        │
│        "Your answer has issues:                            │
│          1. Wrong answer                                   │
│         How to improve:                                    │
│          - Your answer is incorrect. Please reconsider..." │
│                                                              │
│ 3. MemoryStage.process()                                    │
│    ├─▶ Answer incorrect → Store                            │
│    ├─▶ Save to store.jsonl                                 │
│    └─▶ Index in FAISS                                      │
│                                                              │
│ 4. Add hint to hints list                                   │
│    hints = [hint1]                                          │
└─────────────────────────────────────────────────────────────┘

ROUND 2:
┌─────────────────────────────────────────────────────────────┐
│ run_loop()                                                   │
│                                                              │
│ 1. StudentStage.process()                                   │
│    ├─▶ Retrieve from memory (k=3)                          │
│    │   └─▶ Found 1 similar record                          │
│    ├─▶ Prompt: "You are refining...                        │
│    │          Your previous answer was: answer1            │
│    │          Feedback: [hint1]"                           │
│    └─▶ LLM generates: answer2                              │
│                                                              │
│ 2. TeacherStage.process()                                   │
│    └─▶ ... (same flow)                                     │
│                                                              │
│ 3. MemoryStage.process()                                    │
│    └─▶ ... (store if still incorrect)                      │
│                                                              │
│ 4. Check early stopping                                     │
│    └─▶ If no improvement for 2 rounds → STOP              │
└─────────────────────────────────────────────────────────────┘
```

---

## ⚡ Key Data Structures

### CriticFeedback (from HybridCritic)
```python
{
    "issues": [
        "Wrong answer",           # Humanized error key
        "Missing punctuation"     # Humanized error key
    ],
    "fixes": [
        "Your answer is incorrect. Please reconsider the question.",
        "Add proper punctuation at the end of your answer."
    ],
    "lesson": "Your answer needs improvement. Please address the feedback above.",
    "error_keys": ["wrong_answer", "no_punctuation"],
    "scores": {
        "rule": 0.61,
        "llm": 0.75,  # If LLM available
        "overall": 0.68
    },
    "stop_score": 0.65  # Calibrated
}
```

### Hint Format (built by evaluator.py)
```
Your answer has issues:
  1. Wrong answer
  2. Missing punctuation
How to improve:
  - Your answer is incorrect. Please reconsider the question.
  - Add proper punctuation at the end of your answer.
```

---

## 🐛 BUG ANALYSIS

### ❌ What You Thought Was Happening:
```
aggregator.py builds hints from error_keys → Used directly in hint
```

### ✅ What's Actually Happening:
```
aggregator.py: error_keys → _merge_feedback() → CriticFeedback.fixes
                                                        │
                                                        ▼
evaluator.py: CriticFeedback.fixes → Build hint string → Final hint
```

### 🔧 Where Your Fix IS Working:
**aggregator.py lines 448-472** ✅
```python
# This code IS being used!
if rule_error_keys:
    readable_hints = []
    for key in rule_error_keys:
        if key == "wrong_answer":
            readable_hints.append("Your answer is incorrect...")
        # ... more mappings
    fixes = readable_hints  # ← Goes into CriticFeedback
```

### 📍 Where Hint Is Actually Built:
**evaluator.py lines 117-135** ✅
```python
# This code formats the hint
hint_parts = []
if eval_result.issues:  # From CriticFeedback
    hint_parts.append("Your answer has issues:")
    for i, issue in enumerate(eval_result.issues, 1):
        hint_parts.append(f"  {i}. {issue}")

if eval_result.fixes:  # From CriticFeedback.fixes (YOUR readable hints!)
    hint_parts.append("\nHow to improve:")
    for fix in eval_result.fixes:
        hint_parts.append(f"  - {fix}")  # ← YOUR readable hints used here!

hint = "\n".join(hint_parts)
```

---

## ✅ CONCLUSION

**Your readable hints ARE working!** 

The flow is:
1. ✅ `aggregator._merge_feedback()` converts error_keys → readable messages → `CriticFeedback.fixes`
2. ✅ `evaluator.evaluate_and_hint()` formats `CriticFeedback.fixes` → final hint string
3. ✅ Final hint goes to student in next round

**What we saw in logs:**
```
Hint: Your answer has issues: 1. Wrong answer 2. Missing punctuation 
How to improve: - Your answer is incorrect. Please reconsider the question. 
- Add proper punctuation at the end of your answer.
```

This is **correct**! Your mapping is working. The hints are readable.

**Issues in logs you mentioned:**
- Some hints show error_keys → This happens when there's NO issue found, uses generic fallback
- "low_overlap" not mapped → Need to add this key to the mapping

---

## 🎯 What to Fix

1. ✅ **Readable hints** - WORKING (your code is used)
2. ⚠️ **Add mapping for "low_overlap"** - Need to add to aggregator.py
3. ⚠️ **Memory context disabled** - Currently commented out in student.py

---

## 📝 Settings & Configs

**Key Settings (from SETTINGS):**
- `evaluator.temperature`: 0.1
- `evaluator.max_tokens`: 256
- `evaluator.hint_max_length`: 500 (hints truncated if longer)
- `teacher.early_stopping.tau`: 0.85 (correct threshold)
- `teacher.early_stopping.patience`: 2 (rounds without improvement)

**Current Config (custom.yml):**
- `student_model`: gemini-2.0-flash-lite (quota exhausted)
- `teacher_model`: gemini-2.0-flash-lite
- `student_temperature`: 0.0
- `student_max_tokens`: 128
- `llm_reviewer.enabled`: false (disabled due to quota)
- `max_rounds`: 5
- `early_stopping`: true
