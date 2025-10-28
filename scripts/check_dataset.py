"""
Check Dataset File

Validates and displays contents of dataset files.
"""

import json
import sys
from pathlib import Path

def check_dataset(filepath):
    """Check and display dataset contents."""
    path = Path(filepath)
    
    if not path.exists():
        print(f"Error: File not found: {filepath}")
        return
    
    try:
        with open(path, encoding='utf-8') as f:
            lines = f.readlines()
        
        print(f"Dataset: {path.name}")
        print(f"Total questions: {len(lines)}\n")
        print("Dataset contents:")
        print("=" * 80)

        for i, line in enumerate(lines[:10], 1):  # Show first 10
            data = json.loads(line)
            print(f"\n{i}. ID: {data.get('id', 'N/A')}")
            
            question = data.get('question', data.get('instruction', 'N/A'))
            if len(question) > 100:
                question = question[:100] + "..."
            print(f"   Question: {question}")
            print(f"   Expected keywords: {data.get('expected_keywords', [])}")
        
        if len(lines) > 10:
            print(f"\n... and {len(lines) - 10} more questions")
        
        print("\n" + "=" * 80)
        print(f"Validation: OK - {len(lines)} questions loaded successfully")
        
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON format - {e}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
    else:
        # Default to alpaca_20.jsonl
        filepath = "data/alpaca_20.jsonl"
        print(f"No file specified, using default: {filepath}\n")
    
    check_dataset(filepath)
