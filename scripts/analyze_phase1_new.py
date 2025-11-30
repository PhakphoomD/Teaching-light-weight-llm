#!/usr/bin/env python3
"""
Analyze Phase 1 experiment results from the new run.
"""
import json
from collections import defaultdict

def main():
    print("=" * 80)
    print("PHASE 1 EXPERIMENT ANALYSIS - NEW RUN")
    print("=" * 80)
    
    with open('logs/experiments/phase1/debug_per_round.jsonl', 'r', encoding='utf-8') as f:
        records = [json.loads(line) for line in f]
    
    # แยก P1A vs P1B
    p1a = [r for r in records if r['experiment_id'] == 'P1A-NoMemory-Medical20']
    p1b = [r for r in records if r['experiment_id'] == 'P1B-WithMemory-Medical20']
    
    print(f"Total records: {len(records)}")
    print(f"P1A-NoMemory: {len(p1a)} records")
    print(f"P1B-WithMemory: {len(p1b)} records")
    print()
    
    # หาจำนวนคำถาม
    p1a_questions = set(r['question_id'] for r in p1a)
    p1b_questions = set(r['question_id'] for r in p1b)
    print(f"P1A Questions: {len(p1a_questions)}")
    print(f"P1B Questions: {len(p1b_questions)}")
    print()
    
    def get_final_result(records, question_id):
        q_records = [r for r in records if r['question_id'] == question_id]
        if not q_records:
            return None
        # เอารอบสุดท้าย
        final = max(q_records, key=lambda x: x['round'])
        return {
            'question_id': question_id,
            'question': final['question'][:50] + '...',
            'rounds_taken': final['round'],
            'final_score': final['final_score'],
            'passed': final['passed'],
            'memory_used': any(r.get('memory_used', False) for r in q_records)
        }
    
    # สรุปผล P1A
    print("=" * 80)
    print("P1A (No Memory) - Final Results")
    print("=" * 80)
    p1a_results = []
    for qid in sorted(p1a_questions):
        result = get_final_result(p1a, qid)
        if result:
            p1a_results.append(result)
            status = "PASS" if result['passed'] else "FAIL"
            print(f"{result['question_id']}: R{result['rounds_taken']:2d} | {result['final_score']:.4f} | [{status}]")
    
    p1a_pass = sum(1 for r in p1a_results if r['passed'])
    p1a_total = len(p1a_results)
    p1a_avg_score = sum(r['final_score'] for r in p1a_results) / p1a_total if p1a_total > 0 else 0
    p1a_avg_rounds = sum(r['rounds_taken'] for r in p1a_results) / p1a_total if p1a_total > 0 else 0
    
    print()
    print(f"P1A Pass Rate: {p1a_pass}/{p1a_total} = {100*p1a_pass/p1a_total:.1f}%")
    print(f"P1A Average Score: {p1a_avg_score:.4f}")
    print(f"P1A Average Rounds: {p1a_avg_rounds:.1f}")
    
    # สรุปผล P1B
    print()
    print("=" * 80)
    print("P1B (With Memory) - Final Results")
    print("=" * 80)
    p1b_results = []
    for qid in sorted(p1b_questions):
        result = get_final_result(p1b, qid)
        if result:
            p1b_results.append(result)
            status = "PASS" if result['passed'] else "FAIL"
            mem = "[MEM]" if result['memory_used'] else ""
            print(f"{result['question_id']}: R{result['rounds_taken']:2d} | {result['final_score']:.4f} | [{status}] {mem}")
    
    p1b_pass = sum(1 for r in p1b_results if r['passed'])
    p1b_total = len(p1b_results)
    p1b_avg_score = sum(r['final_score'] for r in p1b_results) / p1b_total if p1b_total > 0 else 0
    p1b_avg_rounds = sum(r['rounds_taken'] for r in p1b_results) / p1b_total if p1b_total > 0 else 0
    p1b_mem_used = sum(1 for r in p1b_results if r['memory_used'])
    
    print()
    print(f"P1B Pass Rate: {p1b_pass}/{p1b_total} = {100*p1b_pass/p1b_total:.1f}%")
    print(f"P1B Average Score: {p1b_avg_score:.4f}")
    print(f"P1B Average Rounds: {p1b_avg_rounds:.1f}")
    print(f"P1B Memory Used: {p1b_mem_used}/{p1b_total} questions")
    
    # เปรียบเทียบ
    print()
    print("=" * 80)
    print("COMPARISON: P1A vs P1B")
    print("=" * 80)
    print(f"{'Metric':<25} {'P1A (No Mem)':<15} {'P1B (With Mem)':<15} {'Difference':<15}")
    print("-" * 70)
    print(f"{'Pass Rate':<25} {100*p1a_pass/p1a_total:.1f}%{'':<10} {100*p1b_pass/p1b_total:.1f}%{'':<10} {100*(p1b_pass/p1b_total - p1a_pass/p1a_total):+.1f}%")
    print(f"{'Average Score':<25} {p1a_avg_score:.4f}{'':<10} {p1b_avg_score:.4f}{'':<10} {p1b_avg_score-p1a_avg_score:+.4f}")
    print(f"{'Average Rounds':<25} {p1a_avg_rounds:.1f}{'':<11} {p1b_avg_rounds:.1f}{'':<11} {p1b_avg_rounds-p1a_avg_rounds:+.1f}")
    
    # Per-question comparison
    print()
    print("=" * 80)
    print("PER-QUESTION COMPARISON")
    print("=" * 80)
    print(f"{'Question':<25} {'P1A Score':<12} {'P1B Score':<12} {'Diff':<10} {'Winner'}")
    print("-" * 70)
    
    p1a_wins = 0
    p1b_wins = 0
    ties = 0
    
    for qid in sorted(p1a_questions):
        p1a_r = get_final_result(p1a, qid)
        p1b_r = get_final_result(p1b, qid)
        if p1a_r and p1b_r:
            diff = p1b_r['final_score'] - p1a_r['final_score']
            if abs(diff) < 0.01:
                winner = "TIE"
                ties += 1
            elif diff > 0:
                winner = "P1B (Mem)"
                p1b_wins += 1
            else:
                winner = "P1A (No Mem)"
                p1a_wins += 1
            print(f"{qid:<25} {p1a_r['final_score']:.4f}{'':<6} {p1b_r['final_score']:.4f}{'':<6} {diff:+.4f}{'':<4} {winner}")
    
    print("-" * 70)
    print(f"Winners: P1A={p1a_wins}, P1B={p1b_wins}, Tie={ties}")
    
    # Memory analysis for P1B
    print()
    print("=" * 80)
    print("MEMORY USAGE ANALYSIS (P1B)")
    print("=" * 80)
    
    for qid in sorted(p1b_questions):
        q_records = [r for r in p1b if r['question_id'] == qid]
        for r in q_records:
            if r.get('memory_used', False):
                print(f"Round {r['round']}: {qid} - memory_used=True")
                # ดู feedback ที่ได้
                break

if __name__ == "__main__":
    main()
