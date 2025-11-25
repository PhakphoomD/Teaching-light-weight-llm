"""
Experiment Runner Script

This script runs teaching loop experiments based on YAML configuration files.
It supports multiple variants for systematic comparison of different approaches:
- Memory strategies (raw vs summarized)
- Retrieval settings (k=1/3/5, different embeddings)
- Chain-of-Thought (CoT) prompting
- Refinement strategies (simple, memory, adaptive)

Usage:
    # Run single experiment
    python run_experiments.py --config config/experiment_config/baseline.yml
    
    # Run all experiments
    python run_experiments.py --all
    
    # Run specific experiments
    python run_experiments.py --configs baseline memory_summary adaptive_strategy
    
    # Dry run (show what would be executed)
    python run_experiments.py --all --dry-run

Output:
    - Experiment logs: logs/experiments/<timestamp>_<name>/
    - Detailed results: logs/experiments/<timestamp>_<name>/results.jsonl
    - Summary: logs/experiments/<timestamp>_<name>/summary.json
    - Config snapshot: logs/experiments/<timestamp>_<name>/config.yaml

Dataset Notes:
    The current implementation uses Alpaca dataset (alpaca_20.jsonl, alpaca_100.jsonl).
    
    For production use, consider collecting questions from diverse sources:
    - SQuAD: Reading comprehension questions
    - TriviaQA: General knowledge questions
    - GSM8K: Grade school math problems
    - MMLU: Multi-task language understanding
    - Custom domain-specific questions
    
    Recommended dataset format (data/questions.jsonl):
    {
        "id": "001",
        "question": "What is the capital of France?",
        "answer": "Paris",
        "topic": "geography",          # Optional: for analysis
        "difficulty": "easy",           # Optional: easy/medium/hard
        "source": "squad",              # Optional: dataset source
        "reference": "Expected answer"  # Optional: for evaluation
    }
    
    Additional fields like topic, difficulty, source help with:
    - Per-topic performance analysis
    - Difficulty-based adaptive strategies
    - Dataset diversity metrics
"""

import sys
import os
import json
import jsonlines
import yaml
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import argparse
from tqdm import tqdm
from dotenv import load_dotenv

# Load environment variables (API keys)
load_dotenv()

# Add src to path (FIX: Changed from parent.parent to parent)
sys.path.insert(0, str(Path(__file__).parent))

from src.core.logger import get_logger
from src.core.experiment import ExperimentManager
# New architecture imports
from src.refinement.settings import SETTINGS
from src.refinement.teacher.stage import TeacherStage
from src.refinement.student.stage import StudentStage
from src.refinement.memory.stage import MemoryStage
from src.refinement.memory.plugins.store import MemoryStore
from src.refinement.memory.plugins.vector_index import VectorIndex
from src.refinement.teacher.plugins.aggregator import HybridCritic
from src.refinement.teacher.plugins.simple_critic import TeacherCritic
from src.providers import build_client
from src.refinement.loop import run_loop

logger = get_logger("experiments.runner")


def resolve_env_var(value: Any) -> Any:
    """
    Resolve environment variable syntax ${VAR:-default} in config values.
    
    Args:
        value: Config value (string, int, dict, list, etc.)
    
    Returns:
        Resolved value with environment variables expanded
    """
    if isinstance(value, str):
        # Match ${VAR_NAME:-default_value}
        pattern = r'\$\{([^}:]+)(?::-(.*?))?\}'
        
        def replace_env(match):
            var_name = match.group(1)
            default_value = match.group(2) or ""
            return os.getenv(var_name, default_value)
        
        resolved = re.sub(pattern, replace_env, value)
        
        # Try to convert to int if it looks like a number
        try:
            return int(resolved)
        except ValueError:
            return resolved
    
    elif isinstance(value, dict):
        return {k: resolve_env_var(v) for k, v in value.items()}
    
    elif isinstance(value, list):
        return [resolve_env_var(item) for item in value]
    
    else:
        return value


def load_models_registry() -> Dict:
    """
    PHASE 10: No longer loads models.yml (deleted in Phase 1)
    Returns empty registry - model names should be specified directly in config files
    Rate limits auto-loaded from src/providers/constants.py
    
    Returns:
        Empty dictionary (backwards compatibility only)
    """
    logger.info("models.yml deprecated - using direct model names from config")
    return {"teachers": {}, "students": {}, "primary": None, "primary_student": None}


def resolve_model_name(model_key: str, model_type: str, models_registry: Dict) -> str:
    """
    PHASE 10: No longer resolves from models.yml
    Simply returns model_key as-is (config files must specify full model names)
    
    Args:
        model_key: Full model name (e.g., "gemini-2.0-flash-lite", "TinyLlama/...")
        model_type: "teacher" or "student" (ignored, kept for compatibility)
        models_registry: Empty dict (kept for compatibility)
    
    Returns:
        model_key unchanged
    """
    # Simply return as-is - config files must now specify full model names
    return model_key


def load_config(config_path: str) -> tuple[Dict, Dict]:
    """
    Load experiment configuration from YAML file.
    Resolves model names from models.yml registry.
    
    Args:
        config_path: Path to YAML config file
    
    Returns:
        Tuple of (config dictionary with resolved model names, models_registry)
    
    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If YAML is malformed
    """
    config_file = Path(config_path)
    
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    logger.info(f"Loading config from: {config_path}")
    
    with open(config_file, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # Validate required fields
    required_fields = ['name', 'dataset', 'student_model', 'teacher_model', 'strategy']
    missing = [f for f in required_fields if f not in config]
    if missing:
        raise ValueError(f"Missing required config fields: {missing}")
    
    # Load models registry and resolve model names
    models_registry = load_models_registry()
    
    # PHASE 10: No resolution needed - use model names as-is from config
    # Models registry is now empty (models.yml deleted)
    student_key = config['student_model']
    config['student_model'] = resolve_model_name(student_key, "student", models_registry)
    
    teacher_key = config['teacher_model']
    config['teacher_model'] = resolve_model_name(teacher_key, "teacher", models_registry)
    
    logger.info(f"Loaded config: {config['name']}")
    logger.info(f"  Student: {config['student_model']}")
    logger.info(f"  Teacher: {config['teacher_model']}")
    
    return config, models_registry  # Return registry for rate limit lookup


def load_dataset(dataset_path: str, num_questions: Optional[int] = None) -> List[Dict]:
    """
    Load questions from JSONL dataset file.
    
    Args:
        dataset_path: Path to JSONL file
        num_questions: Optional limit on number of questions (None = all)
    
    Returns:
        List of question dictionaries
    
    Note:
        Expected format: {"id": "...", "question": "...", "answer": "...", ...}
        
        For production, you can extend this to load from multiple sources:
        - SQuAD: Reading comprehension (100k+ questions)
        - TriviaQA: General knowledge (95k questions)
        - GSM8K: Math word problems (8.5k questions)
        - MMLU: Multi-domain understanding (15k questions)
        
        Recommended to add metadata:
        - topic: Category for performance analysis
        - difficulty: For adaptive strategies
        - source: Dataset provenance
    """
    dataset_file = Path(dataset_path)
    
    if not dataset_file.exists():
        raise FileNotFoundError(f"Dataset file not found: {dataset_path}")
    
    logger.info(f"Loading dataset from: {dataset_path}")
    
    questions = []
    with jsonlines.open(dataset_file) as reader:
        for record in reader:
            questions.append(record)
            if num_questions and len(questions) >= num_questions:
                break
    
    logger.info(f"Loaded {len(questions)} questions")
    return questions


# create_strategy function removed - strategies deprecated in new architecture
# All strategy logic now handled by teacher/student/memory stages


def run_experiment(config_path: str, dry_run: bool = False) -> Dict:
    """
    Run a single experiment based on configuration file.
    
    Args:
        config_path: Path to YAML configuration
        dry_run: If True, show what would be executed without running
    
    Returns:
        Experiment summary dictionary
    """
    # Load configuration and models registry
    config, models_registry = load_config(config_path)
    experiment_name = config['name']
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Starting Experiment: {experiment_name}")
    logger.info(f"Description: {config.get('description', 'N/A')}")
    logger.info(f"{'='*60}\n")
    
    if dry_run:
        logger.info("[DRY RUN] Would execute experiment with config:")
        logger.info(json.dumps(config, indent=2))
        return {"status": "dry_run", "config": config}
    
    # Create experiment manager
    experiment = ExperimentManager.create(
        name=experiment_name,
        category="experiments",
        config=config
    )
    
    logger.info(f"Experiment directory: {experiment.run_dir}")
    
    # Load dataset
    questions = load_dataset(
        config['dataset'],
        num_questions=config.get('num_questions')
    )
    
    # Initialize components
    logger.info("Initializing components...")
    
    # PHASE 8: Update SETTINGS from config (priority: config > defaults)
    SETTINGS.update_from_config(config)
    
    # Memory store
    memory_path = experiment.get_memory_store_path()
    memory_store = MemoryStore(str(memory_path))
    
    # Vector index
    embedding_model = config.get('embedding_model', 'all-MiniLM-L6-v2')
    embedding_dim = config.get('embedding_dim', 384)
    index_path = experiment.get_vector_index_path()
    vector_index = VectorIndex(
        embedding_model=embedding_model,
        index_path=str(index_path),
        dim=embedding_dim
    )
    
    # Teacher critic - supports both HybridCritic (new) and TeacherCritic (legacy)
    critic_type = config.get('critic_type', 'hybrid')  # Default to new HybridCritic
    teacher_model = config['teacher_model']
    
    # Rate limits now loaded automatically from src/providers/constants.py
    # No need to read from models.yml - constants.py is the single source of truth
    logger.info(f"Using teacher model: {teacher_model} (rate limits from constants.py)")
    
    if critic_type == 'hybrid':
        #  PRIMARY: HybridCritic with rule-based + LLM evaluation
        logger.info(f"Using HybridCritic with model: {teacher_model}")
        
        # Extract LLM reviewer config from experiment config
        llm_reviewer_config = config.get('llm_reviewer', None)
        
        teacher = HybridCritic(
            provider="gemini",
            model_name=teacher_model,
            rule_weight=config.get('rule_weight', 0.5),
            llm_weight=config.get('llm_weight', 0.5),
            disagreement_threshold=config.get('disagreement_threshold', 0.3),
            disagreements_log=str(experiment.memory_dir / "disagreements.jsonl"),
            llm_reviewer_config=llm_reviewer_config  # Pass LLM reviewer config
            # rpm/tpm/rpd removed - automatically loaded from constants.py
        )
    else:
        # SIMPLE: TeacherCritic (prompt-based XML parsing)
        logger.info(f"Using simple TeacherCritic with model: {teacher_model}")
        teacher = TeacherCritic(
            provider="gemini",
            model_name=teacher_model,
            temperature=config.get('teacher_temperature', 0.3),
            max_tokens=config.get('teacher_max_tokens', 512)
            # rpm/tpm/rpd removed - automatically loaded from constants.py
        )
    
    # Student client - auto-detect provider based on model name
    student_model = config['student_model']
    
    # Rate limits now loaded automatically from src/providers/constants.py
    # No need to read from models.yml - client will auto-detect limits based on model name
    logger.info(f"Using student model: {student_model}")
    
    # Detect if student model is API-based (Gemini/Groq) or local (HuggingFace)
    if student_model.startswith(("gemini", "models/gemini")):
        import os
        student_client = build_client(
            "gemini", 
            model=student_model,
            api_key=os.getenv("GOOGLE_API_KEY")
            # rpm/tpm/rpd removed - automatically loaded from constants.py
        )
    elif student_model.startswith("groq/") or "/" not in student_model and not student_model.startswith("gemini"):
        # Groq models or simple names without slash (assume Groq)
        import os
        student_client = build_client(
            "groq",
            model=student_model.replace("groq/", ""),
            api_key=os.getenv("GROQ_API_KEY")
            # rpm/tpm/rpd removed - automatically loaded from constants.py
        )
    else:
        # HuggingFace model (has organization/model format like "TinyLlama/...")
        # Local models don't need rate limits
        student_client = build_client("local", model=student_model)
    
    # PHASE 8: Create stages (NEW architecture - replaces strategy pattern)
    teacher_stage = TeacherStage(config, teacher)
    student_stage = StudentStage(config, student_client, memory_store, vector_index)
    memory_stage = MemoryStage(memory_store, vector_index)
    
    logger.info(f"Components initialized:")
    logger.info(f"  Student: {student_model}")
    logger.info(f"  Teacher: {teacher_model}")
    logger.info(f"  Embedding: {embedding_model}")
    logger.info(f"  k: {config.get('k', 1)}")
    logger.info(f"  Max rounds: {config.get('max_rounds', 3)}")
    logger.info(f"  Use CoT Teacher: {config.get('use_cot_teacher', False)}")
    logger.info(f"  Use CoT Student: {config.get('use_cot_student', False)}")
    
    # Run experiment
    results = []
    start_time = datetime.now()
    
    logger.info(f"\nProcessing {len(questions)} questions...")
    
    # Progress bar with file output to avoid mixing with logs
    from tqdm import tqdm as tqdm_base
    progress_bar = tqdm_base(
        total=len(questions),
        desc=f"Experiment: {experiment_name}",
        ascii=True,
        position=0,
        leave=True,
        file=__import__('sys').stdout
    )
    
    for i, question_data in enumerate(questions):
        question = question_data['question']
        question_id = question_data.get('id', f"q{i}")
        
        try:
            # Prepare run_loop config (pass config dict directly)
            loop_config = config  # Pass full config to loop
            
            # PHASE 8: Run teaching loop with new stage architecture
            result = run_loop(
                question=question,
                config=loop_config,
                teacher_stage=teacher_stage,
                student_stage=student_stage,
                memory_stage=memory_stage,
                experiment_id=experiment_name,
                question_id=question_id,
                correct_answer=question_data.get('reference')  # Pass reference if available
            )
            
            # Add metadata
            result['question_id'] = question_id
            result['config_name'] = experiment_name
            result['timestamp'] = datetime.now().isoformat()
            
            # Add reference answer if available
            if 'reference' in question_data:
                result['reference_answer'] = question_data['reference']
            
            results.append(result)
            
            # Update progress bar
            progress_bar.update(1)
            
            # Log progress every 5 questions
            if (i + 1) % 5 == 0:
                success_count = sum(1 for r in results if r.get('success', False))
                success_rate = success_count / len(results)
                logger.info(f"Progress: {len(results)}/{len(questions)} - Success rate: {success_rate:.2%}")
            
            # Phase 2: Periodic rule distillation
            distill_interval = config.get("rule_distill_interval", 10)
            if distill_interval > 0 and (i + 1) % distill_interval == 0:
                try:
                    from src.refinement.memory.plugins.semantic_rules import SemanticRuleStore
                    rule_store = SemanticRuleStore()
                    
                    # Load all records from current experiment
                    all_records = list(memory_store.load_records())
                    
                    # Filter to recent records (last distill_interval * avg 3 rounds)
                    recent_records = all_records[-(distill_interval * 3):]
                    
                    # Distill rules
                    rules_created = rule_store.distill_from_episodes(
                        recent_records,
                        min_quality=config.get("rule_min_quality", 0.7)
                    )
                    
                    if rules_created > 0:
                        logger.info(
                            f"Distilled {rules_created} rules from last {len(recent_records)} episodes"
                        )
                except Exception as e:
                    logger.warning(f"Failed to distill rules: {e}")
        
        except Exception as e:
            logger.error(f"Error processing question {question_id}: {e}")
            results.append({
                'question_id': question_id,
                'question': question,
                'error': str(e),
                'success': False,
                'timestamp': datetime.now().isoformat()
            })
            
            if not config.get('retry_on_error', True):
                raise
    
    # Close progress bar
    progress_bar.close()
    
    end_time = datetime.now()
    elapsed = (end_time - start_time).total_seconds()
    
    # Calculate summary statistics
    success_count = sum(1 for r in results if r.get('success', False))
    success_rate = success_count / len(results) if results else 0
    
    # Rounds from run_loop: use 'num_rounds' (fallback to len(iterations))
    rounds_list = [r.get('num_rounds', len(r.get('iterations', []))) for r in results]
    avg_rounds = (sum(rounds_list) / len(results)) if results else 0
    
    # Tokens/latency are per-iteration; aggregate per result, then across results
    total_tokens = sum(
        sum(it.get('tokens', 0) for it in r.get('iterations', []))
        for r in results
    )
    per_result_latency = [
        sum(it.get('latency_ms', 0) for it in r.get('iterations', [])) for r in results
    ]
    avg_latency = (sum(per_result_latency) / len(results)) if results else 0
    
    summary = {
        'experiment_name': experiment_name,
        'config': config,
        'dataset': {
            'path': config['dataset'],
            'total_questions': len(questions),
            'processed': len(results),
            'errors': sum(1 for r in results if 'error' in r)
        },
        'performance': {
            'success_count': success_count,
            'success_rate': success_rate,
            'avg_rounds': avg_rounds,
            'total_tokens': total_tokens,
            'avg_tokens_per_question': total_tokens / len(results) if results else 0,
            'avg_latency_ms': avg_latency,
            'total_time_seconds': elapsed,
            'total_time_minutes': elapsed / 60
        },
        'timestamp': {
            'start': start_time.isoformat(),
            'end': end_time.isoformat(),
            'elapsed_seconds': elapsed
        }
    }
    
    # Save results to experiment directory only (avoid duplication)
    results_file = experiment.run_dir / "results.jsonl"
    with jsonlines.open(results_file, mode='w') as writer:
        for result in results:
            writer.write(result)
    
    logger.info(f"Saved detailed results to: {results_file}")
    
    # Save summary to experiment directory
    experiment.save_summary(summary)
    logger.info(f"Saved summary to: {experiment.run_dir / 'summary.json'}")
    
    # Print summary (visible after progress bar)
    print("\n" + "="*60)
    print(f"EXPERIMENT COMPLETE: {experiment_name}")
    print("="*60)
    print(f"Success Rate: {success_rate:.2%} ({success_count}/{len(results)})")
    print(f"Avg Rounds: {avg_rounds:.2f}")
    print(f"Total Tokens: {total_tokens:,}")
    print(f"Avg Latency: {avg_latency:.1f} ms")
    print(f"Total Time: {elapsed/60:.2f} minutes")
    print("="*60 + "\n")
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Experiment Complete: {experiment_name}")
    logger.info(f"{'='*60}")
    logger.info(f"Success Rate: {success_rate:.2%} ({success_count}/{len(results)})")
    logger.info(f"Avg Rounds: {avg_rounds:.2f}")
    logger.info(f"Total Tokens: {total_tokens:,}")
    logger.info(f"Avg Latency: {avg_latency:.1f} ms")
    logger.info(f"Total Time: {elapsed/60:.2f} minutes")
    logger.info(f"{'='*60}\n")
    
    return summary


def run_all_experiments(configs_dir: str = "experiments/configs", dry_run: bool = False) -> List[Dict]:
    """
    Run all experiments found in configs directory.
    
    Args:
        configs_dir: Directory containing YAML config files
        dry_run: If True, show what would be executed without running
    
    Returns:
        List of experiment summaries
    """
    configs_path = Path(configs_dir)
    
    if not configs_path.exists():
        raise FileNotFoundError(f"Configs directory not found: {configs_dir}")
    
    # Find all YAML files
    config_files = sorted(configs_path.glob("*.yml")) + sorted(configs_path.glob("*.yaml"))
    
    if not config_files:
        logger.warning(f"No config files found in {configs_dir}")
        return []
    
    logger.info(f"Found {len(config_files)} config files:")
    for cf in config_files:
        logger.info(f"  - {cf.name}")
    
    # Run each experiment
    summaries = []
    for config_file in config_files:
        try:
            summary = run_experiment(str(config_file), dry_run=dry_run)
            summaries.append(summary)
        except Exception as e:
            logger.error(f"Failed to run experiment {config_file.name}: {e}")
            import traceback
            traceback.print_exc()
    
    # Print overall summary
    if not dry_run and summaries:
        logger.info(f"\n{'='*60}")
        logger.info("ALL EXPERIMENTS COMPLETE")
        logger.info(f"{'='*60}")
        logger.info(f"Total experiments: {len(summaries)}")
        
        for summary in summaries:
            perf = summary['performance']
            logger.info(f"\n{summary['experiment_name']}:")
            logger.info(f"  Success: {perf['success_rate']:.2%}")
            logger.info(f"  Rounds: {perf['avg_rounds']:.2f}")
            logger.info(f"  Tokens: {perf['total_tokens']:,}")
            logger.info(f"  Time: {perf['total_time_minutes']:.2f} min")
        
        logger.info(f"\n{'='*60}\n")
    
    return summaries


def main():
    """Main entry point for experiment runner."""
    parser = argparse.ArgumentParser(
        description="Run teaching loop experiments",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        '--config',
        type=str,
        help='Path to single YAML config file'
    )
    
    parser.add_argument(
        '--configs',
        nargs='+',
        help='List of config names (without .yml extension) to run'
    )
    
    parser.add_argument(
        '--all',
        action='store_true',
        help='Run all experiments in configs directory'
    )
    
    parser.add_argument(
        '--configs-dir',
        type=str,
        default='config/experiment_config',
        help='Directory containing config files (default: config/experiment_config)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be executed without running'
    )
    
    args = parser.parse_args()
    
    try:
        if args.config:
            # Run single experiment
            run_experiment(args.config, dry_run=args.dry_run)
        
        elif args.configs:
            # Run specified experiments
            for config_name in args.configs:
                config_file = f"{args.configs_dir}/{config_name}.yml"
                run_experiment(config_file, dry_run=args.dry_run)
        
        elif args.all:
            # Run all experiments
            run_all_experiments(args.configs_dir, dry_run=args.dry_run)
        
        else:
            parser.print_help()
            print("\nError: Must specify --config, --configs, or --all")
            sys.exit(1)
    
    except Exception as e:
        logger.error(f"Experiment runner failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
