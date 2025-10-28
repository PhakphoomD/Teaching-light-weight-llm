#!/usr/bin/env python3
"""
Test script to display console menu without interaction
"""

from src.experiment.config import load_experiment_config

def main():
    print("\n" + "=" * 80)
    print(" TEACHING LIGHTWEIGHT LLM - EXPERIMENT RUNNER (PREVIEW)")
    print("=" * 80)
    
    # Load config
    config = load_experiment_config()
    
    # Display Models
    print("\n AVAILABLE STUDENT MODELS:")
    print("-" * 80)
    
    local_models = [m for m in config.models.values() if m.type == 'local']
    api_models = [m for m in config.models.values() if m.type == 'api']
    
    if local_models:
        print("\n    Local Models:")
        for idx, model in enumerate(local_models, 1):
            print(f"    [{idx}] {model.display_name:<25} - {model.description}")
    
    if api_models:
        print("\n    API Models:")
        for idx, model in enumerate(api_models, len(local_models) + 1):
            print(f"    [{idx}] {model.display_name:<25} - {model.description}")
    
    # Display Strategies
    print("\n\n AVAILABLE EXPERIMENT STRATEGIES:")
    print("-" * 80)
    
    strategies = list(config.strategies.values())
    for idx, strategy in enumerate(strategies, 1):
        # Build feature tags
        features = strategy.features
        tags = []
        if features.get('memory'):
            tags.append("Memory")
        if features.get('reflection'):
            tags.append("Reflection")
        if features.get('canonical'):
            tags.append("Canonical")
        
        tag_str = f"[{', '.join(tags)}]" if tags else "[Baseline]"
        
        print(f"  [{idx}] {strategy.display_name:<40} {tag_str}")
        print(f"      {strategy.description}")
        print()
    
    # Display Datasets
    print("\n AVAILABLE DATASETS:")
    print("-" * 80)
    
    for idx, dataset in enumerate(config.datasets, 1):
        print(f"  [{idx}] {dataset.name:<20} ({dataset.size:>6} items) - {dataset.path}")
        print(f"      {dataset.description}")
        print()
    
    # Display Strategy Groups
    print("\n STRATEGY GROUPS:")
    print("-" * 80)
    for group_name, strategy_keys in config.strategy_groups.items():
        print(f"  • {group_name:<20} : {', '.join(strategy_keys)}")
    
    print("\n" + "=" * 80)
    print(" Configuration loaded successfully!")
    print("=" * 80)
    print(f"Total Models    : {len(config.models)}")
    print(f"Total Strategies: {len(config.strategies)}")
    print(f"Total Datasets  : {len(config.datasets)}")
    print("=" * 80)
    
    print("\n To run interactive console:")
    print("   python run_experiment.py")
    print("\n To run with CLI:")
    print("   python run_experiment.py --student tinyllama_1.1b --teacher groq_llama3_70b --strategy baseline --dataset \"Quick Test\"")
    print()

if __name__ == "__main__":
    main()
