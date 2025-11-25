# Memory System Analysis: Current vs GPT Recommendations

## 🔍 สถานะปัจจุบัน (Current State)

### 1. Task Classification
**ปัจจุบัน:**
- ✅ Regex-based classifier (fast, lightweight)
- ✅ 10 task types pre-defined
- ✅ Returns (task_type, confidence)
- ❌ ไม่มี pre-normalization (unicode, lowercase)
- ❌ ไม่มี structure_signature extraction
- ❌ ไม่มี constraints extraction (n, style, cite)
- ❌ ไม่มี fallback classifier

**GPT แนะนำ:**
- Pre-normalize: lowercase, unicode-normalize
- Regex bank เรียงตาม priority พร้อม capture groups
- Extract: task_type, structure_signature, constraints
- Validator: ตรวจสอบความสมเหตุผล
- Fallback: mini classifier/LLM-cheap สำหรับ unknown cases
- Logging: เก็บ unknown/ambiguous cases

### 2. Memory Storage Schema
**ปัจจุบัน (logs/memory/store.jsonl):**
```json
{
  "id": "20251111_151735_6f5c",
  "question": "ชื่อกีฬา extreme 5 อย่าง",  // ❌ เก็บ content เต็ม
  "answer": "Football, Basketball...",     // ❌ เก็บคำตอบเต็ม
  "task_type": "list_generation",          // ✅ มี task_type
  "task_confidence": "high",               // ✅ มี confidence
  "evaluation": "incorrect",
  "reasoning": "...",                      // ❌ เก็บ reasoning ยาว
  "hint": "...",                           // ✅ เก็บ hint (แต่ยาวเกิน)
  "stop_score": 3,
  "error_keys": ["completeness"],          // ✅ มี error_keys
  "timestamp": "2025-11-11T15:17:35"
}
```

**GPT แนะนำ (episodes.jsonl):**
```json
{
  "id": "ep_001",
  "task_type": "list_generation",          // ✅ same
  "structure_signature": "numbered(5)",    // ❌ ไม่มี
  "constraints": {                         // ❌ ไม่มี
    "n": 5,
    "style": "numbered",
    "cite": false
  },
  "error_keys": ["completeness", "count"], // ✅ same
  "domain": "sports",                      // ❌ ไม่มี
  "lang": "th",                           // ❌ ไม่มี
  "semantic_rules": [                      // ❌ แยกไฟล์ (semantic_rules.json)
    "When listing n items, output exactly n numbered bullets."
  ],
  "template": "1. [item]\n2. [item]...",  // ❌ ไม่มี
  "hard_negative_hashes": ["abc123"],     // ❌ แยกไฟล์ (hard_negatives.json)
  "timestamp": "2025-11-11T15:17:35"
}
```

### 3. Vector Embedding Strategy
**ปัจจุบัน:**
- ❌ Embed raw question: "ชื่อกีฬา extreme 5 อย่าง"
- ✅ Model: all-MiniLM-L6-v2 (384-dim, English-focused)
- ✅ FAISS IndexFlatIP (cosine similarity)
- ❌ Embed content words → low same-task similarity

**GPT แนะนำ:**
- ✅ Embed structure only: "list_generation | numbered(5) | n=5"
- ✅ ไม่ embed content (sports, subjects)
- ✅ Multilingual model: intfloat/multilingual-e5-base
- ✅ TF-IDF fallback option

### 4. Retrieval Policy
**ปัจจุบัน (Hybrid):**
```python
# Step 1: Extract task_type
task_type = extract_task_type(question)

# Step 2: Hard filter by task_type (exact match)
same_task = [r for r in all_records if r["task_type"] == task_type]

# Step 3: Semantic similarity within same_task
similar_ids = index.retrieve(question, k=len(same_task))
filtered = [id for id in similar_ids if id in same_task_ids][:k]

# Step 4: Build context from hints
hints = [records[id]["hint"] for id in filtered]
```

**GPT แนะนำ (Multi-stage filtering):**
```python
# Stage 1: Route by task_type (must match)
candidates = filter_by_task_type(task_type)

# Stage 2: Filter by structure_signature
candidates = filter_by_structure(candidates, structure_sig)

# Stage 3: Tag match error_keys
candidates = prioritize_by_error_keys(candidates, current_errors)

# Stage 4: Recency per task (k_task recent examples)
candidates = recent_first(candidates, k_task)

# Stage 5: Minimal embedding similarity (on structure tokens)
results = similarity_search(candidates, query_struct, k)

# Stage 6: Hard-negative filter
results = remove_hard_negatives(results, threshold)

# Stage 7: Dedup & Compress
semantic_rules = deduplicate(results, max_lines=6)
```

### 5. Context Injection Format
**ปัจจุบัน:**
```
Lesson: [Full hint text from similar example, truncated at 150 chars]
Lesson: [Another full hint...]
```

**GPT แนะนำ:**
```
=== Semantic Rules ===
- When listing n items, output exactly n numbered bullets.
- If number is stated, include source+year (APA).

=== Structure Template ===
1. [item with description]
2. [item with description]
...
n. [item with description]

=== Checklist ===
☐ Exactly n items
☐ Numbered format
☐ Citations if required
```

---

## 🎯 แผนปรับปรุง (Improvement Roadmap)

### Phase 1: Enhanced Task Classification ⚡ (ลำดับความสำคัญสูง)
**จุดประสงค์:** เพิ่มความแม่นยำและ robustness ของการจำแนก task

#### 1.1 Pre-normalization Layer
```python
def pre_normalize(text: str) -> str:
    """Normalize text before classification."""
    text = text.lower()
    text = unicodedata.normalize('NFKC', text)
    text = re.sub(r'\s+', ' ', text)  # Collapse whitespace
    text = re.sub(r'[^\w\s\d.,;:!?-]', '', text)  # Remove emoji/special chars
    return text.strip()
```

#### 1.2 Structure Signature Extraction
```python
def extract_structure_signature(question: str, task_type: str) -> str:
    """Extract structural pattern from question."""
    if task_type == "list_generation":
        match = re.search(r'(\d+)', question)
        n = match.group(1) if match else "unknown"
        
        # Detect format (numbered, bulleted, paragraph)
        if "numbered" in question.lower() or re.search(r'\d+\.', question):
            return f"numbered({n})"
        elif "bullet" in question.lower() or "•" in question:
            return f"bulleted({n})"
        else:
            return f"list({n})"
    
    elif task_type == "text_splitting":
        return "split_words"
    
    elif task_type == "definition":
        if "write" in question.lower():
            return "definition_long"
        else:
            return "definition_short"
    
    # ... other task types
    return "default"
```

#### 1.3 Constraints Extraction
```python
def extract_constraints(question: str, task_type: str) -> Dict[str, Any]:
    """Extract constraints from question."""
    constraints = {}
    
    if task_type == "list_generation":
        # Extract n
        match = re.search(r'(\d+)', question)
        constraints["n"] = int(match.group(1)) if match else None
        
        # Extract style
        if "numbered" in question.lower():
            constraints["style"] = "numbered"
        elif "bullet" in question.lower():
            constraints["style"] = "bulleted"
        
        # Extract citation requirement
        constraints["cite"] = bool(re.search(r'(citation|reference|source)', question.lower()))
    
    return constraints
```

#### 1.4 Fallback Classifier
```python
def fallback_classify(question: str) -> Tuple[str, str]:
    """Lightweight fallback when regex fails."""
    # Extract intent tokens (first 5 words)
    tokens = question.lower().split()[:5]
    
    # Keyword matching
    if any(w in tokens for w in ['name', 'list', 'give']):
        return "list_generation", "medium"
    
    if any(w in tokens for w in ['split', 'break', 'separate']):
        return "text_splitting", "medium"
    
    # ... more heuristics
    
    # Last resort: general_instruction
    return "general_instruction", "low"
```

### Phase 2: Memory Schema Redesign 📦 (ลำดับความสำคัญสูง)

**เป้าหมาย:** ลดขนาด storage, เพิ่มความเร็ว retrieval, เก็บเฉพาะ structure/rules

#### 2.1 New Schema Design
```python
# episodes.jsonl - Metadata only (no content)
{
    "id": "ep_001",
    "task_type": "list_generation",
    "structure_signature": "numbered(5)",
    "constraints": {"n": 5, "style": "numbered", "cite": false},
    "error_keys": ["count_mismatch", "format_wrong"],
    "domain": "sports",  # auto-detect or manual tag
    "lang": "th",
    "timestamp": "2025-11-11T15:17:35",
    "rule_refs": ["rule_001", "rule_003"],  # References to semantic_rules.json
    "hard_neg_hashes": ["abc123", "def456"]  # References to hard_negatives.json
}

# semantic_rules.json - Reusable rules
{
    "rule_001": {
        "text": "When listing n items, output exactly n numbered bullets.",
        "task_types": ["list_generation"],
        "error_keys": ["count_mismatch"],
        "support_count": 45,
        "quality_score": 0.92,
        "last_seen": "2025-11-11T15:17:35"
    }
}

# structure_templates.json - Format examples
{
    "numbered_list_5": {
        "template": "1. [item]\n2. [item]\n3. [item]\n4. [item]\n5. [item]",
        "task_type": "list_generation",
        "structure_sig": "numbered(5)"
    }
}

# hard_negatives.json - Bad patterns
{
    "abc123": {
        "hash": "abc123",
        "pattern": "Football Basketball Soccer",  # Bad: no numbering
        "error_keys": ["format_wrong"],
        "hit_count": 12
    }
}
```

#### 2.2 Vector Index Strategy
```python
# BEFORE (current): Embed full content
embed_text = "ชื่อกีฬา extreme 5 อย่าง"

# AFTER (GPT approach): Embed structure only
structure_tokens = f"{task_type} | {structure_sig} | {constraints_str}"
# Example: "list_generation | numbered(5) | n=5,cite=false"
embed_text = structure_tokens
```

### Phase 3: Multi-Stage Retrieval Pipeline 🔍 (ลำดับความสำคัญกลาง)

```python
def retrieve_with_multistage_filter(
    question: str,
    task_type: str,
    structure_sig: str,
    error_keys: List[str],
    k: int = 5
) -> List[str]:
    """Multi-stage filtering for maximum precision."""
    
    # Stage 1: Task type filter (hard constraint)
    candidates = [r for r in records if r["task_type"] == task_type]
    logger.info(f"After task filter: {len(candidates)} candidates")
    
    # Stage 2: Structure signature filter
    candidates = [r for r in candidates 
                  if r["structure_signature"] == structure_sig]
    logger.info(f"After structure filter: {len(candidates)} candidates")
    
    # Stage 3: Error key prioritization (boost matching errors)
    scored = []
    for rec in candidates:
        overlap = len(set(rec["error_keys"]) & set(error_keys))
        scored.append((rec, overlap))
    scored.sort(key=lambda x: x[1], reverse=True)
    
    # Stage 4: Recency (top k_task per task)
    scored = scored[:20]  # Keep top 20 by error_key match
    
    # Stage 5: Minimal embedding similarity (optional refinement)
    # ... (can skip if Stage 1-4 already narrow enough)
    
    # Stage 6: Hard-negative filter
    final = []
    for rec, score in scored:
        if not has_hard_negatives(rec, threshold=3):
            final.append(rec)
        if len(final) >= k:
            break
    
    return final
```

### Phase 4: Context Injection Redesign 💬 (ลำดับความสำคัญกลาง)

```python
def build_structured_context(
    retrieved_episodes: List[Dict],
    task_type: str,
    structure_sig: str
) -> str:
    """Build structured, concise context."""
    
    # Collect semantic rules
    rules = []
    for ep in retrieved_episodes:
        for rule_id in ep["rule_refs"]:
            rule = semantic_rules[rule_id]
            if rule["text"] not in rules:
                rules.append(rule["text"])
    
    # Get template
    template = structure_templates.get(structure_sig, "")
    
    # Build context
    context = f"""=== Task Guidelines ===
Task Type: {task_type}
Structure: {structure_sig}

=== Semantic Rules (from past errors) ===
{chr(10).join(f"- {r}" for r in rules[:5])}

=== Structure Template ===
{template}

=== Critical Reminders ===
- Follow the exact structure shown above
- Do NOT remove correct parts
- Only add/fix what is missing or wrong
"""
    
    return context
```

---

## 🚦 Implementation Priority

### 🔴 HIGH PRIORITY (ทำก่อน - impact สูง)
1. **Pre-normalization** (30 min) - ป้องกัน unicode/whitespace issues
2. **Structure signature extraction** (1 hr) - เพิ่ม precision filtering
3. **Constraints extraction** (1 hr) - เก็บ n, style, cite
4. **Memory schema redesign** (2 hr) - ลดขนาด, เพิ่มความเร็ว

### 🟡 MEDIUM PRIORITY (ทำตาม - good to have)
5. **Multi-stage retrieval** (2 hr) - เพิ่ม precision retrieval
6. **Context injection redesign** (1 hr) - ทำให้ prompt กระชับขึ้น
7. **Fallback classifier** (1 hr) - handle edge cases

### 🟢 LOW PRIORITY (ทีหลัง - nice to have)
8. **Multilingual embedding model** - สำหรับภาษาไทย (ถ้าต้องการ)
9. **TF-IDF fallback** - alternative to embedding
10. **Unknown case logging** - continuous improvement

---

## 💡 คำแนะนำจาก GPT ที่ควรนำมาใช้ทันที

### ✅ ควรทำ (Aligned with current direction)
1. **Structure-based embedding** แทน content-based → ลด noise จาก content words
2. **Multi-stage filtering** → เพิ่ม precision มาก (task → structure → error_keys)
3. **Semantic rules extraction** → reusable, compact, clear
4. **Hard-negative tracking** → ป้องกัน repeat mistakes
5. **Template-based hints** → ให้ student เห็น structure ชัดเจน

### ⚠️ ควรปรับใช้ตามบริบท (Adapt carefully)
1. **LLM fallback** → อาจไม่จำเป็น ถ้า regex ครอบคลุมดีพอ (check coverage first)
2. **Multilingual model** → ทดสอบก่อนว่า all-MiniLM-L6-v2 รองรับไทยได้หรือไม่
3. **TF-IDF option** → ใช้ถ้า embedding ช้าเกินไป (ตอนนี้ยังเร็วดี)

### ❌ ไม่ควรทำ (Over-engineering risks)
1. **Domain classification** → ยังไม่จำเป็น (task_type + structure_sig ก็พอ)
2. **Multi-task support** → เพิ่ม complexity โดยไม่จำเป็น (1 question = 1 task ก็พอ)
3. **Complex validator** → regex + basic checks ก็เพียงพอ

---

## 🎬 Suggested Action Plan

### Sprint 1: Foundation (4 hours)
- [ ] Implement pre-normalization in task_classifier.py
- [ ] Add structure_signature extraction
- [ ] Add constraints extraction
- [ ] Update memory schema (episodes.jsonl, semantic_rules.json)
- [ ] Test with existing data

### Sprint 2: Retrieval Enhancement (3 hours)
- [ ] Implement multi-stage filtering in memory_retrieval.py
- [ ] Update vector embedding to structure-only
- [ ] Add error_key prioritization
- [ ] Test retrieval precision

### Sprint 3: Context Optimization (2 hours)
- [ ] Redesign context injection format
- [ ] Extract semantic rules from hints
- [ ] Create structure templates
- [ ] Test with full experiment

### Sprint 4: Polish & Validate (2 hours)
- [ ] Add fallback classifier
- [ ] Add unknown case logging
- [ ] Measure metrics (route@1, hit_rate, repeat_error_rate)
- [ ] Document final architecture

---

## 📊 Expected Impact

### Before (Current System)
- Storage: ~500 bytes/record (with full content)
- Retrieval precision: 60-70% (same task type guaranteed, but may not match structure)
- Context quality: Medium (hints may be irrelevant to structure)

### After (GPT-recommended System)
- Storage: ~200 bytes/record (metadata only)
- Retrieval precision: 90-95% (task + structure + error_keys match)
- Context quality: High (semantic rules + template + checklist)

### Metrics to Track
- `task_route@1`: % ของ questions ที่ classify ถูก task_type → target: >95%
- `structure_match_rate`: % ของ retrievals ที่ได้ structure ตรง → target: >90%
- `retrieval_hit_rate`: % ของ queries ที่ได้ context ≥1 rule → target: >85%
- `repeat_error_rate`: % ของ errors ที่ซ้ำ (ลดลง) → target: <15%
- `memory_efficiency`: ลด storage size → target: -60%

