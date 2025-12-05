import unittest
import os
from datetime import datetime
from memory.models import Span, HierarchicalSummary, ConversationTurn
from memory.storage import Storage

class TestHMLRStorage(unittest.TestCase):
    def setUp(self):
        self.db_path = "test_hmlr.db"
        self.storage = Storage(self.db_path)

    def tearDown(self):
        self.storage.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_span_crud(self):
        span = Span(
            span_id="span_001",
            day_id="day_2025-10-10",
            created_at=datetime.now(),
            last_active_at=datetime.now(),
            topic_label="Test Topic",
            turn_ids=["turn_1", "turn_2"]
        )
        
        # Create
        self.storage.create_span(span)
        
        # Retrieve
        retrieved = self.storage.get_span("span_001")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.topic_label, "Test Topic")
        self.assertEqual(retrieved.turn_ids, ["turn_1", "turn_2"])
        self.assertTrue(retrieved.is_active)
        
        # Update (Close)
        self.storage.close_span("span_001")
        retrieved = self.storage.get_span("span_001")
        self.assertFalse(retrieved.is_active)

    def test_hierarchical_summary_crud(self):
        summary = HierarchicalSummary(
            summary_id="hsum_001",
            created_at=datetime.now(),
            content="This is a summary.",
            level=1,
            topics=["topic1", "topic2"],
            span_ids=["span_001"]
        )
        
        # Create
        self.storage.create_hierarchical_summary(summary)
        
        # Retrieve
        retrieved = self.storage.get_hierarchical_summary("hsum_001")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.content, "This is a summary.")
        self.assertEqual(retrieved.level, 1)
        self.assertEqual(retrieved.topics, ["topic1", "topic2"])

if __name__ == '__main__':
    unittest.main()
