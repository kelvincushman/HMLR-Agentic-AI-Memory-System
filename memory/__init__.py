"""
Long-Horizon Memory System

A persistent, intelligent memory substrate for CognitiveLattice that enables:
- Day-based organization of conversation history
- Cross-session task state management
- Smart context retrieval for LLM injection
- Pattern recognition and synthesis

Author: CognitiveLattice Team
Created: 2025-10-10
"""

from .models import (
    # Enums
    TaskStatus,
    TaskType,
    QueryType,
    ContextSourceType,
    
    # Core structures
    DayNode,
    Keyword,
    Summary,
    Affect,
    DaySynthesis,
    
    # Task management
    TaskState,
    TaskCommand,
    
    # Retrieval & Intent
    Intent,
    RetrievedContext,
    
    # Conversation
    ConversationTurn,
    SlidingWindow,
    
    # Planning system
    UserPlan,
    PlanItem,
    PlanFeedback,
    PlanModification,
    
    # Utilities
    create_day_id,
    create_task_id,
)

from .storage import Storage
from .conversation_manager import ConversationManager

# NEW: ID generation with lineage tracking
from .id_generator import (
    generate_turn_id,
    generate_session_id,
    generate_summary_id,
    generate_keyword_id,
    generate_affect_id,
    generate_task_id,
    generate_day_id,
    generate_synthesis_id,
    generate_vector_id,
    parse_id,
    validate_id,
    get_id_type,
    extract_source_id,
    is_derived_from,
    format_id_for_display,
)

__version__ = "0.1.0"
__all__ = [
    # Enums
    "TaskStatus",
    "TaskType",
    "QueryType",
    "ContextSourceType",
    
    # Core structures
    "DayNode",
    "Keyword",
    "Summary",
    "Affect",
    "DaySynthesis",
    
    # Task management
    "TaskState",
    "TaskCommand",
    
    # Retrieval & Intent
    "Intent",
    "RetrievedContext",
    
    # Conversation
    "ConversationTurn",
    "SlidingWindow",
    
    # Planning system
    "UserPlan",
    "PlanItem",
    "PlanFeedback",
    "PlanModification",
    
    # Utilities
    "create_day_id",
    "create_task_id",
    
    # NEW: ID Generation
    "generate_turn_id",
    "generate_session_id",
    "generate_summary_id",
    "generate_keyword_id",
    "generate_affect_id",
    "generate_task_id",
    "generate_day_id",
    "generate_synthesis_id",
    "generate_vector_id",
    "parse_id",
    "validate_id",
    "get_id_type",
    "extract_source_id",
    "is_derived_from",
    "format_id_for_display",
    
    # Storage
    "Storage",
    "ConversationManager",
]
