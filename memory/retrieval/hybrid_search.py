"""
Hybrid Search Engine - Combines lexical (keyword) + semantic (vector) retrieval.

Implements the "Two-Key" system:
- Current Day: Return active bridge blocks (hot path, < 100ms)
- Past Days: Lexical filters + vector search with Two-Key verification

This is the core retrieval strategy for Phase 11.5 (Pre-Chunking).
"""
import json
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class HybridMatch:
    """
    Result from hybrid search combining lexical and vector scores.
    
    Attributes:
        chunk_id: Unique chunk identifier
        chunk_type: 'sentence' | 'paragraph' | 'bridge_block'
        text_verbatim: Original text content
        lexical_score: Keyword match score (0.0-1.0)
        vector_score: Semantic similarity score (0.0-1.0)
        combined_score: Weighted combination of both scores
        parent_chunk_id: Link to parent chunk for hierarchy
        metadata: Additional search metadata (ranks, tags, etc.)
    """
    chunk_id: str
    chunk_type: str
    text_verbatim: str
    lexical_score: float
    vector_score: float
    combined_score: float
    parent_chunk_id: Optional[str] = None
    metadata: Optional[Dict] = None


class HybridSearchEngine:
    """
    Retrieves memories using both keyword matching and vector similarity.
    
    Design Principles:
    1. Current Day (Hot Path): Return active bridge blocks instantly
    2. Past Days (Two-Key): Lexical + vector with strict verification
    3. Conservative Strategy: Always retrieve, never assume in context
    """
    
    def __init__(self, chunk_storage, embedding_storage):
        """
        Initialize hybrid search engine.
        
        Args:
            chunk_storage: Instance of ChunkStorage for database access
            embedding_storage: Instance of EmbeddingStorage for vector search
        """
        self.chunk_storage = chunk_storage
        self.embedding_storage = embedding_storage
        self.storage = chunk_storage.storage
    
    def search(
        self, 
        query: str, 
        date_context: str = "past",
        top_k: int = 20
    ) -> List[HybridMatch]:
        """
        Main hybrid search entry point.
        
        Args:
            query: User query text
            date_context: 'today' (hot path) or 'past' (full search)
            top_k: Maximum number of results to return
        
        Returns:
            List of HybridMatch objects sorted by combined score
            
        Rules:
        - TODAY: Return active bridge blocks from daily_ledger (no search)
        - PAST: Use Two-Key system (lexical + vector verification)
        """
        if date_context == "today":
            return self._get_active_bridge_blocks()
        else:
            return self._two_key_search(query, top_k)
    
    def _get_active_bridge_blocks(self) -> List[HybridMatch]:
        """
        Fast path: Return all active bridge blocks from today.
        
        No search needed - sliding window IS the active bridge block.
        This is just for hydrating context if needed (future enhancement).
        
        Returns:
            List of active bridge blocks from current day
        """
        conn = self.storage.conn
        cursor = conn.cursor()
        
        # Get all PAUSED blocks from today
        cursor.execute("""
            SELECT block_id, content_json, created_at
            FROM daily_ledger
            WHERE DATE(created_at) = DATE('now')
            AND status = 'PAUSED'
            ORDER BY created_at DESC
        """)
        
        blocks = []
        for row in cursor.fetchall():
            try:
                block_id, content_json, created_at = row
                content = json.loads(content_json) if content_json else {}
                
                blocks.append(HybridMatch(
                    chunk_id=block_id,
                    chunk_type='bridge_block',
                    text_verbatim=content.get('summary', ''),
                    lexical_score=1.0,  # Perfect match (current topic)
                    vector_score=1.0,
                    combined_score=1.0,
                    metadata={
                        'topic_label': content.get('topic_label', ''),
                        'keywords': content.get('keywords', []),
                        'created_at': created_at
                    }
                ))
            except Exception as e:
                logger.warning(f"Failed to parse bridge block {block_id}: {e}")
                continue
        
        return blocks
    
    def _two_key_search(self, query: str, top_k: int) -> List[HybridMatch]:
        """
        Two-Key System for past memories (conservative retrieval).
        
        Key 1: Lexical filter (keyword match via FTS5)
        Key 2: Vector similarity (semantic match via embeddings)
        
        Approval Rules:
        - Option A: Has lexical match + (sentence OR paragraph) vector match
        - Option B: High vector match (>0.8) + parent context also matches
        
        Args:
            query: User query text
            top_k: Maximum results to return
            
        Returns:
            List of approved HybridMatch objects
        """
        # Step 1: Lexical search (FTS5 keyword matching)
        lexical_matches = self._lexical_search(query)
        logger.debug(f"Lexical search found {len(lexical_matches)} keyword matches")
        
        # Step 2: Vector search (semantic similarity)
        vector_matches = self._vector_search(query, top_k=50)
        logger.debug(f"Vector search found {len(vector_matches)} semantic matches")
        
        # Step 3: Combine with Two-Key rules
        approved = []
        
        for vec_match in vector_matches:
            chunk_id = vec_match['chunk_id']
            chunk_type = vec_match['chunk_type']
            vector_score = vec_match['similarity']
            text_verbatim = vec_match['text']
            parent_chunk_id = vec_match.get('parent_chunk_id')
            
            # Check if chunk has lexical match
            lexical_score = lexical_matches.get(chunk_id, 0.0)
            
            # Option A: Has lexical match + vector match
            if lexical_score > 0.0:
                if chunk_type in ['sentence', 'paragraph']:
                    # Weight: 40% keywords, 60% semantics
                    combined_score = (lexical_score * 0.4) + (vector_score * 0.6)
                    
                    approved.append(HybridMatch(
                        chunk_id=chunk_id,
                        chunk_type=chunk_type,
                        text_verbatim=text_verbatim,
                        lexical_score=lexical_score,
                        vector_score=vector_score,
                        combined_score=combined_score,
                        parent_chunk_id=parent_chunk_id,
                        metadata={'match_type': 'option_a'}
                    ))
            
            # Option B: High vector score but no lexical match (stricter)
            elif vector_score > 0.8:
                # Require parent context to also match (prevent false positives)
                if chunk_type == 'sentence' and parent_chunk_id:
                    parent_match = self._get_parent_similarity(parent_chunk_id, query)
                    
                    if parent_match and parent_match['similarity'] > 0.7:
                        # Slight penalty for missing keywords
                        combined_score = vector_score * 0.85
                        
                        approved.append(HybridMatch(
                            chunk_id=chunk_id,
                            chunk_type=chunk_type,
                            text_verbatim=text_verbatim,
                            lexical_score=0.0,
                            vector_score=vector_score,
                            combined_score=combined_score,
                            parent_chunk_id=parent_chunk_id,
                            metadata={
                                'match_type': 'option_b',
                                'parent_similarity': parent_match['similarity']
                            }
                        ))
        
        # Sort by combined score and return top_k
        approved.sort(key=lambda x: x.combined_score, reverse=True)
        logger.info(f"Two-Key search approved {len(approved)} results from {len(vector_matches)} candidates")
        
        return approved[:top_k]
    
    def _lexical_search(self, query: str) -> Dict[str, float]:
        """
        Keyword-based search using FTS5 full-text index.
        
        Args:
            query: User query text
            
        Returns:
            Dictionary mapping chunk_id → lexical_score (0.0-1.0)
        """
        conn = self.storage.conn
        cursor = conn.cursor()
        
        # Extract keywords from query (same logic as ChunkEngine)
        from .chunk_engine import ChunkEngine
        engine = ChunkEngine()
        query_keywords = engine._extract_keywords(query)
        
        if not query_keywords:
            logger.debug("No keywords extracted from query")
            return {}
        
        # Build FTS5 query (OR logic for multiple keywords)
        search_query = ' OR '.join(query_keywords)
        
        try:
            cursor.execute("""
                SELECT chunk_id, rank
                FROM chunks_fts
                WHERE chunks_fts MATCH ?
                ORDER BY rank
                LIMIT 100
            """, (search_query,))
            
            results = {}
            for row in cursor.fetchall():
                chunk_id, rank = row
                # Convert FTS5 rank to 0-1 score (lower rank = better match)
                # FTS5 rank is negative, closer to 0 is better
                score = 1.0 / (1.0 + abs(rank))
                results[chunk_id] = score
            
            return results
        
        except Exception as e:
            logger.error(f"Lexical search failed: {e}")
            return {}
    
    def _vector_search(self, query: str, top_k: int) -> List[Dict]:
        """
        Semantic search using embedding similarity.
        
        Args:
            query: User query text
            top_k: Maximum results to return
            
        Returns:
            List of dicts with keys: chunk_id, chunk_type, text, similarity, parent_chunk_id
        """
        try:
            # Query embedding storage for similar chunks
            results = self.embedding_storage.search_similar_chunks(
                query_text=query,
                top_k=top_k,
                min_similarity=0.4
            )
            return results
        
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []
    
    def _get_parent_similarity(self, parent_id: str, query: str) -> Optional[Dict]:
        """
        Check if parent chunk also matches the query (for Option B verification).
        
        Args:
            parent_id: Parent chunk identifier
            query: User query text
            
        Returns:
            Dict with 'similarity' score or None if not found
        """
        try:
            # Get parent chunk embedding and compare to query
            result = self.embedding_storage.get_chunk_similarity(parent_id, query)
            return result
        
        except Exception as e:
            logger.warning(f"Failed to get parent similarity for {parent_id}: {e}")
            return None
    
    def get_chunk_with_context(
        self, 
        chunk_id: str, 
        include_siblings: bool = True,
        include_parent: bool = True
    ) -> Dict:
        """
        Retrieve a chunk with its hierarchical context.
        
        Args:
            chunk_id: Chunk to retrieve
            include_siblings: Include other sentences in same paragraph
            include_parent: Include parent paragraph
            
        Returns:
            Dict with chunk, parent, and siblings
        """
        chunk = self.chunk_storage.get_chunk_by_id(chunk_id)
        if not chunk:
            return {}
        
        context = {
            'chunk': chunk,
            'parent': None,
            'siblings': []
        }
        
        if include_parent and chunk.parent_chunk_id:
            context['parent'] = self.chunk_storage.get_chunk_by_id(chunk.parent_chunk_id)
        
        if include_siblings and chunk.parent_chunk_id:
            context['siblings'] = self.chunk_storage.get_child_chunks(chunk.parent_chunk_id)
        
        return context
