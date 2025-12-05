"""
Planning System Data Models for CognitiveLattice

This module defines data structures for the personal planning assistant.
Extends the existing memory system with plan tracking and management.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime


@dataclass
class PlanItem:
    """Individual task within a plan"""
    date: str  # YYYY-MM-DD format
    task: str  # Description of the task
    duration_minutes: int
    completed: bool = False
    notes: str = ""
    actual_duration: Optional[int] = None  # Track actual time spent
    completion_time: Optional[datetime] = None


@dataclass
class UserPlan:
    """Complete user plan with metadata"""
    plan_id: str
    topic: str  # exercise, meal, learning, financial, general
    title: str  # Human-readable title
    created_date: str
    duration_weeks: int = 4
    items: List[PlanItem] = field(default_factory=list)
    status: str = "active"  # active, completed, paused, cancelled
    progress_percentage: float = 0.0
    last_updated: Optional[datetime] = None
    notes: str = ""

    def calculate_progress(self) -> float:
        """Calculate completion percentage"""
        if not self.items:
            return 0.0
        completed_count = sum(1 for item in self.items if item.completed)
        return (completed_count / len(self.items)) * 100.0


@dataclass
class PlanFeedback:
    """User feedback on plan execution"""
    feedback_id: str
    plan_id: str
    date: str
    feedback_type: str  # completion, difficulty, modification_request
    user_feedback: str
    llm_response: str = ""
    emotional_context: str = ""  # from affect tracking
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class PlanModification:
    """Record of plan changes"""
    modification_id: str
    plan_id: str
    modification_type: str  # delay, pause, cancel, modify
    description: str
    old_value: str = ""
    new_value: str = ""
    reason: str = ""
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")