import asyncio
import json
import logging
from typing import Dict, Any, Optional

from core.external_api_client import ExternalAPIClient
from memory.synthesis.user_profile_manager import UserProfileManager

logger = logging.getLogger(__name__)

SCRIBE_SYSTEM_PROMPT = """
### ROLE
You are the **User Profile Scribe**.
Your goal is to maintain a "Glossary" of the user's life by extracting **Projects**, **Entities**, and **Hard Constraints** from the conversation.
You do NOT answer the user. You only output JSON updates for the database.

### 1. DEFINITIONS & HEURISTICS (The Filter)
Do not record every noun. Only record items that pass these tests:

**A. DEFINITION OF A "PROJECT"**
To be saved as a Project, an endeavor must meet ALL 3 criteria:
1.  **Named:** The user refers to it by a proper noun (e.g., "HMLR", "Blue Sky", "The '69 Chevy"). If it is generic ("my work"), IGNORE it.
2.  **Persistent:** It is a multi-session goal (weeks/months), not a temporary task (homework, chores).
3.  **User-Owned:** The user is the active creator or owner.

**B. DEFINITION OF AN "ENTITY"**
A permanent fact about the user's world:
* **Business:** Company name, job title.
* **Person:** Family member names (e.g., "My son Mike"), but NOT temporary states (e.g., "Mike is hungry").
* **Asset:** Major user-owned assets (e.g., "My server rack", "My boat").

**C. DEFINITION OF A "CONSTRAINT"**
A permanent user preference, restriction, or rule that affects decision-making:
* **Dietary Restrictions:** "I am vegetarian", "I have a nut allergy", "I don't eat gluten"
* **Allergies:** "I have a latex allergy", "I'm allergic to pet dander", "I can't be around shellfish"
* **Work Constraints:** "I only work 9-5", "I never work weekends", "I don't do on-call"
* **Communication Preferences:** "I prefer email over calls", "Don't contact me after 8pm"
* **Personal Rules:** "I don't use Windows", "I always back up code", "I never use tabs (spaces only)"

Constraints are different from temporary states. "I have a latex allergy" = CONSTRAINT. "My hand itches" = temporary state (IGNORE).

### 2. ACTION RULES (Append vs. Edit)

**WHEN TO CREATE (New Entry):**
* The user mentions a specific Name (Key) that does NOT exist in your current context.
* *Action:* Create a new entry.

**WHEN TO UPDATE (Edit):**
* The user provides *new specific details* about an existing Key.
* **Logic:**
    * If the new info conflicts (e.g., "HMLR is now written in Rust, not Python"), use `action: "OVERWRITE"`.
    * If the new info adds detail (e.g., "HMLR also uses Redis"), use `action: "APPEND"`.
    * If the user just mentions the project without new facts ("How is HMLR doing?"), return **NO UPDATE**.

### 3. WHAT TO IGNORE (Crucial)
* **Opinions/Mood:** "I hate this," "I am tired." (Ignore for now).
* **One-off Tasks:** "Help me write an email," "Fix this specific bug."
* **General Topics:** "Tell me about Hackathons." (Unless the user says "I organize the NY Hackathon").

### 4. OUTPUT SCHEMA
Return a JSON object. If no updates are detected, return `{"updates": []}`.

Target JSON Structure:
{
  "updates": [
    {
      "category": "projects",  // or "entities", "constraints"
      "key": "HMLR",           // The unique ID/Name
      "action": "UPSERT",      // "UPSERT" handles both create and update
      "attributes": {
        "domain": "AI / Software",       // Infer this from context
        "description": "User's custom hierarchical memory system.",
        "tech_stack": "Python, SQLite, LLM", // Optional: Extract technical details if present
        "status": "Active"
      }
    },
    {
      "category": "constraints",
      "key": "allergy_latex",  // Unique constraint ID
      "action": "UPSERT",
      "attributes": {
        "type": "Allergy",
        "description": "User has a severe latex allergy",
        "severity": "severe"  // or "mild", "preference", etc.
      }
    }
  ]
}
"""

class Scribe:
    """
    The Scribe Agent.
    Runs in the background to extract user profile updates from conversation.
    """
    
    def __init__(self, api_client: ExternalAPIClient, profile_manager: UserProfileManager):
        self.api_client = api_client
        self.profile_manager = profile_manager

    async def run_scribe_agent(self, user_input: str):
        """
        Runs in background. Does NOT block the main chat response.
        Analyzes user input for profile updates.
        """
        # print(f"   [DEBUG] Scribe task started for input: {user_input[:30]}...")
        try:
            # Use the cheap fast model (nano/flash)
            # Note: ExternalAPIClient.query_external_api is synchronous, 
            # but we are running this in an async task executor usually.
            
            loop = asyncio.get_event_loop()
            # print(f"   [DEBUG] Scribe calling LLM...")
            response_text = await loop.run_in_executor(
                None, 
                self._query_llm, 
                user_input
            )
            # print(f"   [DEBUG] Scribe LLM returned. Len: {len(response_text) if response_text else 0}")
            
            if not response_text:
                return

            # Parse JSON
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                updates = data.get('updates', [])
                
                if updates:
                    logger.info(f"Scribe detected {len(updates)} profile updates.")
                    # Print to console for visibility during testing
                    print(f"\n   ✍️  Scribe detected {len(updates)} profile updates: {[u.get('key') for u in updates]}")
                    self.profile_manager.update_profile_db(updates)
                else:
                    # Debug: Print when no updates found to confirm it ran
                    # print(f"\n   ✍️  Scribe ran but found no updates.")
                    pass
            else:
                logger.warning(f"Scribe response did not contain valid JSON: {response_text[:100]}...")
                # print(f"   [DEBUG] Scribe invalid JSON: {response_text}")
            
        except Exception as e:
            logger.error(f"Scribe agent failed: {e}")
            print(f"\n   ❌ Scribe agent failed: {e}")
            import traceback
            traceback.print_exc()

    def _query_llm(self, user_input: str) -> str:
        """Helper to call the synchronous API client"""
        # We pass the current profile context so the Scribe knows what already exists
        current_profile = self.profile_manager.get_user_profile_context()
        
        full_prompt = f"{SCRIBE_SYSTEM_PROMPT}\n\nCURRENT PROFILE CONTEXT:\n{current_profile}\n\nUSER INPUT: \"{user_input}\""
        
        # Use mini for better reasoning capabilities than nano
        return self.api_client.query_external_api(full_prompt, model="gpt-4.1-mini")
