"""
Eviction manager for adaptive sliding window.

Implements dual eviction strategy:
1. Time-based: >24 hours unused → evict
2. Space-based: >5k tokens OR >30 turns → FIFO evict
"""

from typing import List, Dict, Set
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class EvictionStats:
    """Statistics from eviction operation."""
    time_evicted: int
    space_evicted: int
    total_evicted: int
    evicted_turn_ids: List[str]


class EvictionManager:
    """
    Manage eviction from Tier 2 (compressed/recently seen).
    
    Phase 4.3 Week 3 implementation:
    - Time-based eviction (24 hour threshold)
    - Space-based eviction (5k tokens OR 30 turns)
    - Topic affinity tracking on eviction
    """
    
    # Eviction thresholds
    TIME_THRESHOLD_HOURS = 24
    MAX_TIER2_TOKENS = 5000
    MAX_TIER2_TURNS = 30
    
    def __init__(self):
        """Initialize eviction manager."""
        self.eviction_history: List[dict] = []
    
    def check_eviction_needed(
        self,
        sliding_window,
        debug: bool = False
    ) -> EvictionStats:
        """
        Check if eviction is needed and perform it.
        
        Args:
            sliding_window: SlidingWindow object
            debug: Enable debug logging
            
        Returns:
            EvictionStats with counts and evicted turn IDs
        """
        time_evicted_ids = self._evict_by_time(sliding_window, debug)
        space_evicted_ids = self._evict_by_space(sliding_window, debug)
        
        all_evicted = list(set(time_evicted_ids + space_evicted_ids))
        
        stats = EvictionStats(
            time_evicted=len(time_evicted_ids),
            space_evicted=len(space_evicted_ids),
            total_evicted=len(all_evicted),
            evicted_turn_ids=all_evicted
        )
        
        if debug and stats.total_evicted > 0:
            logger.info(f"🗑️  Eviction complete:")
            logger.info(f"   Time-based: {stats.time_evicted}")
            logger.info(f"   Space-based: {stats.space_evicted}")
            logger.info(f"   Total: {stats.total_evicted}")
        
        return stats
    
    def _evict_by_time(
        self,
        sliding_window,
        debug: bool = False
    ) -> List[str]:
        """
        Evict turns from Tier 2 that haven't been accessed in 24 hours.
        
        NOTE: Currently disabled - SlidingWindow already handles eviction
        via max_turns limit. Tier 2 (recently_seen) only stores IDs,
        not full turn objects, so time-based eviction would require
        accessing the storage layer.
        
        Returns list of evicted turn IDs.
        """
        # TODO: Implement time-based eviction from storage layer
        # For now, rely on SlidingWindow's built-in FIFO eviction
        return []
    
    def _evict_by_space(
        self,
        sliding_window,
        debug: bool = False
    ) -> List[str]:
        """
        Evict turns from Tier 2 if over token/turn limits (FIFO).
        
        NOTE: Currently disabled - SlidingWindow already handles eviction
        via max_turns limit. This method would need to be redesigned to
        work with the two-tier ID tracking system where Tier 2 only
        stores IDs, not full turn objects.
        
        Returns list of evicted turn IDs.
        """
        # TODO: Implement space-based eviction with proper tier tracking
        # For now, rely on SlidingWindow's built-in FIFO eviction
        return []
    
    def update_topic_affinity(
        self,
        evicted_turn,
        topic_affinity_tracker: Dict[str, Dict]
    ):
        """
        Update topic affinity when turn is evicted.
        
        Tracks which topics get evicted frequently (low affinity)
        vs stay in window longer (high affinity).
        
        Args:
            evicted_turn: Turn being evicted
            topic_affinity_tracker: Dict to update {topic: {stats}}
        """
        for topic in evicted_turn.topics:
            topic_lower = topic.lower()
            
            if topic_lower not in topic_affinity_tracker:
                topic_affinity_tracker[topic_lower] = {
                    'eviction_count': 0,
                    'total_time_in_window': timedelta(),
                    'avg_time_in_window': timedelta()
                }
            
            stats = topic_affinity_tracker[topic_lower]
            stats['eviction_count'] += 1
            
            # Calculate time in window
            if hasattr(evicted_turn, 'added_to_window_at'):
                time_in_window = datetime.now() - evicted_turn.added_to_window_at
                stats['total_time_in_window'] += time_in_window
                stats['avg_time_in_window'] = (
                    stats['total_time_in_window'] / stats['eviction_count']
                )
    
    def get_eviction_summary(self) -> dict:
        """Get summary of recent evictions."""
        if not self.eviction_history:
            return {
                'total_evictions': 0,
                'time_based': 0,
                'space_based': 0,
                'recent_evictions': []
            }
        
        recent = self.eviction_history[-10:]  # Last 10 eviction events
        
        return {
            'total_evictions': sum(e['count'] for e in self.eviction_history),
            'time_based': sum(e['time_count'] for e in self.eviction_history),
            'space_based': sum(e['space_count'] for e in self.eviction_history),
            'recent_evictions': recent
        }
    
    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimation (4 chars ≈ 1 token)."""
        return len(text) // 4
