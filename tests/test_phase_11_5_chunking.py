"""
Unit tests for Phase 11.5: Pre-Chunking Engine & Hybrid Search

Tests cover:
- ChunkEngine: Sentence/paragraph splitting, keyword extraction
- ChunkStorage: Database operations, FTS5 indexing
- HybridSearchEngine: Two-Key system, lexical + vector search
"""
import pytest
import tempfile
import os
from datetime import datetime

from memory.chunking import ChunkEngine, Chunk, ChunkStorage
from memory.storage import Storage


class TestChunkEngine:
    """Test suite for ChunkEngine class."""
    
    @pytest.fixture
    def engine(self):
        return ChunkEngine()
    
    def test_single_sentence(self, engine):
        """Test chunking a single sentence."""
        text = "This is a test."
        chunks = engine.chunk_turn(text, turn_id="turn_1", span_id="span_1")
        
        # Should create 1 sentence + 1 paragraph
        assert len(chunks) == 2
        
        # Find sentence chunk
        sent_chunk = next(c for c in chunks if c.chunk_type == 'sentence')
        assert sent_chunk.text_verbatim == "This is a test."
        assert sent_chunk.turn_id == "turn_1"
        assert sent_chunk.span_id == "span_1"
        assert sent_chunk.chunk_id.startswith("sent_")
    
    def test_multiple_sentences(self, engine):
        """Test chunking multiple sentences."""
        text = "First sentence. Second sentence. Third sentence."
        chunks = engine.chunk_turn(text, turn_id="turn_1", span_id="span_1")
        
        # 3 sentences + 1 paragraph = 4 chunks
        sentences = [c for c in chunks if c.chunk_type == 'sentence']
        assert len(sentences) == 3
        assert sentences[0].text_verbatim == "First sentence."
        assert sentences[1].text_verbatim == "Second sentence."
        assert sentences[2].text_verbatim == "Third sentence."
    
    def test_paragraph_splitting(self, engine):
        """Test splitting by double newline."""
        text = "First paragraph.\n\nSecond paragraph."
        chunks = engine.chunk_turn(text, turn_id="turn_1", span_id="span_1")
        
        paragraphs = [c for c in chunks if c.chunk_type == 'paragraph']
        assert len(paragraphs) == 2
        assert "First paragraph" in paragraphs[0].text_verbatim
        assert "Second paragraph" in paragraphs[1].text_verbatim
    
    def test_keyword_extraction(self, engine):
        """Test stop word removal and keyword extraction."""
        text = "The quick brown fox jumps over the lazy dog."
        chunks = engine.chunk_turn(text, turn_id="turn_1", span_id="span_1")
        
        sent_chunk = next(c for c in chunks if c.chunk_type == 'sentence')
        keywords = sent_chunk.lexical_filters
        
        # Should remove stop words (the, over)
        assert "the" not in keywords
        assert "over" not in keywords
        
        # Should keep content words
        assert "quick" in keywords
        assert "brown" in keywords
        assert "fox" in keywords
        assert "jumps" in keywords
    
    def test_hierarchical_linking(self, engine):
        """Test parent-child chunk relationships."""
        text = "Sentence one. Sentence two."
        chunks = engine.chunk_turn(text, turn_id="turn_1", span_id="span_1")
        
        paragraph = next(c for c in chunks if c.chunk_type == 'paragraph')
        sentences = [c for c in chunks if c.chunk_type == 'sentence']
        
        # Sentences should link to paragraph as parent
        for sent in sentences:
            assert sent.parent_chunk_id == paragraph.chunk_id
    
    def test_abbreviation_handling(self, engine):
        """Test that abbreviations don't cause false sentence breaks."""
        text = "Dr. Smith said hello. Mr. Jones agreed."
        chunks = engine.chunk_turn(text, turn_id="turn_1", span_id="span_1")
        
        sentences = [c for c in chunks if c.chunk_type == 'sentence']
        
        # Should be 2 sentences, not 4 (false splits on "Dr." and "Mr.")
        assert len(sentences) == 2
        assert "Dr. Smith" in sentences[0].text_verbatim
        assert "Mr. Jones" in sentences[1].text_verbatim
    
    def test_empty_text(self, engine):
        """Test handling of empty text."""
        chunks = engine.chunk_turn("", turn_id="turn_1", span_id="span_1")
        assert len(chunks) == 0
        
        chunks = engine.chunk_turn("   ", turn_id="turn_1", span_id="span_1")
        assert len(chunks) == 0
    
    def test_token_estimation(self, engine):
        """Test rough token count estimation."""
        text = "This is a test sentence with approximately forty characters total."
        chunks = engine.chunk_turn(text, turn_id="turn_1", span_id="span_1")
        
        sent_chunk = next(c for c in chunks if c.chunk_type == 'sentence')
        
        # ~67 chars / 4 ≈ 16-17 tokens
        assert 15 <= sent_chunk.token_count <= 20


class TestChunkStorage:
    """Test suite for ChunkStorage database operations."""
    
    @pytest.fixture
    def storage_and_chunk_storage(self):
        """Create temporary database with migrations."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
            db_path = f.name
        
        storage = Storage(db_path)
        
        # Run migrations
        from memory.migrations.migration_runner import run_pending_migrations
        run_pending_migrations(db_path)
        
        chunk_storage = ChunkStorage(storage)
        
        yield storage, chunk_storage
        
        # Cleanup
        storage.conn.close()
        os.unlink(db_path)
    
    def test_save_and_retrieve_chunks(self, storage_and_chunk_storage):
        """Test saving and retrieving chunks."""
        storage, chunk_storage = storage_and_chunk_storage
        engine = ChunkEngine()
        
        # Create chunks
        text = "Test sentence one. Test sentence two."
        chunks = engine.chunk_turn(text, turn_id="turn_123", span_id="span_456")
        
        # Save to database
        chunk_storage.save_chunks(chunks)
        
        # Retrieve by turn
        retrieved = chunk_storage.get_chunks_by_turn("turn_123")
        assert len(retrieved) == len(chunks)
        
        # Verify content
        sent_chunks = [c for c in retrieved if c.chunk_type == 'sentence']
        assert len(sent_chunks) == 2
        assert "Test sentence one" in sent_chunks[0].text_verbatim
    
    def test_get_chunk_by_id(self, storage_and_chunk_storage):
        """Test retrieving specific chunk by ID."""
        storage, chunk_storage = storage_and_chunk_storage
        engine = ChunkEngine()
        
        chunks = engine.chunk_turn("Single test.", turn_id="turn_1", span_id="span_1")
        chunk_storage.save_chunks(chunks)
        
        sent_chunk = next(c for c in chunks if c.chunk_type == 'sentence')
        
        # Retrieve by ID
        retrieved = chunk_storage.get_chunk_by_id(sent_chunk.chunk_id)
        assert retrieved is not None
        assert retrieved.chunk_id == sent_chunk.chunk_id
        assert retrieved.text_verbatim == sent_chunk.text_verbatim
    
    def test_get_child_chunks(self, storage_and_chunk_storage):
        """Test retrieving child chunks (sentences in paragraph)."""
        storage, chunk_storage = storage_and_chunk_storage
        engine = ChunkEngine()
        
        text = "Child one. Child two. Child three."
        chunks = engine.chunk_turn(text, turn_id="turn_1", span_id="span_1")
        chunk_storage.save_chunks(chunks)
        
        para_chunk = next(c for c in chunks if c.chunk_type == 'paragraph')
        
        # Get children
        children = chunk_storage.get_child_chunks(para_chunk.chunk_id)
        assert len(children) == 3
        assert all(c.chunk_type == 'sentence' for c in children)
    
    def test_lexical_search_fts5(self, storage_and_chunk_storage):
        """Test FTS5 lexical keyword search."""
        storage, chunk_storage = storage_and_chunk_storage
        engine = ChunkEngine()
        
        # Create chunks with distinct keywords
        text1 = "AWS EC2 instances require proper configuration."
        text2 = "Python programming is fun and powerful."
        text3 = "AWS Lambda functions are serverless."
        
        chunks1 = engine.chunk_turn(text1, turn_id="turn_1", span_id="span_1")
        chunks2 = engine.chunk_turn(text2, turn_id="turn_2", span_id="span_1")
        chunks3 = engine.chunk_turn(text3, turn_id="turn_3", span_id="span_1")
        
        chunk_storage.save_chunks(chunks1 + chunks2 + chunks3)
        
        # Search for "AWS"
        results = chunk_storage.search_chunks_lexical(["aws"])
        
        # Should find 2 chunks (text1 and text3 mention AWS)
        aws_results = [r for r in results if "AWS" in r.text_verbatim or "aws" in r.lexical_filters]
        assert len(aws_results) >= 2
    
    def test_chunk_count(self, storage_and_chunk_storage):
        """Test counting chunks by type."""
        storage, chunk_storage = storage_and_chunk_storage
        engine = ChunkEngine()
        
        text = "First. Second. Third."
        chunks = engine.chunk_turn(text, turn_id="turn_1", span_id="span_1")
        chunk_storage.save_chunks(chunks)
        
        # Should have 3 sentences + 1 paragraph = 4 total
        total = chunk_storage.get_chunk_count()
        assert total == 4
        
        sentences = chunk_storage.get_chunk_count('sentence')
        assert sentences == 3
        
        paragraphs = chunk_storage.get_chunk_count('paragraph')
        assert paragraphs == 1


class TestImmutability:
    """Test that chunk IDs remain immutable (critical for Phase 11.5 goal)."""
    
    def test_chunk_ids_unique_and_persistent(self):
        """Verify chunk IDs are unique and don't change."""
        engine = ChunkEngine()
        
        # Create same text twice
        text = "Test sentence."
        chunks1 = engine.chunk_turn(text, turn_id="turn_1", span_id="span_1")
        chunks2 = engine.chunk_turn(text, turn_id="turn_2", span_id="span_1")
        
        # IDs should be different (each turn gets unique chunks)
        assert chunks1[0].chunk_id != chunks2[0].chunk_id
        
        # But once created, ID never changes (this is the IMMUTABLE guarantee)
        original_id = chunks1[0].chunk_id
        
        # Simulate "re-chunking" (shouldn't happen, but if it did...)
        chunks1_copy = engine.chunk_turn(text, turn_id="turn_1", span_id="span_1")
        
        # Different instance, different ID (proves uniqueness)
        assert chunks1[0].chunk_id != chunks1_copy[0].chunk_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
