"""
HMLR v1 End-to-End Integration Test

This test verifies the full "Forever Chat" pipeline:
1. Topic Shift Detection (Tabula Rasa)
2. Span Management (Write Path)
3. Lattice Retrieval -> Governor -> Hydrator (Read Path)
"""

import unittest
import asyncio
import json
from unittest.mock import MagicMock, patch
from datetime import datetime

from core.conversation_engine import ConversationEngine
from core.component_factory import ComponentFactory
from memory.models import ConversationTurn, Span
from memory.storage import Storage

class TestHMLRE2E(unittest.TestCase):
    def setUp(self):
        # Use in-memory DB for testing
        self.storage = Storage(":memory:")
        
        # Create components using factory but with our storage
        # We need to patch Storage in ComponentFactory to use our instance
        with patch('core.component_factory.Storage', return_value=self.storage):
            self.components = ComponentFactory.create_all_components()
            
        # Mock External API
        self.mock_api = MagicMock()
        self.components.external_api = self.mock_api
        
        # Create Engine
        self.engine = ComponentFactory.create_conversation_engine(self.components)
        
        # Inject mock API into engine
        self.engine.external_api = self.mock_api
        
        # Mock Governor (since it uses external API)
        # We want to control what the Governor approves
        self.engine.governor.api_client = self.mock_api

    def test_forever_chat_pipeline(self):
        """
        Simulate a conversation with topic shifts and verify memory retrieval.
        """
        async def run_test():
            print("\n🧪 Starting HMLR E2E Test...")
            
            # --- Turn 1: Discuss Project Alpha ---
            # Mock Nano Intent: Chat, Topic=Project Alpha
            self.mock_api.query_external_api.return_value = "I can help with Project Alpha." # Chat response
            
            # We need to mock the extract_metadata_with_nano call which is imported in conversation_engine
            # Since it's imported inside the method, we patch where it's defined
            
            with patch('core.llama_client.extract_metadata_with_nano') as mock_nano:
                # Setup Turn 1
                mock_nano.return_value = {
                    "intent": "chat",
                    "keywords": ["Project Alpha", "deadline"],
                    "topics": ["Project Alpha"],
                    "affect": "neutral"
                }
                self.mock_api.query_external_api.return_value = "Project Alpha is due on Friday."
                
                print("   🗣️  User: 'When is Project Alpha due?'")
                response1 = await self.engine.process_user_message("When is Project Alpha due?")
                
                # Verify Span 1 created
                active_span = self.storage.get_active_span()
                self.assertIsNotNone(active_span, "Active span should exist")
                print(f"   ✅ Span created: {active_span.span_id} ({active_span.topic_label})")
                span1_id = active_span.span_id
                
                # --- Turn 2: Switch to Project Beta (Topic Shift) ---
                # Mock Nano: Topic Shift detected
                mock_nano.return_value = {
                    "intent": "chat",
                    "keywords": ["Project Beta", "budget"],
                    "topics": ["Project Beta"],
                    "affect": "neutral"
                }
                self.mock_api.query_external_api.return_value = "Project Beta has a budget of $50k."
                
                print("   🗣️  User: 'What is the budget for Project Beta?'")
                response2 = await self.engine.process_user_message("What is the budget for Project Beta?")
                
                # Verify Span 2 created (and different from Span 1)
                active_span = self.storage.get_active_span()
                self.assertIsNotNone(active_span, "Active span should exist")
                print(f"   ✅ New Span created: {active_span.span_id} ({active_span.topic_label})")
                self.assertNotEqual(active_span.span_id, span1_id, "Should have switched to a new span")
                
                # Note: In current implementation, sliding_window doesn't strictly track span_id property 
                # unless we updated SlidingWindow model. 
                # But TabulaRasa should have triggered a span switch in storage.
                
                # --- Turn 3: Recall Project Alpha (Retrieval) ---
                # Mock Nano: Topic=Project Alpha
                mock_nano.return_value = {
                    "intent": "chat",
                    "keywords": ["Project Alpha"],
                    "topics": ["Project Alpha"],
                    "affect": "neutral"
                }
                
                # Mock Governor: Approve the memory from Turn 1
                # The Governor calls api_client.query_external_api
                # We need to make sure the mock returns a JSON list of IDs when Governor calls it
                # But query_external_api is also used for chat response.
                # We can use side_effect to return different values based on input prompt
                
                def api_side_effect(prompt, **kwargs):
                    if "You are The Governor" in prompt:
                        # The Governor expects a JSON object with "approved_indices"
                        # We'll approve all candidates found in the prompt
                        import re
                        matches = re.findall(r"\[(\d+)\] ID:", prompt)
                        indices = [int(m) for m in matches]
                        return json.dumps({"approved_indices": indices})
                    elif "extract_metadata" in prompt:
                        return '{"intent": "chat"}' # Fallback
                    else:
                        return "The deadline for Project Alpha is Friday, as mentioned earlier."

                self.mock_api.query_external_api.side_effect = api_side_effect
                
                print("   🗣️  User: 'Remind me when Alpha is due?'")
                response3 = await self.engine.process_user_message("Remind me when Alpha is due?")
                
                # Verify Retrieval
                # We can check if the Hydrator was called or if context was retrieved
                print(f"   ✅ Response: {response3.response_text}")
                print(f"   ✅ Contexts Retrieved: {response3.contexts_retrieved}")
                
                self.assertTrue(response3.contexts_retrieved > 0, "Should have retrieved context about Project Alpha")
                
        # Run async test
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run_test())
        loop.close()

if __name__ == "__main__":
    unittest.main()
