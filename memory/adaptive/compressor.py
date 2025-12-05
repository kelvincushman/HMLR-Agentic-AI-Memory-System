"""
Adaptive compression logic for sliding window.

Implements the graduated semantic threshold approach with time modifiers.
Preserves bridge turns for smooth topic transitions.
"""

import re
from typing import List, Dict, Set, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class CompressionLevel(Enum):
    """Compression decision levels."""
    NO_COMPRESSION = "no_compression"  # Keep all verbatim
    COMPRESS_PARTIAL = "compress_partial"  # Keep 10 verbatim, compress rest
    COMPRESS_ALL = "compress_all"  # Keep 5 verbatim, compress rest


@dataclass
class CompressionDecision:
    """Result of compression analysis."""
    level: CompressionLevel
    reason: str
    semantic_distance: float
    time_gap_hours: float
    has_explicit_reference: bool
    keep_verbatim_count: int
    bridge_turns_count: int = 3


class AdaptiveCompressor:
    """
    Intelligent compression based on topic shifts and time.
    
    Phase 4.3 Week 1-2 implementation:
    - Calculate semantic distance between queries
    - Graduated thresholds (0.6, 0.8)
    - Time as modifier (1hr, 12hr thresholds)
    - Explicit reference detection
    - Bridge turn preservation
    """
    
    # Semantic distance thresholds
    VERY_DIFFERENT_THRESHOLD = 0.8  # >0.8 = very different topics
    SOMEWHAT_DIFFERENT_THRESHOLD = 0.6  # 0.6-0.8 = somewhat different
    
    # Time thresholds (in hours)
    SHORT_GAP = 1  # <1 hour = recent
    LONG_GAP = 12  # >12 hours = old
    
    # Verbatim preservation counts
    MAX_VERBATIM_HARD_LIMIT = 15  # Safety valve
    COMPRESS_ALL_KEEP = 5
    COMPRESS_PARTIAL_KEEP = 10
    BRIDGE_TURNS = 3
    
    def __init__(self, embedder=None):
        """
        Initialize adaptive compressor.
        
        Args:
            embedder: Function to embed text (optional, uses simple fallback if None)
        """
        self.embedder = embedder
        
        # Explicit reference patterns (from ADAPTIVE_SLIDING_WINDOW_STRATEGIES.md)
        self.reference_patterns = [
            r'\bwe discussed\b',
            r'\byou mentioned\b',
            r'\byou said\b',
            r'\bas I said\b',
            r'\bas you said\b',
            r'\bremember when\b',
            r'\bearlier you\b',
            r'\bearlier we\b',
            r'\bpreviously\b',
            r'\bthat (time|discussion|conversation)\b',
            r'\bgoing back to\b',
            r'\breturning to\b',
        ]
    
    def decide_compression(
        self,
        current_query: str,
        recent_turns: List[Dict],
        current_topics: List[str],
        debug: bool = False
    ) -> CompressionDecision:
        """
        Decide compression level based on topic shift and time.
        
        Args:
            current_query: User's current query
            recent_turns: Recent turns in sliding window
            current_topics: Topics extracted from current query
            debug: Enable debug logging
            
        Returns:
            CompressionDecision with level and reasoning
        """
        if not recent_turns:
            return CompressionDecision(
                level=CompressionLevel.NO_COMPRESSION,
                reason="No recent turns to compress",
                semantic_distance=0.0,
                time_gap_hours=0.0,
                has_explicit_reference=False,
                keep_verbatim_count=0
            )
        
        # Check for explicit references
        has_reference = self.has_explicit_reference(current_query)
        if has_reference:
            if debug:
                logger.info("📌 Explicit reference detected - no compression")
            return CompressionDecision(
                level=CompressionLevel.NO_COMPRESSION,
                reason="Explicit reference to previous context",
                semantic_distance=0.0,
                time_gap_hours=0.0,
                has_explicit_reference=True,
                keep_verbatim_count=len(recent_turns),
                bridge_turns_count=self.BRIDGE_TURNS
            )
        
        # Calculate semantic distance
        semantic_distance = self.calc_semantic_distance(
            current_query,
            recent_turns,
            current_topics
        )
        
        # Calculate time gap
        most_recent = recent_turns[-1]
        time_gap = self._calc_time_gap(most_recent)
        
        if debug:
            logger.info(f"📊 Compression analysis:")
            logger.info(f"   Semantic distance: {semantic_distance:.3f}")
            logger.info(f"   Time gap: {time_gap:.1f} hours")
        
        # Decision logic (from flowchart)
        if semantic_distance < self.SOMEWHAT_DIFFERENT_THRESHOLD:
            # Related topics (<0.6) - no compression
            decision = CompressionDecision(
                level=CompressionLevel.NO_COMPRESSION,
                reason=f"Related topics (distance: {semantic_distance:.3f})",
                semantic_distance=semantic_distance,
                time_gap_hours=time_gap,
                has_explicit_reference=False,
                keep_verbatim_count=len(recent_turns)
            )
        
        elif semantic_distance >= self.VERY_DIFFERENT_THRESHOLD:
            # Very different topics (>0.8)
            if time_gap > self.SHORT_GAP:
                # >1 hour + very different = compress all
                decision = CompressionDecision(
                    level=CompressionLevel.COMPRESS_ALL,
                    reason=f"Very different + time gap (dist: {semantic_distance:.3f}, gap: {time_gap:.1f}h)",
                    semantic_distance=semantic_distance,
                    time_gap_hours=time_gap,
                    has_explicit_reference=False,
                    keep_verbatim_count=self.COMPRESS_ALL_KEEP,
                    bridge_turns_count=self.BRIDGE_TURNS
                )
            else:
                # <1 hour + very different = partial compression
                decision = CompressionDecision(
                    level=CompressionLevel.COMPRESS_PARTIAL,
                    reason=f"Very different but recent (dist: {semantic_distance:.3f}, gap: {time_gap:.1f}h)",
                    semantic_distance=semantic_distance,
                    time_gap_hours=time_gap,
                    has_explicit_reference=False,
                    keep_verbatim_count=self.COMPRESS_PARTIAL_KEEP,
                    bridge_turns_count=self.BRIDGE_TURNS
                )
        
        else:
            # Somewhat different (0.6-0.8)
            # For distances > 0.7, compress even with short time gap
            # For distances 0.6-0.7, require longer time gap
            if semantic_distance >= 0.7 or time_gap > self.LONG_GAP:
                # Higher end of "somewhat different" OR long time gap = partial compression
                decision = CompressionDecision(
                    level=CompressionLevel.COMPRESS_PARTIAL,
                    reason=f"Somewhat different (dist: {semantic_distance:.3f}, gap: {time_gap:.1f}h)",
                    semantic_distance=semantic_distance,
                    time_gap_hours=time_gap,
                    has_explicit_reference=False,
                    keep_verbatim_count=self.COMPRESS_PARTIAL_KEEP,
                    bridge_turns_count=self.BRIDGE_TURNS
                )
            else:
                # Lower end of "somewhat different" + recent = no compression
                decision = CompressionDecision(
                    level=CompressionLevel.NO_COMPRESSION,
                    reason=f"Somewhat different but recent and close topics (dist: {semantic_distance:.3f}, gap: {time_gap:.1f}h)",
                    semantic_distance=semantic_distance,
                    time_gap_hours=time_gap,
                    has_explicit_reference=False,
                    keep_verbatim_count=len(recent_turns)
                )
        
        if debug:
            logger.info(f"   Decision: {decision.level.value}")
            logger.info(f"   Reason: {decision.reason}")
            logger.info(f"   Keep verbatim: {decision.keep_verbatim_count}")
        
        return decision
    
    def calc_semantic_distance(
        self,
        current_query: str,
        recent_turns: List[Dict],
        current_topics: List[str]
    ) -> float:
        """
        Calculate semantic distance between current query topics and recent turn topics.
        
        Uses keyword embeddings instead of full text for cleaner topic-shift detection.
        
        Returns distance (1 - similarity), where:
        - 0.0 = identical topics
        - 0.5 = somewhat different  
        - 1.0 = completely different
        """
        if not recent_turns:
            return 0.0
        
        # Use embedder if available
        if self.embedder:
            # Embed current query KEYWORDS (not full text!)
            current_embedding = self.embedder(" ".join(current_topics))
            
            # Get recent turns' keywords and embed them
            recent_keyword_sets = []
            for turn in recent_turns[-5:]:  # Last 5 turns
                # Use keywords/topics from the turn, NOT full text
                turn_keywords = turn.get('topics', [])
                if turn_keywords:
                    recent_keyword_sets.append(turn_keywords)
            
            if not recent_keyword_sets:
                return 0.0
            
            # Embed and average recent keyword sets
            import numpy as np
            recent_embeddings = [
                self.embedder(" ".join(keywords))
                for keywords in recent_keyword_sets
            ]
            avg_recent = np.mean(recent_embeddings, axis=0)
            
            # Cosine similarity
            similarity = float(
                np.dot(current_embedding, avg_recent) / 
                (np.linalg.norm(current_embedding) * np.linalg.norm(avg_recent))
            )
            
            # Convert to distance
            return 1.0 - similarity
        
        else:
            # Fallback: topic-based distance
            recent_topics = set()
            for turn in recent_turns[-5:]:
                recent_topics.update(turn.get('topics', []))
            
            current_topics_set = set(t.lower() for t in current_topics)
            recent_topics_set = set(t.lower() for t in recent_topics)
            
            if not current_topics_set or not recent_topics_set:
                return 0.5  # Unknown, assume moderate
            
            # Jaccard distance = 1 - (intersection / union)
            intersection = current_topics_set & recent_topics_set
            union = current_topics_set | recent_topics_set
            
            jaccard_similarity = len(intersection) / len(union) if union else 0.0
            return 1.0 - jaccard_similarity
    
    def has_explicit_reference(self, query: str) -> bool:
        """
        Check if query contains explicit reference to previous context.
        
        Examples:
        - "As we discussed earlier..."
        - "You mentioned that Ferrari..."
        - "Remember when we talked about...
        """
        query_lower = query.lower()
        
        for pattern in self.reference_patterns:
            if re.search(pattern, query_lower):
                return True
        
        return False
    
    def identify_bridge_turns(
        self,
        all_turns: List[Dict],
        old_topic: str,
        keep_count: int = 3
    ) -> Set[str]:
        """
        Identify bridge turns from old topic to preserve.
        
        Bridge turns are the last N turns from the previous topic,
        kept to provide smooth context transition.
        
        Args:
            all_turns: All turns in window
            old_topic: Previous topic that's being compressed
            keep_count: Number of bridge turns to preserve (default 3)
            
        Returns:
            Set of turn IDs to keep as bridge turns
        """
        old_topic_turns = [
            turn for turn in all_turns
            if old_topic.lower() in [t.lower() for t in turn.get('topics', [])]
        ]
        
        # Keep last N from old topic
        bridge = old_topic_turns[-keep_count:] if old_topic_turns else []
        return {turn['turn_id'] for turn in bridge}
    
    def apply_compression(
        self,
        sliding_window,
        decision: CompressionDecision,
        current_topics: List[str],
        debug: bool = False
    ) -> Dict[str, int]:
        """
        Apply compression decision to sliding window.
        
        Compresses old-topic turns while keeping recent turns and bridge turns verbatim.
        
        Args:
            sliding_window: SlidingWindow object to modify
            decision: CompressionDecision from decide_compression()
            current_topics: Topics from current query
            debug: Enable debug logging
            
        Returns:
            Dict with statistics (compressed_count, verbatim_count, etc.)
        """
        from datetime import datetime
        
        if debug:
            logger.info(f"🔍 apply_compression() CALLED!")
            logger.info(f"   Decision: {decision.level.value}")
            logger.info(f"   Sliding window: {len(sliding_window.turns)} turns")
            logger.info(f"   Current topics: {current_topics}")
        
        if decision.level == CompressionLevel.NO_COMPRESSION:
            if debug:
                logger.info("✅ No compression needed")
            return {
                'compressed_count': 0,
                'verbatim_count': len(sliding_window.turns),
                'bridge_turns_preserved': 0,
                'old_topic': None
            }
        
        turns = sliding_window.turns
        total_turns = len(turns)
        
        # Determine which turns to keep verbatim
        keep_verbatim_count = min(decision.keep_verbatim_count, total_turns)
        
        # Most recent N turns stay verbatim
        recent_verbatim_ids = {
            turn.turn_id for turn in turns[-keep_verbatim_count:]
        }
        
        # Identify old topic (most common topic in window not in current query)
        topic_counts = {}
        current_topics_lower = [t.lower() for t in current_topics]
        
        for turn in turns[:-keep_verbatim_count]:  # Exclude recent verbatim
            for topic in turn.active_topics if hasattr(turn, 'active_topics') else turn.keywords:
                topic_lower = topic.lower()
                if topic_lower not in current_topics_lower:
                    topic_counts[topic_lower] = topic_counts.get(topic_lower, 0) + 1
        
        old_topic = max(topic_counts, key=topic_counts.get) if topic_counts else None
        
        # Identify bridge turns (if old topic exists)
        bridge_turn_ids = set()
        if old_topic and decision.bridge_turns_count > 0:
            bridge_turn_ids = self.identify_bridge_turns(
                turns[:-keep_verbatim_count],
                old_topic,
                decision.bridge_turns_count
            )
        
        # Compress turns that are not recent verbatim and not bridge
        compressed_count = 0
        for turn in turns:
            if turn.turn_id not in recent_verbatim_ids and turn.turn_id not in bridge_turn_ids:
                if turn.detail_level == 'VERBATIM':
                    # Compress this turn
                    old_level = turn.detail_level
                    turn.detail_level = 'COMPRESSED'
                    turn.compressed_content = turn.assistant_summary or "Summary unavailable"
                    turn.compression_timestamp = datetime.now()
                    compressed_count += 1
                    
                    if debug:
                        logger.info(f"   📦 Compressed {turn.turn_id}: {old_level} → {turn.detail_level}")
                        logger.info(f"       Old topic: {old_topic}, Compressed content: {turn.compressed_content[:50]}...")
        
        stats = {
            'compressed_count': compressed_count,
            'verbatim_count': len(recent_verbatim_ids) + len(bridge_turn_ids),
            'bridge_turns_preserved': len(bridge_turn_ids),
            'old_topic': old_topic
        }
        
        if debug:
            logger.info(f"✅ Compression applied:")
            logger.info(f"   Compressed: {stats['compressed_count']} turns")
            logger.info(f"   Verbatim: {stats['verbatim_count']} turns")
            logger.info(f"   Bridge: {stats['bridge_turns_preserved']} turns")
        
        return stats
    
    def enforce_hard_limit(
        self,
        sliding_window,
        max_verbatim: int = None,
        debug: bool = False
    ) -> int:
        """
        Enforce hard limit on verbatim turns (safety valve).
        
        NOTE: Currently disabled - ConversationTurn doesn't have
        detail_level or compress_to_summary() methods. This would
        require adding compression state tracking to the data model.
        
        Args:
            sliding_window: SlidingWindow object
            max_verbatim: Maximum verbatim turns (default: MAX_VERBATIM_HARD_LIMIT)
            debug: Enable debug logging
            
        Returns:
            Number of turns force-compressed (always 0 for now)
        """
        # TODO: Implement compression when detail_level is added to ConversationTurn
        return 0
    
    def _calc_time_gap(self, recent_turn: Dict) -> float:
        """Calculate time gap in hours since most recent turn."""
        timestamp = recent_turn.get('timestamp')
        if not timestamp:
            return 0.0
        
        if isinstance(timestamp, str):
            # Parse ISO format
            timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        
        gap = datetime.now() - timestamp
        return gap.total_seconds() / 3600
