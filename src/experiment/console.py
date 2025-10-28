"""
Interactive Console for Experiment Selection

Provides user-friendly menu system for selecting models, strategies, and datasets.
"""

import sys
from typing import List, Optional
from src.experiment.config import (
    ExperimentConfig,
    load_experiment_config,
    ModelConfig,
    StrategyConfig,
    DatasetConfig,
)
from src.experiment.runner import ExperimentRunner
from src.core.logger import get_logger

logger = get_logger(__name__)


class InteractiveConsole:
    """
    Interactive console for experiment configuration and execution.

    Steps:
    1. Select student model
    2. Select teacher model
    3. Select experiment strategies (multi-choice)
    4. Select dataset
    5. Confirm and run
    """

    def __init__(self):
        try:
            self.config = load_experiment_config()
            self.runner = ExperimentRunner(self.config)
        except Exception as e:
            print(f"Error loading configuration: {e}")
            sys.exit(1)

    def run(self):
        self.print_header()

        try:
            student = self.select_student_model()
            if not student:
                return

            teacher = self.select_teacher_model()
            if not teacher:
                return

            strategies = self.select_strategies()
            if not strategies:
                return

            dataset = self.select_dataset()
            if not dataset:
                return

            self.confirm_and_run(student, teacher, strategies, dataset)

        except KeyboardInterrupt:
            print("\n\nInterrupted by user. Exiting...")
            sys.exit(0)
        except Exception as e:
            print(f"\nError: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

    def print_header(self):
        print("\n" + "=" * 80)
        print("Teaching Lightweight LLM - Experiment Runner")
        print("=" * 80)
        print("Interactive experiment configuration and execution system")
        print("=" * 80 + "\n")

    def select_student_model(self) -> Optional[ModelConfig]:
        print("SELECT STUDENT MODEL (model being taught):")
        print("-" * 80)

        local_models = [m for m in self.config.models.values() if m.type == "local"]
        api_models = [m for m in self.config.models.values() if m.type == "api"]

        models: List[ModelConfig] = []

        if local_models:
            print("\n  Local Models:")
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
        choice = self.get_user_choice(f"Enter choice [1-{len(models)}]", 1, len(models))
        if choice is None:
            return None
        selected = models[choice - 1]
        print(f"Selected student: {selected.display_name}\n")
        return selected

    def select_teacher_model(self) -> Optional[ModelConfig]:
        print("SELECT TEACHER MODEL (provides feedback and grading):")
        print("-" * 80)
        print("  Recommended: Groq Llama3 70B or Gemini Pro for best quality feedback")
        print()

        local_models = [m for m in self.config.models.values() if m.type == "local"]
        api_models = [m for m in self.config.models.values() if m.type == "api"]

        models: List[ModelConfig] = []

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
        choice = self.get_user_choice(f"Enter choice [1-{len(models)}]", 1, len(models))
        if choice is None:
            return None
        selected = models[choice - 1]
        print(f"Selected teacher: {selected.display_name}\n")
        return selected

    def select_strategy_groups(self) -> Optional[List[StrategyConfig]]:
        """Show strategy groups selection menu"""
        print("STRATEGY GROUPS:")
        print("=" * 80)
        print("  Select a pre-defined group of strategies to run together:")
        print()
        
        if not self.config.strategy_groups:
            print("   No strategy groups configured")
            return None
        
        groups = list(self.config.strategy_groups.items())
        for idx, (group_name, strategy_keys) in enumerate(groups, 1):
            # Get strategy names for display
            strategy_names = []
            for key in strategy_keys:
                if key in self.config.strategies:
                    strategy_names.append(self.config.strategies[key].display_name)
            
            print(f"  [{idx}] {group_name}")
            print(f"      Strategies: {', '.join(strategy_names)}")
            print()
        
        print(f"  [{len(groups) + 1}] Back to individual strategy selection")
        print()
        
        choice = self.get_user_choice(
            f"Enter choice [1-{len(groups) + 1}]", 
            1, 
            len(groups) + 1
        )
        if choice is None:
            return None
        
        # Back to individual selection
        if choice == len(groups) + 1:
            return self.select_strategies()
        
        # Select group
        group_name, strategy_keys = groups[choice - 1]
        selected = [
            self.config.strategies[k] 
            for k in strategy_keys 
            if k in self.config.strategies
        ]
        print(f" Selected group '{group_name}' ({len(selected)} strategies):")
        for s in selected:
            print(f"  - {s.display_name}")
        print()
        return selected

    def select_strategies(self) -> Optional[List[StrategyConfig]]:
        print("SELECT EXPERIMENT STRATEGIES:")
        print("-" * 80)
        print("  Individual strategies:")
        print()

        strategies = list(self.config.strategies.values())
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

        # Add option to go to strategy groups
        print(f"  [{len(strategies) + 1}] → Select Strategy Groups (run multiple strategies together)")
        print()
        print("  Options: numbers (1,3,5) or 'all' for all strategies")
        print("  Options: numbers (1,3,5) or 'all' for all strategies")

        while True:
            user_input = input(
                f"Enter choices [1-{len(strategies) + 1}] or 'all' (or 'q' to quit): "
            ).strip().lower()
            if user_input == "q":
                return None
            if user_input == "all":
                print(f" Selected all {len(strategies)} strategies\n")
                return strategies
            
            # Try parsing as numbers
            try:
                choices = [int(c.strip()) for c in user_input.split(",")]
                
                # Check if user selected the "Strategy Groups" option
                if len(choices) == 1 and choices[0] == len(strategies) + 1:
                    return self.select_strategy_groups()
                
                if all(1 <= c <= len(strategies) for c in choices):
                    selected = [strategies[c - 1] for c in choices]
                    print(f" Selected {len(selected)} strategy(ies):")
                    for s in selected:
                        print(f"  - {s.display_name}")
                    print()
                    return selected
                else:
                    print(
                        f" Invalid choice. Please enter numbers between 1 and {len(strategies) + 1}"
                    )
            except ValueError:
                print(
                    " Invalid format. Use numbers (1,3,5) or 'all'"
                )

    def select_dataset(self) -> Optional[DatasetConfig]:
        print("SELECT DATASET:")
        print("-" * 80)
        datasets = self.config.datasets
        for idx, dataset in enumerate(datasets, 1):
            print(
                f"  [{idx}] {dataset.name:<20} ({dataset.size:>6} items) - {dataset.path}"
            )
            print(f"      {dataset.description}")
            print()
        choice = self.get_user_choice(f"Enter choice [1-{len(datasets)}]", 1, len(datasets))
        if choice is None:
            return None
        selected = datasets[choice - 1]
        print(f"Selected dataset: {selected.name} ({selected.size} items)\n")
        return selected

    def confirm_and_run(
        self,
        student: ModelConfig,
        teacher: ModelConfig,
        strategies: List[StrategyConfig],
        dataset: DatasetConfig,
    ):
        print("\n" + "=" * 80)
        print("EXPERIMENT CONFIGURATION SUMMARY")
        print("=" * 80)
        print(f"  Student Model : {student.display_name}")
        print(f"  Teacher Model : {teacher.display_name}")
        print(f"  Strategies    : {len(strategies)} selected")
        for s in strategies:
            print(f"                  - {s.name}")
        print(f"  Dataset       : {dataset.name} ({dataset.size} items)")
        print(f"  Total Runs    : {len(strategies)} experiment(s)")
        print("=" * 80)

        confirm = input("\nRun experiments? [Y/n]: ").strip().lower()
        if confirm in ["n", "no"]:
            print("Experiments cancelled by user.")
            return

        print("\nStarting experiments...\n")
        try:
            results = self.runner.run_multiple_experiments(
                student_model=student,
                teacher_model=teacher,
                strategies=strategies,
                dataset=dataset,
            )
            print("\n" + "=" * 80)
            print("ALL EXPERIMENTS COMPLETED SUCCESSFULLY")
            print("=" * 80)
            print(f"Completed: {len(results)}/{len(strategies)} experiments")
            print(f"Results saved to: {self.runner.base_output_dir}/")
            print("=" * 80 + "\n")
        except Exception as e:
            print(f"\nError during experiment execution: {e}")
            import traceback
            traceback.print_exc()

    def get_user_choice(self, prompt: str, min_val: int, max_val: int) -> Optional[int]:
        while True:
            user_input = input(f"{prompt} (or 'q' to quit): ").strip().lower()
            if user_input == "q":
                print("Quitting...")
                return None
            try:
                choice = int(user_input)
                if min_val <= choice <= max_val:
                    return choice
                else:
                    print(f"Please enter a number between {min_val} and {max_val}")
            except ValueError:
                print("Invalid input. Please enter a number or 'q' to quit")


def main():
    console = InteractiveConsole()
    console.run()


if __name__ == "__main__":
    main()
