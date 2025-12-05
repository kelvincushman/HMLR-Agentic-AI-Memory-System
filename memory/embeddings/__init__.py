"""
Vector Embeddings Module for RAG Retrieval

This module handles:
- Semantic chunking of conversation turns
- Vector embedding generation
- Similarity search
- Hybrid retrieval (vector + keyword)
"""

from .embedding_manager import EmbeddingManager
from .chunker import SemanticChunker

__all__ = ['EmbeddingManager', 'SemanticChunker']
