"""
Quick Keyword Extractor - Phase 3 Enhancement

Extracts keywords from a query for context retrieval.

Two modes:
1. Fast heuristic mode (no LLM) - for speed
2. LLM mode (GPT-4.1-nano) - for quality

This enables:
1. Retrieve recent conversation context
2. Diagnose intent WITH context (not blind)
3. More accurate intent classification
"""

import re
from typing import List, Optional

def extract_llm_keywords(query: str, api_client=None) -> List[str]:
    """
    High-quality keyword extraction using LLM (GPT-4.1-nano).
    Fast and cheap (~$0.00001 per query).
    
    Args:
        query: User's query text
        api_client: ExternalAPIClient instance (optional)
        
    Returns:
        List of 5-10 high-quality keywords for retrieval
    """
    if not api_client:
        # Fallback to heuristic if no API client
        return extract_quick_keywords(query)
    
    try:
        prompt = f"""Extract 3-7 important keywords from this user query for semantic search.

Rules:
- Focus on NOUNS (topics, entities, concepts)
- Include KEY VERBS only if they change meaning (e.g., "grow", "fix", "build")
- EXCLUDE: filler words (remember, told, before, please, can, you), meta-terms (query, search, prompt)
- EXCLUDE: conversational phrases (do you, can you, I want)

Example:
Query: "do you remember what you told me about tomatoes?"
Keywords: tomatoes, growing, gardening

Query: "can you help me create a plan to run for 7 days?"
Keywords: running plan, 7 days, fitness

Query: "{query}"
Keywords:"""
        
        response = api_client.query_external_api(prompt)
        
        # Parse comma-separated keywords
        keywords = [kw.strip() for kw in response.split(',')]
        keywords = [kw for kw in keywords if kw and len(kw) > 2][:10]  # Max 10
        
        print(f"   🤖 LLM extracted keywords: {keywords}")
        return keywords if keywords else extract_quick_keywords(query)
        
    except Exception as e:
        print(f"   ⚠️ LLM keyword extraction failed: {e}, falling back to heuristic")
        return extract_quick_keywords(query)

def extract_quick_keywords(query: str) -> List[str]:
    """
    Fast, heuristic-based keyword extraction.
    No LLM calls, just pattern matching.
    
    Args:
        query: User's query text
        
    Returns:
        List of 3-8 keywords for retrieval
    """
    # Remove common stop words
    stop_words = {
        'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'should',
        'could', 'can', 'may', 'might', 'must', 'i', 'you', 'he', 'she', 'it',
        'we', 'they', 'them', 'their', 'this', 'that', 'these', 'those',
        'what', 'which', 'who', 'when', 'where', 'why', 'how', 'of', 'to',
        'in', 'on', 'at', 'by', 'for', 'with', 'from', 'about', 'as', 'into',
        'through', 'during', 'before', 'after', 'above', 'below', 'up', 'down',
        'out', 'off', 'over', 'under', 'again', 'further', 'then', 'once'
    }
    
    # Tokenize (keep alphanumeric + hyphens)
    tokens = re.findall(r'\b[\w\-]+\b', query.lower())
    
    # Filter stop words and short tokens
    keywords = [
        token for token in tokens 
        if token not in stop_words and len(token) > 2
    ]
    
    # Detect phrases (2-3 words that appear together)
    phrases = []
    words = query.lower().split()
    for i in range(len(words) - 1):
        # Check if consecutive words are both keywords
        word1 = re.sub(r'[^\w\s-]', '', words[i])
        word2 = re.sub(r'[^\w\s-]', '', words[i+1])
        
        if word1 in keywords and word2 in keywords:
            phrase = f"{word1} {word2}"
            phrases.append(phrase)
    
    # Combine: phrases (higher priority) + individual keywords
    result = phrases + keywords
    
    # Remove duplicates while preserving order
    seen = set()
    unique = []
    for item in result:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    
    # Return top 8 keywords/phrases
    return unique[:8]


def extract_reference_keywords(query: str) -> List[str]:
    """
    Extract reference keywords like "you mentioned", "earlier", "that story".
    
    These indicate the user is referencing previous conversation.
    
    Args:
        query: User's query text
        
    Returns:
        List of keywords that suggest memory lookup is needed
    """
    reference_patterns = [
        r'you (?:said|mentioned|told|explained|talked about)',
        r'(?:earlier|before|previously|last time)',
        r'(?:that|the) (?:story|conversation|topic|discussion|thing)',
        r'remember when',
        r'we (?:discussed|talked about)',
        r'(?:what|which) (?:was|were) (?:that|the)',
    ]
    
    keywords = []
    query_lower = query.lower()
    
    # Check each pattern
    for pattern in reference_patterns:
        if re.search(pattern, query_lower):
            # Extract nearby words as context
            match = re.search(pattern + r'\s+([\w\s]+)', query_lower)
            if match:
                context_words = match.group(1).strip()
                # Add the context words as keywords
                context_keywords = extract_quick_keywords(context_words)
                keywords.extend(context_keywords)
    
    return keywords


def should_retrieve_context(query: str) -> bool:
    """
    Quick heuristic: does this query likely need context?
    
    Args:
        query: User's query text
        
    Returns:
        True if context retrieval is recommended
    """
    # Reference indicators
    reference_patterns = [
        r'you (?:said|mentioned|told|explained)',
        r'(?:earlier|before|previously)',
        r'(?:that|the) (?:story|conversation|topic)',
        r'remember',
        r'we (?:discussed|talked)',
        r'(?:what|which) was',
        r'can you (?:recap|summarize|tell me about)',
    ]
    
    query_lower = query.lower()
    
    # Check if any reference pattern matches
    for pattern in reference_patterns:
        if re.search(pattern, query_lower):
            return True
    
    # Also retrieve if query is short (likely follow-up)
    word_count = len(query.split())
    if word_count <= 5:
        return True
    
    return False


if __name__ == "__main__":
    # Test cases
    test_queries = [
        "you mentioned blue blood, is that because the chemical makeup is different?",
        "what was the story about the cowboy?",
        "tell me a random fact",
        "can you elaborate on that?",
        "help me plan a trip to Paris",
        "earlier you said something about octopuses",
        "what's the weather like?",
    ]
    
    print("=" * 60)
    print("QUICK KEYWORD EXTRACTION TESTS")
    print("=" * 60)
    
    for query in test_queries:
        print(f"\nQuery: {query}")
        keywords = extract_quick_keywords(query)
        print(f"  Keywords: {keywords}")
        
        references = extract_reference_keywords(query)
        if references:
            print(f"  Reference keywords: {references}")
        
        should_retrieve = should_retrieve_context(query)
        print(f"  Should retrieve context? {should_retrieve}")
