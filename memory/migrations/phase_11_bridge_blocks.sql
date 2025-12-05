-- Phase 11: Bridge Block System - Database Schema
-- Creates tables for Daily Ledger and Fact Store
-- Run this migration after Phase 10 (Observability)

-- ============================================================================
-- Table: daily_ledger
-- Purpose: Staging area for Bridge Blocks (conversation save states)
-- Lifecycle: PENDING → LLM enrichment → Embedded → ARCHIVED
-- ============================================================================

CREATE TABLE IF NOT EXISTS daily_ledger (
    block_id TEXT PRIMARY KEY,              -- Format: bb_YYYYMMDD_HHMM_uuid
    prev_block_id TEXT,                     -- Linked list pointer (for context chains)
    span_id TEXT NOT NULL,                  -- Foreign key to spans table
    content_json TEXT NOT NULL,             -- Full Bridge Block JSON (see schema below)
    created_at TEXT NOT NULL,               -- ISO-8601 timestamp (e.g., 2025-12-01T14:30:00Z)
    status TEXT DEFAULT 'PAUSED',           -- ACTIVE | PAUSED | ARCHIVED | PARTIAL
    exit_reason TEXT,                       -- topic_shift | volume_threshold | user_quit
    embedding_status TEXT DEFAULT 'PENDING', -- PENDING | DONE
    
    FOREIGN KEY (span_id) REFERENCES spans(span_id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_ledger_status ON daily_ledger(embedding_status, status);
CREATE INDEX IF NOT EXISTS idx_ledger_created ON daily_ledger(created_at);
CREATE INDEX IF NOT EXISTS idx_ledger_span ON daily_ledger(span_id);

-- ============================================================================
-- Table: fact_store
-- Purpose: Exact-match retrieval for definitions, acronyms, secrets
-- Retrieval: Keyword lookup (10x faster than vector search)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fact_store (
    fact_id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL,                      -- Lookup key (e.g., "HMLR", "user_api_key")
    value TEXT NOT NULL,                    -- The fact itself (e.g., "Hierarchical Memory...")
    category TEXT,                          -- Definition | Acronym | Secret | Entity | Relationship
    source_span_id TEXT,                    -- Provenance: which conversation defined this fact
    created_at TEXT NOT NULL,               -- ISO-8601 timestamp
    
    FOREIGN KEY (source_span_id) REFERENCES spans(span_id) ON DELETE SET NULL
);

-- Indexes for fast keyword lookup
CREATE INDEX IF NOT EXISTS idx_fact_key ON fact_store(key);
CREATE INDEX IF NOT EXISTS idx_fact_category ON fact_store(category);
CREATE INDEX IF NOT EXISTS idx_fact_source ON fact_store(source_span_id);

-- ============================================================================
-- Table: memories (Extension - Add metadata column if not exists)
-- Purpose: Long-term vector storage with rich metadata from Gardener
-- Note: This table may already exist from earlier phases
-- ============================================================================

-- Check if metadata_json column exists, add if not
-- SQLite doesn't support ALTER TABLE IF NOT EXISTS, so we use a workaround
CREATE TABLE IF NOT EXISTS memories (
    memory_id INTEGER PRIMARY KEY AUTOINCREMENT,
    text_content TEXT NOT NULL,
    embedding BLOB NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT  -- NEW: Stores enriched metadata from Manual Gardener
);

-- Add metadata column if it doesn't exist (safe to run multiple times)
-- This is a no-op if column already exists
CREATE TABLE IF NOT EXISTS memories_temp (
    memory_id INTEGER PRIMARY KEY AUTOINCREMENT,
    text_content TEXT NOT NULL,
    embedding BLOB NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

-- Migrate data if needed (only if metadata_json was missing)
INSERT OR IGNORE INTO memories_temp (memory_id, text_content, embedding, created_at, metadata_json)
SELECT memory_id, text_content, embedding, created_at, NULL FROM memories;

-- Drop old table and rename temp (idempotent)
DROP TABLE IF EXISTS memories;
ALTER TABLE memories_temp RENAME TO memories;

-- Index for date-based queries
CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at);

-- ============================================================================
-- CONTENT SCHEMA DOCUMENTATION
-- ============================================================================

-- Bridge Block JSON Schema (content_json field)
-- {
--   "block_id": "bb_20251201_1430_abc123",
--   "prev_block_id": "bb_20251201_1400_xyz789",
--   "span_id": "span_uuid_ref",
--   "timestamp": "2025-12-01T14:30:00Z",
--   
--   "status": "PAUSED",
--   "exit_reason": "topic_shift",
--   
--   "topic_label": "HMLR Architecture Design",
--   "summary": "User designed the separation of Governor and Lattice...",
--   
--   "user_affect": "[T2] Focused, Technical, Cautious about bloat",
--   "bot_persona": "Senior Architect, precise, reassuring",
--   
--   "open_loops": ["Implement Daily Ledger", "Test Phoenix"],
--   "decisions_made": ["Deferred Midnight Gardener to V2"],
--   "active_variables": { "current_project": "HMLR", "db_type": "SQLite" },
--   
--   "keywords": ["HMLR", "Governor", "Ledger", "BridgeBlock"]
-- }

-- Metadata JSON Schema (metadata_json field in memories table)
-- {
--   "entities": {
--     "people": ["Alice (PM)", "Bob (Engineer)"],
--     "projects": ["HMLR V1", "CognitiveLattice"],
--     "tools": ["SQLite", "Arize Phoenix", "Gemini Flash"]
--   },
--   "sentiment": {
--     "user_affect": "Focused and methodical",
--     "conversation_tone": "Technical architecture discussion",
--     "decision_mode": "Designing with V1 simplicity"
--   },
--   "technical_context": {
--     "activity": "System architecture design",
--     "complexity": "High - multi-tier memory system",
--     "domain": "AI memory management, RAG systems"
--   },
--   "tags": ["HMLR", "Governor", "Lattice", "Bridge Blocks"],
--   "open_loops": ["Implement Bridge Block generator"],
--   "decisions": ["Use SQLite not Pinecone"],
--   "source_blocks": ["bb_...", "bb_..."],
--   "source_spans": ["span_...", "span_..."]
-- }

-- ============================================================================
-- SAMPLE QUERIES
-- ============================================================================

-- Query 1: Load all pending blocks for Manual Gardener
-- SELECT * FROM daily_ledger WHERE embedding_status = 'PENDING' ORDER BY created_at;

-- Query 2: Check same-day topics (hot path retrieval)
-- SELECT content_json FROM daily_ledger 
-- WHERE DATE(created_at) = DATE('now') 
-- AND status = 'PAUSED';

-- Query 3: Fact lookup (exact match)
-- SELECT value FROM fact_store WHERE key = 'HMLR' LIMIT 1;

-- Query 4: Check archival status
-- SELECT status, embedding_status, COUNT(*) FROM daily_ledger 
-- GROUP BY status, embedding_status;

-- Query 5: Verify embeddings created today
-- SELECT COUNT(*) FROM memories WHERE DATE(created_at) = DATE('now');

-- ============================================================================
-- MIGRATION VERIFICATION
-- ============================================================================

-- Run these queries to verify migration success:

-- Should return: daily_ledger, fact_store, memories (plus existing tables)
SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;

-- Should return: idx_ledger_status, idx_ledger_created, idx_fact_key, etc.
SELECT name FROM sqlite_master WHERE type='index' ORDER BY name;

-- Should show all columns including metadata_json
PRAGMA table_info(memories);

-- Should be empty initially
SELECT COUNT(*) FROM daily_ledger;
SELECT COUNT(*) FROM fact_store;

-- ============================================================================
-- END OF MIGRATION
-- ============================================================================
