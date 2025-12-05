# Deprecated Storage Methods

This directory contains storage methods that were removed from the main `storage.py` file during the December 2025 cleanup.

## Why These Were Removed

- **Zero external usage** - No production code calls these methods
- **Test-only usage** - Only test files and deprecated modules use them
- **Replaced by better systems** - Bridge Blocks replaced Spans, for example

## What's Here

### lineage_methods.py
**Phase B Lineage-Based Storage Operations**

Methods for lineage tracking that were designed but never integrated into production:
- `save_summary()`, `get_summary_by_id()`
- `save_keyword()`, `get_keyword_by_id()`
- `save_affect()`, `get_affect_by_id()`
- `get_turn_by_id()`, `get_recent_turns()`, `get_turns_by_span()`
- `get_lineage_chain()`

**Database Tables Preserved:**
- `summaries`
- `keywords`
- `affect`

### span_methods.py
**HMLR v1 Span Management**

Methods for the original Span system, replaced by Bridge Blocks in Phase 11:
- `create_span()`, `get_span()`, `update_span()`
- `get_active_span()`, `close_span()`
- `create_hierarchical_summary()`, `get_hierarchical_summary()`

**Database Tables Preserved:**
- `spans`
- `hierarchical_summaries`

**Replaced By:** Bridge Blocks (Phase 11)

## How to Restore

If you need these methods back:

1. Copy the method code from the appropriate file
2. Paste into `memory/storage.py` in the correct section
3. Verify imports are available (Summary, Keyword, Affect, Span, etc.)
4. Run tests to ensure compatibility

## Database Tables

All database tables remain intact. This means:
- ✅ No data loss
- ✅ Historical data preserved
- ✅ Can query tables directly if needed
- ✅ Can restore methods without data migration

## Documentation

See `docs/STORAGE_AUDIT_DEC_2025.md` for full analysis of what was removed and why.

See `docs/STORAGE_CLEANUP_COMPLETE.md` for summary of changes made.
