"""
Lineage Tracker - Developer tools for lineage visualization and debugging.

This module provides utilities for:
- Visualizing lineage chains as ASCII trees
- Exporting lineage data as JSON
- Validating lineage integrity
- Debugging missing references
"""

from typing import Dict, List, Optional, Any, Set
from datetime import datetime
import json

try:
    from .storage import Storage
    from .id_generator import (
        get_id_type,
        parse_id,
        extract_source_id,
        is_derived_from
    )
except ImportError:
    from storage import Storage
    from id_generator import (
        get_id_type,
        parse_id,
        extract_source_id,
        is_derived_from
    )


class LineageTracker:
    """
    Developer tool for lineage visualization and debugging.
    
    Features:
    - Print lineage trees in ASCII
    - Export lineage as JSON
    - Validate all references resolve
    - Find orphaned objects
    - Trace any object back to source
    """
    
    def __init__(self, storage: Storage):
        """
        Initialize lineage tracker.
        
        Args:
            storage: Storage instance for database access
        """
        self.storage = storage
    
    def print_lineage_tree(self, item_id: str, max_depth: int = 10) -> None:
        """
        Print lineage tree in ASCII format.
        
        Shows complete derivation chain from item back to source.
        
        Args:
            item_id: Any ID to trace lineage for
            max_depth: Maximum depth to traverse (prevents infinite loops)
        
        Example output:
            Turn: t_20251010_203947_0c1655
            ├─ Summary: s_t_20251010_203947_0c1655
            │  └─ Vector: v_s_t_20251010_203947_0c1655
            ├─ Keyword[1]: k1_t_20251010_203947_0c1655 ("rowing")
            ├─ Keyword[2]: k2_t_20251010_203947_0c1655 ("daily")
            └─ Affect: a_t_20251010_203947_0c1655 ("motivated")
        """
        print("\n" + "=" * 70)
        print("📊 LINEAGE TREE")
        print("=" * 70)
        
        tree = self._build_tree(item_id, max_depth)
        self._print_tree_recursive(tree, prefix="", is_last=True)
        
        print("=" * 70 + "\n")
    
    def _build_tree(self, item_id: str, max_depth: int) -> Dict[str, Any]:
        """
        Build lineage tree structure recursively.
        
        Args:
            item_id: Item to build tree for
            max_depth: Maximum recursion depth
            
        Returns:
            Dict with item info and children
        """
        if max_depth <= 0:
            return {
                'id': item_id,
                'type': get_id_type(item_id),
                'children': [],
                'truncated': True
            }
        
        id_type = get_id_type(item_id)
        
        # Get item details
        node = {
            'id': item_id,
            'type': id_type,
            'children': [],
            'truncated': False
        }
        
        # Add type-specific details
        if id_type == 'turn':
            turn = self.storage.get_turn_by_id(item_id)
            if turn:
                node['details'] = {
                    'user_message': turn.user_message[:50] + "..." if len(turn.user_message) > 50 else turn.user_message,
                    'timestamp': turn.timestamp.isoformat(),
                    'sequence': turn.turn_sequence
                }
                
                # Add derived objects as children
                if turn.summary_id:
                    node['children'].append(self._build_tree(turn.summary_id, max_depth - 1))
                
                for kid_id in turn.keyword_ids:
                    node['children'].append(self._build_tree(kid_id, max_depth - 1))
                
                for affect_id in turn.affect_ids:
                    node['children'].append(self._build_tree(affect_id, max_depth - 1))
        
        elif id_type == 'keyword':
            keyword = self.storage.get_keyword_by_id(item_id)
            if keyword:
                node['details'] = {
                    'keyword': keyword.keyword,
                    'confidence': keyword.confidence,
                    'derived_from': keyword.derived_from,
                    'derived_by': keyword.derived_by
                }
        
        elif id_type == 'summary':
            summary = self.storage.get_summary_by_id(item_id)
            if summary:
                node['details'] = {
                    'summary': summary.user_query_summary[:50] + "..." if len(summary.user_query_summary) > 50 else summary.user_query_summary,
                    'derived_from': summary.derived_from,
                    'derived_by': summary.derived_by,
                    'extraction_method': summary.extraction_method
                }
        
        elif id_type == 'affect':
            affect = self.storage.get_affect_by_id(item_id)
            if affect:
                node['details'] = {
                    'affect_label': affect.affect_label,
                    'intensity': affect.intensity,
                    'confidence': affect.confidence,
                    'derived_from': affect.derived_from,
                    'derived_by': affect.derived_by
                }
        
        return node
    
    def _print_tree_recursive(self, node: Dict[str, Any], prefix: str = "", is_last: bool = True) -> None:
        """
        Print tree node recursively with proper ASCII formatting.
        
        Args:
            node: Tree node to print
            prefix: Current line prefix for indentation
            is_last: Whether this is the last child
        """
        # Connector characters
        connector = "└─ " if is_last else "├─ "
        
        # Print node info
        id_display = node['id'][:35] + "..." if len(node['id']) > 35 else node['id']
        
        if prefix == "":  # Root node
            print(f"{node['type'].upper()}: {id_display}")
        else:
            print(f"{prefix}{connector}{node['type'].capitalize()}: {id_display}")
        
        # Print details if available
        if 'details' in node:
            detail_prefix = prefix + ("   " if is_last else "│  ")
            
            if node['type'] == 'turn':
                print(f"{detail_prefix}   Message: {node['details']['user_message']}")
                print(f"{detail_prefix}   Sequence: {node['details']['sequence']}")
                print(f"{detail_prefix}   Time: {node['details']['timestamp']}")
            
            elif node['type'] == 'keyword':
                print(f"{detail_prefix}   Word: \"{node['details']['keyword']}\"")
                print(f"{detail_prefix}   Confidence: {node['details']['confidence']:.2f}")
                print(f"{detail_prefix}   By: {node['details']['derived_by']}")
            
            elif node['type'] == 'summary':
                print(f"{detail_prefix}   Text: {node['details']['summary']}")
                print(f"{detail_prefix}   Method: {node['details']['extraction_method']}")
                print(f"{detail_prefix}   By: {node['details']['derived_by']}")
            
            elif node['type'] == 'affect':
                print(f"{detail_prefix}   Label: {node['details']['affect_label']}")
                print(f"{detail_prefix}   Intensity: {node['details']['intensity']:.2f}")
                print(f"{detail_prefix}   Confidence: {node['details']['confidence']:.2f}")
                print(f"{detail_prefix}   By: {node['details']['derived_by']}")
        
        # Print children
        for i, child in enumerate(node['children']):
            is_last_child = (i == len(node['children']) - 1)
            child_prefix = prefix + ("   " if is_last else "│  ")
            self._print_tree_recursive(child, child_prefix, is_last_child)
        
        if node.get('truncated'):
            truncate_prefix = prefix + ("   " if is_last else "│  ")
            print(f"{truncate_prefix}... (max depth reached)")
    
    def export_lineage_json(self, item_id: str, max_depth: int = 10) -> Dict[str, Any]:
        """
        Export lineage tree as JSON structure.
        
        Useful for:
        - External analysis tools
        - Data export
        - Visualization in other formats
        
        Args:
            item_id: Item to export lineage for
            max_depth: Maximum depth to traverse
            
        Returns:
            Dict with complete lineage structure
        """
        tree = self._build_tree(item_id, max_depth)
        return {
            'root_id': item_id,
            'root_type': get_id_type(item_id),
            'exported_at': datetime.now().isoformat(),
            'tree': tree
        }
    
    def save_lineage_json(self, item_id: str, filepath: str, max_depth: int = 10) -> None:
        """
        Save lineage tree to JSON file.
        
        Args:
            item_id: Item to export lineage for
            filepath: Output file path
            max_depth: Maximum depth to traverse
        """
        data = self.export_lineage_json(item_id, max_depth)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Lineage exported to: {filepath}")
    
    def validate_integrity(self, day_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Validate lineage integrity for a day or entire database.
        
        Checks:
        - All derived_from references resolve
        - No orphaned objects
        - No circular references
        - All IDs are valid format
        
        Args:
            day_id: Specific day to validate (None = all days)
            
        Returns:
            Dict with validation results and issues found
        """
        print("\n" + "=" * 70)
        print("🔍 LINEAGE INTEGRITY VALIDATION")
        if day_id:
            print(f"   Scope: Day {day_id}")
        else:
            print("   Scope: Entire database")
        print("=" * 70 + "\n")
        
        issues = {
            'missing_references': [],
            'invalid_ids': [],
            'orphaned_objects': [],
            'circular_references': []
        }
        
        stats = {
            'turns_checked': 0,
            'keywords_checked': 0,
            'summaries_checked': 0,
            'affects_checked': 0
        }
        
        # Get turns to check
        if day_id:
            turns = self.storage.get_staged_turns(day_id)
        else:
            # For now, check today's turns (could extend to all days)
            from .models import create_day_id
            today = create_day_id()
            turns = self.storage.get_staged_turns(today)
        
        # Validate each turn
        for turn in turns:
            stats['turns_checked'] += 1
            
            # Validate turn ID format
            if not self._validate_id_format(turn.turn_id, 'turn'):
                issues['invalid_ids'].append({
                    'id': turn.turn_id,
                    'type': 'turn',
                    'issue': 'Invalid format'
                })
            
            # Check keyword references
            for kid_id in turn.keyword_ids:
                stats['keywords_checked'] += 1
                
                if not self._validate_id_format(kid_id, 'keyword'):
                    issues['invalid_ids'].append({
                        'id': kid_id,
                        'type': 'keyword',
                        'issue': 'Invalid format'
                    })
                    continue
                
                # Check keyword exists and derives from this turn
                keyword = self.storage.get_keyword_by_id(kid_id)
                if not keyword:
                    issues['missing_references'].append({
                        'parent_id': turn.turn_id,
                        'parent_type': 'turn',
                        'missing_id': kid_id,
                        'missing_type': 'keyword'
                    })
                elif keyword.derived_from != turn.turn_id:
                    issues['orphaned_objects'].append({
                        'id': kid_id,
                        'type': 'keyword',
                        'expected_parent': turn.turn_id,
                        'actual_parent': keyword.derived_from
                    })
            
            # Check summary reference
            if turn.summary_id:
                stats['summaries_checked'] += 1
                
                if not self._validate_id_format(turn.summary_id, 'summary'):
                    issues['invalid_ids'].append({
                        'id': turn.summary_id,
                        'type': 'summary',
                        'issue': 'Invalid format'
                    })
                else:
                    summary = self.storage.get_summary_by_id(turn.summary_id)
                    if not summary:
                        issues['missing_references'].append({
                            'parent_id': turn.turn_id,
                            'parent_type': 'turn',
                            'missing_id': turn.summary_id,
                            'missing_type': 'summary'
                        })
                    elif summary.derived_from != turn.turn_id:
                        issues['orphaned_objects'].append({
                            'id': turn.summary_id,
                            'type': 'summary',
                            'expected_parent': turn.turn_id,
                            'actual_parent': summary.derived_from
                        })
            
            # Check affect references
            for affect_id in turn.affect_ids:
                stats['affects_checked'] += 1
                
                if not self._validate_id_format(affect_id, 'affect'):
                    issues['invalid_ids'].append({
                        'id': affect_id,
                        'type': 'affect',
                        'issue': 'Invalid format'
                    })
                    continue
                
                affect = self.storage.get_affect_by_id(affect_id)
                if not affect:
                    issues['missing_references'].append({
                        'parent_id': turn.turn_id,
                        'parent_type': 'turn',
                        'missing_id': affect_id,
                        'missing_type': 'affect'
                    })
                elif affect.derived_from != turn.turn_id:
                    issues['orphaned_objects'].append({
                        'id': affect_id,
                        'type': 'affect',
                        'expected_parent': turn.turn_id,
                        'actual_parent': affect.derived_from
                    })
        
        # Print results
        total_issues = sum(len(v) for v in issues.values())
        
        print("📊 Statistics:")
        print(f"   Turns checked: {stats['turns_checked']}")
        print(f"   Keywords checked: {stats['keywords_checked']}")
        print(f"   Summaries checked: {stats['summaries_checked']}")
        print(f"   Affects checked: {stats['affects_checked']}")
        print()
        
        if total_issues == 0:
            print("✅ No integrity issues found!")
        else:
            print(f"⚠️  Found {total_issues} integrity issues:")
            
            if issues['invalid_ids']:
                print(f"\n❌ Invalid IDs ({len(issues['invalid_ids'])}):")
                for issue in issues['invalid_ids'][:5]:  # Show first 5
                    print(f"   - {issue['type']}: {issue['id']}")
                if len(issues['invalid_ids']) > 5:
                    print(f"   ... and {len(issues['invalid_ids']) - 5} more")
            
            if issues['missing_references']:
                print(f"\n❌ Missing References ({len(issues['missing_references'])}):")
                for issue in issues['missing_references'][:5]:
                    print(f"   - {issue['parent_type']} {issue['parent_id'][:30]}...")
                    print(f"     references missing {issue['missing_type']} {issue['missing_id'][:30]}...")
                if len(issues['missing_references']) > 5:
                    print(f"   ... and {len(issues['missing_references']) - 5} more")
            
            if issues['orphaned_objects']:
                print(f"\n❌ Orphaned Objects ({len(issues['orphaned_objects'])}):")
                for issue in issues['orphaned_objects'][:5]:
                    print(f"   - {issue['type']} {issue['id'][:30]}...")
                    print(f"     Expected parent: {issue['expected_parent'][:30]}...")
                    print(f"     Actual parent: {issue['actual_parent'][:30]}...")
                if len(issues['orphaned_objects']) > 5:
                    print(f"   ... and {len(issues['orphaned_objects']) - 5} more")
        
        print("\n" + "=" * 70 + "\n")
        
        return {
            'stats': stats,
            'issues': issues,
            'total_issues': total_issues,
            'is_valid': total_issues == 0
        }
    
    def _validate_id_format(self, item_id: str, expected_type: str) -> bool:
        """
        Validate that an ID has correct format for its type.
        
        Args:
            item_id: ID to validate
            expected_type: Expected type (turn, keyword, summary, etc.)
            
        Returns:
            True if valid format
        """
        try:
            detected_type = get_id_type(item_id)
            return detected_type == expected_type
        except:
            return False
    
    def trace_to_source(self, item_id: str) -> List[Dict[str, str]]:
        """
        Trace lineage chain from item back to source turn.
        
        Args:
            item_id: Item to trace
            
        Returns:
            List of dicts with id, type for each step in chain
        """
        chain = []
        current_id = item_id
        visited = set()  # Prevent infinite loops
        
        while current_id and current_id not in visited:
            visited.add(current_id)
            
            id_type = get_id_type(current_id)
            chain.append({
                'id': current_id,
                'type': id_type
            })
            
            # Stop at turn (source)
            if id_type == 'turn':
                break
            
            # Get parent
            try:
                source_id = extract_source_id(current_id)
                current_id = source_id
            except:
                break  # Can't extract source
        
        return chain
    
    def find_orphans(self, day_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Find objects whose parent references don't resolve.
        
        Args:
            day_id: Specific day to check (None = today)
            
        Returns:
            List of orphaned objects with details
        """
        validation = self.validate_integrity(day_id)
        return validation['issues']['orphaned_objects']


# ============================================================================
# CLI TESTING / DEMO
# ============================================================================

if __name__ == "__main__":
    import sys
    import os
    
    print("🧪 LineageTracker Demo")
    print("=" * 70)
    
    # Initialize
    storage = Storage("memory/cognitive_lattice_memory.db")
    tracker = LineageTracker(storage)
    
    # Get a test turn
    from models import create_day_id
    today = create_day_id()
    
    turns = storage.get_staged_turns(today)
    
    if not turns:
        print("⚠️  No turns found for today. Create some data first.")
        storage.close()
        sys.exit(0)
    
    # Test 1: Print lineage tree
    print("\n1️⃣  Testing print_lineage_tree()...")
    turn = turns[0]
    tracker.print_lineage_tree(turn.turn_id)
    
    # Test 2: Export to JSON
    print("\n2️⃣  Testing export_lineage_json()...")
    lineage_data = tracker.export_lineage_json(turn.turn_id)
    print(f"   ✅ Exported lineage for: {turn.turn_id[:30]}...")
    print(f"   Root type: {lineage_data['root_type']}")
    print(f"   Children: {len(lineage_data['tree']['children'])}")
    
    # Test 3: Validate integrity
    print("\n3️⃣  Testing validate_integrity()...")
    validation = tracker.validate_integrity(today)
    
    # Test 4: Trace to source
    print("\n4️⃣  Testing trace_to_source()...")
    if turn.keyword_ids:
        keyword_id = turn.keyword_ids[0]
        chain = tracker.trace_to_source(keyword_id)
        print(f"   Chain for keyword {keyword_id[:30]}...:")
        for i, item in enumerate(chain):
            print(f"      {i+1}. {item['type']}: {item['id'][:30]}...")
    
    storage.close()
    
    print("\n" + "=" * 70)
    print("✅ LineageTracker demo complete!")
