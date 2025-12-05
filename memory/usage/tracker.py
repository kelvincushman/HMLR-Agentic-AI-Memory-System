"""
Track context usage over time.

Maintains statistics about which turns are actually used by the LLM,
enabling intelligent retrieval optimization.
"""

from typing import Set, Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class TurnUsage:
    """Usage statistics for a single turn."""
    turn_id: str
    usage_count: int = 0
    last_used: datetime = None
    first_used: datetime = None
    topics: List[str] = field(default_factory=list)
    
    def mark_used(self, timestamp: datetime = None):
        """Mark turn as used at given timestamp."""
        if timestamp is None:
            timestamp = datetime.now()
        
        self.usage_count += 1
        self.last_used = timestamp
        
        if self.first_used is None:
            self.first_used = timestamp


@dataclass
class PlanUsage:
    """Usage statistics for a single plan."""
    plan_id: str
    plan_title: str
    usage_count: int = 0
    last_used: datetime = None
    first_used: datetime = None
    items_completed: int = 0
    total_items: int = 0
    completion_rate: float = 0.0
    
    def mark_used(self, timestamp: datetime = None):
        """Mark plan as used at given timestamp."""
        if timestamp is None:
            timestamp = datetime.now()
        
        self.usage_count += 1
        self.last_used = timestamp
        
        if self.first_used is None:
            self.first_used = timestamp
    
    def update_completion(self, completed: int, total: int):
        """Update plan completion statistics."""
        self.items_completed = completed
        self.total_items = total
        self.completion_rate = completed / total if total > 0 else 0.0


class UsageTracker:
    """
    Track which context turns are actually used by the LLM.
    
    Week 2, Day 3-5 implementation:
    - Track turn usage over time
    - Maintain usage statistics
    - Identify patterns (over-retrieval, under-utilization)
    """
    
    def __init__(self):
        # Per-turn usage tracking
        self.turn_usage: Dict[str, TurnUsage] = {}
        
        # Per-query tracking (what was provided vs used)
        self.query_history: List[dict] = []
        
        # === Phase 6.2: Plan Status Tracking === #
        # Per-plan usage and completion tracking
        self.plan_usage: Dict[str, PlanUsage] = {}
    
    def track_usage(
        self,
        provided_turn_ids: Set[str],
        used_turn_ids: Set[str],
        query_topics: List[str] = None,
        timestamp: datetime = None,
        debug: bool = False
    ):
        """
        Track which turns were provided vs actually used.
        
        Args:
            provided_turn_ids: Turn IDs provided to LLM as context
            used_turn_ids: Turn IDs actually cited/used by LLM
            query_topics: Topics from the query (optional)
            timestamp: When this occurred (default: now)
            debug: Enable debug logging
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        if query_topics is None:
            query_topics = []
        
        # Track each used turn
        for turn_id in used_turn_ids:
            if turn_id not in self.turn_usage:
                self.turn_usage[turn_id] = TurnUsage(
                    turn_id=turn_id,
                    topics=query_topics
                )
            
            self.turn_usage[turn_id].mark_used(timestamp)
        
        # Track this query's efficiency
        efficiency = len(used_turn_ids) / len(provided_turn_ids) if provided_turn_ids else 0.0
        
        self.query_history.append({
            'timestamp': timestamp,
            'topics': query_topics,
            'provided_count': len(provided_turn_ids),
            'used_count': len(used_turn_ids),
            'efficiency': efficiency,
            'provided_ids': provided_turn_ids,
            'used_ids': used_turn_ids,
            'unused_ids': provided_turn_ids - used_turn_ids
        })
        
        if debug:
            logger.info(f"📊 Usage tracking:")
            logger.info(f"   Provided: {len(provided_turn_ids)} turns")
            logger.info(f"   Used: {len(used_turn_ids)} turns")
            logger.info(f"   Efficiency: {efficiency:.1%}")
            
            if efficiency < 0.3:
                logger.warning(f"⚠️  Low efficiency ({efficiency:.1%}) - possible over-retrieval")
    
    def get_turn_usage(self, turn_id: str) -> TurnUsage:
        """Get usage statistics for a specific turn."""
        return self.turn_usage.get(turn_id, TurnUsage(turn_id=turn_id))
    
    def get_most_used_turns(self, limit: int = 10) -> List[TurnUsage]:
        """Get the most frequently used turns."""
        sorted_turns = sorted(
            self.turn_usage.values(),
            key=lambda t: t.usage_count,
            reverse=True
        )
        return sorted_turns[:limit]
    
    def get_recently_used_turns(self, hours: int = 24, limit: int = 10) -> List[TurnUsage]:
        """Get turns used in the last N hours."""
        cutoff = datetime.now()
        cutoff = cutoff.replace(hour=cutoff.hour - hours)
        
        recent = [
            usage for usage in self.turn_usage.values()
            if usage.last_used and usage.last_used > cutoff
        ]
        
        recent.sort(key=lambda t: t.last_used, reverse=True)
        return recent[:limit]
    
    def get_never_used_turns(self, provided_turn_ids: Set[str]) -> Set[str]:
        """
        Get turns that were provided but never used.
        
        Args:
            provided_turn_ids: All turn IDs that have been provided as context
            
        Returns:
            Set of turn IDs never cited by LLM
        """
        used_turn_ids = set(self.turn_usage.keys())
        return provided_turn_ids - used_turn_ids
    
    def get_efficiency_by_topic(self, topic: str) -> float:
        """
        Calculate average efficiency for a specific topic.
        
        Efficiency = used_turns / provided_turns
        
        Returns:
            Average efficiency (0.0 to 1.0) for this topic
        """
        topic_queries = [
            q for q in self.query_history
            if topic.lower() in [t.lower() for t in q['topics']]
        ]
        
        if not topic_queries:
            return 0.0
        
        total_efficiency = sum(q['efficiency'] for q in topic_queries)
        return total_efficiency / len(topic_queries)
    
    def get_overall_efficiency(self) -> float:
        """Get overall retrieval efficiency across all queries."""
        if not self.query_history:
            return 0.0
        
        total_efficiency = sum(q['efficiency'] for q in self.query_history)
        return total_efficiency / len(self.query_history)
    
    def identify_over_retrieval(self, threshold: float = 0.3) -> List[dict]:
        """
        Identify queries with low efficiency (possible over-retrieval).
        
        Args:
            threshold: Efficiency below this is considered over-retrieval
            
        Returns:
            List of queries with low efficiency
        """
        return [
            q for q in self.query_history
            if q['efficiency'] < threshold
        ]
    
    def suggest_max_results_per_topic(self) -> Dict[str, int]:
        """
        Suggest optimal max_results for RAG retrieval per topic.
        
        Based on historical usage patterns, recommend how many
        turns to retrieve for each topic.
        
        Returns:
            Dict mapping topic -> suggested max_results
        """
        topic_stats = {}
        
        # Analyze each topic
        for query in self.query_history:
            for topic in query['topics']:
                topic_lower = topic.lower()
                
                if topic_lower not in topic_stats:
                    topic_stats[topic_lower] = {
                        'total_provided': 0,
                        'total_used': 0,
                        'query_count': 0
                    }
                
                topic_stats[topic_lower]['total_provided'] += query['provided_count']
                topic_stats[topic_lower]['total_used'] += query['used_count']
                topic_stats[topic_lower]['query_count'] += 1
        
        # Calculate suggestions
        suggestions = {}
        for topic, stats in topic_stats.items():
            avg_used = stats['total_used'] / stats['query_count']
            # Add 20% buffer for safety
            suggested = int(avg_used * 1.2)
            # Clamp between 3 and 20
            suggestions[topic] = max(3, min(20, suggested))
        
        return suggestions
    
    def clear_old_history(self, days: int = 30):
        """
        Clear query history older than N days.
        
        Keeps turn usage statistics but removes old query history.
        """
        cutoff = datetime.now()
        cutoff = cutoff.replace(day=cutoff.day - days)
        
        self.query_history = [
            q for q in self.query_history
            if q['timestamp'] > cutoff
        ]
    
    # === Phase 6.2: Plan Status Tracking Methods === #
    
    def track_plan_usage(
        self,
        plan_id: str,
        plan_title: str,
        timestamp: datetime = None,
        debug: bool = False
    ):
        """
        Track that a plan was used/referenced in a query.
        
        Args:
            plan_id: Unique identifier for the plan
            plan_title: Human-readable plan title
            timestamp: When this occurred (default: now)
            debug: Enable debug logging
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        if plan_id not in self.plan_usage:
            self.plan_usage[plan_id] = PlanUsage(
                plan_id=plan_id,
                plan_title=plan_title
            )
        
        self.plan_usage[plan_id].mark_used(timestamp)
        
        if debug:
            logger.info(f"📅 Plan usage tracked: {plan_title} (ID: {plan_id})")
    
    def update_plan_completion(
        self,
        plan_id: str,
        completed_items: int,
        total_items: int,
        debug: bool = False
    ):
        """
        Update completion status for a plan.
        
        Args:
            plan_id: Unique identifier for the plan
            completed_items: Number of completed plan items
            total_items: Total number of plan items
            debug: Enable debug logging
        """
        if plan_id in self.plan_usage:
            self.plan_usage[plan_id].update_completion(completed_items, total_items)
            
            if debug:
                completion_rate = completed_items / total_items if total_items > 0 else 0.0
                logger.info(f"📊 Plan completion updated: {plan_id} - {completed_items}/{total_items} ({completion_rate:.1%})")
    
    def get_plan_usage(self, plan_id: str) -> Optional[PlanUsage]:
        """Get usage statistics for a specific plan."""
        return self.plan_usage.get(plan_id)
    
    def get_most_used_plans(self, limit: int = 5) -> List[PlanUsage]:
        """Get the most frequently referenced plans."""
        sorted_plans = sorted(
            self.plan_usage.values(),
            key=lambda p: p.usage_count,
            reverse=True
        )
        return sorted_plans[:limit]
    
    def get_plan_completion_rates(self) -> Dict[str, float]:
        """
        Get completion rates for all tracked plans.
        
        Returns:
            Dict mapping plan_id -> completion_rate (0.0 to 1.0)
        """
        return {
            plan_id: plan.completion_rate
            for plan_id, plan in self.plan_usage.items()
        }
    
    def get_active_plan_insights(self) -> dict:
        """
        Get insights about plan usage and completion.
        
        Returns:
            Dictionary with plan usage statistics
        """
        total_plans = len(self.plan_usage)
        completed_plans = sum(1 for p in self.plan_usage.values() if p.completion_rate >= 1.0)
        avg_completion = sum(p.completion_rate for p in self.plan_usage.values()) / total_plans if total_plans > 0 else 0.0
        
        return {
            'total_plans_tracked': total_plans,
            'completed_plans': completed_plans,
            'average_completion_rate': round(avg_completion, 3),
            'most_used_plans': [
                {'plan_id': p.plan_id, 'title': p.plan_title, 'usage_count': p.usage_count}
                for p in self.get_most_used_plans(limit=3)
            ]
        }
    
    def get_summary(self) -> dict:
        """Get comprehensive usage summary."""
        total_queries = len(self.query_history)
        total_turns_tracked = len(self.turn_usage)
        overall_efficiency = self.get_overall_efficiency()
        
        most_used = self.get_most_used_turns(limit=5)
        
        # === Phase 6.2: Include Plan Metrics === #
        plan_insights = self.get_active_plan_insights()
        
        return {
            'total_queries': total_queries,
            'total_turns_tracked': total_turns_tracked,
            'overall_efficiency': round(overall_efficiency, 3),
            'most_used_turns': [
                {'turn_id': t.turn_id, 'usage_count': t.usage_count}
                for t in most_used
            ],
            'low_efficiency_queries': len(self.identify_over_retrieval()),
            # Phase 6.2: Plan metrics
            'plan_insights': plan_insights
        }
