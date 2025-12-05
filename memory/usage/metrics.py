"""
Usage metrics and analysis.

Provides high-level metrics about context usage efficiency.
"""

from typing import Dict, List
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


@dataclass
class TopicMetrics:
    """Metrics for a specific topic."""
    topic: str
    query_count: int
    total_provided: int
    total_used: int
    avg_efficiency: float
    suggested_max_results: int


class UsageMetrics:
    """
    High-level metrics and analysis for context usage.
    
    Combines data from UsageTracker to provide insights.
    """
    
    def __init__(self, usage_tracker):
        """
        Initialize metrics from a UsageTracker.
        
        Args:
            usage_tracker: UsageTracker instance to analyze
        """
        self.tracker = usage_tracker
    
    def get_topic_metrics(self) -> List[TopicMetrics]:
        """
        Get metrics broken down by topic.
        
        Returns:
            List of TopicMetrics objects
        """
        # Group queries by topic
        topic_data: Dict[str, dict] = {}
        
        for query in self.tracker.query_history:
            for topic in query['topics']:
                topic_lower = topic.lower()
                
                if topic_lower not in topic_data:
                    topic_data[topic_lower] = {
                        'query_count': 0,
                        'total_provided': 0,
                        'total_used': 0,
                        'efficiencies': []
                    }
                
                data = topic_data[topic_lower]
                data['query_count'] += 1
                data['total_provided'] += query['provided_count']
                data['total_used'] += query['used_count']
                data['efficiencies'].append(query['efficiency'])
        
        # Calculate metrics
        metrics = []
        suggestions = self.tracker.suggest_max_results_per_topic()
        
        for topic, data in topic_data.items():
            avg_efficiency = sum(data['efficiencies']) / len(data['efficiencies'])
            
            metrics.append(TopicMetrics(
                topic=topic,
                query_count=data['query_count'],
                total_provided=data['total_provided'],
                total_used=data['total_used'],
                avg_efficiency=round(avg_efficiency, 3),
                suggested_max_results=suggestions.get(topic, 10)
            ))
        
        # Sort by query count (most common topics first)
        metrics.sort(key=lambda m: m.query_count, reverse=True)
        
        return metrics
    
    def get_efficiency_trend(self, days: int = 7) -> List[dict]:
        """
        Get efficiency trend over time.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            List of daily efficiency averages
        """
        cutoff = datetime.now() - timedelta(days=days)
        
        # Group queries by day
        daily_data: Dict[str, list] = {}
        
        for query in self.tracker.query_history:
            if query['timestamp'] > cutoff:
                day_key = query['timestamp'].strftime('%Y-%m-%d')
                
                if day_key not in daily_data:
                    daily_data[day_key] = []
                
                daily_data[day_key].append(query['efficiency'])
        
        # Calculate daily averages
        trend = []
        for day_key in sorted(daily_data.keys()):
            efficiencies = daily_data[day_key]
            avg_efficiency = sum(efficiencies) / len(efficiencies)
            
            trend.append({
                'date': day_key,
                'avg_efficiency': round(avg_efficiency, 3),
                'query_count': len(efficiencies)
            })
        
        return trend
    
    def get_waste_analysis(self) -> dict:
        """
        Analyze wasted retrieval (context provided but not used).
        
        Returns:
            Dict with waste statistics
        """
        total_provided = sum(q['provided_count'] for q in self.tracker.query_history)
        total_used = sum(q['used_count'] for q in self.tracker.query_history)
        total_wasted = total_provided - total_used
        
        waste_percentage = (total_wasted / total_provided * 100) if total_provided > 0 else 0.0
        
        # Find most wasteful topics
        topic_waste = {}
        for query in self.tracker.query_history:
            for topic in query['topics']:
                topic_lower = topic.lower()
                
                if topic_lower not in topic_waste:
                    topic_waste[topic_lower] = {'provided': 0, 'used': 0}
                
                topic_waste[topic_lower]['provided'] += query['provided_count']
                topic_waste[topic_lower]['used'] += query['used_count']
        
        wasteful_topics = []
        for topic, data in topic_waste.items():
            wasted = data['provided'] - data['used']
            waste_pct = (wasted / data['provided'] * 100) if data['provided'] > 0 else 0.0
            
            if waste_pct > 50:  # More than 50% waste
                wasteful_topics.append({
                    'topic': topic,
                    'provided': data['provided'],
                    'used': data['used'],
                    'wasted': wasted,
                    'waste_percentage': round(waste_pct, 1)
                })
        
        wasteful_topics.sort(key=lambda t: t['wasted'], reverse=True)
        
        return {
            'total_provided': total_provided,
            'total_used': total_used,
            'total_wasted': total_wasted,
            'waste_percentage': round(waste_percentage, 1),
            'wasteful_topics': wasteful_topics[:5]  # Top 5 most wasteful
        }
    
    def get_recommendations(self) -> List[str]:
        """
        Get actionable recommendations based on metrics.
        
        Returns:
            List of recommendation strings
        """
        recommendations = []
        
        # Overall efficiency
        overall_eff = self.tracker.get_overall_efficiency()
        if overall_eff < 0.4:
            recommendations.append(
                f"⚠️  Overall efficiency is low ({overall_eff:.1%}). "
                f"Consider reducing max_results for RAG retrieval."
            )
        
        # Topic-specific
        topic_metrics = self.get_topic_metrics()
        for metric in topic_metrics[:3]:  # Top 3 topics
            if metric.avg_efficiency < 0.3:
                recommendations.append(
                    f"⚠️  Topic '{metric.topic}' has low efficiency ({metric.avg_efficiency:.1%}). "
                    f"Reduce max_results from current to {metric.suggested_max_results}."
                )
        
        # Waste analysis
        waste = self.get_waste_analysis()
        if waste['waste_percentage'] > 60:
            recommendations.append(
                f"⚠️  High waste ({waste['waste_percentage']:.1%} of retrieved context unused). "
                f"Review retrieval strategy."
            )
        
        # Over-retrieval
        over_retrieval_queries = self.tracker.identify_over_retrieval()
        if len(over_retrieval_queries) > len(self.tracker.query_history) * 0.5:
            recommendations.append(
                f"⚠️  Over-retrieval detected in {len(over_retrieval_queries)} queries. "
                f"Consider topic-aware filtering or stricter similarity thresholds."
            )
        
        if not recommendations:
            recommendations.append("✅ Context usage efficiency looks good!")
        
        return recommendations
    
    def print_report(self):
        """Print comprehensive usage report."""
        summary = self.tracker.get_summary()
        
        print("=" * 60)
        print("📊 CONTEXT USAGE REPORT")
        print("=" * 60)
        print(f"\nOverall Statistics:")
        print(f"  Total queries: {summary['total_queries']}")
        print(f"  Turns tracked: {summary['total_turns_tracked']}")
        print(f"  Overall efficiency: {summary['overall_efficiency']:.1%}")
        print(f"  Low efficiency queries: {summary['low_efficiency_queries']}")
        
        print(f"\n📈 Most Used Turns:")
        for turn in summary['most_used_turns']:
            print(f"  {turn['turn_id']}: {turn['usage_count']} uses")
        
        print(f"\n🎯 Topic Metrics:")
        topic_metrics = self.get_topic_metrics()
        for metric in topic_metrics[:5]:  # Top 5 topics
            print(f"  {metric.topic}:")
            print(f"    Queries: {metric.query_count}")
            print(f"    Efficiency: {metric.avg_efficiency:.1%}")
            print(f"    Suggested max: {metric.suggested_max_results} turns")
        
        print(f"\n🗑️  Waste Analysis:")
        waste = self.get_waste_analysis()
        print(f"  Provided: {waste['total_provided']} turns")
        print(f"  Used: {waste['total_used']} turns")
        print(f"  Wasted: {waste['total_wasted']} turns ({waste['waste_percentage']:.1%})")
        
        if waste['wasteful_topics']:
            print(f"\n  Most wasteful topics:")
            for topic in waste['wasteful_topics']:
                print(f"    {topic['topic']}: {topic['waste_percentage']:.1%} waste "
                      f"({topic['wasted']}/{topic['provided']} turns)")
        
        print(f"\n💡 Recommendations:")
        for rec in self.get_recommendations():
            print(f"  {rec}")
        
        print("=" * 60)
