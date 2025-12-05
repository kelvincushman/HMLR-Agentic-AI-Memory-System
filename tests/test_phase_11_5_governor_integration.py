"""
Phase 11.5: Governor Integration Tests

Tests TheGovernor enhancements:
1. Fact Store lookup before vector search
2. Daily Ledger (same-day Bridge Blocks) hot path
3. Integration with existing LLM filtering

Author: CognitiveLattice Team
Created: December 2, 2025
"""

import pytest
import sqlite3
from datetime import datetime
from unittest.mock import Mock, MagicMock
from pathlib import Path
import json

from memory.retrieval.lattice import TheGovernor, MemoryCandidate
from memory.storage import Storage
from core.external_api_client import ExternalAPIClient


@pytest.fixture
def storage():
    """Create in-memory database with Phase 11 tables."""
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    
    # Spans table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS spans (
            span_id TEXT PRIMARY KEY,
            day_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            is_active INTEGER DEFAULT 1
        )
    """)
    
    # Daily ledger table
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
    
    # Fact store table
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
    
    conn.commit()
    
    # Create Storage instance with this connection
    storage = Storage(db_path=":memory:")
    storage.conn = conn  # Override with our test connection
    
    return storage


@pytest.fixture
def api_client():
    """Mock ExternalAPIClient for LLM calls."""
    client = Mock(spec=ExternalAPIClient)
    # Default response: approve all candidates
    client.query_external_api.return_value = '{"approved_indices": [0, 1, 2]}'
    return client


@pytest.fixture
def governor(api_client, storage):
    """Create TheGovernor instance with mocked API client."""
    return TheGovernor(api_client=api_client, storage=storage)


# =============================================================================
# Test Class 1: Fact Store Lookup
# =============================================================================

class TestFactStoreLookup:
    """Test Governor's fact_store exact-match retrieval."""
    
    def test_exact_fact_match_skips_llm(self, governor, storage):
        """Test: Exact fact match returns immediately without LLM call"""
        # Insert a fact into fact_store
        cursor = storage.conn.cursor()
        cursor.execute("""
            INSERT INTO fact_store (key, value, category, created_at)
            VALUES (?, ?, ?, ?)
        """, ("HMLR", "Hierarchical Memory Lookup & Routing", "Acronym", datetime.now().isoformat()))
        storage.conn.commit()
        
        # Query with the acronym
        result = governor.govern("What does HMLR stand for?", candidates=[])
        
        # Should return fact ID without calling LLM
        assert len(result) == 1
        assert result[0].startswith("fact_")
        governor.api_client.query_external_api.assert_not_called()
    
    def test_partial_fact_search(self, governor, storage):
        """Test: Partial keyword matching in fact_store"""
        cursor = storage.conn.cursor()
        cursor.execute("""
            INSERT INTO fact_store (key, value, category, created_at)
            VALUES (?, ?, ?, ?)
        """, ("API_KEY", "sk-1234567890abcdef", "Secret", datetime.now().isoformat()))
        storage.conn.commit()
        
        # Query with partial match
        result = governor.govern("What is the API key?", candidates=[])
        
        # Should find the fact
        assert len(result) >= 1
        assert result[0].startswith("fact_")
    
    def test_no_fact_match_proceeds_to_llm(self, governor, storage):
        """Test: No fact match proceeds to LLM filtering"""
        candidates = [
            MemoryCandidate("mem_1", "Some random memory", 0.8, "turn")
        ]
        
        result = governor.govern("Tell me about quantum physics", candidates=candidates)
        
        # Should call LLM since no facts found
        governor.api_client.query_external_api.assert_called_once()


# =============================================================================
# Test Class 2: Daily Ledger Hot Path
# =============================================================================

class TestDailyLedgerHotPath:
    """Test Governor's same-day Bridge Block retrieval."""
    
    def test_today_bridge_block_included(self, governor, storage):
        """Test: Bridge Blocks from today are included in candidates"""
        # Create a span
        cursor = storage.conn.cursor()
        cursor.execute("""
            INSERT INTO spans (span_id, day_id, session_id, created_at, is_active)
            VALUES (?, ?, ?, ?, ?)
        """, ("span_123", "20251202", "session_abc", datetime.now().isoformat(), 0))
        
        # Create a Bridge Block for today
        bridge_block = {
            "block_id": "bb_20251202_1430_xyz",
            "topic_label": "HMLR Architecture",
            "summary": "Discussed Governor and Lattice separation",
            "keywords": ["HMLR", "Governor", "Lattice"],
            "open_loops": ["Implement Phase 11.5"],
            "decisions_made": ["Use SQLite for V1"]
        }
        
        cursor.execute("""
            INSERT INTO daily_ledger (
                block_id, span_id, content_json, created_at, status, exit_reason
            ) VALUES (?, ?, ?, datetime('now'), ?, ?)
        """, ("bb_20251202_1430_xyz", "span_123", json.dumps(bridge_block), "PAUSED", "topic_shift"))
        storage.conn.commit()
        
        # Query about HMLR (should match keywords)
        governor.api_client.query_external_api.return_value = '{"approved_indices": [0]}'
        result = governor.govern("Tell me about HMLR", candidates=[])
        
        # Should include bridge block in LLM prompt
        governor.api_client.query_external_api.assert_called_once()
        call_args = governor.api_client.query_external_api.call_args[0][0]
        assert "BRIDGE BLOCK" in call_args
        assert "HMLR Architecture" in call_args
    
    def test_irrelevant_bridge_block_filtered(self, governor, storage):
        """Test: Bridge Blocks with irrelevant topics are filtered"""
        cursor = storage.conn.cursor()
        cursor.execute("""
            INSERT INTO spans (span_id, day_id, session_id, created_at, is_active)
            VALUES (?, ?, ?, ?, ?)
        """, ("span_456", "20251202", "session_def", datetime.now().isoformat(), 0))
        
        # Create irrelevant bridge block
        bridge_block = {
            "block_id": "bb_20251202_1500_abc",
            "topic_label": "Cooking Recipes",
            "summary": "Discussed pasta recipes",
            "keywords": ["pasta", "cooking", "Italian"],
            "open_loops": [],
            "decisions_made": []
        }
        
        cursor.execute("""
            INSERT INTO daily_ledger (
                block_id, span_id, content_json, created_at, status, exit_reason
            ) VALUES (?, ?, ?, datetime('now'), ?, ?)
        """, ("bb_20251202_1500_abc", "span_456", json.dumps(bridge_block), "PAUSED", "topic_shift"))
        storage.conn.commit()
        
        # Query about quantum physics (should NOT match cooking)
        governor.api_client.query_external_api.return_value = '{"approved_indices": []}'
        result = governor.govern("Explain quantum entanglement", candidates=[])
        
        # Result should be empty (no facts, no bridge blocks, no candidates)
        assert result == []
        # LLM should not be called when no candidates
        governor.api_client.query_external_api.assert_not_called()


# =============================================================================
# Test Class 3: Integration Tests
# =============================================================================

class TestGovernorIntegration:
    """Test Governor with all Phase 11.5 enhancements."""
    
    def test_priority_fact_then_ledger_then_vector(self, governor, storage):
        """Test: Correct priority - Facts > Ledger > Vector Search"""
        # Setup: Create fact and bridge block
        cursor = storage.conn.cursor()
        
        # Insert fact
        cursor.execute("""
            INSERT INTO fact_store (key, value, category, created_at)
            VALUES (?, ?, ?, ?)
        """, ("HMLR", "Hierarchical Memory", "Acronym", datetime.now().isoformat()))
        
        storage.conn.commit()
        
        # Query that matches fact
        candidates = [
            MemoryCandidate("mem_1", "Vector search result", 0.9, "turn")
        ]
        
        result = governor.govern("What is HMLR?", candidates=candidates)
        
        # Should return fact, NOT vector candidates
        assert len(result) == 1
        assert result[0].startswith("fact_")
        governor.api_client.query_external_api.assert_not_called()
    
    def test_multiple_facts_returned(self, governor, storage):
        """Test: Multiple fact matches returned"""
        cursor = storage.conn.cursor()
        
        # Insert multiple facts
        cursor.execute("""
            INSERT INTO fact_store (key, value, category, created_at)
            VALUES 
                (?, ?, ?, ?),
                (?, ?, ?, ?)
        """, (
            "HMLR", "Hierarchical Memory", "Acronym", datetime.now().isoformat(),
            "Governor", "Memory gatekeeper component", "Definition", datetime.now().isoformat()
        ))
        storage.conn.commit()
        
        # Query matching both
        result = governor.govern("What are HMLR and Governor?", candidates=[])
        
        # Should return both facts
        assert len(result) >= 2
        assert all(r.startswith("fact_") for r in result)
    
    def test_no_facts_no_ledger_uses_vector(self, governor, storage):
        """Test: Falls back to vector search when no facts/blocks"""
        candidates = [
            MemoryCandidate("mem_1", "Vector result 1", 0.9, "turn"),
            MemoryCandidate("mem_2", "Vector result 2", 0.8, "turn")
        ]
        
        governor.api_client.query_external_api.return_value = '{"approved_indices": [0, 1]}'
        result = governor.govern("Random query", candidates=candidates)
        
        # Should use LLM filtering
        governor.api_client.query_external_api.assert_called_once()
        assert len(result) == 2
        assert "mem_1" in result
        assert "mem_2" in result


# =============================================================================
# Test Class 4: Performance & Edge Cases
# =============================================================================

class TestGovernorEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_candidates_empty_facts(self, governor, storage):
        """Test: No candidates and no facts returns empty"""
        result = governor.govern("Test query", candidates=[])
        assert result == []
    
    def test_malformed_bridge_block_json(self, governor, storage):
        """Test: Malformed JSON in daily_ledger is handled gracefully"""
        cursor = storage.conn.cursor()
        cursor.execute("""
            INSERT INTO spans (span_id, day_id, session_id, created_at, is_active)
            VALUES (?, ?, ?, ?, ?)
        """, ("span_789", "20251202", "session_ghi", datetime.now().isoformat(), 0))
        
        # Insert invalid JSON
        cursor.execute("""
            INSERT INTO daily_ledger (
                block_id, span_id, content_json, created_at, status
            ) VALUES (?, ?, ?, datetime('now'), ?)
        """, ("bb_invalid", "span_789", "{{INVALID_JSON}}", "PAUSED"))
        storage.conn.commit()
        
        # Should not crash
        result = governor.govern("Test query", candidates=[])
        # Execution should complete without exception
    
    def test_bridge_block_formatting(self, governor):
        """Test: Bridge Block content is formatted correctly for LLM"""
        content = {
            "topic_label": "Test Topic",
            "summary": "A" * 250,  # Long summary
            "keywords": ["key1", "key2", "key3", "key4"],
            "open_loops": ["Loop 1", "Loop 2", "Loop 3", "Loop 4"],
            "decisions_made": ["Decision 1", "Decision 2", "Decision 3", "Decision 4"]
        }
        
        preview = governor._format_bridge_block(content)
        
        # Check formatting
        assert "[BRIDGE BLOCK]" in preview
        assert "Test Topic" in preview
        assert len(preview) < 500  # Should be truncated
        # Should show only first 3 loops/decisions
        assert "Loop 1" in preview
        assert "Loop 2" in preview
        assert "Loop 3" in preview


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
