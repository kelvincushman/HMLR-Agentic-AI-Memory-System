"""
Topic-based embedding for compression decisions.

Embeds extracted keywords/topics instead of full text for more precise
topic-shift detection and compression decisions.
"""

from typing import List, Optional
import numpy as np
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class TopicEmbedding:
    """Embedding representation of a turn's topics."""
    turn_id: str
    keywords: List[str]  # Original keywords
    embedding: np.ndarray  # Combined embedding vector
    timestamp: str


class TopicEmbedder:
    """
    Creates embeddings from topic keywords for semantic comparison.
    
    Instead of embedding full conversation text, we embed the distilled
    keywords/topics. This gives cleaner topic-shift signals.
    """
    
    def __init__(self, embedder_function):
        """
        Initialize topic embedder.
        
        Args:
            embedder_function: Function that takes text and returns embedding vector
                             (e.g., embedding_manager.encode)
        """
        self.embedder = embedder_function
    
    def embed_keywords(self, keywords: List[str]) -> np.ndarray:
        """
        Create a single embedding vector from a list of keywords.
        
        Strategy: Join keywords with spaces, embed the combined string.
        This captures the semantic "topic space" of the turn.
        
        Args:
            keywords: List of keyword strings
            
        Returns:
            numpy array embedding vector
        """
        if not keywords:
            # Return zero vector for empty keywords
            # Dimension depends on embedding model (384 for all-MiniLM-L6-v2)
            return np.zeros(384)
        
        # Join keywords into a single semantic phrase
        topic_text = " ".join(keywords)
        
        # Embed the combined topics
        embedding = self.embedder(topic_text)
        
        return embedding
    
    def calculate_topic_distance(
        self,
        keywords1: List[str],
        keywords2: List[str]
    ) -> float:
        """
        Calculate semantic distance between two sets of keywords.
        
        Returns distance (1 - cosine_similarity), where:
        - 0.0 = identical topics
        - 0.5 = somewhat different
        - 1.0 = completely different
        
        Args:
            keywords1: First set of keywords
            keywords2: Second set of keywords
            
        Returns:
            Distance score (0.0 to 1.0)
        """
        if not keywords1 or not keywords2:
            return 0.5  # Unknown, assume moderate difference
        
        # Embed both keyword sets
        emb1 = self.embed_keywords(keywords1)
        emb2 = self.embed_keywords(keywords2)
        
        # Cosine similarity
        similarity = float(
            np.dot(emb1, emb2) / 
            (np.linalg.norm(emb1) * np.linalg.norm(emb2))
        )
        
        # Convert to distance
        return 1.0 - similarity
    
    def calculate_distance_to_average(
        self,
        current_keywords: List[str],
        recent_keyword_sets: List[List[str]]
    ) -> float:
        """
        Calculate distance between current keywords and average of recent sets.
        
        This is useful for comparing current query against recent sliding window.
        
        Args:
            current_keywords: Keywords from current query
            recent_keyword_sets: List of keyword sets from recent turns
            
        Returns:
            Distance score (0.0 to 1.0)
        """
        if not current_keywords or not recent_keyword_sets:
            return 0.5
        
        # Embed current keywords
        current_emb = self.embed_keywords(current_keywords)
        
        # Embed each recent set and average
        recent_embeddings = [
            self.embed_keywords(keywords)
            for keywords in recent_keyword_sets
            if keywords  # Skip empty sets
        ]
        
        if not recent_embeddings:
            return 0.5
        
        # Average recent embeddings
        avg_recent = np.mean(recent_embeddings, axis=0)
        
        # Cosine similarity
        similarity = float(
            np.dot(current_emb, avg_recent) /
            (np.linalg.norm(current_emb) * np.linalg.norm(avg_recent))
        )
        
        # Convert to distance
        return 1.0 - similarity
    
    def find_similar_turns(
        self,
        current_keywords: List[str],
        turn_keywords: List[List[str]],
        turn_ids: List[str],
        similarity_threshold: float = 0.3
    ) -> List[tuple]:
        """
        Find turns with similar topics to current keywords.
        
        Used for selective hydration: keep similar turns verbatim,
        compress dissimilar ones.
        
        Args:
            current_keywords: Keywords from current query
            turn_keywords: List of keyword sets from sliding window turns
            turn_ids: Corresponding turn IDs
            similarity_threshold: Min similarity to be considered "similar" (default 0.3 = distance 0.7)
            
        Returns:
            List of (turn_id, similarity_score) tuples, sorted by similarity descending
        """
        if not current_keywords:
            return []
        
        current_emb = self.embed_keywords(current_keywords)
        
        similarities = []
        for keywords, turn_id in zip(turn_keywords, turn_ids):
            if not keywords:
                continue
            
            turn_emb = self.embed_keywords(keywords)
            
            similarity = float(
                np.dot(current_emb, turn_emb) /
                (np.linalg.norm(current_emb) * np.linalg.norm(turn_emb))
            )
            
            # Only include if above threshold
            if similarity >= similarity_threshold:
                similarities.append((turn_id, similarity))
        
        # Sort by similarity descending
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return similarities
