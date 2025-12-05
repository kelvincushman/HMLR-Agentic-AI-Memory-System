"""
Universal Planning Interview System

This module provides a domain-agnostic, LLM-driven planning interview system
that gathers user requirements, generates preliminary plans, validates them,
and converts approved plans into calendar-ready JSON format.

Key Features:
- LLM decides what questions to ask based on plan type
- Multi-turn conversation tracking
- Plan verification step (approve/modify/cancel)
- Duration guardrails (60-day limit)
- Token budget estimation
- Converts to JSON only after user approval
"""

import json
import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class PlanningSession:
    """Tracks state of an active planning interview"""
    user_query: str
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    interview_phase: str = "gathering"  # gathering, verifying, approved, cancelled
    draft_plan: Optional[str] = None
    final_json_plan: Optional[str] = None
    start_time: datetime.datetime = field(default_factory=datetime.datetime.now)
    
    def add_exchange(self, role: str, content: str):
        """Add a conversation turn to history"""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.datetime.now().isoformat()
        })


class UniversalPlanningInterview:
    """
    Manages the entire planning interview lifecycle:
    1. Initial query analysis
    2. Question generation and requirements gathering
    3. Draft plan creation
    4. User verification (approve/modify/cancel)
    5. JSON conversion and calendar integration
    """
    
    # Constants
    MAX_PLAN_DAYS = 60
    TOKEN_WARNING_THRESHOLD = 2000
    
    def __init__(self, external_api_client):
        """
        Args:
            external_api_client: Instance of ExternalAPIClient for LLM calls
        """
        self.api_client = external_api_client
        self.active_sessions: Dict[str, PlanningSession] = {}
    
    def start_interview(self, user_query: str, session_id: str) -> str:
        """
        Start a new planning interview session.
        
        Args:
            user_query: User's initial planning request
            session_id: Unique identifier for this planning session
            
        Returns:
            LLM's initial interview questions
        """
        # Create new session
        session = PlanningSession(user_query=user_query)
        session.add_exchange("user", user_query)
        self.active_sessions[session_id] = session
        
        # Generate initial interview questions
        interview_prompt = self._build_interview_start_prompt(user_query)
        llm_response = self.api_client.query_external_api(interview_prompt)
        
        # Check if LLM has enough info from the initial request
        should_generate = self._should_generate_draft(llm_response)
        
        # Strip delimiter from response before showing to user
        cleaned_response = self._strip_delimiters(llm_response)
        
        session.add_exchange("assistant", cleaned_response)
        
        # If LLM says it's ready, generate draft immediately
        if should_generate:
            return self._generate_draft_plan(session)[0]  # Returns (response, phase)
        
        return cleaned_response
    
    def process_user_response(self, user_response: str, session_id: str) -> Tuple[str, str]:
        """
        Process user's response during interview.
        
        Args:
            user_response: User's answer to interview questions or feedback on plan
            session_id: Session identifier
            
        Returns:
            Tuple of (llm_response, phase) where phase is current interview phase
        """
        session = self.active_sessions.get(session_id)
        if not session:
            return "No active planning session found. Please start a new plan.", "error"
        
        session.add_exchange("user", user_response)
        
        # Handle different phases
        if session.interview_phase == "gathering":
            return self._handle_gathering_phase(session, user_response)
        elif session.interview_phase == "verifying":
            return self._handle_verification_phase(session, user_response)
        else:
            return f"Session in unexpected phase: {session.interview_phase}", "error"
    
    def _handle_gathering_phase(self, session: PlanningSession, user_response: str) -> Tuple[str, str]:
        """Handle the requirements gathering phase"""
        
        # Build prompt with conversation history
        gathering_prompt = self._build_gathering_prompt(session, user_response)
        llm_response = self.api_client.query_external_api(gathering_prompt)
        
        # Check if LLM thinks it has enough information
        should_generate = self._should_generate_draft(llm_response)
        
        # Strip delimiter from response before showing to user
        cleaned_response = self._strip_delimiters(llm_response)
        
        session.add_exchange("assistant", cleaned_response)
        
        if should_generate:
            # Move to draft generation
            return self._generate_draft_plan(session)
        else:
            # Continue gathering
            return cleaned_response, "gathering"
    
    def _strip_delimiters(self, text: str) -> str:
        """
        Remove internal delimiters from LLM response before showing to user.
        
        Removes:
        - [PLAN_READY:TRUE]
        - [PLAN_READY:FALSE]
        - Any other bracketed control codes we add in the future
        """
        import re
        # Remove [PLAN_READY:TRUE] or [PLAN_READY:FALSE] (case insensitive)
        cleaned = re.sub(r'\[PLAN_READY:(TRUE|FALSE)\]', '', text, flags=re.IGNORECASE)
        # Remove extra whitespace that might be left behind
        cleaned = re.sub(r'\n\s*\n\s*\n', '\n\n', cleaned)  # Max 2 consecutive newlines
        return cleaned.strip()
    
    def _generate_draft_plan(self, session: PlanningSession) -> Tuple[str, str]:
        """Generate preliminary draft plan for user review"""
        
        # Check duration and token estimates first
        validation_result = self._validate_plan_scope(session)
        if validation_result:
            return validation_result, "gathering"  # Stay in gathering to negotiate scope
        
        # Generate draft plan with larger token limit for detailed plans
        draft_prompt = self._build_draft_generation_prompt(session)
        draft_plan = self.api_client.query_external_api(draft_prompt, max_tokens=4000)  # Large limit for detailed draft
        
        session.draft_plan = draft_plan
        session.interview_phase = "verifying"
        
        # Create verification message
        verification_message = f"""Based on your requirements, here's the plan I've created:

{draft_plan}

---

Please review this plan carefully. You can:
• Say **"looks good"**, **"approve"**, or **"yes"** if you're satisfied — I'll format it for your calendar
• Tell me **specific changes** you'd like (e.g., "make the workouts shorter" or "add rest days on weekends")
• Say **"nevermind"**, **"cancel"**, or **"start over"** if you want to drop this plan

What would you like to do?"""
        
        session.add_exchange("assistant", verification_message)
        return verification_message, "verifying"
    
    def _handle_verification_phase(self, session: PlanningSession, user_response: str) -> Tuple[str, str]:
        """Handle plan verification and modification requests"""
        
        response_lower = user_response.lower().strip()
        
        # Check for approval
        approval_keywords = ["looks good", "approve", "approved", "yes", "perfect", "great", "sounds good"]
        if any(keyword in response_lower for keyword in approval_keywords):
            return self._finalize_plan(session)
        
        # Check for cancellation
        cancel_keywords = ["nevermind", "cancel", "cancelled", "start over", "forget it", "drop"]
        if any(keyword in response_lower for keyword in cancel_keywords):
            session.interview_phase = "cancelled"
            del self.active_sessions[session.conversation_history[0]["content"]]  # Clean up
            return "No problem! I've cancelled this plan. Let me know if you want to create a different plan.", "cancelled"
        
        # User wants modifications
        modification_prompt = self._build_modification_prompt(session, user_response)
        revised_plan = self.api_client.query_external_api(modification_prompt, max_tokens=4000)  # Large limit for revised plan
        
        session.draft_plan = revised_plan
        
        verification_message = f"""Here's the updated plan based on your feedback:

{revised_plan}

---

Does this look better? You can:
• **Approve** it if you're happy with the changes
• Request **more modifications**
• **Cancel** if you want to drop it

What do you think?"""
        
        session.add_exchange("assistant", verification_message)
        return verification_message, "verifying"
    
    def _finalize_plan(self, session: PlanningSession) -> Tuple[str, str]:
        """Convert approved plan to JSON format for calendar integration"""
        
        # Generate JSON version with LARGE token limit for extensive plans (60+ days)
        json_prompt = self._build_json_conversion_prompt(session)
        json_plan = self.api_client.query_external_api(json_prompt, max_tokens=8000)  # Large limit for 60-day plans
        
        # Validate JSON
        try:
            parsed = json.loads(json_plan)
            session.final_json_plan = json_plan
            session.interview_phase = "approved"
            
            confirmation = f"""Perfect! I've added your plan to the calendar. 

You can view and follow it day-by-day in your planner. The plan includes {len(parsed.get('days', []))} days of scheduled activities.

Is there anything else you'd like to plan?"""
            
            session.add_exchange("assistant", confirmation)
            return confirmation, "approved"
            
        except json.JSONDecodeError as e:
            # Retry JSON generation with error feedback
            retry_prompt = f"""{json_prompt}

The previous response was not valid JSON. Error: {str(e)}

Please return ONLY valid JSON with no additional text."""
            
            json_plan = self.api_client.query_external_api(retry_prompt, max_tokens=8000)  # Large limit for retry too
            session.final_json_plan = json_plan
            session.interview_phase = "approved"
            
            return "Your plan has been added to the calendar!", "approved"
    
    def _validate_plan_scope(self, session: PlanningSession) -> Optional[str]:
        """
        Validate plan doesn't exceed duration or token limits.
        
        Returns:
            Warning message if validation fails, None if valid
        """
        # Check for duration keywords in conversation
        conversation_text = " ".join([turn["content"] for turn in session.conversation_history])
        
        # Look for long duration indicators (be specific to avoid false positives)
        long_duration_patterns = [
            r'\b\d+\s*years?\b',  # "2 years", "1 year"
            r'\b\d+\s*months?\b',  # "6 months", "3 month"
            r'\b(90|100|120|150|180|200|250|300|365)\s*days?\b',  # 90+ days
            r'\bevery\s+day\s+for\s+(months?|years?|a\s+long\s+time)\b',  # "every day for months"
            r'\bdaily\s+for\s+(months?|years?)\b',  # "daily for months"
        ]
        
        import re
        has_long_duration = any(
            re.search(pattern, conversation_text.lower()) 
            for pattern in long_duration_patterns
        )
        
        if has_long_duration:
            return f"""I notice you're asking for a long-term plan. To keep things manageable and avoid overwhelming you with too much at once, I can create plans up to {self.MAX_PLAN_DAYS} days.

Would you like me to:
1. Create the first {self.MAX_PLAN_DAYS} days, and we can extend it later based on your progress
2. Create a pattern-based plan (e.g., "Every Monday/Wednesday/Friday do X") that repeats
3. Adjust the timeframe to something shorter

What would work best for you?"""
        
        # Estimate tokens (rough heuristic: 1 token ≈ 4 characters)
        estimated_tokens = len(conversation_text) / 4
        
        if estimated_tokens > self.TOKEN_WARNING_THRESHOLD:
            return f"""This plan is getting quite detailed, which is great! However, to ensure I can process it effectively, I may need to simplify some aspects or break it into phases.

Would you like me to:
1. Create a high-level plan with key milestones
2. Focus on the first few weeks in detail
3. Continue as planned (may take longer to generate)

What's your preference?"""
        
        return None
    
    def _should_generate_draft(self, llm_response: str) -> bool:
        """
        Determine if LLM has gathered enough information to create a draft.
        
        Looks for the delimiter: [PLAN_READY:TRUE] or [PLAN_READY:FALSE]
        This delimiter is parsed out and not shown to the user.
        """
        # Check for explicit delimiter (preferred method)
        if "[PLAN_READY:TRUE]" in llm_response.upper():
            return True
        if "[PLAN_READY:FALSE]" in llm_response.upper():
            return False
        
        # Fallback: heuristic check for backward compatibility
        response_lower = llm_response.lower()
        signal_phrases = [
            "let me create",
            "i'll create",
            "i'll get that ready",
            "i have what i need",
            "ready to create"
        ]
        
        return any(phrase in response_lower for phrase in signal_phrases)
    
    # ========== Prompt Builders ==========
    
    def _build_interview_start_prompt(self, user_query: str) -> str:
        """Build prompt to start the planning interview"""
        return f"""You are a planning assistant helping a user create a structured, actionable plan. The user has requested:

"{user_query}"

CONTEXT: Your goal is to gather the necessary information to create a day-by-day plan that will be loaded into a calendar interface the user can follow. The plan will show specific tasks/activities for each date.

YOUR TASK:
1. Analyze what type of plan the user wants (fitness, learning, project, habit-building, etc.)
2. Determine what information you need to create an effective plan:
   - Timeline/duration
   - Frequency (daily, weekly, specific days)
   - Intensity/difficulty level
   - Any constraints (schedule, resources, experience level)
   - Specific goals or milestones
3. Ask the user clear, focused questions to gather this information

IMPORTANT CONSTRAINTS:
- Plans should be reasonable in scope (ideally within 60 days)
- Be conversational and friendly, not robotic
- Ask 2-4 questions at a time, don't overwhelm the user
- If the user's request is clear enough, you can suggest starting with sensible defaults

CRITICAL: You must include a delimiter in your response:
- If you have ENOUGH information from the initial request to create the plan, include: [PLAN_READY:TRUE]
- If you need MORE information, include: [PLAN_READY:FALSE]

This delimiter will be hidden from the user. Place it at the beginning or end of your response.

Example responses:
"[PLAN_READY:FALSE] I'd be happy to help! To create the best plan for you, I need to know..."
"[PLAN_READY:TRUE] Great! I have everything I need from your detailed request. Let me create that plan now."

Begin the interview now:"""
    
    def _build_gathering_prompt(self, session: PlanningSession, user_response: str) -> str:
        """Build prompt for continuing the requirements gathering"""
        
        history = "\n".join([
            f"{turn['role'].upper()}: {turn['content']}"
            for turn in session.conversation_history
        ])
        
        return f"""You are continuing a planning interview. Here's the conversation so far:

{history}

The user just responded: "{user_response}"

YOUR TASK:
- Review what information you've gathered so far
- Determine if you have enough information to create a comprehensive day-by-day plan (timeline, frequency, goals, constraints)
- If you're missing CRITICAL information (like duration, frequency, or major constraints), ask 1-2 focused follow-up questions
- Don't over-ask - if the user has given you the basics, proceed to create the plan

CRITICAL: You must include a delimiter in your response:
- If you have ENOUGH information to create the plan, include: [PLAN_READY:TRUE]
- If you need MORE information, include: [PLAN_READY:FALSE]

This delimiter will be hidden from the user. Place it anywhere in your response (beginning or end).

Example responses:
"[PLAN_READY:FALSE] Thanks! Just to clarify - do you want this plan to start tomorrow or next week?"
"Great! I have everything I need. [PLAN_READY:TRUE] Let me create that plan for you now."

IMPORTANT: After 2-3 exchanges, you should have enough to create a plan. Don't keep asking endless questions.

Continue the interview:"""
    
    def _build_draft_generation_prompt(self, session: PlanningSession) -> str:
        """Build prompt for generating the preliminary plan"""
        
        history = "\n".join([
            f"{turn['role'].upper()}: {turn['content']}"
            for turn in session.conversation_history
        ])
        
        return f"""Based on this planning interview, create a preliminary day-by-day plan:

{history}

CONTEXT: This plan will be shown to the user for review before being formatted for their calendar. After they approve it, you'll convert it to JSON where each task will appear on a specific date in their day planner.

REQUIREMENTS:
- Create a day-by-day breakdown (e.g., "Day 1: ...", "Day 2: ...", or use actual dates)
- Be specific about what the user should do each day
- Keep it readable and well-organized
- Limit to {self.MAX_PLAN_DAYS} days maximum
- Include rest days or breaks where appropriate
- Make it actionable and realistic

Generate the preliminary plan (this is a DRAFT for user review, NOT the final JSON format):"""
    
    def _build_modification_prompt(self, session: PlanningSession, modification_request: str) -> str:
        """Build prompt for modifying the draft plan based on user feedback"""
        
        return f"""You created this preliminary plan:

{session.draft_plan}

The user has requested these changes:
"{modification_request}"

YOUR TASK:
- Modify the plan according to the user's feedback
- Keep the same general structure and format
- Make sure the changes address their concerns
- Return the REVISED plan (not JSON format yet, still human-readable)

Generate the updated plan:"""
    
    def _build_json_conversion_prompt(self, session: PlanningSession) -> str:
        """Build prompt for converting approved plan to JSON format"""
        
        return f"""The user has approved this plan:

{session.draft_plan}

CONTEXT: This JSON code will not be shown to the user so it must be precise and well-structured. It will be passed to a backend service for processing. Now convert this plan into JSON format that will be parsed programmatically into a day planner. The user will follow this plan day by day, with each task appearing on the specific date in their calendar interface.

REQUIRED JSON FORMAT:
{{
  "plan_title": "Brief title for this plan",
  "start_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD",
  "days": [
    {{
      "date": "YYYY-MM-DD",
      "day_number": 1,
      "tasks": [
        {{
          "time": "HH:MM" (if specific time, otherwise null),
          "activity": "Specific activity description",
          "duration": "Duration in minutes or description",
          "notes": "Any additional notes or tips"
        }}
      ]
    }}
  ]
}}

IMPORTANT:
- Return ONLY the raw JSON object, no markdown formatting, no code fences, no backticks
- Do NOT wrap in ```json or ``` markers
- Start directly with the opening brace {{
- Use actual dates starting from today ({datetime.date.today().isoformat()}) or the date specified in the plan
- Be precise with the date calculations
- Include all tasks from the approved plan

Generate the JSON now (raw JSON only, starting with opening brace):"""
    
    def get_session_state(self, session_id: str) -> Optional[Dict]:
        """Get current state of a planning session"""
        session = self.active_sessions.get(session_id)
        if not session:
            return None
        
        return {
            "user_query": session.user_query,
            "phase": session.interview_phase,
            "turn_count": len(session.conversation_history),
            "has_draft": session.draft_plan is not None,
            "has_final_json": session.final_json_plan is not None
        }
    
    def get_final_plan(self, session_id: str) -> Optional[str]:
        """Retrieve the final JSON plan for calendar integration"""
        session = self.active_sessions.get(session_id)
        if session and session.interview_phase == "approved":
            return session.final_json_plan
        return None
    
    def cancel_session(self, session_id: str):
        """Cancel and clean up a planning session"""
        if session_id in self.active_sessions:
            self.active_sessions[session_id].interview_phase = "cancelled"
            del self.active_sessions[session_id]
