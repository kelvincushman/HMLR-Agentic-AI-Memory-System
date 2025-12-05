"""
Phase 11.3: FactScrubber Tests

Tests cover:
1. Heuristic fact extraction (no LLM)
2. Fact-chunk linking (sentence → paragraph → block)
3. Fact storage and retrieval
4. Query operations (by key, category, fuzzy search)
5. Edge cases (no facts, malformed input)
"""

import pytest
import asyncio
from datetime import datetime
from typing import List, Dict, Any

from memory.storage import Storage
from memory.fact_scrubber import FactScrubber, Fact
from memory.chunking.chunk_engine import ChunkEngine


@pytest.fixture
def storage():
    """Create in-memory database for testing."""
    storage = Storage(db_path=":memory:")
    
    # Create required tables
    cursor = storage.conn.cursor()
    
    # Spans table (required for foreign keys)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS spans (
            span_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL
        )
    """)
    
    # Chunks table (from Phase 11.5)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            chunk_id TEXT PRIMARY KEY,
            parent_chunk_id TEXT,
            chunk_type TEXT NOT NULL,
            text_verbatim TEXT NOT NULL,
            lexical_filters TEXT,
            span_id TEXT,
            turn_id TEXT,
            block_id TEXT,
            created_at TEXT NOT NULL,
            token_count INTEGER DEFAULT 0,
            metadata TEXT,
            FOREIGN KEY (parent_chunk_id) REFERENCES chunks(chunk_id) ON DELETE CASCADE,
            FOREIGN KEY (span_id) REFERENCES spans(span_id) ON DELETE SET NULL
        )
    """)
    
    storage.conn.commit()
    return storage


@pytest.fixture
def scrubber(storage):
    """Create FactScrubber instance (no LLM for testing)."""
    return FactScrubber(storage=storage, api_client=None)


@pytest.fixture
def chunk_engine():
    """Create ChunkEngine for generating test chunks."""
    return ChunkEngine()


class TestFactExtraction:
    """Test fact extraction from text (heuristic mode)."""
    
    def test_extract_acronym_equals_pattern(self, scrubber, chunk_engine):
        """Test: Extract acronym with = syntax (e.g., 'HMLR = Hierarchical...')"""
        message = "HMLR = Hierarchical Memory Lookup & Routing. It's our system."
        turn_id = "turn_001"
        
        # Generate chunks
        chunks = chunk_engine.chunk_turn(message, turn_id, span_id="span_001")
        
        # Extract facts
        facts = asyncio.run(scrubber.extract_and_save(
            turn_id=turn_id,
            message_text=message,
            chunks=chunks,
            span_id="span_001"
        ))
        
        assert len(facts) == 1
        assert facts[0].key == "HMLR"
        assert "Hierarchical Memory" in facts[0].value
        assert facts[0].category == "Acronym"
        assert facts[0].source_span_id == "span_001"
    
    def test_extract_acronym_stands_for_pattern(self, scrubber, chunk_engine):
        """Test: Extract acronym with 'stands for' syntax"""
        message = "API stands for Application Programming Interface."
        turn_id = "turn_002"
        
        chunks = chunk_engine.chunk_turn(message, turn_id, span_id="span_002")
        
        facts = asyncio.run(scrubber.extract_and_save(
            turn_id=turn_id,
            message_text=message,
            chunks=chunks,
            span_id="span_002"
        ))
        
        assert len(facts) == 1
        assert facts[0].key == "API"
        assert "Application Programming Interface" in facts[0].value
        assert facts[0].category == "Acronym"
    
    def test_extract_multiple_facts(self, scrubber, chunk_engine):
        """Test: Extract multiple facts from one message"""
        message = "HMLR = Hierarchical Memory Lookup & Routing. RAG stands for Retrieval Augmented Generation."
        turn_id = "turn_003"
        
        chunks = chunk_engine.chunk_turn(message, turn_id, span_id="span_003")
        
        facts = asyncio.run(scrubber.extract_and_save(
            turn_id=turn_id,
            message_text=message,
            chunks=chunks,
            span_id="span_003"
        ))
        
        assert len(facts) == 2
        keys = {f.key for f in facts}
        assert "HMLR" in keys
        assert "RAG" in keys
    
    def test_no_facts_found(self, scrubber, chunk_engine):
        """Test: Return empty list when no facts present"""
        message = "This is just a regular sentence with no facts."
        turn_id = "turn_004"
        
        chunks = chunk_engine.chunk_turn(message, turn_id, span_id="span_004")
        
        facts = asyncio.run(scrubber.extract_and_save(
            turn_id=turn_id,
            message_text=message,
            chunks=chunks,
            span_id="span_004"
        ))
        
        assert len(facts) == 0


class TestChunkLinking:
    """Test fact linking to sentence/paragraph/block chunks."""
    
    def test_link_to_sentence_chunk(self, scrubber, chunk_engine, storage):
        """Test: Fact links to the sentence chunk containing evidence"""
        message = "HMLR = Hierarchical Memory Lookup & Routing. This is the second sentence."
        turn_id = "turn_005"
        
        # Generate chunks (2 sentences, 1 paragraph)
        chunks = chunk_engine.chunk_turn(message, turn_id, span_id="span_005")
        
        # Save chunks to database (required for linking)
        cursor = storage.conn.cursor()
        for chunk in chunks:
            # Convert lexical_filters list to JSON string
            import json
            lexical_filters_json = json.dumps(chunk.lexical_filters)
            
            cursor.execute("""
                INSERT INTO chunks (
                    chunk_id, parent_chunk_id, chunk_type, text_verbatim, 
                    lexical_filters, turn_id, span_id, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                chunk.chunk_id,
                chunk.parent_chunk_id,
                chunk.chunk_type,
                chunk.text_verbatim,
                lexical_filters_json,
                chunk.turn_id,
                chunk.span_id,
                datetime.now().isoformat() + "Z"
            ))
        storage.conn.commit()
        
        # Extract facts
        facts = asyncio.run(scrubber.extract_and_save(
            turn_id=turn_id,
            message_text=message,
            chunks=chunks,
            span_id="span_005"
        ))
        
        assert len(facts) == 1
        fact = facts[0]
        
        # Verify fact was extracted
        assert fact.key == "HMLR"
        assert "Hierarchical" in fact.value
        assert fact.source_span_id == "span_005"
        
        # Note: Heuristic extraction calls _create_fact_with_chunk_link, which should link
        # This test verifies the chunk linking mechanism works when chunks are provided
        assert fact.source_chunk_id is not None, "Fact should link to sentence chunk"
        assert fact.source_chunk_id.startswith("sent_"), "Should link to sentence chunk"
    
    def test_link_to_paragraph_chunk(self, scrubber, chunk_engine):
        """Test: Fact links to parent paragraph chunk"""
        message = "HMLR = Hierarchical Memory Lookup & Routing. It's our system."
        turn_id = "turn_006"
        
        chunks = chunk_engine.chunk_turn(message, turn_id, span_id="span_006")
        
        # Find the paragraph chunk
        paragraph_chunks = [c for c in chunks if c.chunk_type == "paragraph"]
        assert len(paragraph_chunks) == 1
        
        facts = asyncio.run(scrubber.extract_and_save(
            turn_id=turn_id,
            message_text=message,
            chunks=chunks,
            span_id="span_006"
        ))
        
        # Verify fact was created
        assert len(facts) == 1


class TestFactStorage:
    """Test fact persistence and retrieval."""
    
    def test_save_and_retrieve_fact(self, scrubber, chunk_engine):
        """Test: Save fact to database and retrieve by key"""
        message = "HMLR = Hierarchical Memory Lookup & Routing."
        turn_id = "turn_007"
        
        chunks = chunk_engine.chunk_turn(message, turn_id, span_id="span_007")
        
        # Extract and save
        facts = asyncio.run(scrubber.extract_and_save(
            turn_id=turn_id,
            message_text=message,
            chunks=chunks,
            span_id="span_007"
        ))
        
        # Retrieve by exact key
        retrieved = scrubber.get_fact_by_key("HMLR")
        
        assert retrieved is not None
        assert retrieved.key == "HMLR"
        assert "Hierarchical Memory" in retrieved.value
        assert retrieved.category == "Acronym"
    
    def test_query_facts_fuzzy_search(self, scrubber, chunk_engine):
        """Test: Fuzzy search for facts (partial match)"""
        # Create multiple facts
        messages = [
            "HMLR = Hierarchical Memory Lookup & Routing.",
            "RAG stands for Retrieval Augmented Generation.",
            "API = Application Programming Interface."
        ]
        
        for i, msg in enumerate(messages):
            turn_id = f"turn_{i+10}"
            chunks = chunk_engine.chunk_turn(msg, turn_id, span_id=f"span_{i+10}")
            asyncio.run(scrubber.extract_and_save(turn_id, msg, chunks, span_id=f"span_{i+10}"))
        
        # Fuzzy search for "Memory"
        results = scrubber.query_facts(query="Memory")
        
        assert len(results) >= 1
        assert any("HMLR" in f.key for f in results)
    
    def test_get_facts_by_category(self, scrubber, chunk_engine):
        """Test: Retrieve all facts in a category"""
        messages = [
            "HMLR = Hierarchical Memory Lookup & Routing.",
            "RAG stands for Retrieval Augmented Generation."
        ]
        
        for i, msg in enumerate(messages):
            turn_id = f"turn_{i+20}"
            chunks = chunk_engine.chunk_turn(msg, turn_id, span_id=f"span_{i+20}")
            asyncio.run(scrubber.extract_and_save(turn_id, msg, chunks, span_id=f"span_{i+20}"))
        
        # Get all acronyms
        acronyms = scrubber.get_facts_by_category("Acronym")
        
        assert len(acronyms) >= 2
        keys = {f.key for f in acronyms}
        assert "HMLR" in keys
        assert "RAG" in keys


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_message(self, scrubber, chunk_engine):
        """Test: Handle empty message gracefully"""
        message = ""
        turn_id = "turn_030"
        
        chunks = chunk_engine.chunk_turn(message, turn_id, span_id="span_030")
        
        facts = asyncio.run(scrubber.extract_and_save(
            turn_id=turn_id,
            message_text=message,
            chunks=chunks,
            span_id="span_030"
        ))
        
        assert len(facts) == 0
    
    def test_no_chunks_provided(self, scrubber):
        """Test: Handle missing chunks (edge case)"""
        message = "HMLR = Hierarchical Memory Lookup & Routing."
        turn_id = "turn_031"
        
        # No chunks provided
        facts = asyncio.run(scrubber.extract_and_save(
            turn_id=turn_id,
            message_text=message,
            chunks=[],
            span_id="span_031"
        ))
        
        # Should still extract facts, just without chunk links
        assert len(facts) == 1
        assert facts[0].source_chunk_id is None
    
    def test_duplicate_key_handling(self, scrubber, chunk_engine):
        """Test: Allow duplicate keys (facts can evolve over time)"""
        import time
        
        # First definition
        message1 = "HMLR = Hierarchical Memory Lookup & Routing."
        chunks1 = chunk_engine.chunk_turn(message1, "turn_032", span_id="span_032")
        asyncio.run(scrubber.extract_and_save("turn_032", message1, chunks1, span_id="span_032"))
        
        # Small delay to ensure different timestamps
        time.sleep(0.01)
        
        # Updated definition (same key)
        message2 = "HMLR = Hierarchical Memory Layer & Routing."  # Slightly different
        chunks2 = chunk_engine.chunk_turn(message2, "turn_033", span_id="span_033")
        asyncio.run(scrubber.extract_and_save("turn_033", message2, chunks2, span_id="span_033"))
        
        # Query should return most recent (by created_at DESC)
        fact = scrubber.get_fact_by_key("HMLR")
        
        assert fact is not None
        assert "Layer" in fact.value  # Most recent definition


class TestPerformance:
    """Test performance targets."""
    
    def test_extraction_performance(self, scrubber, chunk_engine):
        """Test: Fact extraction should complete in <500ms"""
        import time
        
        message = "HMLR = Hierarchical Memory Lookup & Routing. " * 10  # Longer message
        turn_id = "turn_040"
        
        chunks = chunk_engine.chunk_turn(message, turn_id, span_id="span_040")
        
        start = time.time()
        asyncio.run(scrubber.extract_and_save(turn_id, message, chunks, span_id="span_040"))
        duration = time.time() - start
        
        # Heuristic extraction should be very fast (<100ms)
        assert duration < 0.5, f"Extraction took {duration:.3f}s (target: <0.5s)"
    
    def test_query_performance(self, scrubber, chunk_engine):
        """Test: Fact query should complete in <50ms"""
        import time
        
        # Create some facts
        for i in range(10):
            msg = f"FACT{i} = Test fact number {i}."
            chunks = chunk_engine.chunk_turn(msg, f"turn_{i+50}", span_id=f"span_{i+50}")
            asyncio.run(scrubber.extract_and_save(f"turn_{i+50}", msg, chunks, span_id=f"span_{i+50}"))
        
        # Query
        start = time.time()
        results = scrubber.query_facts("FACT5")
        duration = time.time() - start
        
        assert len(results) >= 1
        assert duration < 0.05, f"Query took {duration:.3f}s (target: <0.05s)"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
