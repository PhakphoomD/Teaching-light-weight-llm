"""
Medical Dataset Preparation Script

This script processes raw medical Q&A CSV files and prepares them for the teaching loop system.

Features:
1. Load all CSV files from Medical_Q&A directory
2. Clean and normalize questions and answers
3. Remove duplicates
4. Validate format
5. Export to JSONL format compatible with the system

Usage:
    python scripts/dataset/prepare_medquad.py --output data/medical_clean.jsonl --sample 200
"""

import csv
import json
import re
from pathlib import Path
from typing import List, Dict, Any
import argparse
from collections import defaultdict


class MedicalDatasetCleaner:
    """Clean and prepare medical Q&A dataset."""
    
    def __init__(self):
        self.records = []
        self.stats = defaultdict(int)
    
    def load_csv_files(self, directory: Path) -> List[Dict[str, Any]]:
        """
        Load all CSV files from directory.
        
        Args:
            directory: Path to Medical_Q&A directory
        
        Returns:
            List of raw records
        """
        raw_records = []
        csv_files = list(directory.glob("*.csv"))
        
        print(f"Found {len(csv_files)} CSV files")
        
        for csv_file in csv_files:
            source_name = csv_file.stem
            print(f"  Loading {csv_file.name}...", end=" ")
            
            try:
                with open(csv_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    count = 0
                    
                    for row in reader:
                        # Handle different column names
                        question = row.get('Question') or row.get('question') or ''
                        answer = row.get('Answer') or row.get('answer') or row.get('reference') or ''
                        topic = row.get('topic', source_name)
                        
                        if question and answer:
                            raw_records.append({
                                'question': question.strip(),
                                'answer': answer.strip(),
                                'topic': topic,
                                'source': source_name
                            })
                            count += 1
                    
                    print(f"✓ {count} records")
                    self.stats[f'loaded_{source_name}'] = count
            
            except Exception as e:
                print(f"✗ Error: {e}")
                self.stats[f'error_{source_name}'] = 1
        
        return raw_records
    
    def clean_text(self, text: str) -> str:
        """
        Clean and normalize text.
        
        Args:
            text: Raw text
        
        Returns:
            Cleaned text
        """
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove leading/trailing whitespace
        text = text.strip()
        
        # Remove special formatting artifacts
        text = re.sub(r'\n+', ' ', text)  # Replace newlines with space
        text = re.sub(r'\r', '', text)     # Remove carriage returns
        
        # Normalize quotes
        text = text.replace('"', '"').replace('"', '"')
        text = text.replace(''', "'").replace(''', "'")
        
        # Remove multiple spaces
        text = re.sub(r'  +', ' ', text)
        
        return text
    
    def is_valid_record(self, record: Dict[str, Any]) -> bool:
        """
        Validate record quality.
        
        Args:
            record: Record to validate
        
        Returns:
            True if valid, False otherwise
        """
        question = record['question']
        answer = record['answer']
        
        # Check minimum length
        if len(question) < 10:
            self.stats['rejected_short_question'] += 1
            return False
        
        if len(answer) < 20:
            self.stats['rejected_short_answer'] += 1
            return False
        
        # Check maximum length (too long may not fit in context)
        if len(question) > 500:
            self.stats['rejected_long_question'] += 1
            return False
        
        if len(answer) > 2000:
            self.stats['rejected_long_answer'] += 1
            return False
        
        # Check if question is actually a question
        question_lower = question.lower()
        is_question = (
            question.endswith('?') or
            any(question_lower.startswith(w) for w in [
                'what', 'how', 'why', 'when', 'where', 'who', 
                'is', 'are', 'do', 'does', 'can', 'should'
            ])
        )
        
        if not is_question:
            self.stats['rejected_not_question'] += 1
            return False
        
        return True
    
    def remove_duplicates(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove duplicate questions.
        
        Args:
            records: List of records
        
        Returns:
            Deduplicated records
        """
        seen_questions = set()
        unique_records = []
        
        for record in records:
            # Normalize question for comparison
            normalized_q = record['question'].lower().strip()
            
            if normalized_q not in seen_questions:
                seen_questions.add(normalized_q)
                unique_records.append(record)
            else:
                self.stats['duplicates_removed'] += 1
        
        return unique_records
    
    def process(self, input_dir: Path, max_records: int = None) -> List[Dict[str, Any]]:
        """
        Complete processing pipeline.
        
        Args:
            input_dir: Directory containing CSV files
            max_records: Maximum records to output (None = all)
        
        Returns:
            List of cleaned records
        """
        print("="*80)
        print("MEDICAL DATASET PREPARATION")
        print("="*80)
        
        # Step 1: Load CSV files
        print("\n[1/5] Loading CSV files...")
        raw_records = self.load_csv_files(input_dir)
        print(f"  Total raw records: {len(raw_records)}")
        
        # Step 2: Clean text
        print("\n[2/5] Cleaning text...")
        for record in raw_records:
            record['question'] = self.clean_text(record['question'])
            record['answer'] = self.clean_text(record['answer'])
        print(f"  ✓ Text cleaned")
        
        # Step 3: Validate records
        print("\n[3/5] Validating records...")
        valid_records = [r for r in raw_records if self.is_valid_record(r)]
        print(f"  Valid records: {len(valid_records)}/{len(raw_records)}")
        
        # Step 4: Remove duplicates
        print("\n[4/5] Removing duplicates...")
        unique_records = self.remove_duplicates(valid_records)
        print(f"  Unique records: {len(unique_records)}")
        
        # Step 5: Sample if requested
        if max_records and len(unique_records) > max_records:
            print(f"\n[5/5] Sampling {max_records} records...")
            # Sample evenly from all topics
            from collections import defaultdict
            by_topic = defaultdict(list)
            for record in unique_records:
                by_topic[record['topic']].append(record)
            
            sampled = []
            per_topic = max_records // len(by_topic)
            for topic, records in by_topic.items():
                sampled.extend(records[:per_topic])
            
            # Fill remaining slots
            remaining = max_records - len(sampled)
            if remaining > 0:
                unused = [r for r in unique_records if r not in sampled]
                sampled.extend(unused[:remaining])
            
            unique_records = sampled[:max_records]
            print(f"  Sampled: {len(unique_records)} records")
        else:
            print(f"\n[5/5] Using all records")
        
        self.records = unique_records
        return unique_records
    
    def export_jsonl(self, output_path: Path):
        """
        Export to JSONL format.
        
        Args:
            output_path: Output file path
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            for i, record in enumerate(self.records):
                jsonl_record = {
                    'id': f'medical-{i}',
                    'question': record['question'],
                    'answer': record['answer'],  # Note: system uses 'answer' not 'reference'
                    'topic': record['topic'],
                    'source': record['source']
                }
                f.write(json.dumps(jsonl_record, ensure_ascii=False) + '\n')
        
        print(f"\n✓ Exported to: {output_path}")
        print(f"  Total records: {len(self.records)}")
    
    def print_stats(self):
        """Print processing statistics."""
        print("\n" + "="*80)
        print("PROCESSING STATISTICS")
        print("="*80)
        
        # Group by category
        loaded = {k: v for k, v in self.stats.items() if k.startswith('loaded_')}
        rejected = {k: v for k, v in self.stats.items() if k.startswith('rejected_')}
        
        if loaded:
            print("\nLoaded by source:")
            for source, count in sorted(loaded.items()):
                source_name = source.replace('loaded_', '')
                print(f"  {source_name:<40} {count:>6} records")
        
        if rejected:
            print("\nRejected:")
            for reason, count in sorted(rejected.items()):
                reason_name = reason.replace('rejected_', '').replace('_', ' ')
                print(f"  {reason_name:<40} {count:>6} records")
        
        if self.stats.get('duplicates_removed'):
            print(f"\nDuplicates removed: {self.stats['duplicates_removed']}")
    
    def print_sample(self, n: int = 3):
        """Print sample records."""
        print("\n" + "="*80)
        print(f"SAMPLE RECORDS (first {n})")
        print("="*80)
        
        for i, record in enumerate(self.records[:n], 1):
            print(f"\n[{i}] Topic: {record['topic']}")
            print(f"Question: {record['question'][:100]}...")
            print(f"Answer: {record['answer'][:100]}...")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Prepare medical Q&A dataset for teaching loop system"
    )
    parser.add_argument(
        '--input',
        type=str,
        default='data/Medical_Q&A',
        help='Input directory with CSV files (default: data/Medical_Q&A)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='data/medical_clean.jsonl',
        help='Output JSONL file (default: data/medical_clean.jsonl)'
    )
    parser.add_argument(
        '--sample',
        type=int,
        default=None,
        help='Maximum number of records to output (default: all)'
    )
    parser.add_argument(
        '--no-stats',
        action='store_true',
        help='Do not print statistics'
    )
    
    args = parser.parse_args()
    
    # Initialize cleaner
    cleaner = MedicalDatasetCleaner()
    
    # Process
    input_dir = Path(args.input)
    output_path = Path(args.output)
    
    records = cleaner.process(input_dir, max_records=args.sample)
    
    # Export
    cleaner.export_jsonl(output_path)
    
    # Print statistics
    if not args.no_stats:
        cleaner.print_stats()
        cleaner.print_sample(n=3)
    
    print("\n✓ Done!\n")
    print("Next steps:")
    print(f"1. Review: cat {output_path}")
    print(f"2. Test: python simplified_experiment_runner.py --questions 5")
    print(f"3. Update config: dataset.path = '{output_path}'")


if __name__ == "__main__":
    main()
