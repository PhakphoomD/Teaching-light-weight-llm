"""
Example: Token usage analysis with local and API models
"""

from src.memory.token_tracker import TokenTracker

print("=" * 80)
print(" EXAMPLE: Token Usage Tracking")
print("=" * 80)
print()

# Example 1: Local student + API teacher (most common use case)
print(" Example 1: TinyLlama (local) + Groq Llama3 70B (API)")
print("-" * 80)
tracker1 = TokenTracker(
    student_model_name='tinyllama_1.1b',
    teacher_model_name='groq_llama3_70b',
    strategy_name='Memory + Multi-key + TF-IDF',
    experiment_id='example_run_001'
)

# Simulate 20 tasks
for i in range(20):
    # Student generates answer (local model - estimated tokens)
    tracker1.track_student(prompt_tokens=250, completion_tokens=180)
    
    # Teacher provides feedback (API - actual tokens)
    if i % 3 == 0:  # Only some tasks need teacher feedback
        tracker1.track_teacher(prompt_tokens=180, completion_tokens=120)

tracker1.print_summary()

print("\n" + "=" * 80)
print()

# Example 2: Both local models
print(" Example 2: Llama3 8B (local) + Llama3 8B (same model)")
print("-" * 80)
tracker2 = TokenTracker(
    student_model_name='llama3_8b',
    teacher_model_name='llama3_8b',  # Same model
    strategy_name='Baseline + Reflection',
    experiment_id='example_run_002'
)

# When same model, tokens are combined
for i in range(15):
    tracker2.track_student(prompt_tokens=300, completion_tokens=200)
    if i % 2 == 0:
        tracker2.track_teacher(prompt_tokens=200, completion_tokens=100)

tracker2.print_summary()

print("\n" + "=" * 80)
print()

# Example 3: Both API models
print(" Example 3: Gemini Flash (API) + Groq Llama3 70B (API)")
print("-" * 80)
tracker3 = TokenTracker(
    student_model_name='gemini_1.5_flash',
    teacher_model_name='groq_llama3_70b',
    strategy_name='Full System',
    experiment_id='example_run_003'
)

for i in range(10):
    # Student (API - actual tokens)
    tracker3.track_student(prompt_tokens=280, completion_tokens=150)
    
    # Teacher (API - actual tokens)
    if i % 4 == 0:
        tracker3.track_teacher(prompt_tokens=200, completion_tokens=100)

tracker3.print_summary()

print("=" * 80)
print(" Examples completed!")
print("=" * 80)
