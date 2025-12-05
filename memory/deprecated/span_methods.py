"""
DEPRECATED: HMLR v1 Span Management Methods
Archived: December 3, 2025
Reason: Bridge Blocks (Phase 11) replaced Spans for topic tracking

Spans were part of HMLR v1 but are now deprecated in favor of Bridge Blocks.
The Bridge Block system provides better state preservation and cross-day continuity.

Status:
- Used only in test files and deprecated tabula_rasa.py
- Database tables preserved for data recovery
- Phase 11.4 marked as DEPRECATED in roadmap

Database Tables (preserved):
- spans
- hierarchical_summaries

To restore these methods, copy back to storage.py and verify imports.
"""

from typing import Optional
from datetime import datetime
import json
import sqlite3

# NOTE: These require imports from core.types:
# - Span, HierarchicalSummary


def create_span(self, span: 'Span') -> None:
    """Create a new span in the database."""
    cursor = self.conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO spans (
            span_id, day_id, created_at, last_active_at, topic_label,
            is_active, summary_id, parent_span_id, turn_ids_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        span.span_id,
        span.day_id,
        span.created_at.isoformat(),
        span.last_active_at.isoformat(),
        span.topic_label,
        1 if span.is_active else 0,
        span.summary_id,
        span.parent_span_id,
        json.dumps(span.turn_ids)
    ))
    self.conn.commit()

def get_span(self, span_id: str) -> Optional['Span']:
    """Retrieve a span by ID."""
    cursor = self.conn.cursor()
    row = cursor.execute("SELECT * FROM spans WHERE span_id = ?", (span_id,)).fetchone()
    if not row:
        return None
    
    return Span(
        span_id=row['span_id'],
        day_id=row['day_id'],
        created_at=datetime.fromisoformat(row['created_at']),
        last_active_at=datetime.fromisoformat(row['last_active_at']),
        topic_label=row['topic_label'],
        is_active=bool(row['is_active']),
        summary_id=row['summary_id'],
        parent_span_id=row['parent_span_id'],
        turn_ids=json.loads(row['turn_ids_json']) if row['turn_ids_json'] else []
    )

def update_span(self, span: 'Span') -> None:
    """Update an existing span."""
    self.create_span(span)  # INSERT OR REPLACE handles updates

def get_active_span(self) -> Optional['Span']:
    """Get the currently active span (if any)."""
    cursor = self.conn.cursor()
    row = cursor.execute("SELECT * FROM spans WHERE is_active = 1 ORDER BY last_active_at DESC LIMIT 1").fetchone()
    if not row:
        return None
    return self.get_span(row['span_id'])

def close_span(self, span_id: str) -> None:
    """Mark a span as inactive."""
    cursor = self.conn.cursor()
    cursor.execute("UPDATE spans SET is_active = 0 WHERE span_id = ?", (span_id,))
    self.conn.commit()

def create_hierarchical_summary(self, summary: 'HierarchicalSummary') -> None:
    """Create a new hierarchical summary."""
    cursor = self.conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO hierarchical_summaries (
            summary_id, created_at, content, embedding_json, level,
            topics_json, span_ids_json, child_summary_ids_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        summary.summary_id,
        summary.created_at.isoformat(),
        summary.content,
        json.dumps(summary.embedding) if summary.embedding else None,
        summary.level,
        json.dumps(summary.topics),
        json.dumps(summary.span_ids),
        json.dumps(summary.child_summary_ids)
    ))
    self.conn.commit()

def get_hierarchical_summary(self, summary_id: str) -> Optional['HierarchicalSummary']:
    """Retrieve a hierarchical summary by ID."""
    cursor = self.conn.cursor()
    row = cursor.execute("SELECT * FROM hierarchical_summaries WHERE summary_id = ?", (summary_id,)).fetchone()
    if not row:
        return None
    
    return HierarchicalSummary(
        summary_id=row['summary_id'],
        created_at=datetime.fromisoformat(row['created_at']),
        content=row['content'],
        embedding=json.loads(row['embedding_json']) if row['embedding_json'] else None,
        level=row['level'],
        topics=json.loads(row['topics_json']) if row['topics_json'] else [],
        span_ids=json.loads(row['span_ids_json']) if row['span_ids_json'] else [],
        child_summary_ids=json.loads(row['child_summary_ids_json']) if row['child_summary_ids_json'] else []
    )
