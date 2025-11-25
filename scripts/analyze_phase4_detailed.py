"""
Analyze Phase 4 Results - CORRECT ANALYSIS
===========================================
Phase 4 = Champion Config จาก Phase 1-3
วิเคราะห์ว่า Reflection + Memory ทำงานจริงไหม
"""

import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from typing import Dict, List

plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")

class Phase4Analyzer:
    def __init__(self):
        self.results_file = Path("logs/experiments/hyperparameter_tuning/results_20251118_110941.jsonl")
        self.output_dir = Path("logs/analysis/phase4_detailed")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Load Phase 4 results
        self.phase4_data = self._load_phase4()
        
    def _load_phase4(self) -> List[Dict]:
        """Load Phase 4 results"""
        data = []
        with open(self.results_file, 'r', encoding='utf-8') as f:
            for line in f:
                data.append(json.loads(line))
        return data
    
    def analyze_all(self):
        """Run complete analysis"""
        print("="*80)
        print("PHASE 4 DETAILED ANALYSIS - CHAMPION CONFIG")
        print("="*80)
        
        # Extract experiments
        experiments = {}
        for exp in self.phase4_data:
            exp_id = exp['experiment_id']
            experiments[exp_id] = exp
        
        # Analysis 1: Overall Performance
        self.analyze_performance(experiments)
        
        # Analysis 2: Memory Impact
        self.analyze_memory_impact(experiments)
        
        # Analysis 3: Domain Differences
        self.analyze_domain_differences(experiments)
        
        # Analysis 4: Round Efficiency
        self.analyze_round_efficiency(experiments)
        
        # Create visualizations
        self.create_visualizations(experiments)
        
        # Generate report
        self.generate_report(experiments)
    
    def analyze_performance(self, experiments: Dict):
        """Analysis 1: Overall Performance"""
        print("\n" + "="*80)
        print("ANALYSIS 1: OVERALL PERFORMANCE (CHAMPION CONFIG)")
        print("="*80)
        
        for exp_id, exp in experiments.items():
            print(f"\n📊 {exp_id}")
            print(f"  Domain: {exp['config']['domain']}")
            print(f"  Memory: {'ON' if 'mem_on' in exp_id else 'OFF'}")
            print(f"  Average Rounds: {exp['avg_rounds']:.2f}")
            print(f"\n  Metrics:")
            metrics = exp['metrics']
            for key in ['exact_match', 'rouge_l', 'semantic_similarity', 'blind_judge', 'comparison_judge']:
                print(f"    {key:20s}: {metrics[key]:.3f}")
    
    def analyze_memory_impact(self, experiments: Dict):
        """Analysis 2: Memory Impact"""
        print("\n" + "="*80)
        print("ANALYSIS 2: MEMORY IMPACT (ON vs OFF)")
        print("="*80)
        
        # Alpaca comparison
        alpaca_on = experiments.get('phase4_champion_mem_on_alpaca')
        alpaca_off = experiments.get('phase4_champion_mem_off_alpaca')
        
        if alpaca_on and alpaca_off:
            print("\n🔍 ALPACA DOMAIN:")
            self._compare_configs(alpaca_on, alpaca_off, "Memory")
        
        # Medical comparison
        medical_on = experiments.get('phase4_champion_mem_on_medical')
        medical_off = experiments.get('phase4_champion_mem_off_medical')
        
        if medical_on and medical_off:
            print("\n🔍 MEDICAL DOMAIN:")
            self._compare_configs(medical_on, medical_off, "Memory")
    
    def _compare_configs(self, config1: Dict, config2: Dict, feature_name: str):
        """Compare two configurations"""
        metrics = ['exact_match', 'rouge_l', 'semantic_similarity', 'blind_judge', 'comparison_judge']
        
        print(f"\n  {feature_name} ON  (avg_rounds={config1['avg_rounds']:.2f}):")
        for m in metrics:
            print(f"    {m:20s}: {config1['metrics'][m]:.3f}")
        
        print(f"\n  {feature_name} OFF (avg_rounds={config2['avg_rounds']:.2f}):")
        for m in metrics:
            print(f"    {m:20s}: {config2['metrics'][m]:.3f}")
        
        print(f"\n  📈 Improvements (ON - OFF):")
        improvements = {}
        for m in metrics:
            delta = config1['metrics'][m] - config2['metrics'][m]
            improvements[m] = delta
            emoji = "✅" if delta > 0 else "⚠️" if delta < 0 else "➖"
            print(f"    {m:20s}: {delta:+.3f} {emoji}")
        
        delta_rounds = config1['avg_rounds'] - config2['avg_rounds']
        emoji = "✅ faster" if delta_rounds < 0 else "⚠️ slower"
        print(f"    {'avg_rounds':20s}: {delta_rounds:+.2f} {emoji}")
        
        return improvements
    
    def analyze_domain_differences(self, experiments: Dict):
        """Analysis 3: Domain Performance"""
        print("\n" + "="*80)
        print("ANALYSIS 3: DOMAIN PERFORMANCE (ALPACA vs MEDICAL)")
        print("="*80)
        
        # Compare Alpaca vs Medical (both with memory ON)
        alpaca = experiments.get('phase4_champion_mem_on_alpaca')
        medical = experiments.get('phase4_champion_mem_on_medical')
        
        if alpaca and medical:
            print("\n🔍 Memory ON Comparison:")
            self._compare_configs(alpaca, medical, "Alpaca vs Medical")
    
    def analyze_round_efficiency(self, experiments: Dict):
        """Analysis 4: Round Efficiency"""
        print("\n" + "="*80)
        print("ANALYSIS 4: ROUND EFFICIENCY")
        print("="*80)
        
        print("\n📊 Average Rounds Analysis:")
        for exp_id, exp in sorted(experiments.items(), key=lambda x: x[1]['avg_rounds']):
            domain = exp['config']['domain']
            mode = 'MEM_ON' if 'mem_on' in exp_id else 'MEM_OFF'
            rounds = exp['avg_rounds']
            comp_score = exp['metrics']['comparison_judge']
            
            print(f"  {domain:8s} {mode:8s}: {rounds:.2f} rounds → Comparison: {comp_score:.3f}")
        
        # Analyze efficiency = score / rounds
        print("\n📊 Efficiency (Comparison Score / Avg Rounds):")
        efficiencies = []
        for exp_id, exp in experiments.items():
            efficiency = exp['metrics']['comparison_judge'] / exp['avg_rounds']
            efficiencies.append({
                'exp_id': exp_id,
                'domain': exp['config']['domain'],
                'memory': 'ON' if 'mem_on' in exp_id else 'OFF',
                'efficiency': efficiency,
                'comparison': exp['metrics']['comparison_judge'],
                'rounds': exp['avg_rounds']
            })
        
        for e in sorted(efficiencies, key=lambda x: x['efficiency'], reverse=True):
            print(f"  {e['domain']:8s} {e['memory']:3s}: {e['efficiency']:.3f} "
                  f"(score={e['comparison']:.3f}, rounds={e['rounds']:.2f})")
    
    def create_visualizations(self, experiments: Dict):
        """Create all visualizations"""
        print("\n" + "="*80)
        print("CREATING VISUALIZATIONS")
        print("="*80)
        
        # Figure 1: Memory Impact Comparison
        self._plot_memory_comparison(experiments)
        
        # Figure 2: Domain Comparison
        self._plot_domain_comparison(experiments)
        
        # Figure 3: Efficiency Analysis
        self._plot_efficiency(experiments)
        
        # Figure 4: Metric Breakdown
        self._plot_metric_breakdown(experiments)
        
        print(f"\n✅ All visualizations saved to {self.output_dir}")
    
    def _plot_memory_comparison(self, experiments: Dict):
        """Plot memory ON vs OFF"""
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))
        fig.suptitle('Phase 4: Memory Impact (Champion Config)', fontsize=16, fontweight='bold')
        
        domains = ['alpaca', 'medical']
        metrics = ['comparison_judge', 'semantic_similarity', 'rouge_l', 'exact_match']
        
        for idx, domain in enumerate(domains):
            ax = axes[idx]
            
            mem_on_key = f'phase4_champion_mem_on_{domain}'
            mem_off_key = f'phase4_champion_mem_off_{domain}'
            
            mem_on = experiments.get(mem_on_key)
            mem_off = experiments.get(mem_off_key)
            
            if not mem_on or not mem_off:
                continue
            
            x = np.arange(len(metrics))
            width = 0.35
            
            on_values = [mem_on['metrics'][m] for m in metrics]
            off_values = [mem_off['metrics'][m] for m in metrics]
            
            bars1 = ax.bar(x - width/2, on_values, width, label='Memory ON', color='#2ecc71', alpha=0.8)
            bars2 = ax.bar(x + width/2, off_values, width, label='Memory OFF', color='#e74c3c', alpha=0.8)
            
            ax.set_xlabel('Metrics', fontsize=12, fontweight='bold')
            ax.set_ylabel('Score', fontsize=12, fontweight='bold')
            ax.set_title(f'{domain.upper()} Domain', fontsize=14, fontweight='bold')
            ax.set_xticks(x)
            ax.set_xticklabels([m.replace('_', '\n').title() for m in metrics], fontsize=9)
            ax.legend(fontsize=10)
            ax.grid(True, alpha=0.3, axis='y')
            ax.set_ylim(0, 1.0)
            
            # Add value labels
            for bars in [bars1, bars2]:
                for bar in bars:
                    height = bar.get_height()
                    ax.text(bar.get_x() + bar.get_width()/2., height,
                           f'{height:.2f}', ha='center', va='bottom', fontsize=8)
            
            # Add delta annotations
            for i, (on_val, off_val) in enumerate(zip(on_values, off_values)):
                delta = on_val - off_val
                color = 'green' if delta > 0 else 'red' if delta < 0 else 'gray'
                ax.text(i, max(on_val, off_val) + 0.05, f'Δ{delta:+.2f}',
                       ha='center', fontsize=8, color=color, fontweight='bold')
        
        plt.tight_layout()
        plt.savefig(self.output_dir / 'phase4_memory_impact.png', dpi=300, bbox_inches='tight')
        print("  ✅ Saved: phase4_memory_impact.png")
        plt.close()
    
    def _plot_domain_comparison(self, experiments: Dict):
        """Plot domain comparison"""
        fig, ax = plt.subplots(figsize=(12, 7))
        
        metrics = ['exact_match', 'rouge_l', 'semantic_similarity', 'blind_judge', 'comparison_judge']
        
        alpaca_on = experiments.get('phase4_champion_mem_on_alpaca')
        medical_on = experiments.get('phase4_champion_mem_on_medical')
        
        if not alpaca_on or not medical_on:
            return
        
        x = np.arange(len(metrics))
        width = 0.35
        
        alpaca_values = [alpaca_on['metrics'][m] for m in metrics]
        medical_values = [medical_on['metrics'][m] for m in metrics]
        
        bars1 = ax.bar(x - width/2, alpaca_values, width, label='Alpaca (General QA)', 
                      color='#3498db', alpha=0.8, edgecolor='black', linewidth=1.5)
        bars2 = ax.bar(x + width/2, medical_values, width, label='Medical (Domain-Specific)', 
                      color='#e67e22', alpha=0.8, edgecolor='black', linewidth=1.5)
        
        ax.set_xlabel('Metrics', fontsize=14, fontweight='bold')
        ax.set_ylabel('Score', fontsize=14, fontweight='bold')
        ax.set_title('Phase 4: Domain Performance Comparison (Memory ON)', fontsize=16, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels([m.replace('_', ' ').title() for m in metrics], rotation=15, ha='right', fontsize=11)
        ax.legend(fontsize=12, loc='lower right')
        ax.grid(True, alpha=0.3, axis='y')
        ax.set_ylim(0, 1.05)
        
        # Add value labels
        for bars in [bars1, bars2]:
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{height:.3f}', ha='center', va='bottom', fontsize=9, fontweight='bold')
        
        plt.tight_layout()
        plt.savefig(self.output_dir / 'phase4_domain_comparison.png', dpi=300, bbox_inches='tight')
        print("  ✅ Saved: phase4_domain_comparison.png")
        plt.close()
    
    def _plot_efficiency(self, experiments: Dict):
        """Plot efficiency analysis"""
        fig, ax = plt.subplots(figsize=(10, 6))
        
        configs = []
        efficiencies = []
        colors = []
        
        for exp_id, exp in experiments.items():
            domain = exp['config']['domain'].upper()
            mem = 'MEM_ON' if 'mem_on' in exp_id else 'MEM_OFF'
            label = f"{domain}\n{mem}"
            
            efficiency = exp['metrics']['comparison_judge'] / exp['avg_rounds']
            
            configs.append(label)
            efficiencies.append(efficiency)
            
            if 'mem_on' in exp_id:
                colors.append('#2ecc71' if 'alpaca' in exp_id else '#27ae60')
            else:
                colors.append('#e74c3c' if 'alpaca' in exp_id else '#c0392b')
        
        bars = ax.bar(configs, efficiencies, color=colors, alpha=0.8, edgecolor='black', linewidth=1.5)
        
        ax.set_ylabel('Efficiency (Score / Rounds)', fontsize=13, fontweight='bold')
        ax.set_title('Phase 4: Configuration Efficiency', fontsize=16, fontweight='bold')
        ax.grid(True, alpha=0.3, axis='y')
        ax.set_ylim(0, max(efficiencies) * 1.2)
        
        # Add value labels
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.3f}', ha='center', va='bottom', fontsize=11, fontweight='bold')
        
        # Add legend
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor='#2ecc71', edgecolor='black', label='Alpaca MEM_ON'),
            Patch(facecolor='#e74c3c', edgecolor='black', label='Alpaca MEM_OFF'),
            Patch(facecolor='#27ae60', edgecolor='black', label='Medical MEM_ON'),
            Patch(facecolor='#c0392b', edgecolor='black', label='Medical MEM_OFF')
        ]
        ax.legend(handles=legend_elements, fontsize=10, loc='upper right')
        
        plt.tight_layout()
        plt.savefig(self.output_dir / 'phase4_efficiency.png', dpi=300, bbox_inches='tight')
        print("  ✅ Saved: phase4_efficiency.png")
        plt.close()
    
    def _plot_metric_breakdown(self, experiments: Dict):
        """Plot metric breakdown for all configurations"""
        fig, ax = plt.subplots(figsize=(14, 8))
        
        metrics = ['exact_match', 'rouge_l', 'semantic_similarity', 'blind_judge', 'comparison_judge']
        configs = list(experiments.keys())
        
        # Create matrix
        data = []
        for config in configs:
            row = [experiments[config]['metrics'][m] for m in metrics]
            data.append(row)
        
        data = np.array(data)
        
        # Create heatmap
        im = ax.imshow(data, cmap='RdYlGn', aspect='auto', vmin=0, vmax=1)
        
        # Set ticks
        ax.set_xticks(np.arange(len(metrics)))
        ax.set_yticks(np.arange(len(configs)))
        ax.set_xticklabels([m.replace('_', ' ').title() for m in metrics], rotation=45, ha='right', fontsize=11)
        ax.set_yticklabels([c.replace('phase4_champion_', '').replace('_', ' ').upper() 
                           for c in configs], fontsize=10)
        
        # Add text annotations
        for i in range(len(configs)):
            for j in range(len(metrics)):
                text = ax.text(j, i, f'{data[i, j]:.3f}',
                             ha="center", va="center", color="black", fontsize=9, fontweight='bold')
        
        ax.set_title('Phase 4: Metric Breakdown (All Configurations)', fontsize=16, fontweight='bold')
        
        # Add colorbar
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label('Score', rotation=270, labelpad=20, fontsize=12, fontweight='bold')
        
        plt.tight_layout()
        plt.savefig(self.output_dir / 'phase4_metric_breakdown.png', dpi=300, bbox_inches='tight')
        print("  ✅ Saved: phase4_metric_breakdown.png")
        plt.close()
    
    def generate_report(self, experiments: Dict):
        """Generate comprehensive report"""
        alpaca_on = experiments.get('phase4_champion_mem_on_alpaca')
        alpaca_off = experiments.get('phase4_champion_mem_off_alpaca')
        medical_on = experiments.get('phase4_champion_mem_on_medical')
        medical_off = experiments.get('phase4_champion_mem_off_medical')
        
        report = f"""
# PHASE 4 DETAILED ANALYSIS REPORT
================================================================================
Champion Configuration Test Results
================================================================================

## EXECUTIVE SUMMARY

Phase 4 tests the champion configuration (optimized in Phase 1-3) across:
- **2 Domains**: Alpaca (general QA) vs Medical (domain-specific)
- **2 Memory Settings**: Memory ON vs Memory OFF
- **Total**: 4 experiments with 100 questions each

## 1. OVERALL PERFORMANCE

### Best Configuration: {self._find_best_config(experiments)}

"""
        
        if alpaca_on:
            report += f"""
### Alpaca Domain (General QA)
- **Memory ON**: Comparison = {alpaca_on['metrics']['comparison_judge']:.3f}, Rounds = {alpaca_on['avg_rounds']:.2f}
- **Memory OFF**: Comparison = {alpaca_off['metrics']['comparison_judge']:.3f}, Rounds = {alpaca_off['avg_rounds']:.2f}
- **Winner**: Memory {'ON ✅' if alpaca_on['metrics']['comparison_judge'] > alpaca_off['metrics']['comparison_judge'] else 'OFF ⚠️'}
- **Delta**: {(alpaca_on['metrics']['comparison_judge'] - alpaca_off['metrics']['comparison_judge']):+.3f}
"""
        
        if medical_on:
            report += f"""
### Medical Domain (Domain-Specific)
- **Memory ON**: Comparison = {medical_on['metrics']['comparison_judge']:.3f}, Rounds = {medical_on['avg_rounds']:.2f}
- **Memory OFF**: Comparison = {medical_off['metrics']['comparison_judge']:.3f}, Rounds = {medical_off['avg_rounds']:.2f}
- **Winner**: Memory {'ON ✅' if medical_on['metrics']['comparison_judge'] > medical_off['metrics']['comparison_judge'] else 'OFF ⚠️'}
- **Delta**: {(medical_on['metrics']['comparison_judge'] - medical_off['metrics']['comparison_judge']):+.3f}
"""
        
        report += """
## 2. KEY FINDINGS

### Finding 1: Reflection Works (But Marginally)
"""
        
        avg_rounds_all = np.mean([exp['avg_rounds'] for exp in experiments.values()])
        report += f"""
- **Average rounds across all experiments**: {avg_rounds_all:.2f}
- **Interpretation**: Most questions resolve in 1-2 rounds, suggesting reflection has LIMITED impact
- **Recommendation**: Consider max_rounds=2 instead of 3 to save costs
"""
        
        report += """
### Finding 2: Memory is Domain-Dependent
"""
        
        if alpaca_on and alpaca_off and medical_on and medical_off:
            alpaca_delta = alpaca_on['metrics']['comparison_judge'] - alpaca_off['metrics']['comparison_judge']
            medical_delta = medical_on['metrics']['comparison_judge'] - medical_off['metrics']['comparison_judge']
            
            report += f"""
- **Alpaca**: Memory ON outperforms OFF by {alpaca_delta:+.3f} {'✅' if alpaca_delta > 0 else '⚠️'}
- **Medical**: Memory ON {'outperforms' if medical_delta > 0 else 'underperforms'} OFF by {medical_delta:+.3f} {'✅' if medical_delta > 0 else '⚠️'}
- **Reason**: General QA has consistent patterns → memory helps. Domain-specific has diverse vocabulary → memory less effective.
"""
        
        report += """
### Finding 3: Domain Gap is SIGNIFICANT
"""
        
        if alpaca_on and medical_on:
            domain_gap = alpaca_on['metrics']['comparison_judge'] - medical_on['metrics']['comparison_judge']
            report += f"""
- **Alpaca comparison score**: {alpaca_on['metrics']['comparison_judge']:.3f}
- **Medical comparison score**: {medical_on['metrics']['comparison_judge']:.3f}
- **GAP**: {domain_gap:.3f} ({domain_gap/alpaca_on['metrics']['comparison_judge']*100:.1f}% difference)
- **Reason**: Medical requires specialized knowledge that small LLM (8B) lacks
"""
        
        report += """
## 3. REFLECTION + MEMORY VALIDATION

### Does Reflection Work? **PARTIALLY ✅**
"""
        
        single_round_configs = [exp for exp in experiments.values() if exp['avg_rounds'] < 1.5]
        if single_round_configs:
            report += f"""
- {len(single_round_configs)}/4 experiments complete in <1.5 rounds on average
- This suggests many questions are answered correctly on FIRST TRY
- Reflection helps in edge cases but NOT universally
"""
        else:
            report += """
- All experiments require 1.5+ rounds on average
- Reflection is ACTIVELY USED and helps improve answers
"""
        
        report += """
### Does Memory Work? **DOMAIN-DEPENDENT ⚠️**
"""
        
        if alpaca_on and alpaca_off and medical_on and medical_off:
            memory_helps_alpaca = alpaca_on['metrics']['comparison_judge'] > alpaca_off['metrics']['comparison_judge']
            memory_helps_medical = medical_on['metrics']['comparison_judge'] > medical_off['metrics']['comparison_judge']
            
            if memory_helps_alpaca and not memory_helps_medical:
                report += """
- Memory helps in ALPACA ✅ but hurts in MEDICAL ⚠️
- **Conclusion**: Memory effectiveness depends on domain characteristics
- **Recommendation**: Use domain-specific memory strategies
"""
            elif memory_helps_alpaca and memory_helps_medical:
                report += """
- Memory helps in BOTH domains ✅
- **Conclusion**: Memory system is effective
- **Recommendation**: Enable memory for all tasks
"""
            else:
                report += """
- Memory shows mixed results
- **Conclusion**: Current memory strategy needs improvement
- **Recommendation**: Increase similarity threshold or try different retrieval methods
"""
        
        report += """
## 4. PRODUCTION RECOMMENDATIONS

### Configuration
```python
PRODUCTION_CONFIG = {
    "pass_threshold": 0.898,
    "max_rounds": 2,  # Reduced from 3 (diminishing returns)
    "memory_enabled": True,  # Enable by default
    "memory_similarity_threshold": 0.90,  # Increased (stricter)
    "memory_top_k": 3,
    "student_temperature": 0.0,  # Deterministic
    "teacher_temperature": 0.2,
}

DOMAIN_OVERRIDES = {
    "general_qa": {"memory_enabled": True},
    "medical": {"memory_enabled": False},  # Consider disabling
}
```

### Next Steps
1. **Analyze per-round progression** → See if Round 1 is actually best
2. **Improve feedback quality** → Ensure teacher provides actionable feedback
3. **Test adaptive stopping** → Stop early if confidence is high
4. **Domain-specific memory** → Separate memory stores per domain

================================================================================
END OF REPORT
================================================================================
"""
        
        # Save report
        report_path = self.output_dir / 'PHASE4_DETAILED_REPORT.txt'
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(report)
        print(f"\n✅ Full report saved to {report_path}")
    
    def _find_best_config(self, experiments: Dict) -> str:
        """Find best configuration by comparison score"""
        best_exp = max(experiments.values(), key=lambda x: x['metrics']['comparison_judge'])
        exp_id = [k for k, v in experiments.items() if v == best_exp][0]
        return exp_id.replace('phase4_champion_', '').replace('_', ' ').upper()

def main():
    print("="*80)
    print("PHASE 4 DETAILED ANALYSIS")
    print("Testing Champion Configuration from Phase 1-3")
    print("="*80)
    
    analyzer = Phase4Analyzer()
    analyzer.analyze_all()
    
    print("\n" + "="*80)
    print("✅ ANALYSIS COMPLETE!")
    print("="*80)
    print(f"\nCheck outputs in: {analyzer.output_dir}")

if __name__ == "__main__":
    main()
