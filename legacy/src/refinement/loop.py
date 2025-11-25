"""
Refinement Loop - Orchestrator Only

Minimal orchestration loop that delegates to stages:
- TeacherStage: Evaluate + Hint + Early stopping
- StudentStage: Generate answer with context
- MemoryStage: Store + Log

Original: 1408 lines (mixed business logic)
Refactored: ~200 lines (pure orchestration)
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import uuid
from pathlib import Path

from .teacher.stage import TeacherStage
from .student.stage import StudentStage
from .memory.stage import MemoryStage
from .settings import SETTINGS
from src.core.logger import get_logger

logger = get_logger("refinement.loop")


def run_loop(
    question: str,
    config: Dict[str, Any],
    teacher_stage: TeacherStage,
    student_stage: StudentStage,
    memory_stage: MemoryStage,
    experiment_id: Optional[str] = None,
    question_id: Optional[str] = None,
    correct_answer: Optional[str] = None
) -> Dict[str, Any]:
    """
    Orchestrate refinement loop.
    
    Flow for each round:
    1. Student generates answer (with context from memory)
    2. Teacher evaluates + generates hint
    3. Memory stores (if incorrect) + logs
    4. Check stop conditions
    
    Args:
        question: Question text
        config: Experiment configuration
        teacher_stage: TeacherStage instance
        student_stage: StudentStage instance
        memory_stage: MemoryStage instance
        experiment_id: Experiment ID (optional)
        question_id: Question ID (optional)
        correct_answer: Ground truth (optional)
    
    Returns:
        {
            'question_id': str,
            'question': str,
            'initial_answer': str,
            'final_answer': str,
            'success': bool,
            'num_rounds': int,
            'iterations': list
        }
    """
    # Generate IDs if not provided
    if experiment_id is None:
        experiment_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    if question_id is None:
        question_id = str(uuid.uuid4())[:8]
    
    # Config
    max_rounds = config.get("max_rounds", 5)
    verbose = config.get("verbose", True)
    
    if verbose:
        logger.info(f"\n{'='*60}")
        logger.info(f"Starting run_loop: {question}")
        logger.info(f"Experiment: {experiment_id}, Question: {question_id}")
        logger.info(f"Max rounds: {max_rounds}")
        logger.info(f"{'='*60}")
    
    # Track state
    iterations = []
    hints = []
    initial_answer = None
    final_answer = None
    previous_answer = None  # Track previous attempt for feedback loop
    success = False
    
    # Main refinement loop
    for round_num in range(1, max_rounds + 1):
        if verbose:
            logger.info(f"\n{'='*60}")
            logger.info(f"Round {round_num}/{max_rounds}")
            logger.info(f"{'='*60}")
        
        # ===== Step 1: Student generates answer =====
        if verbose:
            logger.info("Step 1: Student generating answer...")
        
        student_result = student_stage.process(
            question=question,
            hints=hints,
            iteration=round_num,
            previous_answer=previous_answer  # Pass previous attempt for learning
        )
        
        answer = student_result["answer"]
        if round_num == 1:
            initial_answer = answer
        final_answer = answer
        
        # Store for next round
        previous_answer = answer
        
        if verbose:
            logger.info(f"Answer: {answer}")
        
        # ===== Step 2: Teacher evaluates + generates hint =====
        if verbose:
            logger.info("Step 2: Teacher evaluating...")
        
        teacher_result = teacher_stage.process(
            question=question,
            student_answer=answer,
            correct_answer=correct_answer,
            iteration=round_num
        )
        
        if verbose:
            logger.info(f"Evaluation: {teacher_result['evaluation']}")
            logger.info(f"Stop score: {teacher_result['stop_score']:.2f}")
            if not teacher_result['is_correct']:
                logger.info(f"Hint: {teacher_result['hint']}")
        
        # ===== Step 3: Memory stores + logs =====
        if verbose:
            logger.info("Step 3: Memory processing...")
        
        memory_stage.process(
            question=question,
            student_answer=answer,
            evaluation=teacher_result,
            experiment_id=experiment_id,
            question_id=question_id,
            round_num=round_num
        )
        
        # ===== Track iteration =====
        iterations.append({
            "round": round_num,
            "answer": answer,
            "evaluation": teacher_result["evaluation"],
            "hint": teacher_result["hint"],
            "stop_score": teacher_result["stop_score"],
            "context_used": student_result["context_used"],
            "tokens": student_result["tokens_used"],
            "latency_ms": student_result["latency_ms"]
        })
        
        # ===== Step 4: Check stop conditions =====
        
        # Condition 1: Correct answer
        if teacher_result["is_correct"]:
            if verbose:
                logger.info(f"[CORRECT] Answer correct in round {round_num}")
            success = True
            break
        
        # Condition 2: Early stopping
        if teacher_result.get("should_stop", False):
            if verbose:
                logger.info(f"[EARLY STOP] Stopping at round {round_num}")
            break
        
        # Add hint for next round
        hints.append(teacher_result["hint"])
        if verbose:
            logger.info(f"Will refine with {len(hints)} hint(s)")
    
    # Build result
    result = {
        "question_id": question_id,
        "question": question,
        "initial_answer": initial_answer,
        "final_answer": final_answer,
        "success": success,
        "num_rounds": len(iterations),
        "iterations": iterations
    }
    
    if verbose:
        logger.info(f"\n{'='*60}")
        logger.info(f"Loop complete:")
        logger.info(f"  Success: {success}")
        logger.info(f"  Rounds: {len(iterations)}")
        logger.info(f"{'='*60}\n")
    
    return result
