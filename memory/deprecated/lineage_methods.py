"""
DEPRECATED: Phase B Lineage-Based Storage Methods
Archived: December 3, 2025
Reason: Never implemented in production; zero external usage found

These methods were designed for Phase B lineage tracking but were never
integrated into the main conversation flow. Database tables remain for
data recovery if needed.

Database Tables (preserved):
- summaries
- keywords  
- affect

To restore these methods, copy back to storage.py and verify imports.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import sqlite3

# NOTE: These require imports from core.types:
# - Summary, Keyword, Affect, ConversationTurn
# - get_id_type() utility function


def save_summary(self, summary: 'Summary') -> None:
    """
    Save a summary with lineage tracking.
    
    Args:
        summary: Summary object with lineage fields
    """
    cursor = self.conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO summaries
        (summary_id, source_turn_id, day_id, timestamp,
         user_query_summary, assistant_response_summary, keywords_this_turn,
         derived_from, derived_by, extraction_method)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        summary.summary_id,
        summary.source_turn_id,
        summary.day_id,
        summary.timestamp,
        summary.user_query_summary,
        summary.assistant_response_summary,
        json.dumps(summary.keywords_this_turn),
        summary.derived_from,
        summary.derived_by,
        summary.extraction_method
    ))
    self.conn.commit()

def get_summary_by_id(self, summary_id: str) -> Optional['Summary']:
    """Get summary by its unique ID"""
    cursor = self.conn.cursor()
    cursor.execute("SELECT * FROM summaries WHERE summary_id = ?", (summary_id,))
    row = cursor.fetchone()
    
    if not row:
        return None
    
    return Summary(
        summary_id=row['summary_id'],
        source_turn_id=row['source_turn_id'],
        day_id=row['day_id'],
        timestamp=datetime.fromisoformat(row['timestamp']),
        user_query_summary=row['user_query_summary'],
        assistant_response_summary=row['assistant_response_summary'],
        keywords_this_turn=json.loads(row['keywords_this_turn']) if row['keywords_this_turn'] else [],
        derived_from=row['derived_from'],
        derived_by=row['derived_by'],
        extraction_method=row['extraction_method']
    )

def save_keyword(self, keyword: 'Keyword') -> None:
    """
    Save a keyword with lineage tracking.
    
    Args:
        keyword: Keyword object with lineage fields
    """
    cursor = self.conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO keywords
        (keyword_id, keyword, source_turn_id, day_id,
         first_mentioned, last_mentioned, frequency,
         derived_from, derived_by, confidence)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        keyword.keyword_id,
        keyword.keyword,
        keyword.source_turn_id,
        keyword.day_id,
        keyword.first_mentioned,
        keyword.last_mentioned,
        keyword.frequency,
        keyword.derived_from,
        keyword.derived_by,
        keyword.confidence
    ))
    self.conn.commit()

def get_keyword_by_id(self, keyword_id: str) -> Optional['Keyword']:
    """Get keyword by its unique ID"""
    cursor = self.conn.cursor()
    cursor.execute("SELECT * FROM keywords WHERE keyword_id = ?", (keyword_id,))
    row = cursor.fetchone()
    
    if not row:
        return None
    
    return Keyword(
        keyword_id=row['keyword_id'],
        keyword=row['keyword'],
        source_turn_id=row['source_turn_id'],
        day_id=row['day_id'],
        first_mentioned=datetime.fromisoformat(row['first_mentioned']),
        last_mentioned=datetime.fromisoformat(row['last_mentioned']),
        frequency=row['frequency'],
        derived_from=row['derived_from'],
        derived_by=row['derived_by'],
        confidence=row['confidence']
    )

def save_affect(self, affect: 'Affect') -> None:
    """
    Save an affect with lineage tracking.
    
    Args:
        affect: Affect object with lineage fields
    """
    cursor = self.conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO affect
        (affect_id, affect_label, source_turn_id, day_id,
         first_detected, last_detected, intensity, confidence,
         associated_topics, derived_from, derived_by, 
         detection_method, trigger_context)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        affect.affect_id,
        affect.affect_label,
        affect.source_turn_id,
        affect.day_id,
        affect.first_detected,
        affect.last_detected,
        affect.intensity,
        affect.confidence,
        json.dumps(affect.associated_topics),
        affect.derived_from,
        affect.derived_by,
        affect.detection_method,
        affect.trigger_context
    ))
    self.conn.commit()

def get_affect_by_id(self, affect_id: str) -> Optional['Affect']:
    """Get affect by its unique ID"""
    cursor = self.conn.cursor()
    cursor.execute("SELECT * FROM affect WHERE affect_id = ?", (affect_id,))
    row = cursor.fetchone()
    
    if not row:
        return None
    
    return Affect(
        affect_id=row['affect_id'],
        affect_label=row['affect_label'],
        source_turn_id=row['source_turn_id'],
        day_id=row['day_id'],
        first_detected=datetime.fromisoformat(row['first_detected']),
        last_detected=datetime.fromisoformat(row['last_detected']),
        intensity=row['intensity'],
        confidence=row['confidence'],
        associated_topics=json.loads(row['associated_topics']) if row['associated_topics'] else [],
        derived_from=row['derived_from'],
        derived_by=row['derived_by'],
        detection_method=row['detection_method'],
        trigger_context=row['trigger_context'] or ""
    )

def get_turn_by_id(self, turn_id: str) -> Optional['ConversationTurn']:
    """
    Get a turn by its unique string ID.
    
    NEW in Phase B: Supports string IDs like t_20251010_205509_6840db
    """
    cursor = self.conn.cursor()
    cursor.execute("SELECT * FROM metadata_staging WHERE turn_id = ?", (turn_id,))
    row = cursor.fetchone()
    
    if not row:
        return None
    
    return ConversationTurn(
        turn_id=row['turn_id'],
        turn_sequence=row['turn_sequence'],
        session_id=row['session_id'],
        day_id=row['day_id'],
        timestamp=datetime.fromisoformat(row['timestamp']),
        user_message=row['user_message'],
        assistant_response=row['assistant_response'],
        keywords=json.loads(row['keywords']) if row['keywords'] else [],
        detected_affect=json.loads(row['detected_affect']) if row['detected_affect'] else [],
        user_summary=row['user_summary'],
        assistant_summary=row['assistant_summary'],
        active_topics=json.loads(row['active_topics']) if row['active_topics'] else [],
        retrieval_sources=json.loads(row['retrieval_sources']) if row['retrieval_sources'] else [],
        summary_id=row['summary_id'],
        keyword_ids=json.loads(row['keyword_ids']) if row['keyword_ids'] else [],
        affect_ids=json.loads(row['affect_ids']) if row['affect_ids'] else [],
        task_created_id=row['task_created_id'],
        task_updated_ids=json.loads(row['task_updated_ids']) if row['task_updated_ids'] else [],
        loaded_turn_ids=json.loads(row['loaded_turn_ids']) if row['loaded_turn_ids'] else [],
        span_id=row['span_id'] if row['span_id'] else None  # HMLR v1
    )

def get_recent_turns(self, day_id: str = None, limit: int = 20) -> List['ConversationTurn']:
    """
    Get the most recent turns for sliding window.
    
    Args:
        day_id: Optional day ID to filter by. If None, gets recent turns from all days.
        limit: Maximum number of turns to retrieve
        
    Returns:
        List of ConversationTurn objects (oldest first, for proper window order)
    """
    cursor = self.conn.cursor()
    
    if day_id:
        # Filter by specific day
        cursor.execute("""
            SELECT * FROM metadata_staging 
            WHERE day_id = ?
            ORDER BY timestamp ASC
            LIMIT ?
        """, (day_id, limit))
    else:
        # Get recent turns from all days (most recent N)
        cursor.execute("""
            SELECT * FROM metadata_staging 
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
        
        # Reverse to get chronological order (oldest first)
        rows = cursor.fetchall()
        rows.reverse()
    
    if day_id:
        rows = cursor.fetchall()
    
    turns = []
    for row in rows:
        turns.append(ConversationTurn(
            turn_id=row['turn_id'],
            turn_sequence=row['turn_sequence'],
            session_id=row['session_id'],
            day_id=row['day_id'],
            timestamp=datetime.fromisoformat(row['timestamp']),
            user_message=row['user_message'],
            assistant_response=row['assistant_response'],
            keywords=json.loads(row['keywords']) if row['keywords'] else [],
            detected_affect=json.loads(row['detected_affect']) if row['detected_affect'] else [],
            user_summary=row['user_summary'],
            assistant_summary=row['assistant_summary'],
            active_topics=json.loads(row['active_topics']) if row['active_topics'] else [],
            retrieval_sources=json.loads(row['retrieval_sources']) if row['retrieval_sources'] else [],
            summary_id=row['summary_id'],
            keyword_ids=json.loads(row['keyword_ids']) if row['keyword_ids'] else [],
            affect_ids=json.loads(row['affect_ids']) if row['affect_ids'] else [],
            task_created_id=row['task_created_id'],
            task_updated_ids=json.loads(row['task_updated_ids']) if row['task_updated_ids'] else [],
            loaded_turn_ids=json.loads(row['loaded_turn_ids']) if row['loaded_turn_ids'] else []
        ))
    
    return turns

def get_turns_by_span(self, span_id: str) -> List['ConversationTurn']:
    """
    Get all turns that belong to a specific span.
    
    Args:
        span_id: The span ID to filter by
        
    Returns:
        List of ConversationTurn objects in chronological order
    """
    cursor = self.conn.cursor()
    cursor.execute("""
        SELECT * FROM metadata_staging 
        WHERE span_id = ?
        ORDER BY timestamp ASC
    """, (span_id,))
    
    rows = cursor.fetchall()
    turns = []
    
    for row in rows:
        turns.append(ConversationTurn(
            turn_id=row['turn_id'],
            turn_sequence=row['turn_sequence'],
            session_id=row['session_id'],
            day_id=row['day_id'],
            timestamp=datetime.fromisoformat(row['timestamp']),
            user_message=row['user_message'],
            assistant_response=row['assistant_response'],
            keywords=json.loads(row['keywords']) if row['keywords'] else [],
            detected_affect=json.loads(row['detected_affect']) if row['detected_affect'] else [],
            user_summary=row['user_summary'],
            assistant_summary=row['assistant_summary'],
            active_topics=json.loads(row['active_topics']) if row['active_topics'] else [],
            retrieval_sources=json.loads(row['retrieval_sources']) if row['retrieval_sources'] else [],
            summary_id=row['summary_id'],
            keyword_ids=json.loads(row['keyword_ids']) if row['keyword_ids'] else [],
            affect_ids=json.loads(row['affect_ids']) if row['affect_ids'] else [],
            task_created_id=row['task_created_id'],
            task_updated_ids=json.loads(row['task_updated_ids']) if row['task_updated_ids'] else [],
            loaded_turn_ids=json.loads(row['loaded_turn_ids']) if row['loaded_turn_ids'] else [],
            span_id=row['span_id'] if row['span_id'] else None
        ))
    
    return turns

def get_lineage_chain(self, item_id: str) -> List[Dict[str, Any]]:
    """
    Get complete lineage chain for an item.
    
    Args:
        item_id: Any ID (turn, summary, keyword, affect)
        
    Returns:
        List of dicts with lineage information
    """
    chain = []
    id_type = get_id_type(item_id)
    
    if id_type == 'summary':
        summary = self.get_summary_by_id(item_id)
        if summary:
            chain.append({
                'type': 'summary',
                'id': summary.summary_id,
                'derived_from': summary.derived_from,
                'derived_by': summary.derived_by
            })
            # Get parent turn
            turn = self.get_turn_by_id(summary.source_turn_id)
            if turn:
                chain.append({
                    'type': 'turn',
                    'id': turn.turn_id,
                    'day_id': turn.day_id
                })
    
    elif id_type == 'keyword':
        keyword = self.get_keyword_by_id(item_id)
        if keyword:
            chain.append({
                'type': 'keyword',
                'id': keyword.keyword_id,
                'keyword': keyword.keyword,
                'derived_from': keyword.derived_from,
                'derived_by': keyword.derived_by
            })
            # Get parent turn
            turn = self.get_turn_by_id(keyword.source_turn_id)
            if turn:
                chain.append({
                    'type': 'turn',
                    'id': turn.turn_id,
                    'day_id': turn.day_id
                })
    
    elif id_type == 'affect':
        affect = self.get_affect_by_id(item_id)
        if affect:
            chain.append({
                'type': 'affect',
                'id': affect.affect_id,
                'label': affect.affect_label,
                'derived_from': affect.derived_from,
                'derived_by': affect.derived_by
            })
            # Get parent turn
            turn = self.get_turn_by_id(affect.source_turn_id)
            if turn:
                chain.append({
                    'type': 'turn',
                    'id': turn.turn_id,
                    'day_id': turn.day_id
                })
    
    elif id_type == 'turn':
        turn = self.get_turn_by_id(item_id)
        if turn:
            chain.append({
                'type': 'turn',
                'id': turn.turn_id,
                'day_id': turn.day_id
            })
    
    return chain
