# Medical Q&A Dataset by Source

Total Records: **12,428**

## Files

| File | Records | Description |
|------|---------|-------------|
| `Genetic_and_Rare_DiseasesQA.jsonl` | 4,511 | Genetic_and_Rare_Diseases Q&A |
| `growth_hormone_receptorQA.jsonl` | 4,452 | growth_hormone_receptor Q&A |
| `MedicalQuestionAnswering.jsonl` | 1,982 | MedicalQuestionAnswering |
| `Diabetes_and_Digestive_and_Kidney_DiseasesQA.jsonl` | 656 | Diabetes_and_Digestive_and_Kidney_Diseases Q&A |
| `CancerQA.jsonl` | 370 | Cancer Q&A |
| `Heart_Lung_and_BloodQA.jsonl` | 246 | Heart_Lung_and_Blood Q&A |
| `Disease_Control_and_PreventionQA.jsonl` | 211 | Disease_Control_and_Prevention Q&A |

## Sample Usage

```python
# Load specific source
import json

records = []
with open('medical_by_source/CancerQA.jsonl') as f:
    for line in f:
        records.append(json.loads(line))
```
