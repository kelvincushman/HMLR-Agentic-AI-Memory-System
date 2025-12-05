"""
Context usage tracking through LLM citation system.

This module tracks which context the LLM actually uses in its responses,
rather than assuming all provided context is "active".

Key concept: LLM includes [ref:TURN_ID] in responses to cite sources.
We parse these citations to know what was actually used.
"""

from .parser import CitationParser
from .tracker import UsageTracker
from .metrics import UsageMetrics

__all__ = ['CitationParser', 'UsageTracker', 'UsageMetrics']
