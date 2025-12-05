import unittest
from datetime import datetime
from memory.tabula_rasa import TabulaRasa, TopicShiftResult
from memory.storage import Storage
from memory.models import Span

class MockTopicExtractor:
    def __init__(self, topics):
        self.topics = topics
    
    def extract(self, query):
        return self.topics.get(query, [])

class MockTopic:
    def __init__(self, keyword, confidence):
        self.keyword = keyword
        self.confidence = confidence

class TestTabulaRasa(unittest.TestCase):
    def setUp(self):
        self.storage = Storage("test_tabula_rasa.db")
        self.tabula = TabulaRasa(self.storage)
        
    def tearDown(self):
        self.storage.close()
        import os
        if os.path.exists("test_tabula_rasa.db"):
            os.remove("test_tabula_rasa.db")

    def test_no_active_span_triggers_shift(self):
        # If no span exists, it should trigger a shift (creation)
        result = self.tabula.check_for_shift("Hello world", None)
        self.assertTrue(result.is_shift)
        self.assertEqual(result.reason, "No active span")

    def test_continuation_does_not_shift(self):
        span = Span(
            span_id="span_1", day_id="day_1", 
            created_at=datetime.now(), last_active_at=datetime.now(),
            topic_label="Cars"
        )
        # "That is cool" -> "That" is a continuation marker
        result = self.tabula.check_for_shift("That is cool", span)
        self.assertFalse(result.is_shift)
        self.assertEqual(result.reason, "Detected continuation pattern")

    def test_strong_topic_shift(self):
        span = Span(
            span_id="span_1", day_id="day_1", 
            created_at=datetime.now(), last_active_at=datetime.now(),
            topic_label="Cooking"
        )
        
        # Mock the extractor to return a strong "Physics" topic for this query
        mock_extractor = MockTopicExtractor({
            "Tell me about quantum physics": [MockTopic("Quantum Physics", 0.95)]
        })
        self.tabula.topic_extractor = mock_extractor
        
        result = self.tabula.check_for_shift("Tell me about quantum physics", span)
        self.assertTrue(result.is_shift)
        self.assertEqual(result.new_topic_label, "Quantum Physics")

if __name__ == '__main__':
    unittest.main()
