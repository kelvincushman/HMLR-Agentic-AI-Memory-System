"""
Component Factory for CognitiveLattice

This module provides centralized component initialization with dependency injection.
All CognitiveLattice interfaces (CLI, Flask API, Discord bot, etc.) can use this
factory to get a consistent, properly-wired set of components.

Extracted from main.py as part of Phase 3 refactor.
"""

import os
from dataclasses import dataclass
from typing import Optional
from memory import Storage
from memory.conversation_manager import ConversationManager
from memory.models import SlidingWindow
from memory.debug_logger import MemoryDebugLogger
from memory.metadata_extractor import LLMMetadataExtractor
from memory.embeddings.embedding_manager import EmbeddingManager, EmbeddingStorage
from memory.retrieval.intent_analyzer import IntentAnalyzer
from memory.retrieval.crawler import LatticeCrawler
from memory.retrieval.context_hydrator import ContextHydrator
from memory.retrieval.lattice import LatticeRetrieval, TheGovernor
from memory.retrieval.hmlr_hydrator import Hydrator
from memory.tabula_rasa import TabulaRasa
from memory.topics import TopicExtractor, TopicFilter
from memory.usage import CitationParser, UsageTracker
from memory.adaptive import AdaptiveCompressor, EvictionManager, RehydrationManager
from memory.synthesis import SynthesisManager
from memory.synthesis.user_profile_manager import UserProfileManager
from memory.synthesis.scribe import Scribe
from memory.chunking.chunk_engine import ChunkEngine
from memory.fact_scrubber import FactScrubber
from core.external_api_client import ExternalAPIClient
from core.tool_manager import ToolManager
from core.cognitive_lattice import SessionManager
from core.planning_interview import UniversalPlanningInterview


@dataclass
class ComponentBundle:
    """
    Container for all initialized CognitiveLattice components.
    
    This bundle provides all components needed by ConversationEngine
    and other parts of the system, properly initialized and wired together.
    """
    # Core storage and state
    storage: Storage
    conversation_mgr: ConversationManager
    sliding_window: SlidingWindow
    session_manager: SessionManager
    
    # External services
    external_api: Optional[ExternalAPIClient]
    planning_interview: Optional[UniversalPlanningInterview]
    tool_manager: ToolManager
    
    # Retrieval components (Phase 3)
    crawler: LatticeCrawler
    intent_analyzer: IntentAnalyzer
    context_hydrator: ContextHydrator
    
    # HMLR v1 Components (Phase 4 Integration)
    lattice_retrieval: LatticeRetrieval
    governor: TheGovernor
    hydrator: Hydrator
    tabula_rasa: TabulaRasa
    
    # Topic tracking (Phase 4.1)
    topic_extractor: TopicExtractor
    topic_filter: TopicFilter
    
    # Usage tracking (Phase 4.1)
    citation_parser: CitationParser
    usage_tracker: UsageTracker
    
    # Adaptive memory (Phase 4.3)
    adaptive_compressor: AdaptiveCompressor
    eviction_manager: EvictionManager
    rehydration_manager: RehydrationManager
    
    # Synthesis (Phase 4.4)
    synthesis_manager: SynthesisManager
    user_profile_manager: UserProfileManager
    scribe: Scribe
    
    # Chunking and Fact Extraction (Phase 11.3)
    chunk_engine: ChunkEngine
    fact_scrubber: FactScrubber
    
    # Utilities
    debug_logger: MemoryDebugLogger
    metadata_extractor: LLMMetadataExtractor
    embedding_storage: EmbeddingStorage  # Unified: handles encoding AND database storage
    
    # Session state
    previous_day: str  # For synthesis triggers


class ComponentFactory:
    """
    Factory for creating and wiring all CognitiveLattice components.
    
    This factory handles all the complex initialization logic, ensuring
    components are properly configured and dependencies are correctly wired.
    
    Usage:
        # Simple initialization
        components = ComponentFactory.create_all_components()
        
        # Use with ConversationEngine
        engine = ConversationEngine(
            storage=components.storage,
            sliding_window=components.sliding_window,
            ...
        )
    """
    
    @staticmethod
    def create_all_components(
        use_llm_intent_mode: bool = False,
        max_sliding_window_turns: int = 20,
        context_budget_tokens: int = 6000,
        crawler_recency_weight: float = 0.5
    ) -> ComponentBundle:
        """
        Create and wire all CognitiveLattice components.
        
        This method initializes all components in the correct order,
        handling dependencies and configuration.
        
        Args:
            use_llm_intent_mode: Whether to use LLM for intent analysis (default: False)
            max_sliding_window_turns: Max turns in sliding window (default: 20)
            context_budget_tokens: Token budget for context hydration (default: 6000)
            crawler_recency_weight: Weight for recent results (default: 0.5)
        
        Returns:
            ComponentBundle with all initialized components
        """
        print("🏗️  Initializing CognitiveLattice components...")
        
        # === Core Storage and State === #
        print("   📦 Initializing storage and session...")
        session_manager = SessionManager()
        print(f"   🧠 Cognitive Lattice initialized for session: {session_manager.lattice.session_id}")
        
        # Check for test database path override
        db_path = os.environ.get('COGNITIVE_LATTICE_DB')
        storage = Storage(db_path=db_path) if db_path else Storage()
        conversation_mgr = ConversationManager(storage)
        previous_day = conversation_mgr.current_day
        
        # === Utilities === #
        print("   🛠️  Initializing utilities...")
        debug_logger = MemoryDebugLogger()
        print(f"   📝 Memory debug logging enabled")
        
        metadata_extractor = LLMMetadataExtractor(debug_logger=debug_logger)
        print(f"   💾 Persistent memory enabled (day: {conversation_mgr.current_day})")
        print(f"   📊 Metadata extraction enabled")
        
        # Create unified embedding storage (handles encoding AND database)
        embedding_storage = EmbeddingStorage(storage)
        print(f"   🔍 Embedding storage initialized")
        
        # === Phase 3: Retrieval System === #
        print("   🔍 Initializing retrieval system...")
        intent_analyzer = IntentAnalyzer(use_llm_mode=use_llm_intent_mode)
        crawler = LatticeCrawler(storage, recency_weight=crawler_recency_weight)
        context_hydrator = ContextHydrator(storage=storage, max_tokens=context_budget_tokens)
        
        # === HMLR v1 Components === #
        print("   🏛️  Initializing HMLR v1 components...")
        lattice_retrieval = LatticeRetrieval(crawler)
        # Governor needs API client, but we haven't initialized it yet.
        # We'll initialize Governor after ExternalAPIClient.
        hydrator = Hydrator(storage, token_limit=context_budget_tokens)
        
        # Initialize Tabula Rasa (needs storage and topic extractor)
        # We initialize topic extractor first
        print("   🏷️  Initializing topic tracking & usage monitoring...")
        topic_extractor = TopicExtractor()
        topic_filter = TopicFilter()
        citation_parser = CitationParser()
        usage_tracker = UsageTracker()
        print(f"   🏷️  Phase 4.1 enabled: Topic tracking & usage monitoring")
        
        tabula_rasa = TabulaRasa(storage, topic_extractor)
        print(f"   🔄 Tabula Rasa enabled: Automatic topic segmentation")
        
        # Load or create sliding window
        print(f"   📂 Loading sliding window from persistent state...")
        sliding_window = SlidingWindow.load_from_file()
        
        if len(sliding_window.turns) == 0:
            # No saved state - load from database
            print(f"      ℹ️  No saved state - loading from database...")
            try:
                recent_turns = storage.get_recent_turns(day_id=None, limit=max_sliding_window_turns)
                for turn in recent_turns:
                    sliding_window.add_turn(turn)
                
                if recent_turns:
                    print(f"      📝 Loaded {len(recent_turns)} turns from database")
            except Exception as e:
                print(f"      ⚠️  Could not load from database: {e}")
        else:
            print(f"      📂 Loaded sliding window state: {len(sliding_window.turns)} turns")
        
        print(f"   🔍 Retrieval system enabled")
        mode_desc = "LLM mode" if use_llm_intent_mode else "Heuristic mode (nano prompting handles intent)"
        print(f"      - Intent Analyzer: {mode_desc}")
        print(f"      - Crawler: Topic-aware scoring")
        print(f"      - Context Hydrator: {context_budget_tokens} token budget")
        
        # === Phase 4.1: Topic Tracking & Usage === #
        # Already initialized above for Tabula Rasa
        
        # === Phase 4.3: Adaptive Sliding Window === #
        print("   🎯 Initializing adaptive compression...")
        adaptive_compressor = AdaptiveCompressor(embedder=embedding_storage.embedding_manager.encode)
        eviction_manager = EvictionManager()
        rehydration_manager = RehydrationManager()
        print(f"   🎯 Phase 4.3 enabled: Adaptive compression with graduated thresholds")
        
        # === Phase 4.4: Synthesis System === #
        print("   🧠 Initializing synthesis system...")
        synthesis_manager = SynthesisManager(storage)
        user_profile_manager = UserProfileManager()
        # Scribe needs API client, initialized later
        print(f"   🧠 Phase 4.4 enabled: Hierarchical synthesis and user profiling")
        
        # === External Services === #
        print("   🌐 Initializing external services...")
        tool_manager = ToolManager()
        print(f"   🔧 Tool Manager initialized")
        
        try:
            external_api = ExternalAPIClient()
            print(f"   🌐 External API client initialized")
        except Exception as e:
            print(f"   ⚠️  Could not initialize External API Client: {e}")
            external_api = None
        
        # Initialize Governor now that we have API client, storage, and crawler
        governor = TheGovernor(external_api, storage, crawler) if external_api else None
        if governor:
            print(f"   🏛️  The Governor is online")
        else:
            print(f"   ⚠️  The Governor is offline (no API)")
            
        # Initialize Scribe now that we have API client
        scribe = Scribe(external_api, user_profile_manager) if external_api else None
        if scribe:
            print(f"   ✍️  The Scribe is online")
        else:
            print(f"   ⚠️  The Scribe is offline (no API)")
        
        # === Phase 11.3: Chunking and Fact Extraction === #
        print("   🔧 Initializing chunking and fact extraction...")
        chunk_engine = ChunkEngine()
        fact_scrubber = FactScrubber(storage, external_api) if external_api else None
        if fact_scrubber:
            print(f"   🧹 FactScrubber is online")
        else:
            print(f"   ⚠️  FactScrubber is offline (no API)")
        
        planning_interview = None
        if external_api:
            planning_interview = UniversalPlanningInterview(external_api)
            print(f"   📅 Planning Interview system initialized")
        
        print("   ✅ All components initialized successfully")
        
        return ComponentBundle(
            storage=storage,
            conversation_mgr=conversation_mgr,
            sliding_window=sliding_window,
            session_manager=session_manager,
            external_api=external_api,
            planning_interview=planning_interview,
            tool_manager=tool_manager,
            crawler=crawler,
            intent_analyzer=intent_analyzer,
            context_hydrator=context_hydrator,
            lattice_retrieval=lattice_retrieval,
            governor=governor,
            hydrator=hydrator,
            tabula_rasa=tabula_rasa,
            topic_extractor=topic_extractor,
            topic_filter=topic_filter,
            citation_parser=citation_parser,
            usage_tracker=usage_tracker,
            adaptive_compressor=adaptive_compressor,
            eviction_manager=eviction_manager,
            rehydration_manager=rehydration_manager,
            synthesis_manager=synthesis_manager,
            user_profile_manager=user_profile_manager,
            scribe=scribe,
            chunk_engine=chunk_engine,
            fact_scrubber=fact_scrubber,
            debug_logger=debug_logger,
            metadata_extractor=metadata_extractor,
            embedding_storage=embedding_storage,
            previous_day=previous_day
        )
    
    @staticmethod
    def create_conversation_engine(components: ComponentBundle):
        """
        Create a ConversationEngine from a ComponentBundle.
        
        This is a convenience method that wires the components into
        a ConversationEngine with the correct parameters.
        
        Args:
            components: ComponentBundle from create_all_components()
        
        Returns:
            Initialized ConversationEngine
        """
        from core.conversation_engine import ConversationEngine
        
        print("🚀 Creating ConversationEngine...")
        
        engine = ConversationEngine(
            storage=components.storage,
            sliding_window=components.sliding_window,
            external_api=components.external_api,
            planning_interview=components.planning_interview,
            tool_manager=components.tool_manager,
            session_manager=components.session_manager,
            conversation_mgr=components.conversation_mgr,
            crawler=components.crawler,
            intent_analyzer=components.intent_analyzer,
            lattice_retrieval=components.lattice_retrieval,
            governor=components.governor,
            hydrator=components.hydrator,
            tabula_rasa=components.tabula_rasa,
            topic_extractor=components.topic_extractor,
            topic_filter=components.topic_filter,
            context_hydrator=components.context_hydrator,
            citation_parser=components.citation_parser,
            usage_tracker=components.usage_tracker,
            adaptive_compressor=components.adaptive_compressor,
            eviction_manager=components.eviction_manager,
            rehydration_manager=components.rehydration_manager,
            synthesis_manager=components.synthesis_manager,
            user_profile_manager=components.user_profile_manager,
            scribe=components.scribe,
            chunk_engine=components.chunk_engine,
            fact_scrubber=components.fact_scrubber,
            debug_logger=components.debug_logger,
            embedding_storage=components.embedding_storage,
            previous_day=components.previous_day
        )
        
        print("🚀 ConversationEngine initialized")
        
        return engine
