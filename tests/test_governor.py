import unittest
from unittest.mock import MagicMock
from memory.retrieval.lattice import TheGovernor, MemoryCandidate
from memory.retrieval.hmlr_hydrator import Hydrator
from memory.models import ConversationTurn
from datetime import datetime

class TestGovernorAndHydrator(unittest.TestCase):
    def test_governor_filtering(self):
        # Mock API Client
        mock_api = MagicMock()
        # Mock response: Governor approves index 0 and 2
        mock_api.query_external_api.return_value = '{"approved_indices": [0, 2]}'
        
        governor = TheGovernor(mock_api)
        
        candidates = [
            MemoryCandidate(memory_id="mem_1", content_preview="Relevant info about cats", score=0.9, source_type="turn"),
            MemoryCandidate(memory_id="mem_2", content_preview="Irrelevant info about dogs", score=0.5, source_type="turn"),
            MemoryCandidate(memory_id="mem_3", content_preview="Relevant info about kittens", score=0.8, source_type="turn"),
        ]
        
        approved_ids = governor.govern("Tell me about cats", candidates)
        
        self.assertEqual(approved_ids, ["mem_1", "mem_3"])
        
    def test_hydrator(self):
        mock_storage = MagicMock()
        
        # Mock turns
        turn1 = ConversationTurn(
            turn_id="mem_1", session_id="s1", day_id="d1", timestamp=datetime(2025, 10, 10, 10, 0),
            user_message="Hi", assistant_response="Hello", turn_sequence=1
        )
        turn2 = ConversationTurn(
            turn_id="mem_2", session_id="s1", day_id="d1", timestamp=datetime(2025, 10, 10, 10, 5),
            user_message="Bye", assistant_response="Goodbye", turn_sequence=2
        )
        
        mock_storage.get_turn_by_id.side_effect = lambda x: turn1 if x == "mem_1" else (turn2 if x == "mem_2" else None)
        
        hydrator = Hydrator(mock_storage, token_limit=1000)
        
        # Test hydrate
        memories = hydrator.hydrate(["mem_1", "mem_2"])
        self.assertEqual(len(memories), 2)
        self.assertEqual(memories[0].turn_id, "mem_1")
        
        # Test build_context_string
        context_str = hydrator.build_context_string(memories)
        self.assertIn("User: Hi", context_str)
        self.assertIn("User: Bye", context_str)
        self.assertIn("[ref:mem_1]", context_str)

if __name__ == '__main__':
    unittest.main()
