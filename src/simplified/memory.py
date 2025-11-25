"""
Simplified Memory Module

FAISS-based memory system with smart feedback retrieval and ranking.

Key features:
1. FAISS vector search for similar questions
2. JSONL storage for persistence
3. Smart ranking by: success_rate > final_score > attempts
4. Compact memory schema
5. Automatic embedding generation

Memory Schema:
{
    "id": "abc123def",  # Hash of question embedding
    "question": "What is 2+2?",
    "teaching_feedback": "Think about basic addition...",
    "attempts": 3,
    "success_count": 2,
    "success_rate": 0.67,
    "scores": {
        "exact_match": 0.8,
        "f1": 0.85,
        "bleu": 0.75,
        "teacher_score": 0.9,
        "final": 0.825
    },
    "timestamp": "2025-11-13T15:30:00"
}
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import numpy as np


class FAISSMemory:
    """
    FAISS-based memory with smart feedback retrieval.
    
    Features:
    - Vector search using sentence embeddings
    - JSONL storage for easy inspection
    - Ranking by success rate and quality
    - Automatic deduplication
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize FAISS memory system.
        
        Args:
            config: Memory configuration dict with:
                - embedding_model: Model for embeddings (e.g., "all-MiniLM-L6-v2")
                - similarity_threshold: Min similarity for retrieval (default: 0.75)
                - top_k: Number of candidates to retrieve (default: 5)
                - min_success_rate: Min success rate to use feedback (default: 0.3)
                - storage_path: Path to JSONL file
                - index_path: Path to FAISS index
        """
        self.config = config
        self.embedding_model_name = config.get('embedding_model', 'all-MiniLM-L6-v2')
        self.similarity_threshold = config.get('similarity_threshold', 0.75)
        self.top_k = config.get('top_k', 5)
        self.min_success_rate = config.get('min_success_rate', 0.3)
        
        # Storage paths
        self.storage_path = Path(config.get('storage_path', 'logs/simplified/memory.jsonl'))
        self.index_path = Path(config.get('index_path', 'logs/simplified/faiss.index'))
        
        # Create directories
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Lazy load embedding model and FAISS
        self._encoder = None
        self._index = None
        self._id_to_record = {}  # In-memory cache: id -> record
        self._ids = []  # List of IDs in FAISS (parallel to index)
        
        # Load existing data
        self._load_from_disk()
    
    @property
    def encoder(self):
        """Lazy load sentence transformer encoder."""
        if self._encoder is None:
            from sentence_transformers import SentenceTransformer
            self._encoder = SentenceTransformer(self.embedding_model_name)
        return self._encoder
    
    @property
    def index(self):
        """Lazy load FAISS index."""
        if self._index is None:
            import faiss
            # Get embedding dimension
            test_emb = self.encoder.encode(["test"])
            dim = test_emb.shape[1]
            
            # Create index (Inner Product for cosine similarity with normalized vectors)
            self._index = faiss.IndexFlatIP(dim)
            
            # Try to load existing index
            if self.index_path.exists():
                try:
                    self._index = faiss.read_index(str(self.index_path))
                    print(f"[OK] Loaded FAISS index with {self._index.ntotal} vectors")
                except Exception as e:
                    print(f"[WARNING] Could not load index: {e}")
        
        return self._index
    
    def _load_from_disk(self):
        """
        Load memory records from JSONL storage and rebuild FAISS index.
        
        This method performs cold-start initialization by:
        1. Reading all historical teaching records from JSONL file
        2. Populating in-memory cache for fast record lookup
        3. Rebuilding FAISS vector index for semantic search
        
        The FAISS index is not persisted because embeddings may change
        if the encoder model is updated, so we rebuild from questions.
        """
        if not self.storage_path.exists():
            return
        
        try:
            # ===== LOAD RECORDS FROM JSONL =====
            # Read line-by-line to handle large memory files efficiently
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        record = json.loads(line)
                        # Cache record for O(1) lookup by ID
                        self._id_to_record[record['id']] = record
                        # Maintain ordered list of IDs parallel to FAISS index positions
                        if record['id'] not in self._ids:
                            self._ids.append(record['id'])
            
            print(f"[OK] Loaded {len(self._id_to_record)} records from memory")
            
            # ===== REBUILD FAISS INDEX =====
            # Reconstruct vector index from question embeddings
            # This enables fast semantic similarity search
            if self._id_to_record:
                print(f"Rebuilding FAISS index from {len(self._id_to_record)} records...")
                embeddings = []
                for record_id in self._ids:
                    record = self._id_to_record[record_id]
                    # Generate embedding for this question
                    emb = self._compute_embedding(record['question'])
                    embeddings.append(emb)
                
                if embeddings:
                    # Convert to FAISS-compatible format and add to index
                    embeddings = np.array(embeddings).astype('float32')
                    self.index.add(embeddings)
                    print(f"FAISS index rebuilt with {self.index.ntotal} vectors")
            
        except Exception as e:
            print(f"[WARNING] Error loading memory: {e}")
    
    def _compute_embedding(self, text: str) -> np.ndarray:
        """
        Compute normalized embedding for text.
        
        Args:
            text: Input text
        
        Returns:
            Normalized embedding vector
        """
        emb = self.encoder.encode([text], convert_to_numpy=True)[0]
        # L2 normalize for cosine similarity
        norm = np.linalg.norm(emb)
        if norm > 0:
            emb = emb / norm
        return emb.astype('float32')
    
    def _generate_id(self, question: str) -> str:
        """
        Generate unique ID from question embedding.
        
        Args:
            question: Question text
        
        Returns:
            Hex string ID
        """
        emb = self._compute_embedding(question)
        # Hash the embedding bytes
        emb_bytes = emb.tobytes()
        return hashlib.sha256(emb_bytes).hexdigest()[:16]
    
    def search(self, question: str, k: Optional[int] = None) -> List[Tuple[str, float]]:
        """
        Search for similar questions in memory.
        
        Args:
            question: Query question
            k: Number of results (default: self.top_k)
        
        Returns:
            List of (record_id, similarity_score) tuples, sorted by similarity desc
        """
        if k is None:
            k = self.top_k

        # If k <= 0, treat as "memory disabled" and skip FAISS search.
        # faiss.Index.search asserts that k > 0, so we must guard here.
        if k <= 0 or self.index.ntotal == 0:
            return []
        
        # Compute query embedding
        query_emb = self._compute_embedding(question)
        
        # Search FAISS
        scores, indices = self.index.search(
            query_emb.reshape(1, -1), 
            min(k, self.index.ntotal)
        )
        
        # Convert to list of (id, score) tuples
        results = []
        for idx, score in zip(indices[0], scores[0]):
            if idx >= 0 and idx < len(self._ids):
                record_id = self._ids[idx]
                results.append((record_id, float(score)))
        
        return results
    
    def get_best_feedback(self, question: str) -> Optional[Dict[str, Any]]:
        """
        Get best feedback for a question using smart ranking.
        
        Ranking criteria (in order):
        1. Similarity >= threshold
        2. Success rate >= min_success_rate
        3. Higher success rate preferred
        4. Higher final score preferred
        5. More attempts preferred (proven feedback)
        
        Args:
            question: Query question
        
        Returns:
            Dict with keys: id, feedback, success_rate, final_score, attempts
            Or None if no suitable feedback found
        """
        # Search for similar questions
        results = self.search(question, k=self.top_k)
        
        if not results:
            return None
        
        # Filter by similarity threshold
        candidates = [
            (rid, score) for rid, score in results 
            if score >= self.similarity_threshold
        ]
        
        if not candidates:
            return None
        
        # Get full records and filter by min success rate
        valid_candidates = []
        for rid, sim_score in candidates:
            record = self._id_to_record.get(rid)
            if record:
                sr = record.get('success_rate', 0.0)
                if sr >= self.min_success_rate:
                    valid_candidates.append((record, sim_score))
        
        if not valid_candidates:
            return None
        
        # Rank by: success_rate (desc), final_score (desc), attempts (desc), similarity (desc)
        valid_candidates.sort(
            key=lambda x: (
                x[0].get('success_rate', 0.0),
                x[0].get('scores', {}).get('final', 0.0),
                x[0].get('attempts', 0),
                x[1]  # similarity
            ),
            reverse=True
        )
        
        # Return best candidate
        best_record, sim_score = valid_candidates[0]
        
        return {
            'id': best_record['id'],
            'feedback': best_record['teaching_feedback'],
            'success_rate': best_record.get('success_rate', 0.0),
            'final_score': best_record.get('scores', {}).get('final', 0.0),
            'attempts': best_record.get('attempts', 0),
            'similarity': sim_score
        }
    
    def store(self,
              question: str,
              feedback: str,
              scores: Dict[str, float],
              final_score: float,
              attempts: int = 1) -> str:
        """
        Store new feedback or update existing record.
        
        Strategy:
        - If similarity == 1.0 (exact match): UPDATE existing record
        - If similarity < 1.0 (similar but different): CREATE new record
        
        Args:
            question: The question
            feedback: Teaching feedback
            scores: Dict of metric scores
            final_score: Final weighted score
            attempts: Number of attempts (default: 1)
        
        Returns:
            Record ID
        """
        # Check similarity with existing records
        similar_records = self.search(question, k=1)
        
        # Decide: Update or Create?
        needs_save = False
        is_new = False  # Track if this is a new record (for FAISS index save)
        record_id = None
        
        if similar_records and similar_records[0][1] >= 0.8:  # similarity >= 0.8 → reuse memory
            # SIMILAR ENOUGH → Update existing record
            existing_id = similar_records[0][0]
            record = self._id_to_record[existing_id]
            record_id = existing_id
            
            old_score = record['scores'].get('final', 0.0)
            # Update existing record ONLY if new feedback is better
            record = self._id_to_record[record_id]
            old_score = record['scores'].get('final', 0.0)
            
            # Update attempts count
            record['attempts'] += attempts
            record['timestamp'] = datetime.now().isoformat()
            
            # Only update feedback if new score is better
            if final_score > old_score:
                record['teaching_feedback'] = feedback
                record['scores'] = scores
                record['scores']['final'] = final_score
                needs_save = True  # Need to rewrite entire file
            else:
                # Still need to update attempts count in file
                needs_save = True
        else:
            # DIFFERENT QUESTION → Create new record
            is_new = True  # This is a new record, will add to FAISS
            record_id = self._generate_id(question)
            
            record = {
                'id': record_id,
                'question': question,
                'teaching_feedback': feedback,
                'attempts': attempts,
                'success_count': 0,
                'success_rate': 0.0,
                'scores': scores,
                'timestamp': datetime.now().isoformat()
            }
            record['scores']['final'] = final_score
            
            # Add to FAISS index
            emb = self._compute_embedding(question)
            emb = emb.reshape(1, -1).astype('float32')
            self.index.add(emb)
            self._ids.append(record_id)
            
            # Update cache
            self._id_to_record[record_id] = record
            needs_save = True
        
        # Save to disk (rewrite entire file to avoid duplicates)
        if needs_save:
            self._save_all_records()
        
        # Save FAISS index ONLY if new vector was added
        if is_new:
            self._save_index()
        
        return record_id
    
    def update_success(self,
                      record_id: str,
                      success: bool,
                      final_score: float):
        """
        Update success statistics for a record.
        
        Args:
            record_id: Record ID
            success: Whether feedback led to success
            final_score: Final score achieved
        """
        if record_id not in self._id_to_record:
            print(f"Record {record_id} not found")
            return
        
        record = self._id_to_record[record_id]
        old_score = record['scores'].get('final', 0.0)
        
        # Update success count (always update this)
        if success:
            record['success_count'] += 1
        
        # Recalculate success rate
        if record['attempts'] > 0:
            record['success_rate'] = record['success_count'] / record['attempts']
        
        # Update score ONLY if new score is better
        needs_save = False
        if final_score > old_score:
            record['scores']['final'] = final_score
            record['timestamp'] = datetime.now().isoformat()
            needs_save = True
        else:
            record['timestamp'] = datetime.now().isoformat()
            needs_save = True  # Still need to update success_count/rate
        
        # Save updated record (will update in-place, not append)
        # NOTE: No need to save FAISS index here - _ids doesn't change
        if needs_save:
            self._save_all_records()
    
    def _save_record(self, record: Dict[str, Any]):
        """Append record to JSONL file (deprecated - use _save_all_records)."""
        try:
            with open(self.storage_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
        except Exception:
            pass  # Silent fail, already logged in debug file
    
    def _save_all_records(self):
        """Rewrite entire JSONL file with current state (prevents duplicates)."""
        try:
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                for record in self._id_to_record.values():
                    f.write(json.dumps(record, ensure_ascii=False) + '\n')
        except Exception as e:
            print(f"[WARNING] Error rewriting records: {e}")
    
    def _save_index(self):
        """Save FAISS index to disk."""
        try:
            import faiss
            faiss.write_index(self.index, str(self.index_path))
            
            # Also save IDs list
            ids_path = self.index_path.with_suffix('.ids.json')
            with open(ids_path, 'w', encoding='utf-8') as f:
                json.dump(self._ids, f, indent=2)  # Add indent for readability
            
            # Silent save (UI shows summary at the end)
        except Exception as e:
            print(f"[WARNING] Error saving index: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        total_records = len(self._id_to_record)
        total_attempts = sum(r.get('attempts', 0) for r in self._id_to_record.values())
        total_successes = sum(r.get('success_count', 0) for r in self._id_to_record.values())
        
        return {
            'total_records': total_records,
            'total_attempts': total_attempts,
            'total_successes': total_successes,
            'overall_success_rate': total_successes / total_attempts if total_attempts > 0 else 0.0,
            'index_size': self.index.ntotal if self._index else 0
        }


# Example usage
if __name__ == "__main__":
    # Mock config
    config = {
        'embedding_model': 'all-MiniLM-L6-v2',
        'similarity_threshold': 0.75,
        'top_k': 5,
        'min_success_rate': 0.3,
        'storage_path': 'logs/simplified/test_memory.jsonl',
        'index_path': 'logs/simplified/test_faiss.index'
    }
    
    print("="*80)
    print("Testing FAISS Memory")
    print("="*80)
    
    memory = FAISSMemory(config)
    
    # Test 1: Store a record
    print("\n--- Test 1: Store Record ---")
    record_id = memory.store(
        question="What is the capital of France?",
        feedback="Think about major European cities",
        scores={'exact_match': 0.0, 'f1': 0.5, 'bleu': 0.3, 'teacher_score': 0.4},
        final_score=0.3,
        attempts=1
    )
    print(f"Stored record: {record_id}")
    
    # Test 2: Search for similar
    print("\n--- Test 2: Search Similar ---")
    results = memory.search("What is France's capital?", k=3)
    print(f"Found {len(results)} similar questions")
    for rid, score in results:
        print(f"  - ID: {rid}, Similarity: {score:.3f}")
    
    # Test 3: Get best feedback
    print("\n--- Test 3: Get Best Feedback ---")
    best = memory.get_best_feedback("What is France's capital?")
    if best:
        print(f"Best feedback: {best['feedback']}")
        print(f"Success rate: {best['success_rate']:.2f}")
        print(f"Similarity: {best['similarity']:.3f}")
    else:
        print("No suitable feedback found")
    
    # Test 4: Update success
    print("\n--- Test 4: Update Success ---")
    memory.update_success(record_id, success=True, final_score=0.9)
    print("Updated success statistics")
    
    # Test 5: Stats
    print("\n--- Test 5: Memory Stats ---")
    stats = memory.get_stats()
    print(json.dumps(stats, indent=2))
