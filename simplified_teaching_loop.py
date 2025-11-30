"""
Simplified Teaching Loop - Main Orchestration System

This module implements the core orchestration logic for an iterative teaching system
designed to improve small, budget-friendly language models through feedback and memory.

The system addresses the challenge of achieving high accuracy with smaller models
(e.g., Llama 3.1 8B, Gemini Flash) by providing iterative feedback and learning from
past successful teaching interactions.

Key Features:
1. Minimal prompt engineering optimized for small models with limited context windows
2. Multi-metric evaluation combining deterministic and LLM-based scoring
3. FAISS-based semantic memory for retrieving similar successful teaching experiences
4. Intelligent early stopping with patience-based monitoring starting from round 2
5. Comprehensive logging with fixed-width formatting and debug capabilities

System Architecture:
- SimplifiedTeachingLoop: Main orchestrator coordinating all components
- StudentClient: Generates answers using minimal, clear prompts
- MetricsEvaluator: Scores answers using hybrid deterministic + LLM judges
- TeacherFeedback: Generates actionable teaching feedback via chain-of-thought
- FAISSMemory: Stores and retrieves successful teaching strategies
- EarlyStopping: Monitors progress and prevents unnecessary iterations
- PerformanceMonitor: Tracks metrics across all questions

Typical Usage:
    from simplified_teaching_loop import SimplifiedTeachingLoop
    
    # Initialize with configuration
    loop = SimplifiedTeachingLoop(config_path="config/simplified_config.yml")
    
    # Run teaching loop on a question
    result = loop.run(
        question="What is the capital of France?",
        ground_truth="Paris",
        max_rounds=3
    )
    
    # Check results
    print(f"Success: {result['success']}")
    print(f"Rounds: {result['num_rounds']}")
    print(f"Final answer: {result['final_answer']}")
    print(f"Score: {result['final_score']:.3f}")
"""

import json
import time
import yaml
import os
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables (API keys, etc.)
load_dotenv()

PROMPT_STRATEGY_MAP: Dict[str, Tuple[str, str]] = {
    "minimal": ("initial_draft", "refine_with_teacher"),
    "structured": ("structured_first", "structured_refine"),
    "reflective": ("reflective_first", "reflective_refine"),
    "principle": ("initial_draft", "principle_rewrite"),
}

DEFAULT_PROMPT_KEYS = ("first_attempt", "refinement")

# Import core components for the teaching loop system
from src.simplified.student import StudentClient, build_first_attempt_prompt, build_refinement_prompt
from src.prompts.student import build_ground_truth_hint_prompt
from src.simplified.metrics import MetricsEvaluator  # Hybrid scoring system with deterministic + LLM judges
from src.simplified.teacher_feedback import TeacherFeedback  # Chain-of-thought feedback generation
from src.simplified.memory import FAISSMemory
from src.simplified.early_stopping import EarlyStopping
from src.simplified.logger import RoundLogger
from src.simplified.monitor import PerformanceMonitor
from src.eval.metrics import semantic_similarity
from src.simplified.debug_logger import DebugLogger
from src.simplified.terminal_ui import TerminalUI, format_error_summary


class SimplifiedTeachingLoop:
    """
    Main orchestrator for the iterative teaching loop system.
    
    This class coordinates all components to iteratively improve small language model
    responses through evaluation, feedback generation, and memory-based learning from
    past successful teaching interactions.
    
    Core Design Principles:
    - Minimal prompts (3-4 lines max) optimized for small models with limited capacity
    - Hybrid evaluation combining deterministic metrics with LLM-based judges
    - Semantic memory system ranking by success rate, quality score, and usage frequency
    - Progressive early stopping starting from round 2 to avoid false positives
    - Comprehensive logging with both console output and structured JSONL files
    - Repetition detection with ground truth hints as a fallback recovery mechanism
    
    Teaching Loop Workflow:
    1. Search memory for similar successful teaching experiences
    2. Generate student answer using retrieved memory feedback or from scratch
    3. Evaluate answer with multiple metrics (exact match, ROUGE-L, semantic similarity, LLM judges)
    4. If evaluation passes threshold, update memory and return success
    5. If evaluation fails, generate teaching feedback via chain-of-thought reasoning
    6. Check for early stopping conditions (patience exhausted or plateau reached)
    7. Detect repetition loops and trigger ground truth hint if student is stuck
    8. Repeat until success, maximum rounds reached, or early stop triggered
    """
    
    def __init__(self, config_path: str = "config/simplified_config.yml"):
        """
        Initialize simplified teaching loop with configuration.
        
        Args:
            config_path: Path to YAML configuration file
        """
        # Load configuration from YAML file
        self.config = self._load_config(config_path)
        self.project_root = Path(__file__).resolve().parent
        
        # Initialize student model client for answer generation
        self.student = StudentClient(self.config['student'])
        
        # Initialize evaluation and feedback components (separated concerns)
        self.metrics = MetricsEvaluator(self.config['teacher'])  # Hybrid scoring: deterministic + LLM judges
        self.teacher = TeacherFeedback(self.config['teacher'])   # Chain-of-thought feedback generation
        
        # Initialize memory system for storing successful teaching strategies
        self.memory = FAISSMemory(self.config['memory'])
        
        # Resolve logging directories so each experiment/phase keeps separate artifacts
        self.log_dir = self._resolve_log_dir()
        self.log_dir.mkdir(parents=True, exist_ok=True)
        logging_config = dict(self.config.get('logging', {}))
        logging_config['log_path'] = str(self.log_dir)

        # Initialize logging and monitoring systems
        self.logger = RoundLogger(logging_config)
        self.monitor = PerformanceMonitor(logging_config)
        
        # Initialize early stopping mechanism with configurable parameters
        self.early_stopping = EarlyStopping(
            patience=self.config['loop']['early_stopping']['patience'],
            min_improvement=self.config['loop']['early_stopping']['min_improvement'],
            plateau_threshold=self.config['loop']['early_stopping']['plateau_threshold'],
            start_from_round=self.config['loop']['early_stopping']['start_from_round']
        )
        
        # Initialize debug logger for detailed round-by-round analysis
        self.debug_logger = DebugLogger(base_dir=str(self.log_dir / "debug"))
        
        # Initialize terminal UI for clean, readable console output
        self.ui = TerminalUI()
    
    def _detect_repetition(self, current_answer: str, history: List[Dict[str, Any]]) -> bool:
        """
        Detect if student is stuck in repetition loop.
        
        Args:
            current_answer: Current student answer
            history: Previous rounds history
        
        Returns:
            True if repetition detected (similarity >= threshold for N consecutive rounds)
        """
        rep_config = self.config['loop'].get('repetition_detection', {})
        if not rep_config.get('enabled', False):
            return False
        
        threshold = rep_config.get('similarity_threshold', 0.95)
        consecutive = rep_config.get('consecutive_rounds', 2)
        
        if len(history) < consecutive:
            return False
        
        # Check last N answers
        recent_answers = [h['answer'] for h in history[-consecutive:]]
        
        # Calculate similarity with each recent answer
        for prev_answer in recent_answers:
            sim = semantic_similarity(
                current_answer, 
                prev_answer, 
                encoder=self.metrics.encoder
            )
            if sim < threshold:
                return False  # Not repeating
        
        # All similarities >= threshold → repetition detected
        return True
        
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def _resolve_log_dir(self) -> Path:
        """Resolve the log directory using config overrides or environment variables."""
        logging_cfg = self.config.get('logging', {})

        # Highest priority: explicit experiment directory override
        env_dir = os.environ.get('EXPERIMENT_DIR')
        if env_dir:
            return self._to_absolute_path(Path(env_dir))

        experiment_root = Path(logging_cfg.get('experiment_root', 'logs/experiments'))
        phase_name = logging_cfg.get('phase') or os.environ.get('EXPERIMENT_PHASE')
        run_name = (
            logging_cfg.get('run_name') or
            logging_cfg.get('experiment_name') or
            os.environ.get('EXPERIMENT_NAME')
        )

        if phase_name:
            target = experiment_root / phase_name
            if run_name:
                target = target / run_name
            return self._to_absolute_path(target)

        if run_name:
            return self._to_absolute_path(experiment_root / run_name)

        return self._to_absolute_path(Path(logging_cfg.get('log_path', 'logs/simplified')))

    def _to_absolute_path(self, path_obj: Path) -> Path:
        """Convert relative paths to project-root absolute paths."""
        if path_obj.is_absolute():
            return path_obj
        return (self.project_root / path_obj).resolve()
    
    def run(self, 
            question: str, 
            ground_truth: str, 
            question_id: Optional[str] = None,
            question_idx: Optional[int] = None,
            max_rounds: Optional[int] = None,
            student_first_key: Optional[str] = None,
            student_refine_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Run teaching loop for a single question.
        
        Args:
            question: The question to answer
            ground_truth: The correct answer
            question_id: Question identifier for metrics tracking (optional)
            question_idx: Question index for display (optional, 1-based)
            max_rounds: Maximum number of rounds (default from config)
        
        Returns:
            Dict with keys:
            - success: bool
            - num_rounds: int
            - final_answer: str
            - final_score: float
            - history: List[Dict] (round-by-round details)
        """
        if max_rounds is None:
            max_rounds = self.config['loop']['max_rounds']
        
        # Ensure max_rounds is set (type assertion)
        assert max_rounds is not None, "max_rounds must be set"

        # Student prompt strategy (allows experimentation with different student prompts)
        student_first_prompt_type = student_first_key or DEFAULT_PROMPT_KEYS[0]
        student_refine_prompt_type = student_refine_key or DEFAULT_PROMPT_KEYS[1]

        # Control whether any ground-truth-based "last chance" logic is allowed
        loop_cfg = self.config.get('loop', {})
        enable_last_chance = loop_cfg.get('enable_last_chance', True)
        
        history = []
        self.early_stopping.reset()
        repetition_triggered_ground_truth = False  # Track if ground truth was triggered by repetition
        
        # Track feedback for smart memory storage
        last_generated_feedback = None
        last_feedback_structured: Optional[Dict[str, Any]] = None
        last_feedback_scores = None
        feedback_used_id = None  # ID of feedback from memory that was used
        
        # Initialize debug logging for this question
        self.debug_logger.start_question(
            question_idx=question_idx or 0,
            question=question,
            ground_truth=ground_truth
        )
        
        for round_num in range(1, max_rounds + 1):
            round_start = time.time()
            
            # ==================== STEP 1: Retrieve feedback from memory (Round 1 only) ====================
            # Search semantic memory for similar questions with successful teaching feedback.
            # Only attempted on first round to test if prior teaching experience is applicable.
            # Subsequent rounds use newly generated feedback from the teacher model.
            feedback_info = None
            if round_num == 1:
                feedback_info = self.memory.get_best_feedback(question)
                if feedback_info:
                    self.debug_logger.log_warning(
                        f"Testing memory feedback from '{feedback_info['id'][:8]}...' (similarity={feedback_info.get('similarity', 0):.3f})"
                    )
            
            # ==================== STEP 2: Build student prompt based on context ====================
            # Construct appropriate prompt based on round number and student progress.
            # Three prompt types: first attempt (minimal), refinement (with feedback), or last chance (with ground truth).
            
            # Last chance configuration :
            # - enable_last_chance = True  → triggers at last 2 rounds (max_rounds - 1, max_rounds)
            # - enable_last_chance = False → no last chance, normal teaching loop
            #
            # Example: max_rounds = 6
            #   - Round 1-4: Normal teaching (FIRST/REFINE)
            #   - Round 5-6: LAST_CHANCE with ground_truth (if enable_last_chance=True)
            #
            # Formula: ground_truth_hint_round = max_rounds - 1 (starts 2 rounds before end)
            ground_truth_hint_round = max_rounds - 1  # e.g., 6-1=5, so rounds 5,6 get ground_truth
            
            # Detect if student is stuck in a repetition loop (N consecutive similar answers)
            use_ground_truth = False
            rep_config = self.config['loop'].get('repetition_detection', {})
            consecutive_rounds = rep_config.get('consecutive_rounds', 3)
            
            if round_num >= consecutive_rounds + 1 and history and len(history) >= consecutive_rounds:
                # Analyze recent answer history to detect repetition loops
                # This prevents the student from getting stuck generating the same incorrect answer repeatedly
                recent_answers = [h['answer'] for h in history[-consecutive_rounds:]]
                rep_threshold = rep_config.get('similarity_threshold', 0.98)
                
                # Calculate pairwise similarity between consecutive answers
                # All pairs must exceed threshold to confirm true repetition (not just similar, but stuck)
                all_similar = True
                for i in range(len(recent_answers) - 1):
                    sim = semantic_similarity(
                        recent_answers[i],
                        recent_answers[i + 1],
                        encoder=self.metrics.encoder
                    )
                    if sim < rep_threshold:
                        all_similar = False
                        break
                
                if all_similar:
                    # Repetition loop confirmed - student is unable to escape pattern
                    self.debug_logger.log_warning(
                        f"Round {round_num}: REPETITION LOOP DETECTED "
                        f"({consecutive_rounds} consecutive similar answers, threshold={rep_threshold})"
                    )
                    if (
                        enable_last_chance
                        and rep_config.get('trigger_ground_truth', True)
                        and not repetition_triggered_ground_truth
                    ):
                        self.debug_logger.log_warning("Triggering GROUND TRUTH HINT as 'last chance'")
                        use_ground_truth = True
                        repetition_triggered_ground_truth = True
            
            # Select appropriate prompt mode based on round context and progress
            mode = "FIRST"
            if enable_last_chance and (use_ground_truth or (round_num >= ground_truth_hint_round and history and not history[-1]['passed'])):
                # Last resort: provide ground truth hint as final recovery mechanism
                # Triggered by repetition detection or reaching max rounds without success
                mode = "LAST_CHANCE"
                reason = "repetition detected" if use_ground_truth else "max rounds reached"
                previous_answer = history[-1]['answer'] if history else ""
                prompt = build_ground_truth_hint_prompt(question, ground_truth, previous_answer)
            elif round_num == 1:
                # Initial attempt: leverage memory if similar successful experience exists
                mode = "FIRST"
                if feedback_info:
                    # Apply previously successful feedback from semantic memory
                    prompt = build_refinement_prompt(
                        question=question, 
                        previous_answer="-", 
                        feedback=feedback_info['feedback'],
                        prompt_type=student_refine_prompt_type,
                        no_feedback_prompt_type=student_refine_prompt_type,
                    )
                else:
                    # No relevant memory - start with minimal, clean prompt
                    prompt = build_first_attempt_prompt(
                        question,
                        prompt_type=student_first_prompt_type,
                    )
            else:
                # Refinement rounds: apply feedback generated from previous evaluation
                # Memory feedback is only tested in round 1; subsequent rounds use fresh teacher feedback
                mode = "REFINE"
                previous_answer = history[-1]['answer']
                # Extract feedback that was generated by the teacher in the previous round
                teacher_critique = None
                teacher_improvements = None
                principle_critique = None
                principle_improvements = None
                feedback_text = None
                if last_feedback_structured:
                    feedback_text = last_feedback_structured.get('feedback')
                    teacher_critique = last_feedback_structured.get('critique')
                    teacher_improvements = last_feedback_structured.get('improvements')
                    principle_critique = last_feedback_structured.get('principle_critique')
                    principle_improvements = last_feedback_structured.get('principle_improvements')
                elif history:
                    feedback_text = history[-1].get('generated_feedback', None)
                prompt = build_refinement_prompt(
                    question,
                    previous_answer,
                    feedback_text,
                    prompt_type=student_refine_prompt_type,
                    no_feedback_prompt_type=student_refine_prompt_type,
                    teacher_critique=teacher_critique,
                    teacher_improvements=teacher_improvements,
                    teacher_principle_critique=principle_critique,
                    teacher_principle_improvements=principle_improvements,
                )
            
            # ==================== STEP 3: Generate student answer ====================
            # Send constructed prompt to student model and receive answer
            student_answer = self.student.answer(prompt)
            student_raw = None  # Raw response capture reserved for future detailed analysis
            
            # ==================== STEP 4: Evaluate answer quality with hybrid metrics ====================
            # Apply multi-faceted evaluation combining deterministic metrics (ROUGE, exact match)
            # with LLM-based judges (blind assessment and comparison with ground truth)
            evaluation = self.metrics.evaluate(
                question=question,
                student_answer=student_answer,
                ground_truth=ground_truth
            )
            
            # Extract detailed evaluation information for debug logging
            metrics_debug = evaluation.get('debug_info', {})
            metrics_input_combined = "\n\n".join([f"[{label}]\n{p}" for label, p in metrics_debug.get('prompts', [])])
            metrics_responses_combined = metrics_debug.get('responses', [])
            
            # ==================== STEP 5: Determine if answer meets quality threshold ====================
            passed = evaluation['final_score'] >= self.config['teacher']['pass_threshold']
            
            round_time = time.time() - round_start
            
            # Collect flags for this round
            flags = []
            if use_ground_truth:
                flags.append("LAST_CHANCE")
            if repetition_triggered_ground_truth:
                flags.append("REPETITION")
            
            # Determine which feedback was USED in this round (for logging)
            feedback_used_this_round = None
            if round_num == 1 and feedback_info:
                # Round 1: memory feedback
                feedback_used_this_round = feedback_info['feedback']
            elif round_num > 1 and history:
                # Round 2+: feedback from previous round
                feedback_used_this_round = history[-1].get('generated_feedback', None)
            
            # ==================== STEP 6: Log round ====================
            # IMPORTANT: Copy scores dict to avoid mutation issues in history
            scores_snapshot = dict(evaluation['scores'])
            
            round_data = {
                'round': round_num,
                'answer': student_answer,
                'scores': scores_snapshot,
                'final_score': evaluation['final_score'],
                'passed': passed,
                'feedback_used': feedback_info['id'] if feedback_info else None,
                'memory_used': feedback_info is not None,  # Track if memory was used
                'memory_id': feedback_info['id'] if feedback_info else None,
                'time_ms': int(round_time * 1000),
                'mode': mode,
                'flags': flags
            }
            history.append(round_data)
            
            # Log to debug file 
            self.debug_logger.log_round(
                round_num=round_num,
                mode=mode,
                student_input=prompt,
                student_output=student_answer,
                student_raw_response=student_raw,
                teacher_input=metrics_input_combined if metrics_input_combined else None,
                teacher_output=evaluation,
                teacher_raw_response=metrics_responses_combined if metrics_responses_combined else None,
                scores=evaluation['scores'],
                feedback=feedback_used_this_round,
                memory_hits=[feedback_info] if feedback_info else [],
                flags=flags
            )
            
            self.logger.log_round(
                round_num=round_num,
                question=question,
                answer=student_answer,
                scores=evaluation['scores'],
                passed=passed,
                feedback_id=feedback_info['id'] if feedback_info else None,
                time_ms=round_data['time_ms']
            )
            
            # Accumulate metrics for visualization
            # Store feedback that was USED in this round (from memory or previous round)
            if question_id:
                used_feedback = feedback_info['feedback'] if feedback_info else None
                self.logger.accumulate_metrics(
                    question_id=question_id,
                    round_num=round_num,
                    scores=evaluation['scores'],
                    answer=student_answer,
                    passed=passed,
                    teacher_feedback=used_feedback
                )
            
            # ==================== STEP 7: If passed, stop ====================
            if passed:
                # Update memory ONLY if we used memory feedback in Round 1 and it worked
                if round_num == 1 and feedback_info:
                    # Memory feedback worked on first try! 🎉
                    self.memory.update_success(
                        record_id=feedback_info['id'],
                        success=True,
                        final_score=evaluation['final_score']
                    )
                    self.debug_logger.log_warning(
                        f"Memory feedback from '{feedback_info['id'][:8]}...' worked! (similarity={feedback_info.get('similarity', 0):.3f})"
                    )
                # If passed in Round 2+ → means teacher's new feedback worked
                # Save it as new record (it's better than memory feedback)
                elif round_num > 1 and last_generated_feedback:
                    self.memory.store(
                        question=question,
                        feedback=last_generated_feedback,
                        scores=last_feedback_scores if last_feedback_scores else evaluation['scores'],
                        final_score=evaluation['final_score'],
                        attempts=round_num
                    )
                    self.debug_logger.log_warning(
                        f"Saved successful feedback to memory ({round_num} rounds, score={evaluation['final_score']:.3f})"
                    )
                # If passed without memory feedback (Round 1, no memory) → don't save
                # (student figured it out naturally)
                
                # Log question end to debug file
                self.debug_logger.end_question(
                    passed=True,
                    total_rounds=round_num,
                    final_score=evaluation['final_score'],
                    stop_reason="PASSED"
                )
                
                result = {
                    'success': True,
                    'num_rounds': round_num,
                    'final_answer': student_answer,
                    'final_score': evaluation['final_score'],
                    'history': history
                }
                self.monitor.record_result(result)
                return result
            
            # ==================== STEP 8: Generate new feedback (if needed) ====================
            # Use memory feedback only in round 1; from round 2 onward,
            # refine based on the latest teacher-generated feedback.
            if round_num == 1 and feedback_info:
                prev_feedback_arg = feedback_info['feedback']
            else:
                prev_feedback_arg = last_generated_feedback

            feedback_result = self.teacher.generate_feedback(
                question=question,
                student_answer=student_answer,
                ground_truth=ground_truth,
                previous_feedback=prev_feedback_arg,
                round_num=round_num,  # Pass round number for special handling
                return_debug=True
            )
            
            # Extract feedback text and debug info
            if isinstance(feedback_result, dict):
                new_feedback = feedback_result.get('feedback', '')
                feedback_prompt = feedback_result.get('prompt', None)
                feedback_response = feedback_result.get('response', None)
                last_feedback_structured = feedback_result
            else:
                new_feedback = feedback_result
                feedback_prompt = None
                feedback_response = None
                last_feedback_structured = None
            
            round_data['generated_feedback'] = new_feedback
            round_data['teacher_critique'] = (last_feedback_structured or {}).get('critique') if last_feedback_structured else None
            round_data['teacher_improvements'] = (last_feedback_structured or {}).get('improvements') if last_feedback_structured else None
            round_data['teacher_principle_critique'] = (last_feedback_structured or {}).get('principle_critique') if last_feedback_structured else None
            round_data['teacher_principle_improvements'] = (last_feedback_structured or {}).get('principle_improvements') if last_feedback_structured else None
            round_data['teacher_score'] = (last_feedback_structured or {}).get('score') if last_feedback_structured else None
            round_data['teacher_stop_flag'] = (last_feedback_structured or {}).get('stop_flag') if last_feedback_structured else None
            
            # Update debug log with feedback generation info
            if feedback_prompt:
                self.debug_logger.add_feedback_generation_to_last_round(
                    prompt=feedback_prompt,
                    response=feedback_response,
                    feedback=new_feedback
                )
            
            # ==================== STEP 9: Track feedback (but don't save yet) ====================
            # Store feedback in memory ONLY if it helps student pass
            # For now, just track the last generated feedback
            last_generated_feedback = new_feedback  # Always string now
            last_feedback_scores = dict(evaluation['scores'])  # Copy to avoid mutation
            if feedback_info:
                feedback_used_id = feedback_info['id']  # Track which memory feedback failed
            
            # ==================== STEP 10: Early stopping check (with ground truth trick) ====================
            if self.config['loop']['early_stopping']['enabled']:
                should_stop = self.early_stopping.check(
                    round_num=round_num,
                    score=evaluation['final_score']
                )
                
                if should_stop:
                    self.debug_logger.log_warning(f"Early stopping triggered at round {round_num} (no improvement for {self.early_stopping.patience} rounds)")
                    
                    # TRICK: Give one last chance with ground truth hint
                    rep_config = self.config['loop'].get('repetition_detection', {})
                    if rep_config.get('trigger_ground_truth', True) and not repetition_triggered_ground_truth:
                        self.debug_logger.log_warning(f"Giving ONE LAST CHANCE with ground truth hint...")
                        
                        # Force one more round with ground truth
                        round_num_last = round_num + 1
                        if round_num_last <= max_rounds:
                            round_start_last = time.time()
                            
                            # Build ground truth prompt
                            previous_answer = history[-1]['answer']
                            prompt_last = build_ground_truth_hint_prompt(question, ground_truth, previous_answer)
                            
                            # Student answers
                            student_answer_last = self.student.answer(prompt_last)
                            student_raw_last = None
                            
                            # Metrics evaluates
                            evaluation_last = self.metrics.evaluate(
                                question=question,
                                student_answer=student_answer_last,
                                ground_truth=ground_truth
                            )
                            
                            passed_last = evaluation_last['final_score'] >= self.config['teacher']['pass_threshold']
                            round_time_last = time.time() - round_start_last
                            
                            # IMPORTANT: Copy scores to avoid mutation issues
                            scores_last_snapshot = dict(evaluation_last['scores'])
                            
                            # Log last chance round
                            flags_last = ["LAST_CHANCE", "EARLY_STOP"]
                            round_data_last = {
                                'round': round_num_last,
                                'answer': student_answer_last,
                                'scores': scores_last_snapshot,
                                'final_score': evaluation_last['final_score'],
                                'passed': passed_last,
                                'feedback_used': None,
                                'time_ms': int(round_time_last * 1000),
                                'mode': 'LAST_CHANCE',
                                'flags': flags_last
                            }
                            history.append(round_data_last)
                            
                            # Log to debug file
                            self.debug_logger.log_round(
                                round_num=round_num_last,
                                mode='LAST_CHANCE',
                                student_input=prompt_last,
                                student_output=student_answer_last,
                                student_raw_response=student_raw_last,
                                teacher_input=None,
                                teacher_output=evaluation_last,
                                teacher_raw_response=None,
                                scores=scores_last_snapshot,
                                feedback=None,
                                memory_hits=[],
                                flags=flags_last
                            )
                            
                            self.logger.log_round(
                                round_num=round_num_last,
                                question=question,
                                answer=student_answer_last,
                                scores=scores_last_snapshot,
                                passed=passed_last,
                                feedback_id=None,
                                time_ms=round_data_last['time_ms']
                            )
                            
                            if question_id:
                                self.logger.accumulate_metrics(
                                    question_id=question_id,
                                    round_num=round_num_last,
                                    scores=scores_last_snapshot,
                                    answer=student_answer_last,
                                    passed=passed_last,
                                    teacher_feedback=None
                                )
                            
                            # Check if last chance worked
                            if passed_last:
                                # ==================== Memory Save Logic for LAST_CHANCE ====================
                                # Save ground_truth as feedback! This is the "correct answer" feedback.
                                # This helps future similar questions because student learned the answer format.
                                ground_truth_feedback = f"The correct answer is: {ground_truth}"
                                self.memory.store(
                                    question=question,
                                    feedback=ground_truth_feedback,
                                    scores=scores_last_snapshot,
                                    final_score=evaluation_last['final_score'],
                                    attempts=round_num_last
                                )
                                self.debug_logger.log_warning(
                                    f"Saved GROUND_TRUTH as feedback to memory ({round_num_last} rounds, score={evaluation_last['final_score']:.3f})"
                                )
                                
                                self.debug_logger.end_question(
                                    passed=True,
                                    total_rounds=round_num_last,
                                    final_score=evaluation_last['final_score'],
                                    stop_reason="LAST_CHANCE_SUCCESS"
                                )
                                result = {
                                    'success': True,
                                    'num_rounds': round_num_last,
                                    'final_answer': student_answer_last,
                                    'final_score': evaluation_last['final_score'],
                                    'history': history
                                }
                                self.monitor.record_result(result)
                                return result
                            else:
                                self.debug_logger.log_warning(f"Last chance failed (score: {evaluation_last['final_score']:.3f})")
                    
                    self.debug_logger.log_warning(f"Stopping after {len(history)} rounds")
                    break
        
        # ==================== Failed after max rounds ====================
        stop_reason = "MAX_ROUNDS" if len(history) >= max_rounds else "EARLY_STOP"
        
        # ==================== STEP 11: Save feedback to memory (ONLY if failed) ====================
        # Only save if we generated new feedback and it didn't come from memory
        # OR if memory feedback failed (so we have better feedback to save)
        if last_generated_feedback and history:
            # Save the last generated feedback as a new learning experience
            self.memory.store(
                question=question,
                feedback=last_generated_feedback,
                scores=last_feedback_scores if last_feedback_scores else history[-1]['scores'],
                final_score=history[-1]['final_score'],
                attempts=len(history)  # Total attempts made
            )
            self.debug_logger.log_warning(
                f"Saved failed attempt to memory ({len(history)} rounds, score={history[-1]['final_score']:.3f})"
            )
        
        self.debug_logger.end_question(
            passed=False,
            total_rounds=len(history),
            final_score=history[-1]['final_score'],
            stop_reason=stop_reason
        )
        
        result = {
            'success': False,
            'num_rounds': len(history),
            'final_answer': history[-1]['answer'],
            'final_score': history[-1]['final_score'],
            'history': history
        }
        self.monitor.record_result(result)
        return result
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Get performance statistics across all questions."""
        return self.monitor.get_report()
    
    def save_performance_report(self, output_path: Optional[str] = None):
        """Save performance report to JSON file."""
        report = self.get_performance_report()
        if output_path is None:
            output_path = str(self.log_dir / 'performance_report.json')
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\n[OK] Performance report saved to: {output_path}")


def main():
    """Main entry point for testing."""
    # Example usage
    loop = SimplifiedTeachingLoop(config_path="config/simplified_config.yml")
    
    # Test questions
    test_cases = [
        {
            "question": "What is the capital of France?",
            "ground_truth": "Paris"
        },
        {
            "question": "Separate words: helloworld",
            "ground_truth": "hello world"
        },
        {
            "question": "What is 2 + 2?",
            "ground_truth": "4"
        }
    ]
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n{'#'*80}")
        print(f"# Test Case {i}/{len(test_cases)}")
        print(f"{'#'*80}")
        
        result = loop.run(
            question=case['question'],
            ground_truth=case['ground_truth'],
            max_rounds=3
        )
        
        print(f"\nResult: {'[OK]' if result['success'] else '[FAIL]'}")
        print(f"Rounds: {result['num_rounds']}")
        print(f"Final Score: {result['final_score']:.3f}")
    
    # Save performance report
    loop.save_performance_report("logs/simplified/performance_report.json")
    
    # Print summary
    report = loop.get_performance_report()
    print(f"\n{'='*80}")
    print("FINAL SUMMARY")
    print(f"{'='*80}")
    print(f"Success Rate: {report['success_rate']*100:.1f}%")
    print(f"Avg Rounds: {report['avg_rounds']:.2f}")
    print(f"Total Questions: {report['total_questions']}")


if __name__ == "__main__":
    main()
