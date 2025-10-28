# Configuration Guide

This guide explains all configuration options for the Teaching Lightweight LLM system.

## Configuration Files

The system uses several YAML configuration files located in the `config/` directory:

```
config/
├── config.yaml              # Main system configuration
├── models.yaml              # Model definitions
├── strategies.yaml          # Strategy configurations
├── canonical_concepts.json  # Canonical concept definitions
└── ai_config.py            # AI provider settings
```

## Main Configuration (config.yaml)

### Location
`config/config.yaml`

### Key Settings

#### Experiment Parameters
```yaml
experiment:
  max_iterations: 3          # Maximum teaching iterations per task
  timeout: 300               # Timeout per task (seconds)
  save_interval: 10          # Save progress every N tasks
```

#### Model Settings
```yaml
models:
  default_student: "tinyllama_1.1b"
  default_teacher: "gemini-1.5-flash"
  local_model_path: "src/models/"
```

#### Strategy Settings
```yaml
strategies:
  enable_memory: true
  memory_top_k: 5           # Number of similar memories to retrieve
  similarity_threshold: 0.7  # Minimum similarity for retrieval
```

#### Output Settings
```yaml
output:
  results_dir: "results"
  verbose: false
  save_memory: true
  save_feedback: true
```

## Model Configuration (models.yaml)

### Location
`config/models.yaml`

### Structure
```yaml
student_models:
  tinyllama_1.1b:
    path: "src/models/tinyllama_1_1b"
    context_length: 2048
    temperature: 0.7
    
  llama2_7b:
    path: "src/models/llama2_7b"
    context_length: 4096
    temperature: 0.7
    
  llama3_8b:
    path: "src/models/llama3_8b"
    context_length: 8192
    temperature: 0.7

teacher_models:
  gemini-1.5-flash:
    provider: "google"
    temperature: 0.7
    max_tokens: 2048
    
  gemini-1.5-pro:
    provider: "google"
    temperature: 0.7
    max_tokens: 8192
    
  mixtral-8x7b-32768:
    provider: "groq"
    temperature: 0.7
    max_tokens: 32768
```

### Adding New Models

#### Add Student Model
1. Place model files in `src/models/<model_name>/`
2. Add entry to `models.yaml`:
```yaml
student_models:
  my_new_model:
    path: "src/models/my_new_model"
    context_length: 4096
    temperature: 0.7
```

#### Add Teacher Model
1. Get API access for the model
2. Add to `models.yaml`:
```yaml
teacher_models:
  new_teacher:
    provider: "groq"  # or "google"
    temperature: 0.7
    max_tokens: 4096
```

## Strategy Configuration (strategies.yaml)

### Location
`config/strategies.yaml`

### Available Strategies

#### Baseline
```yaml
baseline:
  description: "Direct prompting without memory"
  use_memory: false
  use_reflection: false
```

#### Reflection
```yaml
reflection:
  description: "Self-reflection after each attempt"
  use_memory: false
  use_reflection: true
  reflection_prompt: "Analyze your previous answer and improve it"
```

#### Multi-Key Retrieval
```yaml
multikey:
  description: "Multi-key memory retrieval"
  use_memory: true
  retrieval_method: "multikey"
  num_keys: 3
  top_k: 5
```

#### TF-IDF Based
```yaml
tfidf:
  description: "TF-IDF based memory retrieval"
  use_memory: true
  retrieval_method: "tfidf"
  top_k: 5
```

#### Combined Approach
```yaml
multikey_tfidf:
  description: "Combined multi-key and TF-IDF"
  use_memory: true
  retrieval_method: "hybrid"
  multikey_weight: 0.6
  tfidf_weight: 0.4
  top_k: 5
```

#### Canonical Similarity
```yaml
canonical_similarity:
  description: "Retrieval using canonical concepts"
  use_memory: true
  retrieval_method: "canonical"
  use_synonyms: true
  concept_file: "config/canonical_concepts.json"
```

### Creating Custom Strategies

1. Add to `strategies.yaml`:
```yaml
my_custom_strategy:
  description: "My custom approach"
  use_memory: true
  retrieval_method: "custom"
  custom_param1: value1
  custom_param2: value2
```

2. Implement in code:
```python
# In src/pipelines/unified_pipeline.py or create new file
class MyCustomStrategy:
    def __init__(self, config):
        self.config = config
    
    def process(self, question, context):
        # Your implementation
        pass
```

## Canonical Concepts (canonical_concepts.json)

### Location
`config/canonical_concepts.json`

### Structure
```json
{
  "concepts": [
    {
      "canonical": "mathematics",
      "synonyms": ["math", "calculation", "arithmetic", "algebra"],
      "category": "subject"
    },
    {
      "canonical": "programming",
      "synonyms": ["coding", "development", "software"],
      "category": "skill"
    }
  ]
}
```

### Adding New Concepts
```json
{
  "canonical": "your_concept",
  "synonyms": ["synonym1", "synonym2", "synonym3"],
  "category": "your_category"
}
```

## AI Provider Configuration (ai_config.py)

### Location
`config/ai_config.py`

### Google (Gemini) Configuration
```python
GOOGLE_CONFIG = {
    "api_key": os.getenv("GOOGLE_API_KEY"),
    "default_model": "gemini-1.5-flash",
    "temperature": 0.7,
    "safety_settings": {
        "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
        "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE"
    }
}
```

### Groq Configuration
```python
GROQ_CONFIG = {
    "api_key": os.getenv("GROQ_API_KEY"),
    "default_model": "mixtral-8x7b-32768",
    "temperature": 0.7,
    "max_retries": 3
}
```

### Environment Variables
Set these before running:
```bash
# Windows
set GROQ_API_KEY=your_groq_key
set GOOGLE_API_KEY=your_google_key

# Linux/Mac
export GROQ_API_KEY=your_groq_key
export GOOGLE_API_KEY=your_google_key
```

## Parameter Tuning Guide

### Temperature
- **Range**: 0.0 to 1.0
- **Low (0.1-0.3)**: Deterministic, focused responses
- **Medium (0.5-0.7)**: Balanced creativity and consistency
- **High (0.8-1.0)**: Creative, diverse responses

### Max Iterations
- **1-2**: Quick tests, simple tasks
- **3-5**: Standard experiments
- **5-10**: Complex tasks, research quality

### Top-K (Memory Retrieval)
- **1-3**: Very selective, high precision
- **5-7**: Balanced approach
- **10+**: Broader context, may include noise

### Similarity Threshold
- **0.9+**: Very strict matching
- **0.7-0.8**: Standard threshold
- **<0.7**: Permissive matching

## Performance Tuning

### For Speed
```yaml
experiment:
  max_iterations: 2
  
models:
  default_student: "tinyllama_1.1b"
  default_teacher: "gemini-1.5-flash"
  
strategies:
  memory_top_k: 3
```

### For Quality
```yaml
experiment:
  max_iterations: 5
  
models:
  default_student: "llama3_8b"
  default_teacher: "gemini-1.5-pro"
  
strategies:
  memory_top_k: 7
  similarity_threshold: 0.75
```

### For Cost Efficiency
```yaml
experiment:
  max_iterations: 3
  
models:
  default_teacher: "gemini-1.5-flash"  # Cheaper than Pro
  
strategies:
  memory_top_k: 5
```

## Configuration Best Practices

1. **Start with Defaults**: Use provided configurations first
2. **Document Changes**: Keep notes on what you modify
3. **Version Control**: Track configuration files in git
4. **Test Incrementally**: Change one parameter at a time
5. **Backup Configs**: Save working configurations
6. **Use Comments**: Document why you chose specific values

## Configuration Hierarchy

When running experiments, configurations are merged in this order:
1. Default values (hardcoded)
2. Config files (config/, models.yaml, strategies.yaml)
3. Command-line arguments (highest priority)

Example:
```bash
# This overrides the config file setting
python run_experiment.py --max-iters 5
```

## Troubleshooting

### Configuration Not Loading
- Check YAML syntax (use validator)
- Verify file paths are correct
- Look for typos in parameter names

### Model Not Found
- Verify path in models.yaml
- Check model files exist
- Ensure correct directory structure

### Strategy Errors
- Confirm strategy exists in strategies.yaml
- Check required parameters are set
- Verify memory settings if applicable

### API Issues
- Confirm environment variables are set
- Check API key validity
- Verify provider configuration

## See Also
- [Execution Guide](execution.md)
- [Model Setup Guide](models.md)
- [Strategy Development Guide](strategies.md)
