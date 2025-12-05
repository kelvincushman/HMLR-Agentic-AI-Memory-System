"""
HMLR v1 - Tabula Rasa (Topic Segmentation)

This module implements the 'Tabula Rasa' philosophy:
The system must automatically detect when a conversation shifts topics,
close the current 'Span', and open a new one.

It leverages the existing TopicExtractor but adds the logic to compare
current topics against the active span's context.

Phase 11.5 Enhancement: Integrated with ChunkEngine to create immutable chunks.
Phase 11.4 Enhancement: Integrated with BridgeBlockGenerator and FactScrubber.
"""

import logging
import asyncio
import uuid
from typing import List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

from memory.models import Span, ConversationTurn
from memory.bridge_models.bridge_block import ExitReason
from memory.storage import Storage
from memory.topics.extractor import TopicExtractor, ExtractedTopic
from memory.chunking import ChunkEngine, ChunkStorage
from memory.bridge_block_generator import BridgeBlockGenerator
from memory.fact_scrubber import FactScrubber

logger = logging.getLogger(__name__)

@dataclass
class TopicShiftResult:
    is_shift: bool
    reason: str
    new_topic_label: Optional[str] = None
    confidence: float = 0.0

class TabulaRasa:
    """
    The 'Clean Slate' manager.
    Detects topic shifts and manages Span lifecycles.
    
    Phase 11.5 Enhancement:
    - Creates immutable chunks for each turn (sentence + paragraph)
    - Stores chunks in database for later retrieval
    - Links chunks to spans and turns for hierarchical access
    """
    
    def __init__(
        self, 
        storage: Storage, 
        topic_extractor: Optional[TopicExtractor] = None,
        chunk_engine: Optional[ChunkEngine] = None,
        chunk_storage: Optional[ChunkStorage] = None,
        bridge_block_generator: Optional[BridgeBlockGenerator] = None,
        fact_scrubber: Optional[FactScrubber] = None,
        api_client = None  # ExternalAPIClient for LLM calls
    ):
        self.storage = storage
        self.topic_extractor = topic_extractor or TopicExtractor()
        self.chunk_engine = chunk_engine or ChunkEngine()
        self.chunk_storage = chunk_storage or ChunkStorage(storage)
        self.bridge_block_generator = bridge_block_generator or BridgeBlockGenerator(storage, self.chunk_storage, api_client)
        self.fact_scrubber = fact_scrubber or FactScrubber(storage, api_client)
        self.api_client = api_client
        
        # Thresholds
        self.shift_threshold = 0.7  # Confidence needed to trigger a shift
        
    def check_for_shift(self, query: str, active_span: Optional[Span], nano_metadata: Optional[dict] = None) -> TopicShiftResult:
        """
        Determine if the current query represents a shift from the active span.
        
        Args:
            query: User's query
            active_span: The currently active span
            nano_metadata: Optional metadata from GPT-4o-nano (if available)
        """
        print(f"[CHECK_SHIFT] active={active_span.span_id if active_span else None}, meta={nano_metadata}")
        
        # 1. If no active span, it's definitely a "shift" (to a new start)
        if not active_span:
            # Try to get topic from nano metadata first
            new_label = "General Conversation"
            if nano_metadata and nano_metadata.get('topics'):
                new_label = nano_metadata['topics'][0]
            elif nano_metadata and nano_metadata.get('new_topic_label'):
                new_label = nano_metadata['new_topic_label']
            
            return TopicShiftResult(
                is_shift=True, 
                reason="No active span", 
                new_topic_label=new_label,
                confidence=1.0
            )

        # 2. Use Nano Metadata if available (Smartest Method)
        if nano_metadata and nano_metadata.get('is_topic_shift'):
            print(f"[SHIFT_DETECTED] new_label={nano_metadata.get('new_topic_label')}")
            logger.info(f"Nano metadata detected topic shift: {nano_metadata}")
            return TopicShiftResult(
                is_shift=True,
                reason="GPT-4o-nano detected topic shift",
                new_topic_label=nano_metadata.get('new_topic_label', "New Topic"),
                confidence=0.95
            )
        else:
            print(f"[NO_SHIFT] has_meta={nano_metadata is not None}, is_shift={nano_metadata.get('is_topic_shift') if nano_metadata else 'N/A'}")
        
        # 3. Fallback to Heuristic Extraction (Fast Method)
        current_topics = self.topic_extractor.extract(query)
        if not current_topics:
            return TopicShiftResult(is_shift=False, reason="No clear topics in query")
            
        primary_topic = current_topics[0]
        
        # If the query explicitly references the previous topic, it's a continuation.
        if self._is_continuation(query, active_span):
            return TopicShiftResult(is_shift=False, reason="Detected continuation pattern")

        # If the primary topic is significantly different from the span label
        if primary_topic.keyword.lower() in active_span.topic_label.lower():
             return TopicShiftResult(is_shift=False, reason="Topic match")
             
        if primary_topic.confidence > 0.8:
             return TopicShiftResult(
                is_shift=True, 
                reason=f"Strong new topic: {primary_topic.keyword}",
                new_topic_label=primary_topic.keyword,
                confidence=primary_topic.confidence
            )
            
        return TopicShiftResult(is_shift=False, reason="Weak signal")

    def _is_continuation(self, query: str, active_span: Span) -> bool:
        """
        Check if the query is a continuation of the active span.
        """
        # Simple heuristics
        continuation_markers = ["and", "also", "but", "so", "then", "it", "that", "he", "she", "they"]
    def ensure_active_span(self, query: str, day_id: str, nano_metadata: Optional[dict] = None) -> Span:
        """
        The main entry point for the Write Path.
        Ensures there is an appropriate active span for the incoming query.
        If a shift is detected, closes the old one and opens a new one.
        """
        active_span = self.storage.get_active_span()
        
        shift_result = self.check_for_shift(query, active_span, nano_metadata)
        
        if shift_result.is_shift:
            if active_span:
                print(f"[SHIFT] Old span: {active_span.span_id}, topic: {active_span.topic_label}")
                logger.info(f"Topic Shift Detected: '{active_span.topic_label}' -> '{shift_result.new_topic_label}'")
                
                # Phase 11.4: Generate Bridge Block for closed span
                try:
                    bridge_block = self.bridge_block_generator.generate_from_span(
                        span=active_span,  # Pass Span object, not span_id
                        exit_reason=ExitReason.TOPIC_SHIFT
                    )
                    if bridge_block:
                        self.bridge_block_generator.save_to_ledger(bridge_block)
                        logger.info(f"Created Bridge Block: {bridge_block.block_id}")
                except Exception as e:
                    logger.error(f"Failed to generate Bridge Block for span {active_span.span_id}: {e}")
                
                # Close the old span
                self.storage.close_span(active_span.span_id)
                print(f"[CLOSED] Closed old span {active_span.span_id}")
            
            # Create new span
            # Use UUID to guarantee uniqueness
            new_span_id = f"span_{uuid.uuid4().hex[:12]}"
            print(f"[CREATE] New span ID: {new_span_id}, topic: {shift_result.new_topic_label}")
            
            new_span = Span(
                span_id=new_span_id,
                day_id=day_id,
                created_at=datetime.now(),
                last_active_at=datetime.now(),
                topic_label=shift_result.new_topic_label or "General Conversation",
                is_active=True,
                turn_ids=[]
            )
            self.storage.create_span(new_span)
            print(f"[RETURN] Returning span {new_span.span_id}, is_active={new_span.is_active}")
            return new_span
            
        else:
            # Update active span timestamp
            if active_span:
                active_span.last_active_at = datetime.now()
                self.storage.update_span(active_span)
                return active_span
            else:
                # Should be covered by is_shift=True if no active span, but safety net:
                new_span_id = f"span_{uuid.uuid4().hex[:12]}"
                new_span = Span(
                    span_id=new_span_id,
                    day_id=day_id,
                    created_at=datetime.now(),
                    last_active_at=datetime.now(),
                    topic_label="General Conversation",
                    is_active=True,
                    turn_ids=[]
                )
                self.storage.create_span(new_span)
                return new_span
    
    async def process_turn_async(self, turn: ConversationTurn) -> Tuple[List, List]:
        """
        Process a conversation turn by creating chunks and extracting facts (async).
        
        Phase 11.4 Enhancement:
        - Creates immutable chunks (sentence + paragraph)
        - Extracts hard facts in parallel (non-blocking)
        - Links facts to sentence chunks for provenance
        
        Args:
            turn: ConversationTurn object with user query and/or assistant response
            
        Returns:
            Tuple of (chunks, facts) created
        """
        all_chunks = []
        all_facts = []
        
        # Chunk user query if present
        if turn.user_query:
            user_chunks = self.chunk_engine.chunk_turn(
                text=turn.user_query,
                turn_id=turn.turn_id,
                span_id=turn.span_id
            )
            all_chunks.extend(user_chunks)
            logger.debug(f"Created {len(user_chunks)} chunks for user query")
            
            # Extract facts from user query (async, parallel)
            try:
                user_facts = await self.fact_scrubber.extract_and_save(
                    turn_id=turn.turn_id,
                    message_text=turn.user_query,
                    chunks=user_chunks,
                    span_id=turn.span_id
                )
                all_facts.extend(user_facts)
                if user_facts:
                    logger.info(f"Extracted {len(user_facts)} facts from user query")
            except Exception as e:
                logger.error(f"Fact extraction failed for user query: {e}")
        
        # Chunk assistant response if present
        if turn.assistant_response:
            assistant_chunks = self.chunk_engine.chunk_turn(
                text=turn.assistant_response,
                turn_id=turn.turn_id,
                span_id=turn.span_id
            )
            all_chunks.extend(assistant_chunks)
            logger.debug(f"Created {len(assistant_chunks)} chunks for assistant response")
            
            # Extract facts from assistant response (async, parallel)
            try:
                assistant_facts = await self.fact_scrubber.extract_and_save(
                    turn_id=turn.turn_id,
                    message_text=turn.assistant_response,
                    chunks=assistant_chunks,
                    span_id=turn.span_id
                )
                all_facts.extend(assistant_facts)
                if assistant_facts:
                    logger.info(f"Extracted {len(assistant_facts)} facts from assistant response")
            except Exception as e:
                logger.error(f"Fact extraction failed for assistant response: {e}")
        
        # Save chunks to database
        if all_chunks:
            self.chunk_storage.save_chunks(all_chunks)
            logger.info(f"Saved {len(all_chunks)} chunks for turn {turn.turn_id}")
        
        return all_chunks, all_facts
    
    def process_turn(self, turn: ConversationTurn) -> List:
        """
        Process a conversation turn by creating immutable chunks (sync wrapper).
        
        Phase 11.4 Enhancement:
        - Chunks turn text into sentences and paragraphs
        - Assigns immutable IDs at ingestion time
        - Stores chunks in database for later retrieval
        - Extracts facts in parallel (if event loop available)
        
        Args:
            turn: ConversationTurn object with user query and/or assistant response
            
        Returns:
            List of created Chunk objects
        """
        try:
            # Try to run async version if event loop available
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Already in async context - create task
                task = asyncio.create_task(self.process_turn_async(turn))
                chunks, facts = asyncio.run(asyncio.wait_for(task, timeout=2.0))
                return chunks
            else:
                # No running loop - use asyncio.run
                chunks, facts = asyncio.run(self.process_turn_async(turn))
                return chunks
        except Exception as e:
            logger.warning(f"Async processing failed, falling back to sync: {e}")
            # Fallback to sync-only chunking
            return self._process_turn_sync(turn)
    
    def _process_turn_sync(self, turn: ConversationTurn) -> List:
        """
        Synchronous fallback for turn processing (no fact extraction).
        
        Args:
            turn: ConversationTurn object
            
        Returns:
            List of created Chunk objects
        """
        all_chunks = []
        
        # Chunk user query if present
        if turn.user_query:
            user_chunks = self.chunk_engine.chunk_turn(
                text=turn.user_query,
                turn_id=turn.turn_id,
                span_id=turn.span_id
            )
            all_chunks.extend(user_chunks)
            logger.debug(f"Created {len(user_chunks)} chunks for user query")
        
        # Chunk assistant response if present
        if turn.assistant_response:
            assistant_chunks = self.chunk_engine.chunk_turn(
                text=turn.assistant_response,
                turn_id=turn.turn_id,
                span_id=turn.span_id
            )
            all_chunks.extend(assistant_chunks)
            logger.debug(f"Created {len(assistant_chunks)} chunks for assistant response")
        
        # Save chunks to database
        if all_chunks:
            self.chunk_storage.save_chunks(all_chunks)
            logger.info(f"Saved {len(all_chunks)} chunks for turn {turn.turn_id}")
        
        return all_chunks
