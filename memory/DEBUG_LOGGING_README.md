# Memory System Debug Logging

## Overview

The memory system now includes comprehensive debug logging that captures every step of the context retrieval and prompt building process. This is similar to the web automation debug logs but focused on the memory/RAG system.

## What Gets Logged

For each conversation turn, the following files are created in `memory/debug_logs/`:

### 1. `00_turn_summary_*.json`
High-level overview of the entire turn in JSON format:
- User query and intent analysis results
- Retrieval statistics (method used, contexts found, sources)
- Prompt and response metrics

### 2. `01_user_query_*.txt`
User's input query and analyzed intent:
- Raw user query
- Intent type (CHAT, MEMORY_QUERY, TASK_REQUEST)
- Confidence score
- Extracted keywords
- Primary topics
- Raw query (for vector search)
- Time range filter (if any)

### 3. `02_retrieved_context_*.txt`
What was retrieved from memory:
- Search method used (vector/keyword/both)
- Each retrieved context snippet with:
  - Relevance/similarity score
  - Turn ID, day, timestamp
  - Full text content
- Sources (which days/tasks were queried)
- Total estimated tokens

### 4. `03_sliding_window_*.txt`
Current sliding window contents:
- Number of turns in window
- Each turn's full content:
  - Turn ID, sequence number, timestamp
  - User message
  - Assistant response
  - Keywords and summary

### 5. `04_llm_prompt_*.txt`
Complete prompt sent to the LLM:
- Context summary (turns, contexts, tokens)
- Full assembled prompt including:
  - System instructions
  - Recent conversation history
  - Retrieved context snippets
  - Current user query

### 6. `05_llm_response_*.txt`
LLM's response:
- Response metadata (length, timestamp)
- Full response text

## File Naming Convention

Files are named with a timestamp: `XX_description_YYYYMMDD_HHMMSS_mmm.ext`

Example: `01_user_query_20251015_143821_931.txt`

- Date: October 15, 2025
- Time: 14:38:21.931
- This groups all 6 files from the same turn together

## Example Output

### User Query File
```
================================================================================
USER QUERY AND INTENT ANALYSIS
================================================================================
Timestamp: 2025-10-15 14:38:21
Turn ID: test_turn_123
================================================================================

USER QUERY:
--------------------------------------------------------------------------------
Tell me about the solar eclipse we discussed last week

INTENT ANALYSIS:
--------------------------------------------------------------------------------
Query Type: memory_query
Confidence: 0.85
Keywords: solar, eclipse, discussed, week
Primary Topics: astronomy, solar eclipse
Raw Query (for vector search): Tell me about the solar eclipse we discussed last week
Time Range: last week to today
```

### Retrieved Context File
```
================================================================================
RETRIEVED CONTEXT (What Was Hydrated)
================================================================================
Search Method: vector
================================================================================

RETRIEVED 2 CONTEXT SNIPPET(S):
--------------------------------------------------------------------------------

--- Snippet 1 ---
Relevance Score: 0.856
Turn ID: turn_123
Day: 2025-10-08

Text:
User: Tell me about the Solar Eclipse that happened last week
A: The solar eclipse last week was an annular eclipse...
```

## Use Cases

### 1. **Debugging Retrieval Issues**
- Check if the right contexts were retrieved
- Verify similarity scores are reasonable
- See if vector vs keyword search was used

### 2. **Understanding Context Hydration**
- See exactly what went into the prompt
- Verify sliding window contents
- Check token budget usage

### 3. **Prompt Engineering**
- Review the exact prompt structure
- Optimize system instructions
- Adjust context formatting

### 4. **Response Analysis**
- Compare prompt to response
- Identify hallucinations vs grounded responses
- Verify context was actually used

### 5. **Performance Monitoring**
- Track retrieval effectiveness over time
- Monitor prompt sizes
- Analyze search method effectiveness

## Automatic Cleanup

Old debug logs are automatically cleaned up to prevent disk bloat. By default, the system keeps the most recent 50 conversation turns and deletes older ones.

To manually clean up:
```python
from memory.debug_logger import MemoryDebugLogger
logger = MemoryDebugLogger()
logger.cleanup_old_logs(keep_last_n=50)  # Keep last 50 turns
```

## Integration

The debug logger is automatically initialized in `main.py` and logs every chat interaction. No additional configuration needed!

The logger is active whenever you run:
```bash
python main.py
```

## Disabling Debug Logging

If you want to disable debug logging (for production or performance), you can:

1. **Option 1**: Comment out debug logger initialization in `main.py`
2. **Option 2**: Set an environment variable:
   ```python
   os.environ['DISABLE_MEMORY_DEBUG'] = '1'
   ```

## Comparing to Web Automation Logs

Similar to the web automation debug logs (`debug_runs/`), these memory logs:

- ✅ Show the complete input/output flow
- ✅ Include intermediate processing steps
- ✅ Use timestamped filenames for easy correlation
- ✅ Separate concerns into different files
- ✅ Include summary metadata

But focused on:

- 🧠 Memory retrieval instead of DOM navigation
- 🔍 Vector/keyword search instead of element selection
- 💬 Context hydration instead of page observation
- 📝 Prompt building instead of action planning

## File Structure

```
memory/
├── debug_logs/
│   ├── 00_turn_summary_20251015_143821_931.json
│   ├── 01_user_query_20251015_143821_931.txt
│   ├── 02_retrieved_context_20251015_143821_931.txt
│   ├── 03_sliding_window_20251015_143821_931.txt
│   ├── 04_llm_prompt_20251015_143821_931.txt
│   ├── 05_llm_response_20251015_143821_931.txt
│   └── ... (50 most recent turns kept)
├── debug_logger.py          # Logger implementation
└── ... (other memory modules)
```

## Benefits

1. **Full Transparency**: See exactly what the system is doing at each step
2. **Easy Debugging**: Quickly identify where things go wrong
3. **Reproducibility**: Debug logs can be shared for troubleshooting
4. **Learning Tool**: Understand how RAG/memory retrieval works
5. **Quality Assurance**: Verify retrieval quality and prompt construction

---

**Implementation**: See `memory/debug_logger.py` for the complete implementation.

**Test**: Run `python test_debug_logger.py` to see example output.
