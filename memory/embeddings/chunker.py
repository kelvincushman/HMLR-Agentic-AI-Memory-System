"""
Semantic Chunker - Splits conversation turns into semantic chunks

Chunks responses by paragraphs/sentences to avoid topic dilution.
Always includes user context in each chunk for better retrieval.
"""

import re
from typing import List, Tuple


class SemanticChunker:
    """
    Splits conversation turns into semantic chunks.
    Simple strategy: chunk by paragraphs, include user context.
    """
    
    def __init__(self, max_chunk_size: int = 400):
        """
        Initialize chunker.
        
        Args:
            max_chunk_size: Max characters per chunk (default 400 ~= 100 tokens)
        """
        self.max_chunk_size = max_chunk_size
    
    def chunk_turn(self, user_message: str, assistant_response: str) -> List[str]:
        """
        Chunk a conversation turn into semantic pieces.
        
        Args:
            user_message: User's query
            assistant_response: Assistant's response
            
        Returns:
            List of chunks, each with user context included
        """
        # User context to prepend to each chunk
        user_context = f"User: {user_message}\n\nAssistant: "
        
        # If response is short, return as single chunk
        if len(assistant_response) <= self.max_chunk_size:
            return [user_context + assistant_response]
        
        # Try splitting by paragraphs first
        chunks = self._chunk_by_paragraphs(user_context, assistant_response)
        
        # If paragraphs are too long, split by sentences
        if any(len(chunk) > self.max_chunk_size * 1.5 for chunk in chunks):
            chunks = self._chunk_by_sentences(user_context, assistant_response)
        
        return chunks
    
    def _chunk_by_paragraphs(self, user_context: str, text: str) -> List[str]:
        """Split by paragraph boundaries."""
        paragraphs = re.split(r'\n\n+', text)
        chunks = []
        current_chunk = ""
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            # If adding this paragraph exceeds limit, save current chunk
            if current_chunk and len(current_chunk) + len(para) > self.max_chunk_size:
                chunks.append(user_context + current_chunk.strip())
                current_chunk = ""
            
            current_chunk += para + "\n\n"
        
        # Add final chunk
        if current_chunk.strip():
            chunks.append(user_context + current_chunk.strip())
        
        return chunks if chunks else [user_context + text]
    
    def _chunk_by_sentences(self, user_context: str, text: str) -> List[str]:
        """Split by sentence boundaries."""
        # Split on sentence endings
        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks = []
        current_chunk = ""
        
        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue
            
            # If adding this sentence exceeds limit, save current chunk
            if current_chunk and len(current_chunk) + len(sent) > self.max_chunk_size:
                chunks.append(user_context + current_chunk.strip())
                current_chunk = ""
            
            current_chunk += sent + " "
        
        # Add final chunk
        if current_chunk.strip():
            chunks.append(user_context + current_chunk.strip())
        
        return chunks if chunks else [user_context + text]
    
    def estimate_chunks(self, assistant_response: str) -> int:
        """
        Estimate how many chunks a response will produce.
        
        Args:
            assistant_response: Response text
            
        Returns:
            Estimated number of chunks
        """
        if len(assistant_response) <= self.max_chunk_size:
            return 1
        
        # Rough estimate based on length
        return max(1, len(assistant_response) // self.max_chunk_size)


# Convenience function
def chunk_conversation(user_message: str, assistant_response: str, 
                      max_chunk_size: int = 400) -> List[str]:
    """
    Quick function to chunk a conversation turn.
    
    Args:
        user_message: User's query
        assistant_response: Assistant's response
        max_chunk_size: Max characters per chunk
        
    Returns:
        List of chunks
    """
    chunker = SemanticChunker(max_chunk_size=max_chunk_size)
    return chunker.chunk_turn(user_message, assistant_response)


if __name__ == "__main__":
    # Test the chunker
    print("🧪 Testing SemanticChunker...\n")
    
    chunker = SemanticChunker(max_chunk_size=200)
    
    # Test 1: Short response (no chunking)
    user_msg = "What's a bicycle?"
    assistant_msg = "A bicycle is a two-wheeled vehicle powered by pedaling."
    
    chunks = chunker.chunk_turn(user_msg, assistant_msg)
    print(f"Test 1: Short response")
    print(f"  Chunks: {len(chunks)}")
    print(f"  Content: {chunks[0][:100]}...\n")
    
    # Test 2: Long response (paragraph chunking)
    user_msg = "Tell me about Python and JavaScript"
    assistant_msg = """Python is a high-level programming language known for its readability. It's widely used in data science, machine learning, and web development. The syntax is clean and emphasizes code readability with significant whitespace.

JavaScript, on the other hand, is primarily used for web development. It runs in browsers and enables interactive web pages. Node.js allows JavaScript to run on servers as well.

Both languages have their strengths and are popular in modern software development."""
    
    chunks = chunker.chunk_turn(user_msg, assistant_msg)
    print(f"Test 2: Long response")
    print(f"  Chunks: {len(chunks)}")
    for i, chunk in enumerate(chunks):
        print(f"  Chunk {i+1}: {len(chunk)} chars")
        print(f"    Preview: {chunk[:100]}...")
