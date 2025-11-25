"""
Two-Stage Hyperparameter Tuning with LHS + Focused Grid

Stage 1: Latin Hypercube Sampling (broad exploration)
Stage 2: Focused Grid Search (local optimization)
"""

# Groq pricing (per 1M tokens)
GROQ_PRICES = {
    'llama-3.1-8b-instant': {'input': 0.05, 'output': 0.08},
    'llama-3.3-70b-versatile': {'input': 0.59, 'output': 0.79}
}

# Token estimation per component
TOKENS_PER_ROUND = {
    'student_input': 150,      # Question + feedback + memory context
    'student_output': 100,     # Answer
    'teacher_input': 300,      # Question + student answer + ground truth + CoT prompt
    'teacher_output': 150,     # Feedback with CoT reasoning
    'judge_blind_input': 200,  # Question + student answer + criteria
    'judge_blind_output': 10,  # Score only
    'judge_comp_input': 250,   # Question + student answer + ground truth + criteria
    'judge_comp_output': 10,   # Score only
}


def calculate_round_cost():
    """
    Calculate cost per round.
    
    Per round we call:
    1. Student (8B) - generates answer
    2. Teacher (70B) - generates feedback
    3. Blind Judge (70B) - evaluates without ground truth
    4. Comparison Judge (70B) - evaluates with ground truth
    
    Total: 4 API calls per round
    """
    # Input costs
    student_input_cost = (TOKENS_PER_ROUND['student_input'] / 1_000_000) * GROQ_PRICES['llama-3.1-8b-instant']['input']
    teacher_input_cost = (TOKENS_PER_ROUND['teacher_input'] / 1_000_000) * GROQ_PRICES['llama-3.3-70b-versatile']['input']
    judge_input_cost = ((TOKENS_PER_ROUND['judge_blind_input'] + TOKENS_PER_ROUND['judge_comp_input']) / 1_000_000) * GROQ_PRICES['llama-3.3-70b-versatile']['input']
    
    # Output costs
    student_output_cost = (TOKENS_PER_ROUND['student_output'] / 1_000_000) * GROQ_PRICES['llama-3.1-8b-instant']['output']
    teacher_output_cost = (TOKENS_PER_ROUND['teacher_output'] / 1_000_000) * GROQ_PRICES['llama-3.3-70b-versatile']['output']
    judge_output_cost = ((TOKENS_PER_ROUND['judge_blind_output'] + TOKENS_PER_ROUND['judge_comp_output']) / 1_000_000) * GROQ_PRICES['llama-3.3-70b-versatile']['output']
    
    total_input_cost = student_input_cost + teacher_input_cost + judge_input_cost
    total_output_cost = student_output_cost + teacher_output_cost + judge_output_cost
    
    return total_input_cost + total_output_cost


def calculate_phase_cost(questions, avg_rounds):
    """Calculate cost for a phase."""
    cost_per_round = calculate_round_cost()
    return questions * avg_rounds * cost_per_round


def main():
    print('=' * 80)
    print('TOKEN COST ANALYSIS - GROQ API')
    print('=' * 80)
    
    print('\n--- GROQ PRICING ---')
    print('Student (Llama 3.1 8B Instant):')
    print('  Input:  $0.05 / 1M tokens (20M tokens per $1)')
    print('  Output: $0.08 / 1M tokens (12.5M tokens per $1)')
    print('Teacher (Llama 3.3 70B Versatile):')
    print('  Input:  $0.59 / 1M tokens (1.69M tokens per $1)')
    print('  Output: $0.79 / 1M tokens (1.27M tokens per $1)')
    
    # Calculate per-round metrics
    total_input_tokens = sum([
        TOKENS_PER_ROUND['student_input'],
        TOKENS_PER_ROUND['teacher_input'],
        TOKENS_PER_ROUND['judge_blind_input'],
        TOKENS_PER_ROUND['judge_comp_input']
    ])
    total_output_tokens = sum([
        TOKENS_PER_ROUND['student_output'],
        TOKENS_PER_ROUND['teacher_output'],
        TOKENS_PER_ROUND['judge_blind_output'],
        TOKENS_PER_ROUND['judge_comp_output']
    ])
    cost_per_round = calculate_round_cost()
    
    print('\n--- TOKEN USAGE PER ROUND ---')
    print('Per round = 4 API calls:')
    print('  1. Student (8B):          Answer generation')
    print('  2. Teacher (70B):         Feedback generation')
    print('  3. Blind Judge (70B):     Quality evaluation (no GT)')
    print('  4. Comparison Judge (70B): Semantic evaluation (with GT)')
    print()
    print(f'Total Input:  {total_input_tokens} tokens')
    print(f'Total Output: {total_output_tokens} tokens')
    print(f'Total Tokens: {total_input_tokens + total_output_tokens} tokens')
    print(f'Cost:         ${cost_per_round:.6f} per round (4 calls)')
    
    # Per question (avg 4 rounds)
    avg_rounds = 4
    cost_per_question = cost_per_round * avg_rounds
    tokens_per_question = (total_input_tokens + total_output_tokens) * avg_rounds
    
    print(f'\n--- COST PER QUESTION (avg {avg_rounds} rounds) ---')
    print(f'Tokens: {tokens_per_question:,}')
    print(f'Cost:   ${cost_per_question:.4f}')
    
    print('\n' + '=' * 80)
    print('EXPERIMENT PLANS COMPARISON')
    print('=' * 80)
    
    # Original Full Plan
    print('\nPLAN A: COMPREHENSIVE (EXPENSIVE)')
    full_phases = [
        ('Phase 0: Baseline', 50, 1),
        ('Phase 1: Teacher-Student Grid', 1200, 4),
        ('Phase 2: Hyperparameters', 3600, 4),
        ('Phase 3: Judge Analysis', 300, 4),
        ('Phase 4: Cross-Domain', 800, 4),
    ]
    
    full_total_q = sum(q for _, q, _ in full_phases)
    full_total_cost = sum(calculate_phase_cost(q, r) for _, q, r in full_phases)
    full_total_tokens = sum(q * r * (total_input_tokens + total_output_tokens) for _, q, r in full_phases)
    
    for name, questions, rounds in full_phases:
        phase_cost = calculate_phase_cost(questions, rounds)
        print(f'  {name}: {questions:,}Q @ {rounds}R = ${phase_cost:.2f}')
    
    print(f'\n  TOTAL: {full_total_q:,} questions')
    print(f'         {full_total_tokens/1_000_000:.1f}M tokens')
    print(f'         ${full_total_cost:.2f}')
    print(f'         ~{full_total_q * 0.5 / 60:.0f} hours')
    
    # Optimized Plan
    print('\nPLAN B: OPTIMIZED (RECOMMENDED)')
    opt_phases = [
        ('Phase 0: Baseline', 20, 1),
        ('Phase 1: Top 9 Pairs', 450, 3),
        ('Phase 2: Top 3 Configs', 450, 3),
        ('Phase 3: Best Config Only', 150, 3),
        ('Phase 4: 2 Domains', 200, 3),
    ]
    
    opt_total_q = sum(q for _, q, _ in opt_phases)
    opt_total_cost = sum(calculate_phase_cost(q, r) for _, q, r in opt_phases)
    opt_total_tokens = sum(q * r * (total_input_tokens + total_output_tokens) for _, q, r in opt_phases)
    
    for name, questions, rounds in opt_phases:
        phase_cost = calculate_phase_cost(questions, rounds)
        print(f'  {name}: {questions:,}Q @ {rounds}R = ${phase_cost:.2f}')
    
    print(f'\n  TOTAL: {opt_total_q:,} questions')
    print(f'         {opt_total_tokens/1_000_000:.1f}M tokens')
    print(f'         ${opt_total_cost:.2f}')
    print(f'         ~{opt_total_q * 0.5 / 60:.0f} hours')
    print(f'  SAVINGS: ${full_total_cost - opt_total_cost:.2f} ({100*(1-opt_total_cost/full_total_cost):.0f}% cheaper)')
    
    # Ultra Budget Plan
    print('\nPLAN C: ULTRA-BUDGET (FAST ITERATION)')
    mini_phases = [
        ('Phase 0: Baseline', 20, 1),
        ('Phase 1: Top 9 Pairs', 180, 2),
        ('Phase 2: Best Config Only', 100, 2),
        ('Phase 3: Quick Judge Check', 50, 2),
    ]
    
    mini_total_q = sum(q for _, q, _ in mini_phases)
    mini_total_cost = sum(calculate_phase_cost(q, r) for _, q, r in mini_phases)
    mini_total_tokens = sum(q * r * (total_input_tokens + total_output_tokens) for _, q, r in mini_phases)
    
    for name, questions, rounds in mini_phases:
        phase_cost = calculate_phase_cost(questions, rounds)
        print(f'  {name}: {questions:,}Q @ {rounds}R = ${phase_cost:.2f}')
    
    print(f'\n  TOTAL: {mini_total_q:,} questions')
    print(f'         {mini_total_tokens/1_000_000:.1f}M tokens')
    print(f'         ${mini_total_cost:.2f}')
    print(f'         ~{mini_total_q * 0.5 / 60:.0f} hours')
    
    print('\n' + '=' * 80)
    print('FINAL RECOMMENDATION')
    print('=' * 80)
    print("""
Recommended plan: PLAN B (Optimized)
  - Good balance between coverage and budget
  - Keeps tokens under control
  - Allows for more iterations on the best config
  - Leaves some budget for Phase 4 (cross-domain tests)
""")


if __name__ == "__main__":
    main()

