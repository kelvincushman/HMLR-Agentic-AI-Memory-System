"""
Rehydration manager for adaptive sliding window.

Handles rehydrating turns from storage back to Tier 1 (verbatim)
or Tier 2 (compressed) based on token budget availability.
"""

from typing import List, Dict, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class RehydrationLevel(Enum):
    """Rehydration target level."""
    TO_VERBATIM = "to_verbatim"  # Tier 1 - full verbatim
    TO_COMPRESSED = "to_compressed"  # Tier 2 - summary
    SKIP = "skip"  # No rehydration, budget too tight


class RehydrationManager:
    """
    Manage rehydration from storage to sliding window.
    
    Phase 4.3 Week 3 implementation:
    - Token-budget aware decisions
    - >10k available → verbatim
    - 5k-10k available → compressed
    - <5k → skip rehydration
    """
    
    # Token budget thresholds
    ABUNDANT_BUDGET = 10000  # >10k = rehydrate to verbatim
    MODERATE_BUDGET = 5000   # 5k-10k = rehydrate to compressed
    
    def __init__(self):
        """Initialize rehydration manager."""
        self.rehydration_history: List[dict] = []
    
    def decide_rehydration(
        self,
        available_tokens: int,
        turn_full_size: int,
        turn_summary_size: int,
        debug: bool = False
    ) -> RehydrationLevel:
        """
        Decide rehydration level based on token budget.
        
        Args:
            available_tokens: Tokens available in budget
            turn_full_size: Size of turn if rehydrated to verbatim
            turn_summary_size: Size of turn if rehydrated to compressed
            debug: Enable debug logging
            
        Returns:
            RehydrationLevel decision
        """
        if available_tokens >= self.ABUNDANT_BUDGET:
            # Abundant budget - rehydrate to verbatim
            if turn_full_size <= available_tokens:
                decision = RehydrationLevel.TO_VERBATIM
                reason = f"Abundant budget ({available_tokens} tokens)"
            else:
                # Even with abundant budget, turn is too big
                decision = RehydrationLevel.TO_COMPRESSED
                reason = f"Turn too large ({turn_full_size} > {available_tokens})"
        
        elif available_tokens >= self.MODERATE_BUDGET:
            # Moderate budget - rehydrate to compressed
            if turn_summary_size <= available_tokens:
                decision = RehydrationLevel.TO_COMPRESSED
                reason = f"Moderate budget ({available_tokens} tokens)"
            else:
                decision = RehydrationLevel.SKIP
                reason = f"Insufficient budget ({available_tokens} < {turn_summary_size})"
        
        else:
            # Tight budget - skip rehydration
            decision = RehydrationLevel.SKIP
            reason = f"Tight budget ({available_tokens} tokens)"
        
        if debug:
            logger.info(f"💧 Rehydration decision: {decision.value}")
            logger.info(f"   Reason: {reason}")
        
        return decision
    
    def rehydrate_turn(
        self,
        turn,
        level: RehydrationLevel,
        sliding_window,
        debug: bool = False
    ) -> bool:
        """
        Rehydrate turn from storage to sliding window.
        
        Args:
            turn: Turn to rehydrate
            level: RehydrationLevel (verbatim, compressed, or skip)
            sliding_window: SlidingWindow to add to
            debug: Enable debug logging
            
        Returns:
            True if rehydrated successfully
        """
        if level == RehydrationLevel.SKIP:
            if debug:
                logger.info(f"   ⏭️  Skipped {turn.turn_id} (no budget)")
            return False
        
        # Set detail level
        if level == RehydrationLevel.TO_VERBATIM:
            turn.detail_level = 'VERBATIM'
            target_tier = "Tier 1"
        else:  # TO_COMPRESSED
            turn.detail_level = 'SUMMARY'
            target_tier = "Tier 2"
        
        # Add to window
        sliding_window.add_turn(turn)
        
        # Track rehydration
        if not hasattr(turn, 'rehydration_count'):
            turn.rehydration_count = 0
        turn.rehydration_count += 1
        
        turn.last_accessed = turn.timestamp.__class__.now() if hasattr(turn, 'timestamp') else None
        
        self.rehydration_history.append({
            'turn_id': turn.turn_id,
            'level': level.value,
            'timestamp': turn.last_accessed,
            'topics': turn.topics if hasattr(turn, 'topics') else []
        })
        
        if debug:
            logger.info(f"   💧 Rehydrated {turn.turn_id} to {target_tier}")
        
        return True
    
    def rehydrate_multiple(
        self,
        turns: List,
        available_tokens: int,
        sliding_window,
        prefer_recent: bool = True,
        debug: bool = False
    ) -> Dict[str, int]:
        """
        Rehydrate multiple turns within token budget.
        
        Args:
            turns: List of turns to potentially rehydrate
            available_tokens: Total token budget available
            sliding_window: SlidingWindow to add to
            prefer_recent: If True, prioritize more recent turns
            debug: Enable debug logging
            
        Returns:
            Dict with statistics (rehydrated_count, verbatim_count, etc.)
        """
        if prefer_recent:
            # Sort by timestamp (most recent first)
            turns = sorted(
                turns,
                key=lambda t: t.timestamp if hasattr(t, 'timestamp') else 0,
                reverse=True
            )
        
        stats = {
            'rehydrated_count': 0,
            'verbatim_count': 0,
            'compressed_count': 0,
            'skipped_count': 0,
            'tokens_used': 0
        }
        
        remaining_budget = available_tokens
        
        for turn in turns:
            # Estimate sizes
            full_size = self._estimate_tokens(turn.full_text if hasattr(turn, 'full_text') else '')
            summary_size = self._estimate_tokens(turn.summary if hasattr(turn, 'summary') else '')
            
            # Decide rehydration level
            level = self.decide_rehydration(
                remaining_budget,
                full_size,
                summary_size,
                debug=False  # Suppress per-turn debug
            )
            
            # Apply rehydration
            if level != RehydrationLevel.SKIP:
                success = self.rehydrate_turn(turn, level, sliding_window, debug=False)
                
                if success:
                    stats['rehydrated_count'] += 1
                    
                    if level == RehydrationLevel.TO_VERBATIM:
                        stats['verbatim_count'] += 1
                        stats['tokens_used'] += full_size
                        remaining_budget -= full_size
                    else:
                        stats['compressed_count'] += 1
                        stats['tokens_used'] += summary_size
                        remaining_budget -= summary_size
            else:
                stats['skipped_count'] += 1
        
        if debug:
            logger.info(f"💧 Batch rehydration complete:")
            logger.info(f"   Total rehydrated: {stats['rehydrated_count']}")
            logger.info(f"   To verbatim: {stats['verbatim_count']}")
            logger.info(f"   To compressed: {stats['compressed_count']}")
            logger.info(f"   Skipped: {stats['skipped_count']}")
            logger.info(f"   Tokens used: {stats['tokens_used']}/{available_tokens}")
        
        return stats
    
    def get_rehydration_summary(self) -> dict:
        """Get summary of recent rehydrations."""
        if not self.rehydration_history:
            return {
                'total_rehydrations': 0,
                'to_verbatim': 0,
                'to_compressed': 0,
                'recent_rehydrations': []
            }
        
        recent = self.rehydration_history[-10:]  # Last 10
        
        return {
            'total_rehydrations': len(self.rehydration_history),
            'to_verbatim': sum(1 for r in self.rehydration_history if r['level'] == 'to_verbatim'),
            'to_compressed': sum(1 for r in self.rehydration_history if r['level'] == 'to_compressed'),
            'recent_rehydrations': recent
        }
    
    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimation (4 chars ≈ 1 token)."""
        return len(text) // 4 if text else 0
