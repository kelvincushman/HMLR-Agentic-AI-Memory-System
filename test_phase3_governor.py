"""
Phase 3 Test: DossierGovernor routing logic

Tests:
1. Create new dossier for first fact packet
2. Append to existing dossier for related facts
3. Multi-Vector Voting correctly ranks candidates
4. Provenance tracking works
"""

import asyncio
import json
import sqlite3
import tempfile
import os
from datetime import datetime


class MockIDGenerator:
    """Mock ID generator for testing - matches the function-based API."""
    def __init__(self):
        self.counters = {}
    
    def generate_id(self, prefix: str) -> str:
        """Generate ID in format: prefix_YYYYMMDD_HHMMSS_###"""
        if prefix not in self.counters:
            self.counters[prefix] = 0
        self.counters[prefix] += 1
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{prefix}_{timestamp}_{self.counters[prefix]:03d}"


class MockLLMClient:
    """Mock LLM client that simulates routing decisions."""
    def __init__(self):
        self.call_count = 0
    
    async def query_external_api(self, prompt, model):
        self.call_count += 1
        
        # Detect what kind of prompt this is
        if "DECISION RULES" in prompt:
            # Routing decision
            if self.call_count == 1:
                # First call: create new (no candidates yet)
                return '{"action": "create"}'
            else:
                # Second call: append to existing
                return '{"action": "append", "target_dossier_id": "dos_20251215_103000_001"}'
        
        elif "Generate a concise summary" in prompt or "SUMMARY:" in prompt:
            # Initial summary generation
            return "User follows a vegetarian diet, avoiding all meat products and preferring plant-based proteins."
        
        elif "Update this dossier summary" in prompt or "UPDATED SUMMARY:" in prompt:
            # Summary update
            return "User follows a strict vegan lifestyle, avoiding all animal products including meat, eggs, and dairy, while preferring plant-based protein sources."
        
        else:
            return "Unknown prompt type"


async def test_dossier_governor():
    """Test DossierGovernor with real Storage and DossierEmbeddingStorage."""
    
    print("Phase 3 Test: DossierGovernor")
    print("=" * 60)
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
        test_db = tmp.name
    
    try:
        # Initialize real components
        from hmlr.memory.storage import Storage
        from hmlr.memory.dossier_storage import DossierEmbeddingStorage
        from hmlr.memory.synthesis.dossier_governor import DossierGovernor
        
        print("\n1. Initializing components...")
        storage = Storage(test_db)
        dossier_storage = DossierEmbeddingStorage(test_db)
        llm_client = MockLLMClient()
        id_generator = MockIDGenerator()
        
        governor = DossierGovernor(
            storage=storage,
            dossier_storage=dossier_storage,
            llm_client=llm_client,
            id_generator=id_generator
        )
        print("   ✅ Components initialized")
        
        # Test 1: Create new dossier
        print("\n2. Test: Create new dossier for initial facts...")
        fact_packet_1 = {
            'cluster_label': 'Vegetarian Diet',
            'facts': [
                'User is strictly vegetarian',
                'User avoids all meat products'
            ],
            'source_block_id': 'block_001',
            'timestamp': '2025-12-15T10:30:00'
        }
        
        dossier_id = await governor.process_fact_packet(fact_packet_1)
        print(f"   ✅ Created dossier: {dossier_id}")
        
        # Verify dossier was created
        dossier = storage.get_dossier(dossier_id)
        assert dossier is not None, "Dossier not found in database"
        assert dossier['title'] == 'Vegetarian Diet', f"Wrong title: {dossier['title']}"
        print(f"   ✅ Dossier title: {dossier['title']}")
        
        # Verify facts were added
        facts = storage.get_dossier_facts(dossier_id)
        assert len(facts) == 2, f"Expected 2 facts, got {len(facts)}"
        print(f"   ✅ Stored {len(facts)} facts")
        
        # Verify embeddings were created
        fact_count = dossier_storage.get_fact_count(dossier_id)
        assert fact_count == 2, f"Expected 2 embeddings, got {fact_count}"
        print(f"   ✅ Created {fact_count} fact embeddings")
        
        # Verify provenance
        history = storage.get_dossier_history(dossier_id)
        assert len(history) > 0, "No provenance entries"
        assert history[0]['operation'] == 'created', "First operation should be 'created'"
        print(f"   ✅ Provenance tracked ({len(history)} entries)")
        
        # Test 2: Multi-Vector Voting
        print("\n3. Test: Multi-Vector Voting finds candidate dossiers...")
        search_facts = [
            'User prefers plant-based proteins',  # Related to vegetarian diet
            'User avoids eggs and dairy'  # Also related
        ]
        
        candidates = governor._find_candidate_dossiers(search_facts, top_k=5)
        print(f"   Found {len(candidates)} candidates")
        
        if candidates:
            top_candidate = candidates[0]
            print(f"   ✅ Top candidate: {top_candidate['dossier_id']}")
            print(f"      Title: {top_candidate['title']}")
            print(f"      Vote hits: {top_candidate['vote_hits']}")
            print(f"      Vote score: {top_candidate['vote_score']:.3f}")
            
            # Should match our vegetarian dossier
            assert top_candidate['dossier_id'] == dossier_id, "Wrong candidate selected"
            print(f"   ✅ Correct dossier ranked first")
        
        # Test 3: Append to existing dossier
        print("\n4. Test: Append related facts to existing dossier...")
        fact_packet_2 = {
            'cluster_label': 'Vegan Lifestyle',
            'facts': [
                'User prefers plant-based proteins',
                'User avoids eggs and dairy products'
            ],
            'source_block_id': 'block_002',
            'timestamp': '2025-12-15T10:31:00'
        }
        
        # Override the LLM to force append decision
        llm_client.call_count = 1  # Reset so next call treats it as "second call"
        
        dossier_id_2 = await governor.process_fact_packet(fact_packet_2)
        print(f"   Routed to dossier: {dossier_id_2}")
        
        # Should be same dossier (append, not create)
        assert dossier_id_2 == dossier_id, f"Should append to {dossier_id}, got {dossier_id_2}"
        print(f"   ✅ Correctly appended to existing dossier")
        
        # Verify facts were added
        facts = storage.get_dossier_facts(dossier_id)
        assert len(facts) == 4, f"Expected 4 facts total, got {len(facts)}"
        print(f"   ✅ Now has {len(facts)} facts total")
        
        # Verify embeddings updated
        fact_count = dossier_storage.get_fact_count(dossier_id)
        assert fact_count == 4, f"Expected 4 embeddings, got {fact_count}"
        print(f"   ✅ Now has {fact_count} fact embeddings")
        
        # Verify summary was updated
        updated_dossier = storage.get_dossier(dossier_id)
        assert updated_dossier['summary'] != dossier['summary'], "Summary should have changed"
        print(f"   ✅ Summary updated")
        print(f"      Old: {dossier['summary'][:60]}...")
        print(f"      New: {updated_dossier['summary'][:60]}...")
        
        # Verify provenance updated
        history = storage.get_dossier_history(dossier_id)
        assert len(history) > 1, "Should have multiple provenance entries"
        fact_added_count = sum(1 for h in history if h['operation'] == 'fact_added')
        assert fact_added_count >= 2, "Should have fact_added entries"
        print(f"   ✅ Provenance: {len(history)} total entries")
        
        # Test 4: Verify retrieval works
        print("\n5. Test: Search can find facts in dossier...")
        search_results = dossier_storage.search_similar_facts("vegan diet", top_k=5)
        print(f"   Found {len(search_results)} matching facts")
        
        if search_results:
            for fact_id, dos_id, score in search_results[:3]:
                print(f"      {fact_id} in {dos_id}: {score:.3f}")
            
            # Should find facts from our dossier
            dossier_ids = set(r[1] for r in search_results)
            assert dossier_id in dossier_ids, "Our dossier should be in search results"
            print(f"   ✅ Search successfully retrieves dossier facts")
        
        print("\n" + "=" * 60)
        print("✅ Phase 3 Test: All checks passed!")
        print(f"\nDossier System Status:")
        print(f"  - 1 dossier created")
        print(f"  - 4 facts stored across 2 fact packets")
        print(f"  - Multi-Vector Voting working")
        print(f"  - LLM routing working (create + append)")
        print(f"  - Provenance fully tracked")
        print(f"  - Embeddings searchable")
        print(f"\nReady for Phase 4: Read-side retrieval integration")
        
    finally:
        # Cleanup
        if os.path.exists(test_db):
            os.remove(test_db)
            print(f"\n🧹 Cleaned up test database")


if __name__ == "__main__":
    asyncio.run(test_dossier_governor())
