"""
Simplified Metrics Module - Scoring System

Separates scoring (metrics) from teaching (teacher).
Handles both deterministic and LLM-based scoring.

Architecture:
1. Deterministic Metrics (no LLM):
   - exact_match: Binary match
   - rouge_l: Longest common subsequence
   - semantic_sim: Embedding similarity

2. LLM-based Judges:
   - blind_judge: Quality assessment WITHOUT ground truth (unbiased)
   - comparison_judge: Accuracy assessment WITH ground truth (accurate)

3. Final Score Calculation:
   - Weighted average of all metrics
   - Configurable weights per metric

Usage:
    from src.simplified.metrics import MetricsEvaluator
    
    evaluator = MetricsEvaluator(config)
    result = evaluator.evaluate(question, student_answer, ground_truth)
    
    print(f"Final Score: {result['final_score']}")
    print(f"Passed: {result['passed']}")
"""

import re
from typing import Dict, Any, Optional
from pathlib import Path
import sys

# Add project root
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import deterministic metrics from existing module
from src.eval import metrics as det_metrics
from src.providers.factory import build_client
from src.utils.prompt_loader import get_prompt_loader


class MetricsEvaluator:
    """
    Scoring system with deterministic + LLM-based metrics.
    
    Completely separate from teaching logic.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize metrics evaluator.
        
        Args:
            config: Metrics configuration dict with:
                - pass_threshold: Score threshold to pass (default: 0.8)
                - weights: Dict with metric weights
                - hybrid_scoring: Dict with blind/comparison judge config
        """
        self.config = config
        self.pass_threshold = config.get('pass_threshold', 0.8)
        
        # Metric weights (should sum to 1.0)
        DEFAULT_WEIGHTS = {
            'blind_score': 0.3,      # Blind judge (unbiased)
            'comparison_score': 0.3, # Comparison judge (accurate)
            'semantic_sim': 0.25,    # Embedding similarity
            'rouge_l': 0.10,         # Format check
            'exact_match': 0.05      # Perfect match bonus
        }
        # Extract weights from nested config structure
        metrics_config = config.get('metrics', {})
        self.weights = metrics_config.get('weights', DEFAULT_WEIGHTS)
        
        # Initialize LLM judges
        hybrid_config = config.get('hybrid_scoring', {})
        
        # Check if hybrid scoring is enabled
        if not hybrid_config.get('enabled', True):
            print("  WARNING: Hybrid scoring is DISABLED in config!")
            print("   Blind judge and comparison judge scores will be 0.0")
            self.judges_enabled = False
        else:
            self.judges_enabled = True
        
        # Blind judge (no ground truth)
        blind_cfg = hybrid_config.get('blind_judge', {})
        self.blind_judge = build_client(
            provider=blind_cfg.get('provider', 'groq'),
            model=blind_cfg.get('model', 'llama-3.1-8b-instant')
        )
        
        # Comparison judge (with ground truth)
        comp_cfg = hybrid_config.get('comparison_judge', {})
        self.comparison_judge = build_client(
            provider=comp_cfg.get('provider', 'groq'),
            model=comp_cfg.get('model', 'llama-3.3-70b-versatile')
        )
        
        # Initialize sentence encoder for semantic similarity
        try:
            from sentence_transformers import SentenceTransformer
            self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
        except ImportError:
            print("sentence-transformers not installed, semantic_similarity will be disabled")
            self.encoder = None
        
        # Debug mode
        self.debug = config.get('debug', False)
    
    def evaluate(self,
                 question: str,
                 student_answer: str,
                 ground_truth: str) -> Dict[str, Any]:
        """
        Evaluate student answer using multiple metrics.
        
        Args:
            question: The question asked
            student_answer: Student's answer
            ground_truth: Correct answer
        
        Returns:
            Dict with:
            - scores: Dict of individual metric scores
            - final_score: Weighted average
            - passed: Boolean (>= threshold)
            - debug_info: Dict with prompts/responses for logging
        """
        scores = {}
        debug_info = {
            'prompts': [],
            'responses': []
        }
        
        # ===== 1. DETERMINISTIC METRICS (No LLM) =====
        
        # 1.1 Exact Match (perfect match bonus)
        scores['exact_match'] = float(det_metrics.exact_match(
            student_answer, ground_truth
        ))
        
        # 1.2 ROUGE-L Recall (longest common subsequence)
        rouge = det_metrics.rouge_scores(student_answer, ground_truth)
        scores['rouge_l'] = rouge['rouge-l']
        
        # 1.3 Semantic Similarity (sentence embeddings)
        if self.encoder:
            scores['semantic_sim'] = det_metrics.semantic_similarity(
                student_answer, ground_truth, encoder=self.encoder
            )
        else:
            scores['semantic_sim'] = 0.0
        
        # ===== 2. LLM-BASED METRICS =====
        
        if self.judges_enabled:
            # 2.1 Blind Judge (unbiased quality assessment)
            blind_result = self._get_blind_score(question, student_answer)
            scores['blind_score'] = blind_result['score'] if blind_result['score'] is not None else 0.0
            
            if blind_result.get('prompt'):
                debug_info['prompts'].append(('blind_judge', blind_result['prompt']))
            if blind_result.get('response'):
                debug_info['responses'].append(('blind_judge', blind_result['response']))
            
            # 2.2 Comparison Judge (accurate evaluation with ground truth)
            comparison_result = self._get_comparison_score(question, student_answer, ground_truth)
            scores['comparison_score'] = comparison_result['score'] if comparison_result['score'] is not None else 0.0
            
            if comparison_result.get('prompt'):
                debug_info['prompts'].append(('comparison_judge', comparison_result['prompt']))
            if comparison_result.get('response'):
                debug_info['responses'].append(('comparison_judge', comparison_result['response']))
        else:
            # Judges disabled - set scores to 0
            scores['blind_score'] = 0.0
            scores['comparison_score'] = 0.0
        
        # ===== 3. FINAL SCORE CALCULATION =====
        
        final_score = self._compute_final_score(scores)
        scores['final'] = final_score  # Add to scores dict for logging
        
        # Check if passed
        passed = final_score >= self.pass_threshold
        
        return {
            'scores': scores,
            'final_score': final_score,
            'passed': passed,
            'debug_info': debug_info
        }
    
    def _compute_final_score(self, scores: Dict[str, float]) -> float:
        """
        Compute weighted final score from individual metrics.
        
        Args:
            scores: Dict of metric scores
        
        Returns:
            Weighted average score (0.0 to 1.0)
        """
        weighted_sum = 0.0
        total_weight = 0.0
        
        for metric, weight in self.weights.items():
            if metric in scores:
                weighted_sum += scores[metric] * weight
                total_weight += weight
        
        # Normalize by total weight (in case some metrics are missing)
        if total_weight > 0:
            return weighted_sum / total_weight
        else:
            return 0.0
    
    def _get_blind_score(self,
                        question: str,
                        student_answer: str) -> Dict[str, Any]:
        """
        Get blind judge score (no ground truth - unbiased).
        
        Evaluates answer quality based on:
        - Relevance to question
        - Coherence and clarity
        - Completeness
        - General correctness (based on judge's knowledge)
        
        Args:
            question: The question
            student_answer: Student's answer
        
        Returns:
            Dict with 'score', 'prompt', 'response'
        """
        loader = get_prompt_loader()
        prompt = loader.get_metrics_prompt(
            'blind_judge',
            question=question,
            student_answer=student_answer
        )
        
        try:
            response = self.blind_judge.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,  # Deterministic scoring
                max_tokens=10,
                timeout_s=30
            )
            
            if getattr(response, 'error', None):
                if self.debug:
                    print(f"  Blind judge error: {response.error}")
                return {'score': None, 'prompt': prompt, 'response': None}
            
            score = self._parse_score(response.text or "")
            
            if self.debug and score is not None:
                print(f"  DEBUG: Blind score = {score:.2f}")
            
            return {'score': score, 'prompt': prompt, 'response': response}
            
        except Exception as e:
            if self.debug:
                print(f"  Blind judge exception: {e}")
            return {'score': None, 'prompt': prompt, 'response': None}
    
    def _get_comparison_score(self,
                             question: str,
                             student_answer: str,
                             ground_truth: str) -> Dict[str, Any]:
        """
        Get comparison judge score (with ground truth - accurate).
        
        Compares student answer with reference answer focusing on:
        - Semantic equivalence (meaning, not format)
        - Factual correctness
        - Key information coverage
        
        Args:
            question: The question
            student_answer: Student's answer
            ground_truth: Correct answer
        
        Returns:
            Dict with 'score', 'prompt', 'response'
        """
        loader = get_prompt_loader()
        prompt = loader.get_metrics_prompt(
            'comparison_judge',
            question=question,
            student_answer=student_answer,
            ground_truth=ground_truth
        )
        
        try:
            response = self.comparison_judge.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,  # Deterministic scoring
                max_tokens=10,
                timeout_s=30
            )
            
            if getattr(response, 'error', None):
                if self.debug:
                    print(f"  Comparison judge error: {response.error}")
                return {'score': None, 'prompt': prompt, 'response': None}
            
            score = self._parse_score(response.text or "")
            
            if self.debug and score is not None:
                print(f"  DEBUG: Comparison score = {score:.2f}")
            
            return {'score': score, 'prompt': prompt, 'response': response}
            
        except Exception as e:
            if self.debug:
                print(f"  Comparison judge exception: {e}")
            return {'score': None, 'prompt': prompt, 'response': None}
    
    def _parse_score(self, text: str) -> Optional[float]:
        """
        Parse score from judge response.
        
        Args:
            text: Response text
        
        Returns:
            Score or None if parsing failed
        """
        # Try to extract first number
        match = re.search(r'(\d+\.?\d*)', text)
        if match:
            try:
                score = float(match.group(1))
                # Clamp to [0.0, 1.0]
                return max(0.0, min(1.0, score))
            except ValueError:
                pass
        return None
