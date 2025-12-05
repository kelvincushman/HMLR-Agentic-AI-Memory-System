"""
Memory System Debug Logger

Saves detailed snapshots of:
1. User query and intent analysis
2. Retrieved context (what was hydrated)
3. Sliding window contents
4. Full prompt sent to LLM
5. LLM response
6. Terminal output (all print statements during the turn)

Creates timestamped debug files in memory/debug_logs/

Usage:
    # Start a turn (begins capturing output)
    debug_logger.start_turn(turn_id="optional_id")
    
    # Your code with print statements...
    print("This will be captured!")
    
    # End the turn (stops capturing and saves output)
    debug_logger.end_turn()

Files generated per turn:
    - 00_terminal_output_*.txt: All print statements during this turn
    - 00_turn_summary_*.json: Summary metadata
    - 01_user_query_*.txt: User's input
    - 02_retrieved_context_*.txt: Retrieved context
    - 03_sliding_window_*.txt: Sliding window state
    - 04_llm_prompt_*.txt: Full prompt sent to LLM
    - 05_llm_response_*.txt: LLM's response
    - 06_metadata_extraction_*.txt: Metadata extraction details
"""

import os
import json
import sys
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path
from io import StringIO


class OutputCapture:
    """Context manager to capture print statements"""
    
    def __init__(self):
        self.captured_lines = []
        self.original_stdout = None
        self.string_io = None
    
    def __enter__(self):
        self.string_io = StringIO()
        self.original_stdout = sys.stdout
        sys.stdout = self
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout = self.original_stdout
        return False
    
    def write(self, text):
        """Capture output and also print to original stdout"""
        self.original_stdout.write(text)
        self.original_stdout.flush()
        self.captured_lines.append(text.rstrip())
    
    def flush(self):
        """Flush both outputs"""
        self.original_stdout.flush()
    
    def get_output(self) -> List[str]:
        """Get all captured lines"""
        return [line for line in self.captured_lines if line.strip()]


class MemoryDebugLogger:
    """Logs memory system operations for debugging and analysis"""
    
    def __init__(self, base_dir: str = "memory/debug_logs", enabled: bool = False):
        self.enabled = enabled
        if not self.enabled:
            return
            
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.current_turn_id = None
        self.current_timestamp = None
        self.output_capture = None
    
    def start_turn(self, turn_id: str = None):
        """Start logging a new conversation turn"""
        if not self.enabled:
            return
            
        self.current_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        if turn_id:
            self.current_turn_id = turn_id
        else:
            self.current_turn_id = f"turn_{self.current_timestamp}"
        
        # Start capturing output for this turn
        self.output_capture = OutputCapture()
        self.output_capture.__enter__()
    
    def end_turn(self):
        """End the current turn and save captured output"""
        if not self.enabled:
            return
            
        if self.output_capture:
            # Stop capturing
            self.output_capture.__exit__(None, None, None)
            
            # Save the captured output
            captured_lines = self.output_capture.get_output()
            if captured_lines:
                self.log_terminal_output(captured_lines)
            
            self.output_capture = None
    
    def _get_filename(self, prefix: str, extension: str = "txt") -> Path:
        """Generate a timestamped filename"""
        if not self.current_timestamp:
            self.start_turn()
        return self.base_dir / f"{prefix}_{self.current_timestamp}.{extension}"
    
    def log_user_query(self, query: str, intent: Any = None):
        """
        Log the user's query and analyzed intent
        
        Args:
            query: Raw user input
            intent: Intent object (if available)
        """
        if not self.enabled:
            return
            
        filepath = self._get_filename("01_user_query")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("USER QUERY AND INTENT ANALYSIS\n")
            f.write("=" * 80 + "\n")
            f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Turn ID: {self.current_turn_id}\n")
            f.write("=" * 80 + "\n\n")
            
            f.write("USER QUERY:\n")
            f.write("-" * 80 + "\n")
            f.write(f"{query}\n\n")
            
            if intent:
                f.write("INTENT ANALYSIS:\n")
                f.write("-" * 80 + "\n")
                f.write(f"Query Type: {intent.query_type.value if hasattr(intent.query_type, 'value') else intent.query_type}\n")
                f.write(f"Confidence: {intent.confidence:.2f}\n")
                f.write(f"Keywords: {', '.join(intent.keywords)}\n")
                
                if hasattr(intent, 'primary_topics') and intent.primary_topics:
                    f.write(f"Primary Topics: {', '.join(intent.primary_topics)}\n")
                
                if hasattr(intent, 'raw_query') and intent.raw_query:
                    f.write(f"Raw Query (for vector search): {intent.raw_query}\n")
                
                if hasattr(intent, 'time_range') and intent.time_range:
                    f.write(f"Time Range: {intent.time_range[0]} to {intent.time_range[1]}\n")
                
                if hasattr(intent, 'task_filter') and intent.task_filter:
                    f.write(f"Task Filter: {intent.task_filter}\n")
        
        print(f"   📝 Debug: User query logged to {filepath.name}")
    
    def log_retrieved_context(self, context: Any, search_method: str = "unknown"):
        """
        Log the retrieved context (what was hydrated from memory)
        
        Args:
            context: RetrievedContext object
            search_method: Which search method was used (vector/keyword/both)
        """
        if not self.enabled:
            return
            
        filepath = self._get_filename("02_retrieved_context")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("RETRIEVED CONTEXT (What Was Hydrated)\n")
            f.write("=" * 80 + "\n")
            f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Turn ID: {self.current_turn_id}\n")
            f.write(f"Search Method: {search_method}\n")
            f.write("=" * 80 + "\n\n")
            
            # Context snippets
            if hasattr(context, 'contexts') and context.contexts:
                f.write(f"RETRIEVED {len(context.contexts)} CONTEXT SNIPPET(S):\n")
                f.write("-" * 80 + "\n\n")
                
                for i, ctx in enumerate(context.contexts, 1):
                    f.write(f"--- Snippet {i} ---\n")
                    
                    if isinstance(ctx, dict):
                        # Show relevance score
                        if 'relevance_score' in ctx:
                            f.write(f"Relevance Score: {ctx['relevance_score']:.3f}\n")
                        
                        # Show turn metadata
                        if 'turn_id' in ctx:
                            f.write(f"Turn ID: {ctx['turn_id']}\n")
                        if 'day_id' in ctx:
                            f.write(f"Day: {ctx['day_id']}\n")
                        if 'timestamp' in ctx:
                            f.write(f"Timestamp: {ctx['timestamp']}\n")
                        
                        # Debug: Show all keys
                        f.write(f"All Keys: {list(ctx.keys())}\n")
                        
                        # Show the actual text
                        if 'text' in ctx:
                            f.write(f"\nText:\n{ctx['text']}\n")
                        elif 'user_message' in ctx or 'assistant_response' in ctx:
                            if 'user_message' in ctx:
                                f.write(f"\nUser: {ctx['user_message']}\n")
                            if 'assistant_response' in ctx:
                                f.write(f"Assistant: {ctx['assistant_response']}\n")
                        elif 'context' in ctx:
                            context_text = ctx['context']
                            if context_text:
                                f.write(f"\nContext:\n{context_text[:200]}...\n")
                            else:
                                f.write(f"\nContext: (empty)\n")
                    else:
                        f.write(f"{ctx}\n")
                    
                    f.write("\n")
            else:
                f.write("NO CONTEXT RETRIEVED\n\n")
            
            # Sources
            if hasattr(context, 'sources') and context.sources:
                f.write(f"SOURCES ({len(context.sources)}):\n")
                f.write("-" * 80 + "\n")
                for source in context.sources:
                    f.write(f"  - {source}\n")
                f.write("\n")
            
            # Active tasks
            if hasattr(context, 'active_tasks') and context.active_tasks:
                f.write(f"ACTIVE TASKS ({len(context.active_tasks)}):\n")
                f.write("-" * 80 + "\n")
                for task in context.active_tasks:
                    if hasattr(task, 'task_title'):
                        f.write(f"  - {task.task_title}\n")
                    else:
                        f.write(f"  - {task}\n")
                f.write("\n")
            
            # Metadata
            if hasattr(context, 'total_tokens'):
                f.write(f"Estimated Tokens: {context.total_tokens}\n")
            
            if hasattr(context, 'retrieved_turn_ids') and context.retrieved_turn_ids:
                f.write(f"Retrieved Turn IDs: {', '.join(context.retrieved_turn_ids[:5])}")
                if len(context.retrieved_turn_ids) > 5:
                    f.write(f" ... and {len(context.retrieved_turn_ids) - 5} more")
                f.write("\n")
        
        print(f"   📝 Debug: Retrieved context logged to {filepath.name}")
    
    def log_sliding_window(self, sliding_window: Any):
        """
        Log the current sliding window contents
        
        Args:
            sliding_window: SlidingWindow object
        """
        if not self.enabled:
            return
            
        filepath = self._get_filename("03_sliding_window")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("SLIDING WINDOW (Recent Conversation Context)\n")
            f.write("=" * 80 + "\n")
            f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Turn ID: {self.current_turn_id}\n")
            f.write("=" * 80 + "\n\n")
            
            if hasattr(sliding_window, 'turns') and sliding_window.turns:
                f.write(f"WINDOW SIZE: {len(sliding_window.turns)} / {sliding_window.max_turns} turns\n")
                if hasattr(sliding_window, 'total_tokens'):
                    f.write(f"Total Tokens: {sliding_window.total_tokens}\n\n")
                else:
                    f.write("\n")
                
                f.write("TURNS IN WINDOW:\n")
                f.write("-" * 80 + "\n\n")
                
                for i, turn in enumerate(sliding_window.turns, 1):
                    f.write(f"--- Turn {i} ---\n")
                    f.write(f"Turn ID: {turn.turn_id}\n")
                    f.write(f"Sequence: {turn.turn_sequence}\n")
                    f.write(f"Timestamp: {turn.timestamp}\n\n")
                    
                    f.write(f"User: {turn.user_message}\n\n")
                    
                    # Show what will actually appear in the prompt
                    if turn.detail_level == 'VERBATIM':
                        f.write(f"Assistant: {turn.assistant_response}\n\n")
                    elif turn.detail_level == 'COMPRESSED':
                        compressed = turn.compressed_content or turn.assistant_summary or "[Summary unavailable]"
                        f.write(f"Assistant: [Compressed] {compressed}\n\n")
                    else:  # SUMMARY
                        f.write(f"Assistant: [Summary] Turn {turn.turn_id}\n\n")
                    
                    if turn.keywords:
                        f.write(f"Keywords: {', '.join(turn.keywords)}\n")
                    
                    if hasattr(turn, 'summary') and turn.summary:
                        f.write(f"Summary: {turn.summary}\n")
                    
                    f.write("\n")
            else:
                f.write("SLIDING WINDOW IS EMPTY\n")
        
        print(f"   📝 Debug: Sliding window logged to {filepath.name}")
    
    def log_full_prompt(self, prompt: str, context_summary: Dict[str, Any] = None):
        """
        Log the complete prompt sent to the LLM
        
        Args:
            prompt: Full prompt text
            context_summary: Optional metadata about what was included
        """
        if not self.enabled:
            return
            
        filepath = self._get_filename("04_llm_prompt")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("FULL PROMPT SENT TO LLM\n")
            f.write("=" * 80 + "\n")
            f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Turn ID: {self.current_turn_id}\n")
            f.write("=" * 80 + "\n\n")
            
            if context_summary:
                f.write("CONTEXT SUMMARY:\n")
                f.write("-" * 80 + "\n")
                for key, value in context_summary.items():
                    f.write(f"{key}: {value}\n")
                f.write("\n")
            
            f.write("FULL PROMPT:\n")
            f.write("-" * 80 + "\n")
            f.write(prompt)
            f.write("\n")
        
        print(f"   📝 Debug: Full prompt logged to {filepath.name}")
    
    def log_llm_response(self, response: str, metadata: Dict[str, Any] = None):
        """
        Log the LLM's response
        
        Args:
            response: Full response text
            metadata: Optional metadata (tokens, time, etc.)
        """
        if not self.enabled:
            return
            
        filepath = self._get_filename("05_llm_response")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("LLM RESPONSE\n")
            f.write("=" * 80 + "\n")
            f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Turn ID: {self.current_turn_id}\n")
            f.write("=" * 80 + "\n\n")
            
            if metadata:
                f.write("RESPONSE METADATA:\n")
                f.write("-" * 80 + "\n")
                for key, value in metadata.items():
                    f.write(f"{key}: {value}\n")
                f.write("\n")
            
            f.write("FULL RESPONSE:\n")
            f.write("-" * 80 + "\n")
            f.write(response)
            f.write("\n")
        
        print(f"   📝 Debug: LLM response logged to {filepath.name}")
    
    def log_summary(self, summary_data: Dict[str, Any]):
        """
        Log a summary of the entire turn
        
        Args:
            summary_data: Dictionary with summary information
        """
        if not self.enabled:
            return
            
        filepath = self._get_filename("00_turn_summary", "json")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(summary_data, f, indent=2, default=str)
        
        print(f"   📝 Debug: Turn summary logged to {filepath.name}")
    
    def log_terminal_output(self, output_lines: List[str]):
        """
        Log the terminal output from this turn
        
        Args:
            output_lines: List of print statements/output lines from the turn
        """
        if not self.enabled:
            return
            
        filepath = self._get_filename("00_terminal_output", "txt")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("TERMINAL OUTPUT FOR THIS TURN\n")
            f.write("=" * 80 + "\n")
            f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Turn ID: {self.current_turn_id}\n")
            f.write("=" * 80 + "\n\n")
            
            for line in output_lines:
                f.write(line + "\n")
        
        print(f"   📝 Debug: Terminal output logged to {filepath.name}")
    
    def log_metadata_extraction(
        self, 
        user_message: str,
        assistant_response: str,
        extraction_prompt: str,
        llm_response: str,
        metadata: Any = None
    ):
        """
        Log metadata extraction details (prompt, raw LLM output, parsed metadata)
        
        Args:
            user_message: Original user message
            assistant_response: Original assistant response
            extraction_prompt: Prompt sent to LLM for metadata extraction
            llm_response: Raw LLM response (JSON)
            metadata: Parsed TurnMetadata object (if successful)
        """
        if not self.enabled:
            return
            
        filepath = self._get_filename("06_metadata_extraction", "txt")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("METADATA EXTRACTION\n")
            f.write("=" * 80 + "\n")
            f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Turn ID: {self.current_turn_id}\n")
            f.write("=" * 80 + "\n\n")
            
            f.write("ORIGINAL CONVERSATION:\n")
            f.write("-" * 80 + "\n")
            f.write(f"User: {user_message}\n\n")
            f.write(f"Assistant: {assistant_response[:500]}{'...' if len(assistant_response) > 500 else ''}\n\n")
            
            f.write("EXTRACTION PROMPT SENT TO LLM:\n")
            f.write("-" * 80 + "\n")
            f.write(f"{extraction_prompt}\n\n")
            
            f.write("RAW LLM RESPONSE:\n")
            f.write("-" * 80 + "\n")
            f.write(f"{llm_response}\n\n")
            
            if metadata:
                f.write("PARSED METADATA:\n")
                f.write("-" * 80 + "\n")
                f.write(f"Keywords: {metadata.keywords}\n")
                f.write(f"Assistant Summary: {metadata.assistant_summary}\n")
                f.write(f"Affect Label: {metadata.affect_label}\n")
                f.write(f"Affect Intensity: {metadata.affect_intensity}\n")
                f.write(f"Affect Confidence: {metadata.affect_confidence}\n")
            else:
                f.write("PARSING FAILED\n")
                f.write("-" * 80 + "\n")
                f.write("Could not parse metadata from LLM response\n")
        
        print(f"   📝 Debug: Metadata extraction logged to {filepath.name}")
    
    def cleanup_old_logs(self, keep_last_n: int = 50):
        """
        Remove old debug logs, keeping only the most recent N turns
        
        Args:
            keep_last_n: Number of recent turn logs to keep
        """
        if not self.base_dir.exists():
            return
        
        # Get all turn timestamps by looking at summary files
        summary_files = sorted(self.base_dir.glob("00_turn_summary_*.json"))
        
        if len(summary_files) > keep_last_n:
            # Extract timestamps from files to delete
            files_to_delete = summary_files[:-keep_last_n]
            timestamps_to_delete = set()
            
            for summary_file in files_to_delete:
                # Extract timestamp from filename
                parts = summary_file.stem.split("_")
                if len(parts) >= 3:
                    timestamp = "_".join(parts[-2:])  # Last two parts are the timestamp
                    timestamps_to_delete.add(timestamp)
            
            # Delete all files with those timestamps
            for timestamp in timestamps_to_delete:
                for file in self.base_dir.glob(f"*{timestamp}.*"):
                    file.unlink()
            
            print(f"   🧹 Cleaned up {len(timestamps_to_delete)} old debug log sets")
