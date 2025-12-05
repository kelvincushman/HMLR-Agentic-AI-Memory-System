"""
Phase 11.9.E: Test 7 - State Conflict & Updates (CRITICAL)

Tests the system's ability to handle:
1. Updated/rotated secrets (API key rotation)
2. Contradictory user facts (vegetarian → steakhouse)
3. Timestamp-based conflict resolution
4. User profile vs conversation context

Key Question: Does the system prefer recent truths over past truths?
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from typing import Dict, Any

from memory.storage import Storage
from memory.fact_scrubber import FactScrubber
from memory.synthesis.scribe import Scribe
from memory.synthesis.user_profile_manager import UserProfileManager
from core.external_api_client import ExternalAPIClient
from core.conversation_engine import ConversationEngine
from memory.retrieval.lattice import Lattice
from memory.retrieval.context_hydrator import ContextHydrator
from memory.chunking.chunk_engine import ChunkEngine


@pytest.fixture
def storage():
    """In-memory database for testing."""
    storage = Storage(db_path=":memory:")
    yield storage
    storage.conn.close()


@pytest.fixture
def api_client():
    """Real API client for LLM calls."""
    return ExternalAPIClient()


@pytest.fixture
def scrubber(storage, api_client):
    """FactScrubber for extracting block-level facts."""
    return FactScrubber(storage, api_client)


@pytest.fixture
def chunk_engine():
    """ChunkEngine for generating test chunks."""
    return ChunkEngine()


@pytest.fixture
def profile_manager(storage):
    """UserProfileManager for Scribe."""
    return UserProfileManager(storage)


@pytest.fixture
def scribe(api_client, profile_manager):
    """Scribe for extracting user-level facts."""
    return Scribe(api_client, profile_manager)


@pytest.fixture
def governor(storage, api_client):
    """Lattice (Governor) for routing and fact retrieval."""
    return Lattice(storage, api_client)


@pytest.fixture
def hydrator(storage):
    """ContextHydrator for building LLM context."""
    return ContextHydrator(storage)


@pytest.fixture
def engine(storage, api_client, governor, hydrator, scribe):
    """ConversationEngine for E2E testing."""
    return ConversationEngine(storage, api_client, governor, hydrator, scribe)


class TestFactConflictResolution:
    """Test 7A: API Key Rotation - Block-level fact updates."""
    
    def test_api_key_rotation_conflict(self, engine, storage, scrubber, chunk_engine):
        """
        Scenario: User stores API key, then rotates it weeks later.
        Expected: System returns the MOST RECENT key when asked.
        
        Turn 1: "My API Key is ABC123." (Fact stored with timestamp T1)
        Turn 2: "I rotated my keys. The new API Key is XYZ789." (Fact stored with timestamp T2)
        Turn 3: "What is my API key?" (Should retrieve XYZ789, not ABC123)
        """
        print("\n" + "="*80)
        print("TEST 7A: API Key Rotation (Block-Level Fact Conflict)")
        print("="*80)
        
        # === TURN 1: Store original API key ===
        print("\n📝 TURN 1: Storing original API key (ABC123)")
        message_1 = "My API Key for the weather service is ABC123. Can you help me set up a dashboard?"
        chunks_1 = chunk_engine.chunk_turn(message_1, "turn_001", span_id="span_001")
        
        # Extract facts (FactScrubber should detect "API Key = ABC123")
        facts_1 = asyncio.run(scrubber.extract_and_save(
            turn_id="turn_001",
            message_text=message_1,
            chunks=chunks_1,
            span_id="span_001",
            block_id="bb_test_001"
        ))
        
        print(f"   ✅ Facts extracted: {len(facts_1)}")
        for fact in facts_1:
            print(f"      - {fact.key} = {fact.value} (category: {fact.category})")
        
        # Verify fact was saved
        stored_fact_1 = storage.query_fact_store("API Key")
        if not stored_fact_1:
            # Try alternate key patterns
            stored_fact_1 = storage.query_fact_store("weather_api_key") or storage.query_fact_store("ABC123")
        
        assert stored_fact_1 is not None, "Original API key should be stored"
        print(f"   ✅ Stored fact: {stored_fact_1['key']} = {stored_fact_1['value']}")
        timestamp_1 = stored_fact_1['created_at']
        print(f"   📅 Timestamp 1: {timestamp_1}")
        
        # === TURN 2: Rotate API key (simulate time passing) ===
        print("\n📝 TURN 2: Rotating API key to XYZ789 (weeks later)")
        
        # Simulate time passing (in real scenario, this would be days/weeks later)
        import time
        time.sleep(0.1)  # Small delay to ensure different timestamp
        
        message_2 = "I rotated my keys. The new API Key for the weather service is XYZ789."
        chunks_2 = chunk_engine.chunk_turn(message_2, "turn_002", span_id="span_001")
        
        facts_2 = asyncio.run(scrubber.extract_and_save(
            turn_id="turn_002",
            message_text=message_2,
            chunks=chunks_2,
            span_id="span_001",
            block_id="bb_test_001"
        ))
        
        print(f"   ✅ Facts extracted: {len(facts_2)}")
        for fact in facts_2:
            print(f"      - {fact.key} = {fact.value} (category: {fact.category})")
        
        # === VERIFICATION: Check which key is returned ===
        print("\n🔍 VERIFICATION: Querying for current API key")
        
        # Check the database directly - should return MOST RECENT (XYZ789)
        current_fact = storage.query_fact_store("API Key")
        if not current_fact:
            current_fact = storage.query_fact_store("weather_api_key") or storage.query_fact_store("XYZ789")
        
        assert current_fact is not None, "Current API key should be stored"
        print(f"   📊 Retrieved fact: {current_fact['key']} = {current_fact['value']}")
        print(f"   📅 Timestamp: {current_fact['created_at']}")
        
        # === CRITICAL VALIDATION ===
        print("\n⚔️  CONFLICT RESOLUTION TEST:")
        print(f"   - Original key (T1): ABC123 @ {timestamp_1}")
        print(f"   - Updated key (T2): {current_fact['value']} @ {current_fact['created_at']}")
        
        # The system should return the MOST RECENT value
        assert "XYZ789" in current_fact['value'], \
            f"FAILED: System returned old key! Expected XYZ789, got {current_fact['value']}"
        
        assert current_fact['created_at'] > timestamp_1, \
            "FAILED: Returned fact timestamp is not newer than original"
        
        print(f"\n   ✅ SUCCESS: System correctly returned the MOST RECENT key (XYZ789)")
        print(f"   ✅ Timestamp-based conflict resolution working!")
        
        # === BONUS: Check if BOTH facts exist in database ===
        print("\n📚 Database State Check:")
        cursor = storage.conn.cursor()
        cursor.execute("""
            SELECT key, value, created_at 
            FROM fact_store 
            WHERE key LIKE '%API%' OR value LIKE '%ABC123%' OR value LIKE '%XYZ789%'
            ORDER BY created_at ASC
        """)
        all_facts = cursor.fetchall()
        
        print(f"   Total facts in database: {len(all_facts)}")
        for i, (key, value, created_at) in enumerate(all_facts, 1):
            print(f"   {i}. {key} = {value} @ {created_at}")
        
        print("\n" + "="*80)
        print("TEST 7A: ✅ PASSED")
        print("="*80)


class TestUserProfileConflict:
    """Test 7B: Vegetarian Conflict - User profile vs conversation context."""
    
    def test_vegetarian_steakhouse_conflict(self, engine, scribe, profile_manager, storage):
        """
        Scenario: User states they are vegetarian (user-level fact), 
                  then later says they're going to a steakhouse.
        
        Expected: System acknowledges the conflict and suggests vegetarian options.
        
        Turn 1 (Block A): "I am strictly a vegetarian."
                          → Scribe updates user profile: dietary_preference = "vegetarian"
        
        Turn 2 (Block B): "I'm going to a steakhouse tonight. What should I order?"
                          → Expected: LLM sees conflict
                          → Response: "I thought you were vegetarian? Try the salad..."
                          OR: "If you're eating meat now, get the Ribeye."
        
        FAILURE CONDITION: Blindly recommending steak without acknowledging vegetarian fact.
        """
        print("\n" + "="*80)
        print("TEST 7B: Vegetarian → Steakhouse (User Profile Conflict)")
        print("="*80)
        
        # === TURN 1: Declare vegetarian preference ===
        print("\n📝 TURN 1: User declares vegetarian preference")
        query_1 = "I am strictly a vegetarian. I don't eat any meat or fish."
        
        # Run Scribe to extract user-level fact
        asyncio.run(scribe.run_scribe_agent(query_1))
        
        # Verify Scribe updated user profile
        profile_context = profile_manager.get_user_profile_context()
        print(f"   📊 Updated user profile:")
        print(f"   {profile_context[:500]}...")
        
        # Check if vegetarian constraint was added
        # Note: Scribe might categorize this as a "constraint" or "entity"
        assert "vegetarian" in profile_context.lower() or "diet" in profile_context.lower(), \
            "Scribe should have extracted dietary preference"
        
        print(f"   ✅ Scribe extracted dietary preference")
        
        # === TURN 2: Steakhouse scenario (contradictory context) ===
        print("\n📝 TURN 2: User going to steakhouse (contradictory context)")
        query_2 = "I'm going to a steakhouse tonight. What should I order?"
        
        # Run full E2E conversation (includes Scribe + Governor + Hydrator + LLM)
        response = asyncio.run(engine.process_user_query(query_2))
        
        print(f"\n   🤖 LLM Response:")
        print(f"   {response[:500]}...")
        
        # === CRITICAL VALIDATION ===
        print("\n⚔️  CONFLICT RESOLUTION TEST:")
        print(f"   - User Profile: Vegetarian (from Turn 1)")
        print(f"   - Current Context: Steakhouse (Turn 2)")
        print(f"   - Expected: LLM should acknowledge conflict OR suggest vegetarian options")
        
        # Check if response acknowledges the conflict
        conflict_acknowledged = any([
            "vegetarian" in response.lower(),
            "salad" in response.lower(),
            "meat" in response.lower() and "don't" in response.lower(),
            "fish" in response.lower() and ("no" in response.lower() or "avoid" in response.lower())
        ])
        
        # Check if response blindly recommends steak (FAILURE)
        blind_recommendation = any([
            "ribeye" in response.lower() and "vegetarian" not in response.lower(),
            "steak" in response.lower() and "vegetarian" not in response.lower() and "salad" not in response.lower(),
            "filet" in response.lower() and "vegetarian" not in response.lower()
        ])
        
        print(f"\n   📊 Response Analysis:")
        print(f"   - Conflict acknowledged: {conflict_acknowledged}")
        print(f"   - Blind steak recommendation (FAIL): {blind_recommendation}")
        
        assert conflict_acknowledged, \
            "FAILED: LLM did not acknowledge vegetarian preference or suggest alternatives"
        
        assert not blind_recommendation, \
            "FAILED: LLM blindly recommended meat without mentioning vegetarian preference"
        
        print(f"\n   ✅ SUCCESS: System acknowledged user profile conflict!")
        print(f"   ✅ LLM response is context-aware and references dietary preference")
        
        print("\n" + "="*80)
        print("TEST 7B: ✅ PASSED")
        print("="*80)


class TestTimestampOrdering:
    """Test 7C: Verify timestamp-based retrieval ordering."""
    
    def test_multiple_updates_same_key(self, storage, scrubber, chunk_engine):
        """
        Create 5 facts with the same key at different timestamps.
        Verify that query_fact_store always returns the MOST RECENT.
        """
        print("\n" + "="*80)
        print("TEST 7C: Timestamp Ordering (Multiple Updates)")
        print("="*80)
        
        key = "favorite_color"
        values = ["Blue", "Red", "Green", "Yellow", "Purple"]
        
        print(f"\n📝 Creating 5 facts for key '{key}' with different values:")
        
        for i, color in enumerate(values, 1):
            message = f"My favorite color is {color}."
            chunks = chunk_engine.chunk_turn(message, f"turn_{i:03d}", span_id=f"span_{i:03d}")
            
            facts = asyncio.run(scrubber.extract_and_save(
                turn_id=f"turn_{i:03d}",
                message_text=message,
                chunks=chunks,
                span_id=f"span_{i:03d}"
            ))
            
            print(f"   {i}. Stored: {color} @ {datetime.now().isoformat()}")
            
            # Small delay to ensure different timestamps
            import time
            time.sleep(0.05)
        
        # === VERIFICATION ===
        print(f"\n🔍 Querying for key: '{key}'")
        result = storage.query_fact_store(key)
        
        if not result:
            # Try alternate key patterns
            result = storage.query_fact_store("color") or storage.query_fact_store("favorite")
        
        assert result is not None, f"Should retrieve fact for key '{key}'"
        
        print(f"   📊 Retrieved: {result['key']} = {result['value']}")
        print(f"   📅 Timestamp: {result['created_at']}")
        
        # === CRITICAL VALIDATION ===
        print(f"\n⚔️  TIMESTAMP ORDERING TEST:")
        print(f"   - Expected: {values[-1]} (most recent)")
        print(f"   - Actual: {result['value']}")
        
        assert values[-1] in result['value'], \
            f"FAILED: Expected most recent value '{values[-1]}', got '{result['value']}'"
        
        print(f"\n   ✅ SUCCESS: System returned the MOST RECENT value")
        
        # === BONUS: Show all facts in database ===
        print(f"\n📚 Database State (all '{key}' facts):")
        cursor = storage.conn.cursor()
        cursor.execute("""
            SELECT value, created_at 
            FROM fact_store 
            WHERE key LIKE ?
            ORDER BY created_at ASC
        """, (f"%{key}%",))
        
        all_facts = cursor.fetchall()
        print(f"   Total facts: {len(all_facts)}")
        for i, (value, timestamp) in enumerate(all_facts, 1):
            marker = " ← RETURNED" if value == result['value'] else ""
            print(f"   {i}. {value} @ {timestamp}{marker}")
        
        print("\n" + "="*80)
        print("TEST 7C: ✅ PASSED")
        print("="*80)


if __name__ == "__main__":
    """
    Run tests individually for debugging:
    
    python -m pytest tests/test_phase_11_9_e_fact_conflicts.py::TestFactConflictResolution::test_api_key_rotation_conflict -v -s
    python -m pytest tests/test_phase_11_9_e_fact_conflicts.py::TestUserProfileConflict::test_vegetarian_steakhouse_conflict -v -s
    python -m pytest tests/test_phase_11_9_e_fact_conflicts.py::TestTimestampOrdering::test_multiple_updates_same_key -v -s
    """
    pytest.main([__file__, "-v", "-s"])
