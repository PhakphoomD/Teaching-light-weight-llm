"""
Test console display without running experiments - NEW VERSION
"""

from src.experiment.config import load_experiment_config

config = load_experiment_config()

print("=" * 80)
print(" Teaching Lightweight LLM - Experiment Runner")
print("=" * 80)
print()

# Display models
print(" AVAILABLE MODELS:")
print("-" * 80)

local_models = [m for m in config.models.values() if m.type == "local"]
api_models = [m for m in config.models.values() if m.type == "api"]
models = []

if local_models:
    print("  Local Models:")
    for model in local_models:
        idx = len(models) + 1
        models.append(model)
        print(f"    [{idx}] {model.display_name:<25} - {model.description}")

if api_models:
    print("\n  API Models:")
    for model in api_models:
        idx = len(models) + 1
        models.append(model)
        print(f"    [{idx}] {model.display_name:<25} - {model.description}")

print()
print("-" * 80)
print()

# Display strategies with new option
print(" AVAILABLE EXPERIMENT STRATEGIES:")
print("-" * 80)
print("  Individual strategies:")
print()

strategies = list(config.strategies.values())
for idx, strategy in enumerate(strategies, 1):
    features = strategy.features
    tags = []
    if features.get("memory"):
        tags.append("Memory")
    if features.get("reflection"):
        tags.append("Reflection")
    if features.get("canonical"):
        tags.append("Canonical")
    tag_str = f"[{', '.join(tags)}]" if tags else "[Baseline]"
    print(f"  [{idx}] {strategy.display_name:<40} {tag_str}")
    print(f"      {strategy.description}")
    print()

print(f"  [{len(strategies) + 1}] → Select Strategy Groups (run multiple strategies together)")
print()
print("  Options: numbers (1,3,5) or 'all' for all strategies")
print()
print("-" * 80)
print()

# Display strategy groups (this is where user goes if they select option 7)
print(" STRATEGY GROUPS (if you select option 7):")
print("=" * 80)
print("  Available pre-defined groups:")
print()

if config.strategy_groups:
    for idx, (group_name, strategy_keys) in enumerate(config.strategy_groups.items(), 1):
        strategy_names = []
        for key in strategy_keys:
            if key in config.strategies:
                strategy_names.append(config.strategies[key].display_name)
        
        print(f"  [{idx}] {group_name}")
        print(f"      Strategies: {', '.join(strategy_names)}")
        print()
    
    print(f"  [{len(config.strategy_groups) + 1}] Back to individual strategy selection")
    print()

print("-" * 80)
print()

# Display datasets
print(" AVAILABLE DATASETS:")
print("-" * 80)
datasets = config.datasets
for idx, dataset in enumerate(datasets, 1):
    print(f"  [{idx}] {dataset.name:<20} ({dataset.size:>6} items) - {dataset.path}")
    print(f"      {dataset.description}")
    print()

print("=" * 80)
print(" Console display test completed!")
print("=" * 80)
