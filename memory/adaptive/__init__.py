"""
Adaptive sliding window with intelligent compression.

This module implements the sophisticated compression strategy designed
in ADAPTIVE_SLIDING_WINDOW_STRATEGIES.md and validated in
TOPIC_SHIFT_FLOW_WALKTHROUGH.md.

Key concepts:
- Graduated semantic thresholds (0.6, 0.8)
- Time as modifier (not primary rule)
- Bridge turns preservation
- Dual eviction (time + space based)
- Token-budget aware rehydration
"""

from .compressor import AdaptiveCompressor, CompressionLevel, CompressionDecision
from .eviction import EvictionManager, EvictionStats
from .rehydration import RehydrationManager, RehydrationLevel

__all__ = [
    'AdaptiveCompressor',
    'CompressionLevel',
    'CompressionDecision',
    'EvictionManager',
    'EvictionStats',
    'RehydrationManager',
    'RehydrationLevel'
]
