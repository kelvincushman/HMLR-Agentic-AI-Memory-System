"""
Topic-aware context filtering.

Filters retrieved context based on active topics in the sliding window.
This is "smart filtering" not "skip RAG" - we run RAG for accuracy,
then filter results by topic relevance.
"""

from typing import List, Dict, Set
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


@dataclass
class FilteredContext:
    """Result of topic-aware filtering."""
    turn_id: str
    relevance_score: float
    matched_topics: List[str]
    filter_reason: str  # 'active_topic', 'reference_detected', 'high_similarity', 'excluded'


class TopicFilter:
    """
    Filter retrieved context based on active topics.
    
    Week 1, Day 3 implementation:
    - Check if turn topics match active topics in sliding window
    - Handle reference detection (explicit mentions)
    - Combine with existing two-tier filtering
    """
    
    def __init__(self, topic_match_threshold: float = 0.5):
        """
        Initialize topic filter.
        
        Args:
            topic_match_threshold: Minimum overlap ratio to consider topics matching
        """
        self.topic_match_threshold = topic_match_threshold
        
    def filter_by_active_topics(
        self,
        retrieved_turns: List[Dict],
        query_topics: List[str],
        sliding_window,
        has_explicit_reference: bool = False,
        debug: bool = False
    ) -> List[FilteredContext]:
        """
        Filter retrieved turns based on active topics in sliding window.
        
        Args:
            retrieved_turns: Turns from RAG retrieval
            query_topics: Topics extracted from current query
            sliding_window: SlidingWindow object with active_topics
            has_explicit_reference: True if query has explicit reference ("that Ferrari")
            debug: Enable debug logging
            
        Returns:
            List of FilteredContext objects with relevance scores
        """
        if debug:
            logger.info(f"🔍 Topic filtering: {len(retrieved_turns)} turns")
            logger.info(f"  Query topics: {query_topics}")
            logger.info(f"  Active topics: {list(sliding_window.active_topics.keys())}")
            logger.info(f"  Explicit reference: {has_explicit_reference}")
        
        filtered = []
        
        # If explicit reference detected, be more lenient
        # (e.g., "tell me more about that" - keep recent topics)
        if has_explicit_reference:
            if debug:
                logger.info("  📌 Explicit reference detected - including recent topics")
            recent_topics = self._get_recent_topics(sliding_window, minutes=30)
            effective_active_topics = set(sliding_window.active_topics.keys()) | recent_topics
        else:
            effective_active_topics = set(sliding_window.active_topics.keys())
        
        for turn in retrieved_turns:
            # Use embedding similarity from RAG (the whole point of vector search!)
            embedding_similarity = turn.get('similarity', 0.0)
            
            # Get turn's topics for additional filtering
            turn_topics = set(turn.get('topics', []))
            
            # Calculate topic overlap (secondary check)
            if query_topics:
                query_topic_set = set(t.lower() for t in query_topics)
                overlap = query_topic_set & turn_topics
                topic_overlap_ratio = len(overlap) / len(query_topic_set) if query_topic_set else 0.0
            else:
                # No query topics extracted, fall back to active topics
                overlap = effective_active_topics & turn_topics
                topic_overlap_ratio = len(overlap) / len(effective_active_topics) if effective_active_topics else 0.0
            
            matched_topics = list(overlap)
            
            # PRIMARY: Use embedding similarity (RAG already did semantic matching!)
            # SECONDARY: Check topic overlap for additional confidence
            
            if embedding_similarity >= 0.5:
                # Good embedding match - include it!
                # Use embedding similarity as the relevance score
                filtered.append(FilteredContext(
                    turn_id=turn['turn_id'],
                    relevance_score=embedding_similarity,
                    matched_topics=matched_topics,
                    filter_reason='embedding_match'
                ))
                if debug:
                    logger.info(f"  ✅ {turn['turn_id']}: {embedding_similarity:.2f} similarity, {topic_overlap_ratio:.2f} topic overlap")
            
            elif topic_overlap_ratio >= self.topic_match_threshold:
                # Weak embedding but strong topic match - include with lower score
                filtered.append(FilteredContext(
                    turn_id=turn['turn_id'],
                    relevance_score=topic_overlap_ratio * 0.7,
                    matched_topics=matched_topics,
                    filter_reason='topic_match'
                ))
                if debug:
                    logger.info(f"  📌 {turn['turn_id']}: {embedding_similarity:.2f} similarity, {topic_overlap_ratio:.2f} topic overlap (topic match)")
            
            elif has_explicit_reference and (embedding_similarity >= 0.3 or topic_overlap_ratio > 0.0):
                # Reference detected and some relevance
                score = max(embedding_similarity, topic_overlap_ratio) * 0.8
                filtered.append(FilteredContext(
                    turn_id=turn['turn_id'],
                    relevance_score=score,
                    matched_topics=matched_topics,
                    filter_reason='reference_detected'
                ))
                if debug:
                    logger.info(f"  📌 {turn['turn_id']}: {embedding_similarity:.2f} similarity (reference)")
            
            else:
                # Turn doesn't match - log but don't include
                if debug:
                    logger.info(f"  ❌ {turn['turn_id']}: {embedding_similarity:.2f} similarity, {topic_overlap_ratio:.2f} topic overlap (excluded)")
        
        # Sort by relevance score
        filtered.sort(key=lambda fc: fc.relevance_score, reverse=True)
        
        if debug:
            logger.info(f"  ✅ Filtered to {len(filtered)} turns")
        
        return filtered
    
    def _get_recent_topics(self, sliding_window, minutes: int = 30) -> Set[str]:
        """
        Get topics that were active in the last N minutes.
        
        Used when explicit reference is detected - user might be referring
        to something discussed recently but not in current active topics.
        """
        cutoff = datetime.now() - timedelta(minutes=minutes)
        recent_topics = set()
        
        for topic, timestamp in sliding_window.active_topics.items():
            if timestamp > cutoff:
                recent_topics.add(topic)
        
        return recent_topics
    
    def mark_topics_active(
        self,
        sliding_window,
        topics: List[str],
        debug: bool = False
    ):
        """
        Mark topics as active in the sliding window.
        
        Args:
            sliding_window: SlidingWindow object to update
            topics: List of topic keywords to mark active
            debug: Enable debug logging
        """
        now = datetime.now()
        
        for topic in topics:
            topic_lower = topic.lower()
            sliding_window.active_topics[topic_lower] = now
            
            if debug:
                logger.info(f"  ✅ Marked topic '{topic_lower}' as active")
        
        if debug:
            logger.info(f"  📊 Active topics: {len(sliding_window.active_topics)} total")
    
    def is_topic_active(self, sliding_window, topic: str) -> bool:
        """Check if a topic is currently active."""
        return topic.lower() in sliding_window.active_topics
    
    def get_active_topics(self, sliding_window, max_age_minutes: int = 60) -> Dict[str, datetime]:
        """
        Get currently active topics.
        
        Args:
            sliding_window: SlidingWindow object
            max_age_minutes: Maximum age of topic to consider active
            
        Returns:
            Dict mapping topic -> timestamp
        """
        cutoff = datetime.now() - timedelta(minutes=max_age_minutes)
        
        active = {
            topic: timestamp
            for topic, timestamp in sliding_window.active_topics.items()
            if timestamp > cutoff
        }
        
        return active
