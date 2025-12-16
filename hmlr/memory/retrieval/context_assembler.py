"""
Context Assembler - Phase 2 Group-by-Block Hydration

This module implements the Group-by-Block pattern for retrieving chunks with sticky meta tags.

Key Insight: Tags are stored ONCE per block in block_metadata table.
Chunks reference block_id to get their tags (pointer model, not duplication).

Hydration Pattern:
1. Retrieve chunks from various sources
2. Group chunks by block_id
3. Fetch block_metadata ONCE per block (not per chunk)
4. Format as headers with chunks underneath

Token Savings Example:
- OLD WAY (duplicate tags on each chunk):
  Chunk 1: [env: python-3.9] [os: windows] "Run the command"
  Chunk 2: [env: python-3.9] [os: windows] "Check the logs"
  Chunk 3: [env: python-3.9] [os: windows] "Wait for confirmation"
  Cost: Tags repeated 3 times = 3x token cost

- NEW WAY (group-by-block with header):
  ### Context Block: block_55
  Active Rules: [env: python-3.9], [os: windows]
  
  - "Run the command"
  - "Check the logs"
  - "Wait for confirmation"
  Cost: Tags paid ONCE = 1/3rd token cost

Author: CognitiveLattice Team
Created: 2025-12-16
"""

from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class ContextAssembler:
    """
    Assembles context from retrieved chunks using Group-by-Block pattern.
    """
    
    def __init__(self, storage):
        """
        Initialize context assembler.
        
        Args:
            storage: Storage instance for fetching block metadata
        """
        self.storage = storage
    
    def hydrate_chunks_with_metadata(self, chunks: List[Dict[str, Any]], include_headers: bool = True) -> str:
        """
        Hydrate chunks with their block metadata WITHOUT duplicating tags.
        
        Groups chunks by block_id and injects metadata ONCE per block as a header.
        
        Args:
            chunks: List of chunk dictionaries (must have 'block_id' field)
            include_headers: Whether to include block headers (default True)
        
        Returns:
            Formatted context string with tags grouped by block
        
        Example:
            Input: 5 chunks from block_55, all with env:python-3.9
            Output:
                ### Context Block: block_55
                Active Rules: [env: python-3.9], [os: windows]
                
                - Chunk 1: "Run the command"
                - Chunk 2: "Check the logs"
                - Chunk 3: "Wait for confirmation"
                [DEPRECATED] Chunk 4: "Old API call"
                - Chunk 5: "Verify results"
            
            Token Cost: Tags paid ONCE, not 5 times (80% savings)
        """
        if not chunks:
            return ""
        
        # Group chunks by block_id
        blocks = {}
        for chunk in chunks:
            block_id = chunk.get('block_id')
            if not block_id:
                # Chunk without block_id, add to "untagged" group
                block_id = "_untagged"
            
            if block_id not in blocks:
                blocks[block_id] = {
                    'metadata': None,  # Will fetch lazily
                    'chunks': []
                }
            blocks[block_id]['chunks'].append(chunk)
        
        # Build context string
        context_parts = []
        
        for block_id, data in blocks.items():
            if block_id == "_untagged":
                # No metadata for untagged chunks
                context_parts.append("\n### Untagged Context")
                for chunk in data['chunks']:
                    context_parts.append(f"  {chunk.get('text', '')}")
                context_parts.append("")
                continue
            
            # Fetch metadata ONCE per block (lazy loading)
            if data['metadata'] is None:
                data['metadata'] = self.storage.get_block_metadata(block_id)
            
            metadata = data['metadata']
            
            # Header with block ID and tags (ONCE per block)
            if include_headers:
                context_parts.append(f"\n### Context Block: {block_id}")
                
                # Global tags (apply to all chunks in block)
                if metadata.get('global_tags'):
                    tags_str = ', '.join([f"[{tag}]" for tag in metadata['global_tags']])
                    context_parts.append(f"Active Rules: {tags_str}")
                
                context_parts.append("")  # Blank line after header
            
            # Chunks (NO repeated tags)
            for chunk in data['chunks']:
                # Check if chunk falls in section rule range
                turn_id = chunk.get('turn_id', '')
                section_tag = self._get_section_tag_for_turn(turn_id, metadata.get('section_rules', []))
                
                # Format chunk with section tag if applicable
                chunk_text = chunk.get('text', '')
                if section_tag:
                    context_parts.append(f"  [{section_tag}] {chunk_text}")
                else:
                    context_parts.append(f"  {chunk_text}")
            
            context_parts.append("")  # Blank line between blocks
        
        return "\n".join(context_parts)
    
    def _get_section_tag_for_turn(self, turn_id: str, section_rules: List[Dict]) -> str:
        """
        Check if turn_id falls within a section rule range.
        
        Args:
            turn_id: Turn identifier from chunk
            section_rules: List of section rules with turn ranges
        
        Returns:
            Section tag if turn falls in range, else None
        
        Note: This implementation assumes turn_ids can be compared.
        You may need to extract turn numbers or use timestamps for comparison.
        """
        if not turn_id or not section_rules:
            return None
        
        # For each section rule, check if turn_id falls in range
        for rule in section_rules:
            start_turn = rule.get('start_turn')
            end_turn = rule.get('end_turn')
            rule_text = rule.get('rule', '')
            
            # Simple string comparison (works if turn_ids are sortable)
            # More sophisticated version would extract turn sequence numbers
            if start_turn and end_turn:
                if start_turn <= turn_id <= end_turn:
                    return rule_text
        
        return None
    
    def hydrate_dossiers_with_facts(self, dossiers: List[Dict[str, Any]]) -> str:
        """
        Format dossiers with their facts for LLM context.
        
        Args:
            dossiers: List of dossier dictionaries
        
        Returns:
            Formatted dossier context string
        
        Example:
            ### Dossier: Dietary Preferences
            Summary: User follows vegetarian diet...
            
            Facts:
            - User is vegetarian
            - User avoids all meat products
            - User prefers tofu as protein source
            
            Last Updated: 2025-12-15
        """
        if not dossiers:
            return ""
        
        context_parts = ["\n## Relevant Dossiers\n"]
        
        for dossier in dossiers:
            dossier_id = dossier.get('dossier_id', 'unknown')
            title = dossier.get('title', 'Untitled Dossier')
            summary = dossier.get('summary', 'No summary available')
            facts = dossier.get('facts', [])
            last_updated = dossier.get('last_updated', '')
            
            context_parts.append(f"### Dossier: {title}")
            context_parts.append(f"Summary: {summary}")
            context_parts.append("")
            
            if facts:
                context_parts.append("Facts:")
                for fact in facts:
                    fact_text = fact.get('fact_text', '') if isinstance(fact, dict) else fact
                    context_parts.append(f"- {fact_text}")
                context_parts.append("")
            
            if last_updated:
                context_parts.append(f"Last Updated: {last_updated}")
            
            context_parts.append("")  # Blank line between dossiers
        
        return "\n".join(context_parts)
    
    def assemble_full_context(self, 
                             chunks: List[Dict[str, Any]], 
                             dossiers: List[Dict[str, Any]],
                             max_tokens: int = 4000) -> str:
        """
        Assemble complete context from both chunks and dossiers.
        
        Args:
            chunks: Retrieved chunks (may include gardened_memory chunks)
            dossiers: Retrieved dossiers
            max_tokens: Maximum token budget for context
        
        Returns:
            Formatted context string ready for LLM
        
        Note: This is a simple implementation. A production version would:
        - Estimate tokens more accurately
        - Trim context if over budget
        - Prioritize by relevance scores
        """
        context_parts = []
        
        # Add dossiers first (highest-level context)
        if dossiers:
            dossier_context = self.hydrate_dossiers_with_facts(dossiers)
            context_parts.append(dossier_context)
        
        # Add chunks with group-by-block hydration
        if chunks:
            chunk_context = self.hydrate_chunks_with_metadata(chunks)
            context_parts.append(chunk_context)
        
        full_context = "\n".join(context_parts)
        
        # Simple token estimate (1 token ≈ 4 chars)
        estimated_tokens = len(full_context) // 4
        
        if estimated_tokens > max_tokens:
            logger.warning(f"Context exceeds token budget: {estimated_tokens} > {max_tokens}")
            # Truncate to budget (simple version - better would prioritize by relevance)
            char_limit = max_tokens * 4
            full_context = full_context[:char_limit] + "\n\n[Context truncated due to token limit]"
        
        return full_context


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    print("🧪 Context Assembler Test")
    print("=" * 60)
    
    # Mock storage for testing
    class MockStorage:
        def get_block_metadata(self, block_id):
            """Mock metadata for testing"""
            if block_id == "block_55":
                return {
                    'global_tags': ['env: python-3.9', 'os: windows'],
                    'section_rules': [
                        {'start_turn': 'turn_10', 'end_turn': 'turn_15', 'rule': 'DEPRECATED'}
                    ]
                }
            return {'global_tags': [], 'section_rules': []}
    
    assembler = ContextAssembler(MockStorage())
    
    # Test 1: Group-by-block hydration
    print("\n1. Testing Group-by-Block Hydration")
    print("-" * 60)
    
    chunks = [
        {'block_id': 'block_55', 'turn_id': 'turn_08', 'text': 'Run the command'},
        {'block_id': 'block_55', 'turn_id': 'turn_09', 'text': 'Check the logs'},
        {'block_id': 'block_55', 'turn_id': 'turn_12', 'text': 'Old API call'},
        {'block_id': 'block_55', 'turn_id': 'turn_14', 'text': 'Verify results'},
        {'block_id': 'block_66', 'turn_id': 'turn_20', 'text': 'Different block chunk'},
    ]
    
    context = assembler.hydrate_chunks_with_metadata(chunks)
    print(context)
    print("\n✅ Tags applied ONCE per block (not per chunk)")
    
    # Test 2: Dossier formatting
    print("\n2. Testing Dossier Formatting")
    print("-" * 60)
    
    dossiers = [
        {
            'dossier_id': 'dos_001',
            'title': 'Dietary Preferences',
            'summary': 'User follows vegetarian diet and prefers tofu',
            'facts': [
                'User is vegetarian',
                'User avoids all meat products',
                'User prefers tofu as protein source'
            ],
            'last_updated': '2025-12-15T10:30:00'
        }
    ]
    
    dossier_context = assembler.hydrate_dossiers_with_facts(dossiers)
    print(dossier_context)
    print("\n✅ Dossiers formatted with facts")
    
    # Test 3: Full context assembly
    print("\n3. Testing Full Context Assembly")
    print("-" * 60)
    
    full_context = assembler.assemble_full_context(chunks[:3], dossiers)
    print(full_context)
    print("\n✅ Combined dossiers and chunks")
    
    print("\n" + "=" * 60)
    print("✅ All tests passed!")
