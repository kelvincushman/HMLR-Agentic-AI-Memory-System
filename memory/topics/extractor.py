"""
Topic extraction from user queries.

Extracts meaningful topics/keywords from user queries to enable
topic-aware context filtering and intelligent compression.
"""

import re
from typing import List, Set, Dict
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class ExtractedTopic:
    """Represents a topic extracted from a query."""
    keyword: str
    confidence: float  # 0.0 to 1.0
    category: str  # 'primary', 'secondary', 'reference'


class TopicExtractor:
    """
    Extract topics from user queries using multiple strategies.
    
    Week 1, Day 1-2 implementation:
    - Keyword extraction (noun phrases, proper nouns)
    - Reference detection ("that Ferrari", "we discussed")
    - Multi-word topic handling
    """
    
    def __init__(self):
        # Common stop words to exclude
        self.stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'up', 'about', 'into', 'through', 'during',
            'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
            'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might',
            'can', 'tell', 'me', 'you', 'we', 'they', 'it', 'this', 'that', 'these',
            'those', 'what', 'which', 'who', 'where', 'when', 'why', 'how'
        }
        
        # Explicit reference patterns
        self.reference_patterns = [
            r'that (\w+(?:\s+\w+){0,2})',  # "that Ferrari", "that red Ferrari"
            r'the (\w+(?:\s+\w+){0,2}) (?:we|you|I) (?:discussed|mentioned|talked about)',
            r'(?:we|you|I) (?:discussed|mentioned|talked about) (?:the )?(\w+(?:\s+\w+){0,2})',
            r'as (?:we|you|I) (?:said|discussed|mentioned)',  # Detect reference without topic
            r'(?:previously|earlier|before) (?:we|you|I) (?:discussed|mentioned|talked about)',
        ]
        
        # Proper noun indicators (capitalized words not at start)
        self.proper_noun_pattern = r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b'
        
    def extract(self, query: str, debug: bool = False) -> List[ExtractedTopic]:
        """
        Extract topics from a user query.
        
        Args:
            query: User's query text
            debug: Enable debug logging
            
        Returns:
            List of ExtractedTopic objects, sorted by confidence
        """
        if debug:
            logger.info(f"🔍 Extracting topics from: '{query}'")
        
        topics: Dict[str, ExtractedTopic] = {}
        
        # Strategy 1: Detect explicit references
        reference_topics = self._extract_references(query)
        for topic in reference_topics:
            topics[topic.keyword.lower()] = topic
            if debug:
                logger.info(f"  📌 Reference detected: {topic.keyword} (confidence: {topic.confidence})")
        
        # Strategy 2: Extract proper nouns (e.g., "Ferrari", "Mars", "Python")
        proper_noun_topics = self._extract_proper_nouns(query)
        for topic in proper_noun_topics:
            key = topic.keyword.lower()
            if key not in topics:
                topics[key] = topic
                if debug:
                    logger.info(f"  🏷️  Proper noun: {topic.keyword} (confidence: {topic.confidence})")
        
        # Strategy 3: Extract significant keywords
        keyword_topics = self._extract_keywords(query)
        for topic in keyword_topics:
            key = topic.keyword.lower()
            if key not in topics:
                topics[key] = topic
                if debug:
                    logger.info(f"  🔑 Keyword: {topic.keyword} (confidence: {topic.confidence})")
        
        # Sort by confidence
        sorted_topics = sorted(topics.values(), key=lambda t: t.confidence, reverse=True)
        
        if debug:
            logger.info(f"  ✅ Extracted {len(sorted_topics)} topics")
        
        return sorted_topics
    
    def _extract_references(self, query: str) -> List[ExtractedTopic]:
        """Extract topics from explicit references like 'that Ferrari'."""
        topics = []
        query_lower = query.lower()
        
        for pattern in self.reference_patterns:
            matches = re.finditer(pattern, query_lower)
            for match in matches:
                if match.groups():
                    # Captured topic (e.g., "ferrari" from "that ferrari")
                    topic_text = match.group(1).strip()
                    topics.append(ExtractedTopic(
                        keyword=topic_text,
                        confidence=0.95,  # High confidence for explicit references
                        category='reference'
                    ))
                else:
                    # Reference detected but topic not captured
                    # Set flag for "user is referencing previous context"
                    topics.append(ExtractedTopic(
                        keyword='__REFERENCE_DETECTED__',
                        confidence=1.0,
                        category='reference'
                    ))
        
        return topics
    
    def _extract_proper_nouns(self, query: str) -> List[ExtractedTopic]:
        """Extract proper nouns (capitalized words)."""
        topics = []
        
        # Find all proper nouns (excluding first word of sentence)
        words = query.split()
        for i, word in enumerate(words):
            # Skip first word and words after punctuation
            if i == 0 or (i > 0 and words[i-1][-1] in '.!?'):
                continue
            
            # Check if word is capitalized and not a stop word
            if word[0].isupper() and word.lower() not in self.stop_words:
                # Handle multi-word proper nouns (e.g., "New York", "Machine Learning")
                topic_words = [word]
                j = i + 1
                while j < len(words) and words[j][0].isupper():
                    topic_words.append(words[j])
                    j += 1
                
                topic_text = ' '.join(topic_words)
                topics.append(ExtractedTopic(
                    keyword=topic_text,
                    confidence=0.85,  # High confidence for proper nouns
                    category='primary'
                ))
        
        return topics
    
    def _extract_keywords(self, query: str) -> List[ExtractedTopic]:
        """
        Extract significant keywords using simple heuristics.
        
        Future enhancement: Use TF-IDF or RAKE for better extraction.
        """
        topics = []
        seen_keywords = set()  # Avoid duplicates
        
        # Remove punctuation and convert to lowercase
        cleaned = re.sub(r'[^\w\s]', ' ', query.lower())
        words = cleaned.split()
        
        # Filter out stop words and short words
        significant_words = [
            word for word in words
            if word not in self.stop_words and len(word) > 3
        ]
        
        # Look for noun phrases (simple: sequences of significant words)
        i = 0
        while i < len(words):
            if words[i] not in self.stop_words and len(words[i]) > 3:
                # Check if followed by more significant words (noun phrase)
                phrase_words = [words[i]]
                j = i + 1
                while j < len(words) and j < i + 3:  # Max 3-word phrases
                    if words[j] not in self.stop_words and len(words[j]) > 3:
                        phrase_words.append(words[j])
                        j += 1
                    else:
                        break
                
                if len(phrase_words) > 1:
                    # Multi-word phrase (higher confidence)
                    phrase = ' '.join(phrase_words)
                    if phrase not in seen_keywords:
                        topics.append(ExtractedTopic(
                            keyword=phrase,
                            confidence=0.7,
                            category='primary'
                        ))
                        seen_keywords.add(phrase)
                    
                    # Also add individual words if not already added
                    for word in phrase_words:
                        if word not in seen_keywords:
                            topics.append(ExtractedTopic(
                                keyword=word,
                                confidence=0.6,
                                category='secondary'
                            ))
                            seen_keywords.add(word)
                    
                    i = j
                else:
                    # Single word
                    word = phrase_words[0]
                    if word not in seen_keywords:
                        topics.append(ExtractedTopic(
                            keyword=word,
                            confidence=0.6,
                            category='secondary'
                        ))
                        seen_keywords.add(word)
                    i += 1
            else:
                i += 1
        
        return topics
    
    def has_explicit_reference(self, query: str) -> bool:
        """
        Check if query contains explicit reference to previous context.
        
        Returns True for queries like:
        - "Tell me more about that"
        - "We discussed Mars earlier"
        - "As you mentioned..."
        """
        query_lower = query.lower()
        
        # Strong reference indicators (require word boundaries)
        strong_indicators = [
            r'\bthat\b(?! [A-Z])',  # "that" not followed by proper noun like "that Ferrari"
            r'\bthose\b',
            r'\bthese\b',
            r'\bit\b',
            r'\bthem\b',
            r'we discussed',
            r'you mentioned',
            r'we talked about',
            r'as you said',
            r'as we said',
            r'as mentioned',
        ]
        
        # Context indicators (need to be combined with other words)
        context_indicators = [
            (r'\bearlier\b', ['we', 'you', 'discussed', 'mentioned']),
            (r'\bbefore\b', ['we', 'you', 'discussed', 'mentioned', 'talked']),
            (r'\bpreviously\b', ['we', 'you', 'discussed', 'mentioned']),
        ]
        
        # Check strong indicators
        for pattern in strong_indicators:
            if re.search(pattern, query_lower):
                return True
        
        # Check context indicators (need supporting words)
        for pattern, required_words in context_indicators:
            if re.search(pattern, query_lower):
                if any(word in query_lower for word in required_words):
                    return True
        
        return False
    
    def extract_simple(self, query: str) -> List[str]:
        """
        Simplified extraction that returns just keyword strings.
        
        Convenience method for when full ExtractedTopic objects aren't needed.
        """
        topics = self.extract(query)
        return [t.keyword for t in topics if t.keyword != '__REFERENCE_DETECTED__']
