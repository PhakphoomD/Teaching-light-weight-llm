# Appendix: Prompt Templates, Memory System & Code Snippets

This appendix provides detailed documentation of the core components used in our Teaching-Loop system for improving lightweight LLMs.

---

## A. Prompt Templates

### A.1 Student Prompts

#### A.1.1 Initial Draft Prompt (First Attempt)
Used when the student generates an answer for the first time without any prior feedback.

```text
You are the Student model.

[Task]
{question}

Produce your best possible answer to the task.
Be clear, concise, and avoid making up facts.

Output:
Draft:
<your answer>
```

#### A.1.2 Refinement Prompt (ORCA-Style)
Used in subsequent rounds when the student receives Teacher's critique and improvement suggestions.

```text
You are the Student model.

[Task]
{question}

[Previous Answer]
{previous_answer}

[Teacher Critique]
{teacher_critique}

[Teacher Improvements]
{teacher_improvements}

Your job:
- Generate a new improved answer.
- Follow all Teacher Improvements exactly.
- Fix every issue mentioned in the Critique.
- Do NOT introduce unsupported information.

Output:
Refined_Answer:
<your improved answer>
```

---

### A.2 Teacher Prompts

#### A.2.1 ORCA-Style Critique Prompt
Teacher evaluates the student's answer and provides structured feedback.

```text
You are the Teacher model.

[Task]
{question}

[Target Answer]
{ground_truth}

[Student Answer]
{student_answer}

Your job is to evaluate the student's answer.

1. Critique:
  - Point out factual errors, missing reasoning steps, and unclear parts.
  - Be concrete and concise.

2. Score:
  - Give an overall quality score from 0 to 100.

3. Improvements:
  - Provide step-by-step instructions for how the student should improve the answer.
  - Do NOT rewrite the whole answer.

Output format:
Critique:
- ...

Improvements:
1) ...
2) ...
3) ...
```

---

### A.3 Evaluation Judge Prompts

#### A.3.1 Blind Judge Prompt
Evaluates answer quality WITHOUT seeing the ground truth (unbiased assessment).

```text
You are an evaluator. Rate the quality of this answer WITHOUT seeing the correct answer.

Question: {question}
Student's answer: {student_answer}

Evaluation criteria:
1. RELEVANCE: Does the answer address the question? (most important)
2. COHERENCE: Is it clear and well-structured?
3. COMPLETENESS: Does it provide sufficient information?
4. CORRECTNESS: Based on your knowledge, is it factually accurate?

Rating scale (0.0 to 1.0):
- 1.0 = Excellent answer (relevant, coherent, complete, accurate)
- 0.8-0.9 = Good answer (minor issues but generally correct)
- 0.6-0.7 = Acceptable (relevant but incomplete or unclear)
- 0.4-0.5 = Poor (partially relevant or has errors)
- 0.0-0.3 = Very poor (irrelevant, incoherent, or wrong)

Output ONLY a number between 0.0 and 1.0. No explanation.

Score:
```

#### A.3.2 Comparison Judge Prompt
Compares student's answer with ground truth (semantic comparison).

```text
You are an evaluator. Compare student's answer with the reference answer.

Question: {question}
Reference answer: {ground_truth}
Student's answer: {student_answer}

CRITICAL RULES - Focus on MEANING, not FORMAT:
1. If student's answer has the SAME MEANING → 0.9-1.0
   - Different wording is OK (e.g., "dog" = "canine")
   - Different format is OK (e.g., "Paris" = "The capital is Paris")
   - Different order is OK (e.g., "A and B" = "B and A")
2. Extra information is OK if core meaning is correct
3. Only penalize if FACTS/MEANING are wrong or missing

Rating scale (0.0 to 1.0):
- 1.0 = Same meaning, may have different words/format/order
- 0.9 = Same meaning with minor extra/missing details
- 0.7-0.8 = Mostly correct but missing important parts
- 0.5-0.6 = Partially correct (some right, some wrong)
- 0.0-0.4 = Wrong meaning or irrelevant

Output ONLY a number between 0.0 and 1.0. No explanation.

Score:
```

---

## B. Memory System (FAISS-based Semantic Memory)

### B.1 Memory Schema

Each memory record stores a successful teaching experience:

```json
{
    "id": "abc123def456",
    "question": "What are the symptoms of Woolly hair syndrome?",
    "teaching_feedback": "1. Include all symptoms from HPO...\n2. Add frequency percentages...",
    "attempts": 5,
    "success_count": 3,
    "success_rate": 0.60,
    "scores": {
        "exact_match": 0.0,
        "rouge_l": 0.14,
        "semantic_sim": 0.81,
        "blind_score": 0.85,
        "comparison_score": 0.90,
        "final": 0.78
    },
    "timestamp": "2025-11-30T02:51:17"
}
```

### B.2 Memory Retrieval Algorithm

The system retrieves feedback using smart ranking:

```python
def get_best_feedback(self, question: str) -> Optional[Dict[str, Any]]:
    """
    Get best feedback for a question using smart ranking.
    
    Ranking criteria (in order):
    1. Similarity >= threshold (0.75)
    2. Success rate >= min_success_rate (0.3)
    3. Higher success rate preferred
    4. Higher final score preferred
    5. More attempts preferred (proven feedback)
    """
    # Search for similar questions using FAISS
    results = self.search(question, k=self.top_k)
    
    if not results:
        return None
    
    # Filter by similarity threshold
    candidates = [
        (rid, score) for rid, score in results 
        if score >= self.similarity_threshold
    ]
    
    # Filter by minimum success rate
    valid_candidates = []
    for rid, sim_score in candidates:
        record = self._id_to_record.get(rid)
        if record:
            sr = record.get('success_rate', 0.0)
            if sr >= self.min_success_rate:
                valid_candidates.append((record, sim_score))
    
    # Rank by: success_rate, final_score, attempts, similarity
    valid_candidates.sort(
        key=lambda x: (
            x[0].get('success_rate', 0.0),
            x[0].get('scores', {}).get('final', 0.0),
            x[0].get('attempts', 0),
            x[1]  # similarity
        ),
        reverse=True
    )
    
    return best_candidate
```

### B.3 Memory Storage Strategy

```python
def store(self, question: str, feedback: str, scores: Dict, final_score: float):
    """
    Store new feedback or update existing record.
    
    Strategy:
    - If similarity >= 0.8 (similar question exists): UPDATE existing record
    - If similarity < 0.8 (new question): CREATE new record
    - Only update feedback if new score is BETTER than existing
    """
    similar_records = self.search(question, k=1)
    
    if similar_records and similar_records[0][1] >= 0.8:
        # Similar enough → Update existing record
        existing_id = similar_records[0][0]
        record = self._id_to_record[existing_id]
        
        old_score = record['scores'].get('final', 0.0)
        record['attempts'] += 1
        
        # Only update feedback if new score is better
        if final_score > old_score:
            record['teaching_feedback'] = feedback
            record['scores'] = scores
    else:
        # Different question → Create new record
        record_id = self._generate_id(question)
        
        # Generate embedding and add to FAISS index
        emb = self._compute_embedding(question)
        self.index.add(emb.reshape(1, -1))
        
        # Store record
        self._id_to_record[record_id] = {
            'id': record_id,
            'question': question,
            'teaching_feedback': feedback,
            'attempts': 1,
            'success_count': 0,
            'success_rate': 0.0,
            'scores': scores
        }
```

---

## C. Core System Code Snippets

### C.1 Teaching Loop Main Orchestration

```python
class SimplifiedTeachingLoop:
    """
    Main orchestrator for the iterative teaching loop system.
    
    Core Design Principles:
    - Minimal prompts optimized for small models (3-4 lines max)
    - Hybrid evaluation: deterministic metrics + LLM-based judges
    - Semantic memory ranking by success rate, quality, and frequency
    - Progressive early stopping starting from round 2
    - Repetition detection with ground truth hints as fallback
    """
    
    def run(self, question: str, ground_truth: str, max_rounds: int = 8):
        """Run teaching loop for a single question."""
        
        history = []
        self.early_stopping.reset()
        
        for round_num in range(1, max_rounds + 1):
            
            # STEP 1: Retrieve feedback from memory (Round 1 only)
            feedback_info = None
            if round_num == 1:
                feedback_info = self.memory.get_best_feedback(question)
            
            # STEP 2: Build appropriate prompt
            if round_num == 1:
                if feedback_info:
                    # Apply memory feedback
                    prompt = build_refinement_prompt(
                        question=question,
                        previous_answer="-",
                        feedback=feedback_info['feedback']
                    )
                else:
                    # Start fresh
                    prompt = build_first_attempt_prompt(question)
            else:
                # Use feedback from previous round
                prompt = build_refinement_prompt(
                    question=question,
                    previous_answer=history[-1]['answer'],
                    feedback=last_generated_feedback
                )
            
            # STEP 3: Generate student answer
            student_answer = self.student.answer(prompt)
            
            # STEP 4: Evaluate with hybrid metrics
            evaluation = self.metrics.evaluate(
                question=question,
                student_answer=student_answer,
                ground_truth=ground_truth
            )
            
            # STEP 5: Check if passed
            passed = evaluation['final_score'] >= self.config['pass_threshold']
            
            if passed:
                # Update memory with successful feedback
                self.memory.update_success(feedback_info['id'], success=True)
                return {'success': True, 'rounds': round_num}
            
            # STEP 6: Generate teacher feedback for next round
            last_generated_feedback = self.teacher.generate_feedback(
                question=question,
                student_answer=student_answer,
                ground_truth=ground_truth
            )
            
            # STEP 7: Check early stopping
            if self.early_stopping.should_stop(evaluation['final_score']):
                break
        
        return {'success': False, 'rounds': round_num}
```

### C.2 Hybrid Scoring System

```python
class MetricsEvaluator:
    """
    Hybrid scoring combining deterministic metrics with LLM-based judges.
    
    Components:
    1. Exact Match (0.0 or 1.0)
    2. ROUGE-L (0.0 to 1.0)
    3. Semantic Similarity (0.0 to 1.0) - using sentence embeddings
    4. Blind Judge Score (0.0 to 1.0) - LLM evaluation without ground truth
    5. Comparison Judge Score (0.0 to 1.0) - LLM comparison with ground truth
    
    Final Score = weighted combination of all metrics
    """
    
    def evaluate(self, question: str, student_answer: str, ground_truth: str):
        # Deterministic metrics
        exact = exact_match(student_answer, ground_truth)
        rouge = rouge_l_score(student_answer, ground_truth)
        semantic = semantic_similarity(student_answer, ground_truth)
        
        # LLM-based judges
        blind = self._call_blind_judge(question, student_answer)
        comparison = self._call_comparison_judge(question, student_answer, ground_truth)
        
        # Weighted final score
        weights = self.config['scoring_weights']
        final_score = (
            weights['exact_match'] * exact +
            weights['rouge_l'] * rouge +
            weights['semantic_sim'] * semantic +
            weights['blind_judge'] * blind +
            weights['comparison_judge'] * comparison
        )
        
        return {
            'scores': {
                'exact_match': exact,
                'rouge_l': rouge,
                'semantic_sim': semantic,
                'blind_score': blind,
                'comparison_score': comparison,
                'final': final_score
            },
            'final_score': final_score,
            'passed': final_score >= self.pass_threshold
        }
```

### C.3 Early Stopping Mechanism

```python
class EarlyStopping:
    """
    Progressive early stopping with patience-based monitoring.
    
    Features:
    - Starts monitoring from round 2 (avoids false positives in round 1)
    - Tracks best score and improvement delta
    - Stops if no improvement for N consecutive rounds (patience)
    - Detects score plateaus
    """
    
    def __init__(self, patience=3, min_improvement=0.01, plateau_threshold=0.005):
        self.patience = patience
        self.min_improvement = min_improvement
        self.plateau_threshold = plateau_threshold
    
    def should_stop(self, current_score: float, round_num: int) -> bool:
        # Don't stop before round 2
        if round_num < self.start_from_round:
            return False
        
        # Check improvement
        improvement = current_score - self.best_score
        
        if improvement >= self.min_improvement:
            # Improvement detected - reset counter
            self.best_score = current_score
            self.rounds_without_improvement = 0
            return False
        else:
            # No significant improvement
            self.rounds_without_improvement += 1
            
            # Check if patience exhausted
            if self.rounds_without_improvement >= self.patience:
                return True
        
        return False
```

---

## D. Example Teaching Loop Execution

### D.1 Sample Debug Log Entry

```json
{
    "run_timestamp": "20251130_025117",
    "question_idx": 1,
    "question": "What are the symptoms of Woolly hair syndrome?",
    "ground_truth": "Fine hair 90%, Woolly hair 90%, Hypopigmentation 50%...",
    
    "round": 1,
    "mode": "FIRST",
    
    "student_input": "You are the Student model...\n[Task]\nWhat are the symptoms...",
    "student_output": "Refined_Answer:\n\nWoolly hair syndrome includes:\n1. Fine hair...",
    
    "teacher_input": "[blind_judge]...\n[comparison_judge]...",
    "teacher_output": {
        "scores": {
            "exact_match": 0.0,
            "rouge_l": 0.12,
            "semantic_sim": 0.75,
            "blind_score": 0.9,
            "comparison_score": 0.7,
            "final": 0.71
        },
        "passed": false
    },
    
    "feedback": "1. Include all symptoms from HPO...\n2. Add percentages..."
}
```

### D.2 Score Progression Example

| Round | Mode   | Score  | Passed | Memory Hit |
|-------|--------|--------|--------|------------|
| 1     | FIRST  | 0.714  | ❌     | None       |
| 2     | REFINE | 0.780  | ❌     | -          |
| 3     | REFINE | 0.792  | ❌     | -          |
| 4     | REFINE | 0.786  | ❌     | -          |
| 5     | REFINE | 0.790  | ❌     | -          |
| 6     | REFINE | 0.786  | ❌     | -          |
| 7     | REFINE | 0.785  | ❌     | -          |
| 8     | REFINE | 0.781  | ❌     | -          |

**Analysis**: Score plateaued around 0.78-0.79, indicating the student model's knowledge ceiling for this medical domain question.

---

## E. Configuration Reference

### E.1 Key Parameters

```yaml
# Loop Configuration
loop:
  max_rounds: 8
  early_stopping:
    patience: 3
    min_improvement: 0.01
    start_from_round: 2
  repetition_detection:
    enabled: true
    similarity_threshold: 0.98
    consecutive_rounds: 3

# Memory Configuration
memory:
  embedding_model: "all-MiniLM-L6-v2"
  similarity_threshold: 0.75
  top_k: 5
  min_success_rate: 0.3

# Scoring Weights
teacher:
  pass_threshold: 0.80
  scoring_weights:
    exact_match: 0.10
    rouge_l: 0.15
    semantic_sim: 0.25
    blind_judge: 0.20
    comparison_judge: 0.30
```

---

*Document generated for thesis appendix - Teaching Lightweight LLMs Project*
