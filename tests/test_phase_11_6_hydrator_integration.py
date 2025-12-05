"""
Phase 11.6: Hydrator Integration Tests

Tests the Bridge Block hydration strategy:
- Active block: Hydrates full conversation turns verbatim
- Inactive blocks: Creates lightweight metadata placeholders
- Token budgeting and formatting
"""

import unittest
import json
from datetime import datetime
from unittest.mock import MagicMock, patch
from memory.retrieval.hmlr_hydrator import Hydrator
from memory.storage import Storage
from memory.models import ConversationTurn, Span


class TestBridgeBlockHydration(unittest.TestCase):
    """Test Bridge Block hydration strategy."""
    
    def setUp(self):
        """Create test storage and hydrator."""
        self.storage = Storage(":memory:")
        # Tables are created automatically in Storage.__init__
        self.hydrator = Hydrator(self.storage, token_limit=5000)
        
        # Create test Bridge Blocks in daily_ledger
        self._create_test_bridge_blocks()
    
    def _create_test_bridge_blocks(self):
        """Create test Bridge Blocks and spans with turns."""
        cursor = self.storage.conn.cursor()
        
        # Create AWS Bridge Block
        aws_content = {
            'topic_label': 'AWS Cloud Architecture',
            'summary': 'Discussion about serverless services and EC2 deployment strategies.',
            'keywords': ['AWS', 'serverless', 'EC2', 'Lambda'],
            'open_loops': ['Deploy Lambda function', 'Set up VPC'],
            'decisions_made': ['Use CloudFormation for IaC'],
            'user_affect': '[T2] Focused, Technical',
            'bot_persona': 'Cloud Architect'
        }
        cursor.execute("""
            INSERT INTO daily_ledger (block_id, content_json, span_id, created_at, status, exit_reason, embedding_status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            'bb_20251202_1000_aws',
            json.dumps(aws_content),
            'span_aws_123',
            '2025-12-02T10:00:00',
            'PAUSED',
            'topic_shift',
            'PENDING'
        ))
        
        # Create Mountains Bridge Block
        mountains_content = {
            'topic_label': 'Mountain Climbing Trip',
            'summary': 'Planning a climbing trip to the Rockies.',
            'keywords': ['mountains', 'climbing', 'Rockies', 'gear'],
            'open_loops': ['Buy climbing gear', 'Book cabin'],
            'decisions_made': ['Go in June'],
            'user_affect': '[T1] Excited, Adventurous',
            'bot_persona': 'Travel Guide'
        }
        cursor.execute("""
            INSERT INTO daily_ledger (block_id, content_json, span_id, created_at, status, exit_reason, embedding_status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            'bb_20251202_1100_mountains',
            json.dumps(mountains_content),
            'span_mountains_456',
            '2025-12-02T11:00:00',
            'PAUSED',
            'topic_shift',
            'PENDING'
        ))
        
        # Create CarRepair Bridge Block
        car_content = {
            'topic_label': 'Car Repair Discussion',
            'summary': 'Troubleshooting brake issues.',
            'keywords': ['car', 'brakes', 'repair', 'mechanic'],
            'open_loops': ['Get brake pads replaced'],
            'decisions_made': ['Take to shop on Friday'],
            'user_affect': '[T3] Concerned, Practical',
            'bot_persona': 'Mechanic Advisor'
        }
        cursor.execute("""
            INSERT INTO daily_ledger (block_id, content_json, span_id, created_at, status, exit_reason, embedding_status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            'bb_20251202_1200_car',
            json.dumps(car_content),
            'span_car_789',
            '2025-12-02T12:00:00',
            'PAUSED',
            'topic_shift',
            'PENDING'
        ))
        self.storage.conn.commit()
        
        # Create spans with turns (track global sequence counter)
        self.turn_counter = 0
        self._create_span_with_turns('span_aws_123', 'AWS Cloud Architecture', ['turn_aws_1', 'turn_aws_2', 'turn_aws_3'])
        self._create_span_with_turns('span_mountains_456', 'Mountain Climbing Trip', ['turn_mtn_1', 'turn_mtn_2'])
        self._create_span_with_turns('span_car_789', 'Car Repair Discussion', ['turn_car_1'])
    
    def _create_span_with_turns(self, span_id: str, topic: str, turn_ids: list):
        """Create a span and its associated turns."""
        from memory.models import Span
        
        # Create span
        span = Span(
            span_id=span_id,
            day_id='day_2025-12-02',
            created_at=datetime.now(),
            last_active_at=datetime.now(),
            topic_label=topic,
            is_active=False,
            turn_ids=turn_ids
        )
        self.storage.create_span(span)
        
        # Create turns with global unique sequences
        for turn_id in turn_ids:
            turn = ConversationTurn(
                turn_id=turn_id,
                session_id="test_session",
                day_id='day_2025-12-02',
                timestamp=datetime.now(),
                turn_sequence=self.turn_counter,  # Use global counter
                user_message=f"User message in {turn_id}",
                assistant_response=f"Assistant response in {turn_id}",
                span_id=span_id
            )
            self.storage.stage_turn_metadata(turn)
            self.turn_counter += 1  # Increment for next turn
    
    def test_active_bridge_block_hydration(self):
        """Test that active Bridge Block loads full conversation turns."""
        # Governor approves AWS Bridge Block
        approved_ids = ['bb_20251202_1000_aws']
        
        # Hydrate with AWS-related query
        hydrated = self.hydrator.hydrate(approved_ids, query="Tell me about serverless services")
        
        # Should have 3 AWS turns (verbatim)
        self.assertEqual(len(hydrated), 3)
        self.assertTrue(all('turn_aws_' in t.turn_id for t in hydrated))
        self.assertTrue(all('User message' in t.user_message for t in hydrated))
    
    def test_inactive_bridge_block_metadata(self):
        """Test that inactive Bridge Blocks create metadata placeholders."""
        # Governor approves Mountains Bridge Block
        approved_ids = ['bb_20251202_1100_mountains']
        
        # Hydrate with unrelated query (no topic match)
        hydrated = self.hydrator.hydrate(approved_ids, query="Tell me about cooking")
        
        # Should have 1 metadata placeholder (no topic match, so treated as inactive)
        # Actually, fallback uses most recent as active, so this will hydrate verbatim
        # Let's test with multiple blocks instead
        approved_ids = ['bb_20251202_1000_aws', 'bb_20251202_1100_mountains']
        hydrated = self.hydrator.hydrate(approved_ids, query="Tell me about serverless")
        
        # AWS (active): 3 turns verbatim
        # Mountains (inactive): 1 metadata placeholder
        aws_turns = [t for t in hydrated if 'turn_aws_' in t.turn_id]
        metadata_turns = [t for t in hydrated if t.session_id == 'bridge_block_metadata']
        
        self.assertEqual(len(aws_turns), 3)
        self.assertEqual(len(metadata_turns), 1)
        
        # Check metadata format
        metadata = metadata_turns[0]
        self.assertIn('Bridge Block: Mountain Climbing Trip', metadata.assistant_response)
        self.assertIn('Keywords:', metadata.assistant_response)
        self.assertIn('Open Loops:', metadata.assistant_response)
    
    def test_multiple_bridge_blocks_prioritization(self):
        """Test that query matching prioritizes correct active block."""
        # Governor approves all three Bridge Blocks
        approved_ids = [
            'bb_20251202_1000_aws',
            'bb_20251202_1100_mountains',
            'bb_20251202_1200_car'
        ]
        
        # Query about mountains
        hydrated = self.hydrator.hydrate(approved_ids, query="What about the climbing trip?")
        
        # Mountains should be active (2 turns verbatim)
        mountain_turns = [t for t in hydrated if 'turn_mtn_' in t.turn_id]
        metadata_turns = [t for t in hydrated if t.session_id == 'bridge_block_metadata']
        
        self.assertEqual(len(mountain_turns), 2)  # Mountains active: 2 turns
        self.assertEqual(len(metadata_turns), 2)  # AWS + Car inactive: 2 metadata
    
    def test_no_query_uses_most_recent(self):
        """Test that without query, most recent Bridge Block is active."""
        approved_ids = [
            'bb_20251202_1000_aws',
            'bb_20251202_1200_car'  # More recent
        ]
        
        # No query provided
        hydrated = self.hydrator.hydrate(approved_ids, query=None)
        
        # Car (most recent) should be active
        car_turns = [t for t in hydrated if 'turn_car_' in t.turn_id]
        metadata_turns = [t for t in hydrated if t.session_id == 'bridge_block_metadata']
        
        self.assertEqual(len(car_turns), 1)  # Car active: 1 turn
        self.assertEqual(len(metadata_turns), 1)  # AWS inactive: 1 metadata
    
    def test_mixed_turns_and_bridge_blocks(self):
        """Test hydration with both regular turns and Bridge Blocks."""
        # Create a regular turn with unique sequence (continue from global counter)
        regular_turn = ConversationTurn(
            turn_id='turn_regular_1',
            session_id="test_session",
            day_id='day_2025-12-02',
            timestamp=datetime.now(),
            turn_sequence=self.turn_counter,  # Use global counter
            user_message="Regular user message",
            assistant_response="Regular assistant response",
            span_id="span_regular"
        )
        self.storage.stage_turn_metadata(regular_turn)
        
        # Mix regular turn + Bridge Block
        approved_ids = ['turn_regular_1', 'bb_20251202_1000_aws']
        hydrated = self.hydrator.hydrate(approved_ids, query="Tell me about AWS")
        
        # Should have: 1 regular turn + 3 AWS turns
        regular = [t for t in hydrated if t.turn_id == 'turn_regular_1']
        aws_turns = [t for t in hydrated if 'turn_aws_' in t.turn_id]
        
        self.assertEqual(len(regular), 1)
        self.assertEqual(len(aws_turns), 3)
    
    def test_invalid_bridge_block_id(self):
        """Test handling of invalid Bridge Block IDs."""
        approved_ids = ['bb_invalid_block']
        
        # Should log warning but not crash
        hydrated = self.hydrator.hydrate(approved_ids, query="test")
        
        # No memories returned
        self.assertEqual(len(hydrated), 0)
    
    def test_bridge_block_without_span(self):
        """Test handling of Bridge Block with missing span."""
        cursor = self.storage.conn.cursor()
        
        # Create Bridge Block with non-existent span
        orphan_content = {
            'topic_label': 'Orphan Block',
            'summary': 'Block without span',
            'keywords': ['orphan'],
            'open_loops': [],
            'decisions_made': []
        }
        cursor.execute("""
            INSERT INTO daily_ledger (block_id, content_json, span_id, created_at, status, exit_reason, embedding_status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            'bb_orphan',
            json.dumps(orphan_content),
            'span_nonexistent',
            '2025-12-02T13:00:00',
            'PAUSED',
            'topic_shift',
            'PENDING'
        ))
        self.storage.conn.commit()
        
        approved_ids = ['bb_orphan']
        hydrated = self.hydrator.hydrate(approved_ids, query="test")
        
        # Should log warning but not crash
        # Since span doesn't exist, no turns hydrated
        self.assertEqual(len(hydrated), 0)


class TestContextStringFormatting(unittest.TestCase):
    """Test context string formatting with Bridge Blocks."""
    
    def setUp(self):
        """Create test hydrator."""
        self.storage = Storage(":memory:")
        # Tables are created automatically in Storage.__init__
        self.hydrator = Hydrator(self.storage, token_limit=5000)
    
    def test_metadata_placeholder_formatting(self):
        """Test that metadata placeholders format differently from regular turns."""
        # Create regular turn
        regular_turn = ConversationTurn(
            turn_id='turn_1',
            session_id="test_session",
            day_id='day_2025-12-02',
            timestamp=datetime(2025, 12, 2, 10, 0),
            turn_sequence=0,
            user_message="What is Python?",
            assistant_response="Python is a programming language.",
            span_id="span_1"
        )
        
        # Create metadata placeholder
        metadata_turn = ConversationTurn(
            turn_id='bb_metadata',
            session_id="bridge_block_metadata",
            day_id='day_2025-12-02',
            timestamp=datetime(2025, 12, 2, 11, 0),
            turn_sequence=0,
            user_message="[Topic Reference: AWS]",
            assistant_response="[Bridge Block: AWS]\nSummary: Cloud discussion\nKeywords: AWS, EC2",
            span_id="span_2"
        )
        
        context_str = self.hydrator.build_context_string([regular_turn, metadata_turn])
        
        # Regular turn should have timestamp + ref
        self.assertIn('[2025-12-02 10:00]', context_str)
        self.assertIn('[ref:turn_1]', context_str)
        self.assertIn('User: What is Python?', context_str)
        
        # Metadata should NOT have timestamp/ref (compact format)
        self.assertNotIn('[ref:bb_metadata]', context_str)
        self.assertIn('[Bridge Block: AWS]', context_str)
    
    def test_token_budget_enforcement(self):
        """Test that token budget is enforced with Bridge Blocks."""
        # Create many turns
        turns = []
        for i in range(20):
            turn = ConversationTurn(
                turn_id=f'turn_{i}',
                session_id="test_session",
                day_id='day_2025-12-02',
                timestamp=datetime(2025, 12, 2, 10, i),
                turn_sequence=i,
                user_message=f"Message {i}" * 50,  # Long message
                assistant_response=f"Response {i}" * 50,  # Long response
                span_id="span_1"
            )
            turns.append(turn)
        
        # Set low token limit
        self.hydrator.token_limit = 500
        context_str = self.hydrator.build_context_string(turns)
        
        # Should stop before all 20 turns
        turn_count = context_str.count('[ref:turn_')
        self.assertLess(turn_count, 20)
        self.assertGreater(turn_count, 0)


class TestActiveBlockIdentification(unittest.TestCase):
    """Test active Bridge Block identification logic."""
    
    def setUp(self):
        """Create test hydrator."""
        self.storage = Storage(":memory:")
        # Tables are created automatically in Storage.__init__
        self.hydrator = Hydrator(self.storage, token_limit=5000)
    
    def test_topic_label_matching(self):
        """Test that topic_label matches query."""
        blocks = [
            {
                'block_id': 'bb_1',
                'content': {
                    'topic_label': 'Python Programming',
                    'keywords': ['python', 'code']
                },
                'created_at': '2025-12-02T10:00:00'
            },
            {
                'block_id': 'bb_2',
                'content': {
                    'topic_label': 'JavaScript Tutorial',
                    'keywords': ['javascript', 'web']
                },
                'created_at': '2025-12-02T11:00:00'
            }
        ]
        
        active, inactive = self.hydrator._identify_active_block(blocks, "Tell me about Python")
        
        self.assertEqual(active['block_id'], 'bb_1')
        self.assertEqual(len(inactive), 1)
        self.assertEqual(inactive[0]['block_id'], 'bb_2')
    
    def test_keyword_matching(self):
        """Test that keywords match query."""
        blocks = [
            {
                'block_id': 'bb_1',
                'content': {
                    'topic_label': 'Cloud Architecture',
                    'keywords': ['AWS', 'serverless', 'Lambda']
                },
                'created_at': '2025-12-02T10:00:00'
            }
        ]
        
        active, inactive = self.hydrator._identify_active_block(blocks, "What about serverless?")
        
        self.assertEqual(active['block_id'], 'bb_1')
    
    def test_most_recent_fallback(self):
        """Test that most recent block is active when no match."""
        blocks = [
            {
                'block_id': 'bb_old',
                'content': {
                    'topic_label': 'Old Topic',
                    'keywords': ['old']
                },
                'created_at': '2025-12-02T10:00:00'
            },
            {
                'block_id': 'bb_new',
                'content': {
                    'topic_label': 'New Topic',
                    'keywords': ['new']
                },
                'created_at': '2025-12-02T11:00:00'
            }
        ]
        
        # Query doesn't match either
        active, inactive = self.hydrator._identify_active_block(blocks, "Tell me about something else")
        
        # Most recent should be active
        self.assertEqual(active['block_id'], 'bb_new')


if __name__ == '__main__':
    unittest.main()
