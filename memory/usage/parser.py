"""
Parse citations from LLM responses.

The LLM includes [ref:TURN_ID] markers in its responses to cite which
context turns it referenced. This parser extracts those citations.
"""

import re
from typing import List, Set, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class Citation:
    """A citation extracted from LLM response."""
    turn_id: str
    position: int  # Character position in response
    context: str   # Surrounding text for debugging


class CitationParser:
    """
    Parse [ref:TURN_ID] citations from LLM responses.
    
    Week 2, Day 1-3 implementation:
    - Extract citation markers from response
    - Strip citations before showing user
    - Track which turns were actually used
    """
    
    # Pattern: [ref:TURN_ID] where TURN_ID is like t_20251017_143055_abc123
    CITATION_PATTERN = r'\[ref:([^\]]+)\]'
    
    def __init__(self):
        self.citation_regex = re.compile(self.CITATION_PATTERN)
    
    def parse_citations(self, response: str, debug: bool = False) -> List[Citation]:
        """
        Extract all citations from LLM response.
        
        Args:
            response: LLM's response text with [ref:TURN_ID] markers
            debug: Enable debug logging
            
        Returns:
            List of Citation objects
        """
        citations = []
        
        for match in self.citation_regex.finditer(response):
            turn_id = match.group(1)
            position = match.start()
            
            # Get surrounding context (20 chars before and after)
            start = max(0, position - 20)
            end = min(len(response), match.end() + 20)
            context = response[start:end]
            
            citations.append(Citation(
                turn_id=turn_id,
                position=position,
                context=context
            ))
            
            if debug:
                logger.info(f"📎 Citation found: {turn_id} at position {position}")
                logger.info(f"   Context: ...{context}...")
        
        if debug:
            logger.info(f"✅ Extracted {len(citations)} citations")
        
        return citations
    
    def extract_turn_ids(self, response: str) -> Set[str]:
        """
        Extract just the turn IDs from citations (convenience method).
        
        Args:
            response: LLM response with [ref:TURN_ID] markers
            
        Returns:
            Set of turn IDs that were cited
        """
        citations = self.parse_citations(response)
        return {c.turn_id for c in citations}
    
    def strip_citations(self, response: str) -> str:
        """
        Remove citation markers from response before showing to user.
        
        Args:
            response: LLM response with [ref:TURN_ID] markers
            
        Returns:
            Clean response without citation markers
        """
        # Replace [ref:TURN_ID] with empty string
        cleaned = self.citation_regex.sub('', response)
        
        # Clean up any double spaces left behind
        cleaned = re.sub(r'\s+', ' ', cleaned)
        
        # Clean up spaces before punctuation
        cleaned = re.sub(r'\s+([.,!?;:])', r'\1', cleaned)
        
        return cleaned.strip()
    
    def get_citation_stats(self, response: str) -> dict:
        """
        Get statistics about citations in response.
        
        Returns:
            Dict with citation statistics
        """
        citations = self.parse_citations(response)
        turn_ids = self.extract_turn_ids(response)
        
        # Calculate citation density (citations per 100 words)
        word_count = len(response.split())
        citation_density = (len(citations) / word_count * 100) if word_count > 0 else 0.0
        
        return {
            'total_citations': len(citations),
            'unique_turns_cited': len(turn_ids),
            'word_count': word_count,
            'citation_density': round(citation_density, 2),
            'turn_ids': sorted(list(turn_ids))
        }
    
    def validate_citations(
        self,
        response: str,
        available_turn_ids: Set[str],
        debug: bool = False
    ) -> Tuple[Set[str], Set[str]]:
        """
        Validate that cited turns were actually provided in context.
        
        This helps detect hallucinated citations.
        
        Args:
            response: LLM response with citations
            available_turn_ids: Turn IDs that were provided in context
            debug: Enable debug logging
            
        Returns:
            Tuple of (valid_turn_ids, invalid_turn_ids)
        """
        cited_turn_ids = self.extract_turn_ids(response)
        
        valid = cited_turn_ids & available_turn_ids
        invalid = cited_turn_ids - available_turn_ids
        
        if debug:
            logger.info(f"📊 Citation validation:")
            logger.info(f"   Cited: {len(cited_turn_ids)} turns")
            logger.info(f"   Valid: {len(valid)} turns")
            logger.info(f"   Invalid: {len(invalid)} turns")
            
            if invalid:
                logger.warning(f"⚠️  Invalid citations (not in context): {invalid}")
        
        return valid, invalid
    
    def add_citations_to_prompt(
        self,
        context_turns: List[dict],
        instruction: str = None
    ) -> str:
        """
        Create prompt section explaining citation system to LLM.
        
        Args:
            context_turns: List of turns being provided as context
            instruction: Custom instruction (optional)
            
        Returns:
            Formatted prompt section with citation instructions
        """
        if instruction is None:
            instruction = (
                "When you reference information from the context, "
                "include a citation using [ref:TURN_ID] immediately after the referenced content. "
                "This helps track which context you're actually using."
            )
        
        # Build list of available turn IDs
        available_ids = [turn.get('turn_id', 'unknown') for turn in context_turns]
        
        prompt = f"""
{instruction}

Available context turn IDs:
{chr(10).join(f"- {turn_id}" for turn_id in available_ids)}

Example format:
"Information from retrieved context [ref:TURN_ID]."

Place the citation immediately after referencing information from the context above.
""".strip()
        
        return prompt


class SemanticFallbackParser:
    """
    Fallback parser for when LLM doesn't include citations.
    
    Uses semantic similarity to infer which context was likely used.
    """
    
    def __init__(self, similarity_threshold: float = 0.7):
        """
        Initialize semantic fallback parser.
        
        Args:
            similarity_threshold: Minimum similarity to consider a turn "used"
        """
        self.similarity_threshold = similarity_threshold
    
    def infer_used_turns(
        self,
        response: str,
        context_turns: List[dict],
        embedder=None,  # Embedding function (to be injected)
        debug: bool = False
    ) -> Set[str]:
        """
        Infer which turns were likely used based on semantic similarity.
        
        This is a fallback when LLM doesn't provide citations.
        
        Args:
            response: LLM response (without citations)
            context_turns: Context turns that were provided
            embedder: Function to embed text (optional, uses simple overlap if None)
            debug: Enable debug logging
            
        Returns:
            Set of turn IDs likely used
        """
        if debug:
            logger.info("🔍 Using semantic fallback (no citations found)")
        
        likely_used = set()
        
        if embedder is None:
            # Simple fallback: word overlap
            response_words = set(response.lower().split())
            
            for turn in context_turns:
                turn_id = turn.get('turn_id', 'unknown')
                turn_text = turn.get('full_text', '')
                turn_words = set(turn_text.lower().split())
                
                # Calculate Jaccard similarity
                intersection = response_words & turn_words
                union = response_words | turn_words
                similarity = len(intersection) / len(union) if union else 0.0
                
                if similarity >= self.similarity_threshold:
                    likely_used.add(turn_id)
                    if debug:
                        logger.info(f"   ✅ {turn_id}: {similarity:.2f} similarity")
                elif debug:
                    logger.info(f"   ❌ {turn_id}: {similarity:.2f} similarity (below {self.similarity_threshold})")
        else:
            # Use provided embedder (more accurate)
            response_embedding = embedder(response)
            
            for turn in context_turns:
                turn_id = turn.get('turn_id', 'unknown')
                turn_text = turn.get('full_text', '')
                turn_embedding = embedder(turn_text)
                
                # Cosine similarity
                similarity = self._cosine_similarity(response_embedding, turn_embedding)
                
                if similarity >= self.similarity_threshold:
                    likely_used.add(turn_id)
                    if debug:
                        logger.info(f"   ✅ {turn_id}: {similarity:.2f} similarity")
        
        if debug:
            logger.info(f"✅ Inferred {len(likely_used)} turns as likely used")
        
        return likely_used
    
    def _cosine_similarity(self, vec_a, vec_b) -> float:
        """Calculate cosine similarity between two vectors."""
        import numpy as np
        return float(np.dot(vec_a, vec_b) / (np.linalg.norm(vec_a) * np.linalg.norm(vec_b)))
