-- Phase 11.5: Pre-Chunking Engine & Hybrid Search
-- Migration: Add chunks table with hierarchical structure and FTS5 indexing
-- Date: December 2, 2025

-- ============================================================================
-- TABLE: metadata (For migration tracking)
-- ============================================================================
CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- TABLE: chunks (Hierarchical chunk storage)
-- ============================================================================
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,              -- sent_YYYYMMDD_HHMMSS_uuid or para_YYYYMMDD_HHMMSS_uuid
    parent_chunk_id TEXT,                   -- Paragraph contains sentences, blocks contain paragraphs
    chunk_type TEXT NOT NULL,               -- 'sentence' | 'paragraph' | 'bridge_block'
    
    -- Text Storage (Dual representation for hybrid search)
    text_verbatim TEXT NOT NULL,            -- Original text (for embeddings, display)
    lexical_filters TEXT,                   -- JSON array of keywords (for hybrid search)
    
    -- Hierarchy Links
    span_id TEXT,                           -- Which conversation span
    turn_id TEXT,                           -- Which turn (for sentences/paragraphs)
    block_id TEXT,                          -- Which bridge block (if archived)
    
    -- Metadata
    created_at TEXT NOT NULL,               -- ISO-8601 timestamp
    token_count INTEGER DEFAULT 0,          -- Cached token count
    metadata TEXT,                          -- JSON blob for additional data
    
    -- Foreign Keys
    FOREIGN KEY (parent_chunk_id) REFERENCES chunks(chunk_id) ON DELETE CASCADE,
    FOREIGN KEY (span_id) REFERENCES spans(span_id) ON DELETE SET NULL
    -- Note: block_id FK will be added in Phase 11.1 when daily_ledger is created
);

-- ============================================================================
-- INDEXES: Performance optimization for chunk queries
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_chunks_type ON chunks(chunk_type);
CREATE INDEX IF NOT EXISTS idx_chunks_parent ON chunks(parent_chunk_id);
CREATE INDEX IF NOT EXISTS idx_chunks_span ON chunks(span_id);
CREATE INDEX IF NOT EXISTS idx_chunks_turn ON chunks(turn_id);
CREATE INDEX IF NOT EXISTS idx_chunks_block ON chunks(block_id);
CREATE INDEX IF NOT EXISTS idx_chunks_created ON chunks(created_at);

-- Composite index for common query pattern (span + type)
CREATE INDEX IF NOT EXISTS idx_chunks_span_type ON chunks(span_id, chunk_type);

-- ============================================================================
-- FTS5: Full-text search for lexical filters (keyword matching)
-- ============================================================================
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    chunk_id UNINDEXED,
    lexical_filters,
    tokenize = 'porter unicode61'  -- Porter stemming + Unicode support
);

-- Trigger: Sync FTS5 index on INSERT
CREATE TRIGGER IF NOT EXISTS chunks_fts_insert AFTER INSERT ON chunks
BEGIN
    INSERT INTO chunks_fts(rowid, chunk_id, lexical_filters)
    VALUES (new.rowid, new.chunk_id, new.lexical_filters);
END;

-- Trigger: Sync FTS5 index on UPDATE
CREATE TRIGGER IF NOT EXISTS chunks_fts_update AFTER UPDATE ON chunks
BEGIN
    UPDATE chunks_fts
    SET chunk_id = new.chunk_id,
        lexical_filters = new.lexical_filters
    WHERE rowid = new.rowid;
END;

-- Trigger: Sync FTS5 index on DELETE
CREATE TRIGGER IF NOT EXISTS chunks_fts_delete AFTER DELETE ON chunks
BEGIN
    DELETE FROM chunks_fts WHERE rowid = old.rowid;
END;

-- ============================================================================
-- TABLE: fact_store (Enhanced with chunk linking)
-- ============================================================================
-- Create fact_store table if it doesn't exist (Phase 11 prerequisite)
CREATE TABLE IF NOT EXISTS fact_store (
    fact_id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL,                   -- "HMLR", "API_KEY", "user_name"
    value TEXT NOT NULL,                 -- The fact itself
    category TEXT,                       -- Definition, Acronym, Secret, Entity
    source_span_id TEXT,                 -- Provenance (which conversation)
    created_at TEXT NOT NULL,
    FOREIGN KEY (source_span_id) REFERENCES spans(span_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_fact_key ON fact_store(key);

-- Add new columns to existing fact_store table for precise chunk linking
-- Use ALTER TABLE IF NOT EXISTS pattern (SQLite 3.35+) or check first
-- For compatibility, we'll use a safer approach with BEGIN/END
BEGIN;

-- Check if columns exist before adding (prevents duplicate column errors)
-- SQLite doesn't have IF NOT EXISTS for ALTER TABLE ADD COLUMN in older versions
-- We'll attempt and ignore errors (handled by migration runner)

ALTER TABLE fact_store ADD COLUMN source_chunk_id TEXT;
ALTER TABLE fact_store ADD COLUMN source_paragraph_id TEXT;
ALTER TABLE fact_store ADD COLUMN source_block_id TEXT;
ALTER TABLE fact_store ADD COLUMN evidence_snippet TEXT;

COMMIT;

-- Index for chunk lookups (create if fact_store exists)
CREATE INDEX IF NOT EXISTS idx_fact_chunk ON fact_store(source_chunk_id);
CREATE INDEX IF NOT EXISTS idx_fact_paragraph ON fact_store(source_paragraph_id);
CREATE INDEX IF NOT EXISTS idx_fact_block ON fact_store(source_block_id);

-- ============================================================================
-- TABLE: embeddings (Add chunk_id reference)
-- ============================================================================
-- Create embeddings table if it doesn't exist
CREATE TABLE IF NOT EXISTS embeddings (
    embedding_id INTEGER PRIMARY KEY AUTOINCREMENT,
    turn_id TEXT,
    embedding BLOB,
    created_at TEXT NOT NULL
);

-- Link embeddings to chunks instead of raw turns
BEGIN;
ALTER TABLE embeddings ADD COLUMN chunk_id TEXT;
COMMIT;

CREATE INDEX IF NOT EXISTS idx_embeddings_chunk ON embeddings(chunk_id);

-- ============================================================================
-- MIGRATION METADATA
-- ============================================================================
INSERT INTO metadata (key, value, updated_at)
VALUES ('migration_phase_11_5', 'complete', datetime('now'))
ON CONFLICT(key) DO UPDATE SET value = 'complete', updated_at = datetime('now');

-- Log migration completion
INSERT INTO metadata (key, value, updated_at)
VALUES ('last_migration', 'phase_11_5_chunks', datetime('now'))
ON CONFLICT(key) DO UPDATE SET value = 'phase_11_5_chunks', updated_at = datetime('now');
