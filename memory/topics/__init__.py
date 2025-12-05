"""
Topic tracking and filtering module.

This module handles:
- Topic extraction from user queries
- Active topic tracking in sliding window
- Topic-aware context filtering
- Topic-based semantic embeddings for compression
"""

from .extractor import TopicExtractor
from .filter import TopicFilter
from .topic_embedder import TopicEmbedder

__all__ = ['TopicExtractor', 'TopicFilter', 'TopicEmbedder']

