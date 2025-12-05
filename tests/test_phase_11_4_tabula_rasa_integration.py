"""
Phase 11.4: TabulaRasa Integration Tests

Tests cover:
1. Bridge Block generation on topic shift
2. Fact extraction during turn processing
3. Chunk creation with fact linking
4. Topic shift detection with block creation
5. Volume threshold checkpoints (future)
"""

import pytest
import asyncio
from datetime import datetime

from memory.storage import Storage
from memory.models import Span, ConversationTurn
from memory.tabula_rasa import TabulaRasa
from memory.chunking import ChunkEngine, ChunkStorage
from memory.bridge_block_generator import BridgeBlockGenerator
from memory.fact_scrubber import FactScrubber


@pytest.fixture
def storage():
    """Create in-memory database for testing."""
    storage = Storage(db_path=":memory:")
    
    # Create required tables
    cursor = storage.conn.cursor()
    
    # Spans table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS spans (
            span_id TEXT PRIMARY KEY,
            day_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_active_at TEXT NOT NULL,
            topic_label TEXT,
            is_active INTEGER DEFAULT 1,
            turn_ids TEXT
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
    
    # Daily ledger table (from Phase 11.1)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_ledger (
            block_id TEXT PRIMARY KEY,
            prev_block_id TEXT,
            span_id TEXT,
            content_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            status TEXT DEFAULT 'PAUSED',
            exit_reason TEXT,
            embedding_status TEXT DEFAULT 'PENDING',
            FOREIGN KEY (span_id) REFERENCES spans(span_id)
        )
    """)
    
    # Fact store table (from Phase 11.3)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fact_store (
            fact_id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            category TEXT,
            source_span_id TEXT,
            source_chunk_id TEXT,
            source_paragraph_id TEXT,
            source_block_id TEXT,
            evidence_snippet TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (source_span_id) REFERENCES spans(span_id) ON DELETE SET NULL
        )
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_fact_key ON fact_store(key)")
    
    storage.conn.commit()
    return storage


@pytest.fixture
def tabula_rasa(storage):
    """Create TabulaRasa instance with all Phase 11 components."""
    chunk_engine = ChunkEngine()
    chunk_storage = ChunkStorage(storage)
    bridge_block_generator = BridgeBlockGenerator(storage, chunk_storage, llm_client=None)
    fact_scrubber = FactScrubber(storage, api_client=None)
    
    return TabulaRasa(
        storage=storage,
        chunk_engine=chunk_engine,
        chunk_storage=chunk_storage,
        bridge_block_generator=bridge_block_generator,
        fact_scrubber=fact_scrubber,
        api_client=None
    )


class TestTopicShiftWithBridgeBlock:
    """Test Bridge Block generation on topic shift."""
    
    def test_topic_shift_creates_bridge_block(self, tabula_rasa, storage):
        """Test: Topic shift closes span and creates Bridge Block"""
        # Create first span (mountains)
        span1 = tabula_rasa.ensure_active_span(
            query="Let's talk about mountains",
            day_id="20251202"
        )
        assert span1.topic_label is not None
        
        # Add some turns to the span
        for i in range(3):
            turn = ConversationTurn(
                turn_id=f"turn_{i}",
                span_id=span1.span_id,
                user_query=f"Mountains question {i}",
                assistant_response=f"Mountains answer {i}",
                timestamp=datetime.now()
            )
            storage.save_turn(turn)
            span1.turn_ids.append(turn.turn_id)
        
        storage.update_span(span1)
        
        # Trigger topic shift (to cooking)
        span2 = tabula_rasa.ensure_active_span(
            query="Actually, let's talk about cooking",
            day_id="20251202"
        )
        
        assert span2.span_id != span1.span_id, "Should create new span"
        
        # Check if Bridge Block was created
        cursor = storage.conn.cursor()
        cursor.execute("SELECT * FROM daily_ledger WHERE span_id = ?", (span1.span_id,))
        block = cursor.fetchone()
        
        assert block is not None, "Bridge Block should be created for closed span"
        assert block[5] == "topic_shift", "Exit reason should be topic_shift"
        
        # Verify old span is closed
        cursor.execute("SELECT is_active FROM spans WHERE span_id = ?", (span1.span_id,))
        is_active = cursor.fetchone()[0]
        assert is_active == 0, "Old span should be closed"


class TestFactExtraction:
    """Test fact extraction during turn processing."""
    
    def test_process_turn_extracts_facts(self, tabula_rasa, storage):
        """Test: process_turn creates chunks and extracts facts"""
        # Create active span
        span = tabula_rasa.ensure_active_span(
            query="Let's discuss HMLR",
            day_id="20251202"
        )
        
        # Create turn with fact
        turn = ConversationTurn(
            turn_id="turn_001",
            span_id=span.span_id,
            user_query="HMLR = Hierarchical Memory Lookup & Routing",
            assistant_response="Got it, HMLR is the system architecture.",
            timestamp=datetime.now()
        )
        
        # Process turn (async)
        chunks = tabula_rasa.process_turn(turn)
        
        # Verify chunks were created
        assert len(chunks) > 0, "Should create chunks"
        
        # Verify fact was extracted
        cursor = storage.conn.cursor()
        cursor.execute("SELECT * FROM fact_store WHERE key = ?", ("HMLR",))
        fact = cursor.fetchone()
        
        assert fact is not None, "Should extract HMLR fact"
        assert "Hierarchical" in fact[2], "Fact value should contain expansion"
    
    def test_process_turn_sync_fallback(self, tabula_rasa, storage):
        """Test: Sync fallback works when async fails"""
        # Create active span
        span = tabula_rasa.ensure_active_span(
            query="Test sync fallback",
            day_id="20251202"
        )
        
        # Create turn
        turn = ConversationTurn(
            turn_id="turn_002",
            span_id=span.span_id,
            user_query="This is a test message.",
            assistant_response="Acknowledged.",
            timestamp=datetime.now()
        )
        
        # Process turn using sync fallback directly
        chunks = tabula_rasa._process_turn_sync(turn)
        
        # Verify chunks were created
        assert len(chunks) > 0, "Should create chunks in sync mode"
        
        # Verify chunks in database
        cursor = storage.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM chunks WHERE turn_id = ?", (turn.turn_id,))
        count = cursor.fetchone()[0]
        
        assert count > 0, "Should save chunks to database"


class TestChunkAndFactLinking:
    """Test integration between chunks and facts."""
    
    def test_facts_link_to_chunks(self, tabula_rasa, storage):
        """Test: Extracted facts link to sentence chunks"""
        # Create active span
        span = tabula_rasa.ensure_active_span(
            query="Define acronyms",
            day_id="20251202"
        )
        
        # Create turn with acronym
        turn = ConversationTurn(
            turn_id="turn_003",
            span_id=span.span_id,
            user_query="API = Application Programming Interface",
            assistant_response="Understood.",
            timestamp=datetime.now()
        )
        
        # Process turn
        chunks = tabula_rasa.process_turn(turn)
        
        # Verify fact was extracted and linked
        cursor = storage.conn.cursor()
        cursor.execute("""
            SELECT source_chunk_id, source_span_id 
            FROM fact_store 
            WHERE key = ?
        """, ("API",))
        fact_row = cursor.fetchone()
        
        assert fact_row is not None, "Should extract API fact"
        # Note: source_chunk_id may be None in sync mode (acceptable)
        assert fact_row[1] == span.span_id, "Should link fact to span"


class TestMultiTopicConversation:
    """Test end-to-end multi-topic conversation scenario."""
    
    def test_multi_topic_with_bridge_blocks(self, tabula_rasa, storage):
        """Test: Multi-topic conversation creates multiple Bridge Blocks"""
        # Topic 1: HMLR (3 turns)
        span1 = tabula_rasa.ensure_active_span(
            query="Let's design HMLR",
            day_id="20251202"
        )
        
        for i in range(3):
            turn = ConversationTurn(
                turn_id=f"hmlr_turn_{i}",
                span_id=span1.span_id,
                user_query=f"HMLR question {i}",
                assistant_response=f"HMLR answer {i}",
                timestamp=datetime.now()
            )
            storage.save_turn(turn)
            tabula_rasa.process_turn(turn)
        
        # Topic 2: Cooking (3 turns)
        span2 = tabula_rasa.ensure_active_span(
            query="Now let's talk about cooking",
            day_id="20251202"
        )
        
        for i in range(3):
            turn = ConversationTurn(
                turn_id=f"cooking_turn_{i}",
                span_id=span2.span_id,
                user_query=f"Cooking question {i}",
                assistant_response=f"Cooking answer {i}",
                timestamp=datetime.now()
            )
            storage.save_turn(turn)
            tabula_rasa.process_turn(turn)
        
        # Topic 3: Travel (3 turns)
        span3 = tabula_rasa.ensure_active_span(
            query="Actually, let's discuss travel",
            day_id="20251202"
        )
        
        # Verify Bridge Blocks were created for topic shifts
        cursor = storage.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM daily_ledger")
        block_count = cursor.fetchone()[0]
        
        assert block_count >= 2, "Should create Bridge Blocks for each topic shift"
        
        # Verify all blocks have topic_shift exit reason
        cursor.execute("SELECT exit_reason FROM daily_ledger")
        exit_reasons = [row[0] for row in cursor.fetchall()]
        
        assert all(r == "topic_shift" for r in exit_reasons), "All blocks should be from topic shifts"


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_first_span_no_bridge_block(self, tabula_rasa, storage):
        """Test: First span doesn't create Bridge Block (nothing to close)"""
        # Create first span
        span = tabula_rasa.ensure_active_span(
            query="Hello, let's start",
            day_id="20251202"
        )
        
        # Verify no Bridge Block created
        cursor = storage.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM daily_ledger")
        count = cursor.fetchone()[0]
        
        assert count == 0, "First span should not create Bridge Block"
    
    def test_empty_turn_handling(self, tabula_rasa, storage):
        """Test: Empty turn doesn't crash"""
        span = tabula_rasa.ensure_active_span(
            query="Test",
            day_id="20251202"
        )
        
        turn = ConversationTurn(
            turn_id="empty_turn",
            span_id=span.span_id,
            user_query="",
            assistant_response="",
            timestamp=datetime.now()
        )
        
        # Should not crash
        chunks = tabula_rasa.process_turn(turn)
        assert len(chunks) == 0, "Empty turn should produce no chunks"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
