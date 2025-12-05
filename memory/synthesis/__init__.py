"""
Synthesis module for CognitiveLattice.

Provides hierarchical synthesis of user behavior patterns from daily metadata.
"""

from .synthesis_engine import (
    UserProfile,
    DaySynthesizer,
    HierarchicalSynthesizer,
    SynthesisManager
)

__all__ = [
    'UserProfile',
    'DaySynthesizer',
    'HierarchicalSynthesizer',
    'SynthesisManager'
]