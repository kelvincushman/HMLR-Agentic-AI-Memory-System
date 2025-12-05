# 🧠 Long-Horizon Memory System

## Overview

The Long-Horizon Memory System provides persistent, day-based memory for CognitiveLattice with smart retrieval, task tracking, and lineage-based context management.

**Core Modules:**
- `models.py` - Data models (DayNode, TaskState, ConversationTurn, etc.)
- `storage.py` - SQLite persistence layer
- `id_generator.py` - Unique ID generation with lineage tracking
- `metadata_extractor.py` - LLM response parser
- `conversation_manager.py` - Turn logging
- `retrieval/` - Context retrieval system (crawler, intent analyzer)

## 📚 Documentation

**All detailed documentation has been moved to `docs/` folder:**

- **[docs/INTEGRATION_GUIDE.md](docs/INTEGRATION_GUIDE.md)** - How to integrate into main.py
- **[docs/QUICK_REFERENCE.md](docs/QUICK_REFERENCE.md)** - API quick reference
- **[docs/LINEAGE_PROGRESS_REPORT.md](docs/LINEAGE_PROGRESS_REPORT.md)** - Current implementation status
- **[docs/STORAGE_DOCUMENTATION.md](docs/STORAGE_DOCUMENTATION.md)** - Database schema details
- **[docs/README.md](docs/README.md)** - Full documentation index

## Quick Start

```python
from memory import (
    DayNode, 
    TaskState, 
    TaskType, 
    TaskStatus,
    Intent,
    QueryType,
    create_day_id,
    create_task_id
)
from datetime import datetime

# Create a day node
today = create_day_id()  # "2025-10-10"
day_node = DayNode(
    day_id=today,
    created_at=datetime.now(),
    session_ids=["session_20251010_120000"]
)

# Create a task
task = TaskState(
    task_id=create_task_id(TaskType.RECURRING_PLAN),
    task_type=TaskType.RECURRING_PLAN,
    status=TaskStatus.ACTIVE,
    created_date=today,
    created_at=datetime.now(),
    last_updated=datetime.now(),
    task_title="30-day rowing challenge",
    total_steps=30
)
```

## Core Data Structures

### DayNode
Represents one calendar day in the temporal lattice. Days are linked together like a doubly-linked list.

**Key Fields:**
- `day_id`: Date string in YYYY-MM-DD format
- `prev_day` / `next_day`: Links to adjacent days
- `session_ids`: Which sessions occurred this day
- `keywords`: Topics discussed this day
- `synthesis`: End-of-day summary (optional)

**Example:**
```python
day = DayNode(
    day_id="2025-10-10",
    created_at=datetime.now(),
    prev_day="2025-10-09",
    session_ids=["session_20251010_120000"]
)
```

### TaskState
Persistent task state that survives across sessions.

**Key Fields:**
- `task_id`: Unique identifier
- `task_type`: DISCRETE, RECURRING_PLAN, or ONGOING_COMMITMENT
- `status`: ACTIVE, PAUSED, COMPLETED, or CANCELLED
- `total_steps` / `completed_steps`: Progress tracking
- `state_json`: Task-specific state data

**Example:**
```python
task = TaskState(
    task_id=create_task_id(TaskType.RECURRING_PLAN),
    task_type=TaskType.RECURRING_PLAN,
    status=TaskStatus.ACTIVE,
    created_date="2025-10-10",
    created_at=datetime.now(),
    last_updated=datetime.now(),
    task_title="30-day rowing challenge",
    total_steps=30,
    completed_steps=7
)

# Check progress
progress = task.progress_percentage()  # 23.3%
```

### Keyword
Tracks when and how often topics were discussed.

**Key Fields:**
- `keyword`: The topic/term
- `first_mentioned` / `last_mentioned`: Time range
- `frequency`: How many times mentioned
- `turn_ids`: Which conversation turns

**Example:**
```python
keyword = Keyword(
    keyword="rowing",
    first_mentioned=datetime.now(),
    last_mentioned=datetime.now(),
    frequency=5,
    turn_ids=[1, 3, 7, 12, 15]
)

# Update when mentioned again
keyword.increment(turn_id=20)
```

### Intent
Analyzed user intent for driving retrieval.

**Key Fields:**
- `keywords`: Extracted key terms
- `query_type`: CHAT, TASK_REQUEST, TASK_UPDATE, or MEMORY_QUERY
- `confidence`: 0.0 to 1.0
- `primary_topics`: High-weight topics

**Example:**
```python
intent = Intent(
    keywords=["rowing", "progress", "check"],
    query_type=QueryType.TASK_UPDATE,
    confidence=0.85,
    primary_topics=["rowing"]
)
```

### RetrievedContext
Bundle of context retrieved from memory for LLM injection.

**Key Fields:**
- `contexts`: List of retrieved snippets
- `active_tasks`: Relevant tasks
- `sources`: Provenance tracking
- `total_tokens`: Estimated token count

**Example:**
```python
context = RetrievedContext()
context.add_context(
    {"date": "2025-10-03", "content": "Started rowing plan"},
    source="day_keyword"
)
context.active_tasks.append(task)
```

## Conversation Management

### ConversationTurn
Single turn in a conversation, stored temporarily before synthesis.

**Example:**
```python
turn = ConversationTurn(
    turn_id=1,
    session_id="session_20251010_120000",
    day_id="2025-10-10",
    timestamp=datetime.now(),
    user_message="How's my rowing going?",
    assistant_response="You're on day 7 of 30!",
    keywords=["rowing", "progress"],
    active_topics=["rowing"]
)
```

### SlidingWindow
Manages active conversation context and prevents redundant retrieval.

**Example:**
```python
window = SlidingWindow(max_turns=20)
window.add_turn(turn)

# Check if topic is already loaded
if window.is_topic_active("rowing"):
    print("Already have rowing context")
else:
    # Retrieve rowing context from memory
    window.mark_topic_active("rowing")
```

## Enums

### TaskType
- `DISCRETE`: One-time tasks
- `RECURRING_PLAN`: 30-day challenges, habits
- `ONGOING_COMMITMENT`: Open-ended goals

### TaskStatus
- `ACTIVE`: Currently in progress
- `PAUSED`: Temporarily stopped
- `COMPLETED`: Successfully finished
- `CANCELLED`: Abandoned

### QueryType
- `CHAT`: General conversation
- `TASK_REQUEST`: Create new task
- `TASK_UPDATE`: Update/check task
- `MEMORY_QUERY`: Ask about past context

## Utility Functions

### create_day_id(dt=None)
Generate day_id string in YYYY-MM-DD format.

```python
today = create_day_id()  # "2025-10-10"
yesterday = create_day_id(datetime.now() - timedelta(days=1))  # "2025-10-09"
```

### create_task_id(task_type, created_at=None)
Generate unique task ID.

```python
task_id = create_task_id(TaskType.RECURRING_PLAN)
# "recurring_plan_20251010_120530"
```

## Integration Points

These models are designed to integrate with:

1. **Storage Layer** (`memory/storage.py` - to be created)
   - Persist DayNodes, Tasks, Keywords to SQLite
   - Query by date ranges, keywords, task status

2. **Main Lattice** (`memory/main_lattice.py` - to be created)
   - Manage day node creation and linking
   - Handle temporal chain navigation

3. **Existing CognitiveLattice** (`core/cognitive_lattice.py`)
   - Extend current session management
   - Add persistence layer underneath

4. **Retrieval System** (`memory/retrieval/` - to be created)
   - Use Intent to drive searches
   - Return RetrievedContext for LLM injection

## Backward Compatibility

These models do NOT conflict with:
- `tools/web_automation/models.py` (different domain)
- Existing session JSON files (can be imported)
- Current `CognitiveLattice` class (extension, not replacement)

## Next Steps

After models are working:
1. Create `memory/storage.py` for database persistence
2. Create `memory/main_lattice.py` for day management
3. Integrate with existing `core/cognitive_lattice.py`
4. Build retrieval layer

## Testing

Run the built-in tests:
```bash
python memory/models.py
```

Expected output:
```
🧠 Memory Models Test
==================================================
✅ Created DayNode: 2025-10-10
✅ Created Keyword: rowing (frequency: 1)
✅ Created Task: 30-day rowing challenge
   Progress: 23.3% complete
✅ Created Intent: task_update (confidence: 0.85)
✅ Created RetrievedContext with 1 snippets

🎉 All models created successfully!
==================================================
```

## Questions?

These models form the foundation for the entire long-term memory system. They're designed to be:
- **Type-safe**: Using dataclasses and enums
- **Serializable**: Easy conversion to/from JSON and SQL
- **Extensible**: Add new fields without breaking existing code
- **Clean**: Separate from web automation models

For more details, see `Long_Horizon_Memory_System_Roadmap.md`.
