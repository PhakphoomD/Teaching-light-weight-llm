"""
Split Medical Dataset by Source

This script splits the cleaned medical dataset into separate files by source.

Usage:
    python scripts/split_medical_by_source.py --input data/medical_all_clean.jsonl --output-dir data/medical_by_source/
"""

import json
import argparse
from pathlib import Path
from collections import defaultdict


def split_by_source(input_file: Path, output_dir: Path):
    """Split JSONL file by source field."""
    
    print("="*80)
    print("SPLITTING MEDICAL DATASET BY SOURCE")
    print("="*80)
    
    # Read all records
    print(f"\nReading: {input_file}")
    records_by_source = defaultdict(list)
    
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            record = json.loads(line)
            source = record.get('source', 'unknown')
            records_by_source[source].append(record)
    
    total_records = sum(len(records) for records in records_by_source.values())
    print(f"Total records: {total_records}")
    print(f"Sources found: {len(records_by_source)}")
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Write separate files
    print(f"\nWriting to: {output_dir}/")
    for source, records in sorted(records_by_source.items()):
        output_file = output_dir / f"{source}.jsonl"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
        
        print(f"  ✓ {source:<45} {len(records):>6} records -> {output_file.name}")
    
    # Create combined stats file
    stats_file = output_dir / "README.md"
    with open(stats_file, 'w', encoding='utf-8') as f:
        f.write("# Medical Q&A Dataset by Source\n\n")
        f.write(f"Total Records: **{total_records:,}**\n\n")
        f.write("## Files\n\n")
        f.write("| File | Records | Description |\n")
        f.write("|------|---------|-------------|\n")
        
        for source, records in sorted(records_by_source.items(), key=lambda x: -len(x[1])):
            f.write(f"| `{source}.jsonl` | {len(records):,} | {source.replace('QA', ' Q&A')} |\n")
        
        f.write("\n## Sample Usage\n\n")
        f.write("```python\n")
        f.write("# Load specific source\n")
        f.write("import json\n\n")
        f.write("records = []\n")
        f.write("with open('medical_by_source/CancerQA.jsonl') as f:\n")
        f.write("    for line in f:\n")
        f.write("        records.append(json.loads(line))\n")
        f.write("```\n")
    
    print(f"\n✓ Stats written to: {stats_file}")
    print("\n✓ Done!")


def main():
    parser = argparse.ArgumentParser(
        description="Split medical dataset by source"
    )
    parser.add_argument(
        '--input',
        type=str,
        default='data/medical_all_clean.jsonl',
        help='Input JSONL file'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='data/medical_by_source',
        help='Output directory'
    )
    
    args = parser.parse_args()
    
    split_by_source(Path(args.input), Path(args.output_dir))


if __name__ == "__main__":
    main()
