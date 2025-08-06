from pydantic import BaseModel
from typing import Any, Dict, List, Optional
import pandas as pd
import os
import hashlib


# Define schemas for the audit tool
class SelectCategoryParams(BaseModel):
    category: str


class AnswerQuestionParams(BaseModel):
    session_id: str
    answer: str


class ProvideEvidenceParams(BaseModel):
    session_id: str
    evidence: str


class GetCurrentQuestionParams(BaseModel):
    session_id: str


# Load the audit data from Excel
def load_audit_data():
    """Load and structure the audit data from the Excel file"""
    try:
        # Try multiple possible paths for the Excel file
        possible_paths = [
            '/app/Audit.xlsx',  # Docker container path
            'c:/Users/bhala/Downloads/agent_skeleton/Audit.xlsx',  # Local development path
            'Audit.xlsx',  # Current directory
            'agent_skeleton/agent/multi_tool_agent/app/Audit.xlsx'  # Relative path
        ]
       
        df = None
        for path in possible_paths:
            try:
                # Read the specific sheet "GenAI Security Audit Sheet"
                df = pd.read_excel(path, sheet_name="GenAI Security Audit Sheet")
                print(f"✅ Successfully loaded audit data from: {path}")
                print(f"   Data shape: {df.shape}")
                print(f"   Columns: {list(df.columns)}")
                break
            except FileNotFoundError:
                continue
            except Exception as e:
                print(f"Error reading {path}: {e}")
                continue
       
        if df is None:
            print(f"❌ Could not find Audit.xlsx in any of these paths: {possible_paths}")
            return None
           
        return df
    except Exception as e:
        print(f"Error loading audit data: {e}")
        return None


# Get available NIST AI RMF categories
def get_nist_categories() -> List[str]:
    """Get the 7 NIST AI RMF categories"""
    return [
        "Privacy-Enhanced",
        "Valid & Reliable",
        "Safe",
        "Secure & Resilient",
        "Accountable & Transparent",
        "Explainable and Interpretable",
        "Fair – With Harmful Bias Managed"
    ]


# Session storage for audit progress
audit_sessions = {}
user_sessions = {}  # Track sessions per user to prevent multiple sessions
multi_category_sessions = {}  # Track multi-category audits


class MultiCategoryAudit:
    """Clean multi-category audit state management"""
    
    def __init__(self, user_id: str, categories: List[str]):
        self.user_id = user_id
        self.categories = categories
        self.current_index = 0  # Index of currently active category
        self.completed_categories = []
        self.active_session_id = None
        self.status = 'active'
        self.session_mapping = {}  # category -> session_id mapping
    
    def get_current_category(self) -> Optional[str]:
        """Get the currently active category"""
        if self.current_index < len(self.categories):
            return self.categories[self.current_index]
        return None
    
    def get_next_category(self) -> Optional[str]:
        """Get the next category to audit"""
        next_index = self.current_index + 1
        if next_index < len(self.categories):
            return self.categories[next_index]
        return None
    
    def mark_current_completed(self):
        """Mark current category as completed and move to next"""
        current_category = self.get_current_category()
        if current_category and current_category not in self.completed_categories:
            self.completed_categories.append(current_category)
    
    
    def is_completed(self) -> bool:
        """Check if all categories are completed"""
        return len(self.completed_categories) >= len(self.categories)
    
    def get_remaining_categories(self) -> List[str]:
        """Get list of remaining categories"""
        return self.categories[self.current_index + 1:]
    
    def get_progress_summary(self) -> Dict[str, Any]:
        """Get progress summary"""
        return {
            'total_categories': len(self.categories),
            'completed_count': len(self.completed_categories),
            'current_category': self.get_current_category(),
            'remaining_categories': self.get_remaining_categories(),
            'completed_categories': self.completed_categories.copy(),
            'status': 'completed' if self.is_completed() else 'active'
        }


def get_user_session_key(category: str, user_id: str = "default") -> str:
    """Generate a consistent session key for user + category"""
    return f"audit_{user_id}_{category.replace(' ', '_').replace('&', 'and').replace('–', '-').lower()}"


class AuditSession:
    def __init__(self, session_id: str, category: str):
        self.session_id = session_id
        self.category = category
        self.questions = []
        self.current_question_idx = 0
        self.observations = []
        self.evidence_evaluations = []
        self.status = "started"
        self.state = "waiting_for_question_answer"  # Track conversation state
        self._load_category_questions()
   
    def _load_category_questions(self):
        """Load questions for the selected category"""
        df = load_audit_data()
        if df is not None:
            # Filter by category using the correct column name
            category_data = df[df['Trust-worthiness characteristic'] == self.category]
            print(f"Found {len(category_data)} rows for category: {self.category}")
           
            # Extract sub questions and baseline evidence
            for _, row in category_data.iterrows():
                if pd.notna(row['Sub Question']) and row['Sub Question'].strip():
                    question = {
                        'sub_question': row['Sub Question'],
                        'baseline_evidence': row['Baseline Evidence '] if pd.notna(row['Baseline Evidence ']) else '',
                        'nist_control': row['NIST AI RMF Control'] if pd.notna(row['NIST AI RMF Control']) else '',
                        'question_id': row['Question ID'] if pd.notna(row['Question ID']) else ''
                    }
                    self.questions.append(question)
           
            print(f"Loaded {len(self.questions)} sub-questions for {self.category}")
   
    def get_current_question(self):
        """Get the current question in the audit"""
        if self.current_question_idx < len(self.questions):
            return self.questions[self.current_question_idx]
        return None
   
    def add_observation(self, answer: str):
        """Add user's answer as an observation"""
        self.observations.append({
            'question_idx': self.current_question_idx,
            'observation': answer
        })
        self.state = "waiting_for_evidence"
   
    def evaluate_evidence(self, evidence: str) -> Dict[str, Any]:
        """Evaluate provided evidence against baseline"""
        current_q = self.get_current_question()
        if not current_q:
            return {"error": "No current question"}
       
        baseline_evidence = current_q['baseline_evidence']
       
        # Enhanced evaluation logic using keyword matching and content analysis
        evidence_lower = evidence.lower()
        baseline_lower = baseline_evidence.lower()
       
        # Extract key terms and requirements from baseline
        evidence_words = set(word.strip('.,!?()[]{}":;') for word in evidence_lower.split() if len(word) > 3)
        baseline_words = set(word.strip('.,!?()[]{}":;') for word in baseline_lower.split() if len(word) > 3)
       
        # Look for specific audit keywords
        audit_keywords = {'policy', 'documentation', 'config', 'screenshot', 'logs', 'audit',
                         'compliance', 'review', 'approval', 'signed', 'attestation', 'report',
                         'testing', 'validation', 'monitoring', 'procedure', 'checklist'}
       
        evidence_audit_terms = evidence_words.intersection(audit_keywords)
        baseline_audit_terms = baseline_words.intersection(audit_keywords)
       
        # Calculate overlap scores
        word_overlap = len(evidence_words.intersection(baseline_words))
        audit_overlap = len(evidence_audit_terms.intersection(baseline_audit_terms))
       
        # Calculate evidence completeness score
        evidence_length = len(evidence.strip())
        baseline_requirements = baseline_evidence.count('\n') + baseline_evidence.count('.')
       
        # Determine conformity level based on multiple factors
        total_score = (word_overlap * 0.4) + (audit_overlap * 0.4) + (min(evidence_length/200, 1) * 0.2)
       
        if total_score >= 0.8 and evidence_length > 100 and audit_overlap >= 2:
            conformity = "Full Conformity"
            justification = f"Provided evidence comprehensively addresses baseline requirements with {audit_overlap} key audit elements and strong content overlap ({word_overlap} matching terms)."
        elif total_score >= 0.5 and evidence_length > 50 and audit_overlap >= 1:
            conformity = "Partial Conformity"
            justification = f"Provided evidence partially meets baseline requirements with {audit_overlap} audit elements. Consider providing additional documentation or details to achieve full conformity."
        else:
            conformity = "No Conformity"
            justification = f"Provided evidence does not adequately match baseline requirements. Missing key audit elements and insufficient detail. Please review baseline evidence requirements and provide comprehensive documentation."
       
        evaluation = {
            'question_idx': self.current_question_idx,
            'evidence': evidence,
            'conformity': conformity,
            'justification': justification,
            'baseline_evidence': baseline_evidence,
            'overlap_score': word_overlap,
            'audit_terms_found': list(evidence_audit_terms)
        }
       
        self.evidence_evaluations.append(evaluation)
        return evaluation
   
    def move_to_next_question(self):
        """Move to the next question"""
        self.current_question_idx += 1
        if self.current_question_idx >= len(self.questions):
            self.status = "completed"
        else:
            self.state = "waiting_for_question_answer"
   
    def get_progress(self):
        """Get audit progress"""
        return {
            'current': self.current_question_idx + 1,
            'total': len(self.questions),
            'status': self.status,
            'category': self.category
        }


def get_audit_categories() -> Dict[str, Any]:
    """Get the list of available NIST AI RMF categories"""
    return {
        "categories": get_nist_categories(),
        "message": "Please select one of the 7 NIST AI RMF categories to begin your audit"
    }


def start_audit_session(category: str, user_id: str = "default") -> Dict[str, Any]:
    """Start a new audit session for the selected category"""
    if category not in get_nist_categories():
        return {
            "error": f"Invalid category. Please select from: {', '.join(get_nist_categories())}"
        }
   
    # Use consistent session key based on user and category
    session_id = get_user_session_key(category, user_id)
   
    # Check if session already exists for this user+category combo
    if session_id in audit_sessions and audit_sessions[session_id].status != "completed":
        existing_session = audit_sessions[session_id]
        current_question = existing_session.get_current_question()
       
        return {
            "action": "session_exists",
            "session_id": session_id,
            "category": category,
            "message": f"You already have an active audit session for **{category}**. Continuing from where you left off.\n\n**Current Sub-Question:**\n{current_question['sub_question']}\n\nPlease provide your observation/answer for this question.",
            "current_question": current_question,
            "progress": existing_session.get_progress()
        }
   
    # Create new session
    session = AuditSession(session_id, category)
    audit_sessions[session_id] = session
    user_sessions[user_id] = session_id  # Track this user's active session
   
    current_question = session.get_current_question()
   
    return {
        "action": "category_selected",
        "session_id": session_id,
        "category": category,
        "message": f"Excellent! I've started your NIST AI RMF audit for **{category}**.\n\n**Current Sub-Question:**\n{current_question['sub_question']}\n\nPlease provide your observation/answer for this question.",
        "current_question": current_question,
        "progress": session.get_progress()
    }


def get_current_question(session_id: str) -> Dict[str, Any]:
    """Get the current question for the audit session"""
    if session_id not in audit_sessions:
        return {"error": "Invalid session ID"}
   
    session = audit_sessions[session_id]
    current_question = session.get_current_question()
   
    if not current_question:
        return {
            "message": "Audit completed!",
            "status": "completed",
            "progress": session.get_progress(),
            "summary": {
                "total_questions": len(session.questions),
                "observations": len(session.observations),
                "evaluations": len(session.evidence_evaluations)
            }
        }
   
    return {
        "session_id": session_id,
        "current_question": current_question,
        "progress": session.get_progress()
    }


def submit_answer(session_id: str, answer: str) -> Dict[str, Any]:
    """Submit an answer/observation for the current question"""
    if session_id not in audit_sessions:
        return {"error": "Invalid session ID"}
   
    session = audit_sessions[session_id]
    current_question = session.get_current_question()
   
    if not current_question:
        return {"error": "No current question to answer"}
   
    session.add_observation(answer)
   
    # Return baseline evidence for user to provide matching evidence
    baseline_evidence = current_question['baseline_evidence']
   
    return {
        "action": "observation_recorded",
        "observation": answer,
        "baseline_evidence": baseline_evidence,
        "message": f"**Observation Recorded:** {answer}\n\n**Baseline Evidence Requirements:**\n{baseline_evidence}\n\nPlease provide evidence that demonstrates compliance with these baseline requirements."
    }


# def submit_evidence(session_id: str, evidence: str, user_id: str = "clyde") -> Dict[str, Any]:
#     """Submit evidence and get evaluation - NO AUTO-TRANSITIONS"""
#     if session_id not in audit_sessions:
#         return {"error": "Invalid session ID"}
   
#     session = audit_sessions[session_id]
#     evaluation = session.evaluate_evidence(evidence)
   
#     # Move to next question
#     session.move_to_next_question()
   
#     # Get next question or completion status
#     next_question = session.get_current_question()
   
#     result = {
#         "action": "evidence_evaluated",
#         "evaluation": evaluation,
#         "progress": session.get_progress()
#     }
   
#     if next_question:
#         # Continue with next question in same category
#         result["next_question"] = next_question
#         result["message"] = f"**Evidence Evaluation:**\n\n**Conformity Level:** {evaluation['conformity']}\n\n**Justification:** {evaluation['justification']}"
#         result["completed"] = False
#     else:
#         # Category completed - check if this is part of a multi-category audit
#         multi_audit = get_user_multi_category_audit(session.category, user_id)
        
#         if multi_audit:
#             # This is part of a multi-category audit
#             multi_audit.mark_current_completed()
            
#             if multi_audit.is_completed():
#                 # All categories completed
#                 result["action"] = "multi_audit_completed"
#                 result["message"] = f"**Evidence Evaluation:**\n\n**Conformity Level:** {evaluation['conformity']}\n\n**Justification:** {evaluation['justification']}\n\n🎉 **Multi-Category Audit Completed!**\n\nYou have successfully completed all {len(multi_audit.categories)} categories!"
#                 result["multi_audit_summary"] = multi_audit.get_progress_summary()
#                 result["completed"] = True
#             else:
#                 # More categories to go - show transition option
#                 next_category = multi_audit.get_next_category()
#                 result["action"] = "category_completed_multi"
#                 result["message"] = f"**Evidence Evaluation:**\n\n**Conformity Level:** {evaluation['conformity']}\n\n**Justification:** {evaluation['justification']}\n\n🎉 **Category '{session.category}' Completed!**\n\nNext category: **{next_category}**\n\nClick 'Continue to Next Category' when you're ready to proceed."
#                 result["multi_audit_progress"] = multi_audit.get_progress_summary()
#                 result["next_category"] = next_category
#                 result["completed"] = False
#                 result["needs_transition"] = True
#         else:
#             # Single category audit completed
#             result["message"] = f"**Evidence Evaluation:**\n\n**Conformity Level:** {evaluation['conformity']}\n\n**Justification:** {evaluation['justification']}\n\n🎉 **Audit Completed!**\n\nYou have successfully completed the NIST AI RMF audit for **{session.category}**.\n\n**Summary:**\n• Total Questions: {session.get_progress()['total']}\n• Observations Recorded: {len(session.observations)}\n• Evidence Evaluations: {len(session.evidence_evaluations)}"
#             result["status"] = "completed"
#             result["completed"] = True
   
#     return result
def submit_evidence(session_id: str, evidence: str, user_id: str = "clyde") -> Dict[str, Any]:
    """Submit evidence and get evaluation - NO AUTO-TRANSITIONS"""
    if session_id not in audit_sessions:
        return {"error": "Invalid session ID"}
   
    session = audit_sessions[session_id]
    evaluation = session.evaluate_evidence(evidence)
   
    # Move to next question
    session.move_to_next_question()
   
    # Get next question or completion status
    next_question = session.get_current_question()
   
    result = {
        "action": "evidence_evaluated",
        "evaluation": evaluation,
        "progress": session.get_progress()
    }
   
    if next_question:
        # Continue with next question in same category
        result["next_question"] = next_question
        result["message"] = f"**Evidence Evaluation:**\n\n**Conformity Level:** {evaluation['conformity']}\n\n**Justification:** {evaluation['justification']}"
        result["completed"] = False
    else:
        # Category completed - check if this is part of a multi-category audit
        
        # DEBUG LINES - ADD THESE:
        print(f"DEBUG: Category '{session.category}' completed for user_id: '{user_id}'")
        print(f"DEBUG: Available multi_category_sessions: {list(multi_category_sessions.keys())}")
        for mid, multi_audit_obj in multi_category_sessions.items():
            print(f"DEBUG: Multi-session {mid}: user_id='{multi_audit_obj.use_summaryr_id}', categories={multi_audit_obj.categories}, status='{multi_audit_obj.status}'")
        
        multi_audit = get_user_multi_category_audit(session.category, user_id)
        print(f"DEBUG: Found multi_audit: {multi_audit is not None}")
        
        if multi_audit:
            print(f"DEBUG: Multi-audit found! Categories: {multi_audit.categories}")
            print(f"DEBUG: Current completed categories: {multi_audit.completed_categories}")
            print(f"DEBUG: Current index: {multi_audit.current_index}")
            
            # This is part of a multi-category audit
            multi_audit.mark_current_completed()
            
            print(f"DEBUG: After marking completed - completed categories: {multi_audit.completed_categories}")
            print(f"DEBUG: After marking completed - current index: {multi_audit.current_index}")
            print(f"DEBUG: Is audit completed? {multi_audit.is_completed()}")
           
            if multi_audit.is_completed():
                # All categories completed
                print(f"DEBUG: All categories completed!")
                result["action"] = "multi_audit_completed"
                result["message"] = f"**Evidence Evaluation:**\n\n**Conformity Level:** {evaluation['conformity']}\n\n**Justification:** {evaluation['justification']}\n\n🎉 **Multi-Category Audit Completed!**\n\nYou have successfully completed all {len(multi_audit.categories)} categories!"
                result["multi_audit_summary"] = multi_audit.get_progress_summary()
                result["completed"] = True
            else:
                # More categories to go - show transition option
                next_category = multi_audit.get_next_category()
                print(f"DEBUG: Setting up transition to next category: {next_category}")
                result["action"] = "category_completed_multi"
                result["message"] = f"**Evidence Evaluation:**\n\n**Conformity Level:** {evaluation['conformity']}\n\n**Justification:** {evaluation['justification']}\n\n🎉 **Category '{session.category}' Completed!**\n\nNext category: **{next_category}**\n\nClick 'Continue to Next Category' when you're ready to proceed."
                result["multi_audit_progress"] = multi_audit.get_progress_summary()
                result["next_category"] = next_category
                result["completed"] = False
                result["needs_transition"] = True
        else:
            print(f"DEBUG: No multi-audit found - treating as single category")
            print(f"DEBUG: Checking all multi-audits for category '{session.category}' and user '{user_id}':")
            for mid, multi_audit_obj in multi_category_sessions.items():
                print(f"  Multi-session {mid}:")
                print(f"    - user_id: '{multi_audit_obj.user_id}' (matches: {multi_audit_obj.user_id == user_id})")
                print(f"    - categories: {multi_audit_obj.categories} (contains '{session.category}': {session.category in multi_audit_obj.categories})")
                print(f"    - status: '{multi_audit_obj.status}' (active: {multi_audit_obj.status == 'active'})")
            
            # Single category audit completed
            result["message"] = f"**Evidence Evaluation:**\n\n**Conformity Level:** {evaluation['conformity']}\n\n**Justification:** {evaluation['justification']}\n\n🎉 **Audit Completed!**\n\nYou have successfully completed the NIST AI RMF audit for **{session.category}**.\n\n**Summary:**\n• Total Questions: {session.get_progress()['total']}\n• Observations Recorded: {len(session.observations)}\n• Evidence Evaluations: {len(session.evidence_evaluations)}"
            result["status"] = "completed"
            result["completed"] = True
   
    return result


# def start_multi_category_audit(categories: List[str], user_id: str = "clyde") -> Dict[str, Any]:
#     """Start a multi-category audit session"""
#     if not categories:
#         return {"error": "No categories provided"}
   
#     if len(categories) < 2:
#         return {"error": "Multi-category audit requires at least 2 categories"}
   
#     # Validate categories
#     valid_categories = get_nist_categories()
#     invalid_categories = [cat for cat in categories if cat not in valid_categories]
#     if invalid_categories:
#         return {"error": f"Invalid categories: {invalid_categories}"}
   
#     # Create multi-category audit tracker
#     multi_session_id = f"multi_{user_id}_{hashlib.md5('_'.join(categories).encode()).hexdigest()[:8]}"
#     multi_audit = MultiCategoryAudit(user_id, categories)
#     multi_category_sessions[multi_session_id] = multi_audit
   
#     print(f"DEBUG: Created multi-category session {multi_session_id} for categories: {categories}")
   
#     # Start first category
#     first_category = categories[0]
#     result = start_audit_session(first_category, user_id)
   
#     if 'error' not in result:
#         # Track this session in the multi-audit
#         multi_audit.active_session_id = result['session_id']
#         multi_audit.session_mapping[first_category] = result['session_id']
        
#         # Add multi-category info to response
#         result['action'] = 'multi_category_started'
#         result['multi_session_id'] = multi_session_id
#         result['multi_audit_progress'] = multi_audit.get_progress_summary()
#         result['message'] = f"**Multi-Category Audit Started**\n\nTotal categories: {len(categories)}\nStarting with: **{first_category}** (1 of {len(categories)})\n\n{result.get('message', '')}"
   
#     return result

def start_multi_category_audit(categories: List[str], user_id: str = "clyde") -> Dict[str, Any]:
    """Start a multi-category audit session"""
    print(f"DEBUG: start_multi_category_audit called with categories={categories}, user_id='{user_id}'")
    
    if not categories:
        return {"error": "No categories provided"}
   
    if len(categories) < 2:
        return {"error": "Multi-category audit requires at least 2 categories"}
   
    # Validate categories
    valid_categories = get_nist_categories()
    invalid_categories = [cat for cat in categories if cat not in valid_categories]
    if invalid_categories:
        return {"error": f"Invalid categories: {invalid_categories}"}
   
    # Create multi-category audit tracker
    multi_session_id = f"multi_{user_id}_{hashlib.md5('_'.join(categories).encode()).hexdigest()[:8]}"
    multi_audit = MultiCategoryAudit(user_id, categories)
    multi_category_sessions[multi_session_id] = multi_audit
   
    print(f"DEBUG: Created multi-category session {multi_session_id} for categories: {categories}")
    print(f"DEBUG: Multi-category sessions now: {list(multi_category_sessions.keys())}")
   
    # Start first category
    first_category = categories[0]
    result = start_audit_session(first_category, user_id)
   
    if 'error' not in result:
        # Track this session in the multi-audit
        multi_audit.active_session_id = result['session_id']
        multi_audit.session_mapping[first_category] = result['session_id']
       
        # Add multi-category info to response
        result['action'] = 'multi_category_started'
        result['multi_session_id'] = multi_session_id
        result['multi_audit_progress'] = multi_audit.get_progress_summary()
        result['message'] = f"**Multi-Category Audit Started**\n\nTotal categories: {len(categories)}\nStarting with: **{first_category}** (1 of {len(categories)})\n\n{result.get('message', '')}"
        
        print(f"DEBUG: Multi-category audit setup complete. Session created successfully.")
    else:
        print(f"DEBUG: Failed to start first category: {result}")
   
    return result


# def continue_to_next_category(user_id: str = "clyde") -> Dict[str, Any]:
#     """Continue to the next category in a multi-category audit"""
#     print(f"DEBUG: continue_to_next_category called for user {user_id}")
    
#     # Find user's multi-category audit
#     multi_audit = None
#     multi_session_id = None
    
#     for session_id, audit in multi_category_sessions.items():
#         if audit.user_id == user_id and audit.status == 'active':
#             multi_audit = audit
#             multi_session_id = session_id
#             break
    
#     if not multi_audit:
#         return {"error": "No active multi-category audit found"}
    
#     # Get next category
#     next_category = multi_audit.get_next_category()
#     if not next_category:
#         return {"error": "No more categories to audit"}
    
#     # Start audit for next category
#     result = start_audit_session(next_category, user_id)
    
#     if 'error' not in result:
#         # Update multi-audit tracking
#         multi_audit.active_session_id = result['session_id']
#         multi_audit.session_mapping[next_category] = result['session_id']
        
#         # Add transition info to response
#         result['action'] = 'next_category_started'
#         result['multi_session_id'] = multi_session_id
#         result['multi_audit_progress'] = multi_audit.get_progress_summary()
#         result['previous_category'] = multi_audit.categories[multi_audit.current_index - 1] if multi_audit.current_index > 0 else None
#         result['message'] = f"**Starting Next Category**\n\nNow auditing: **{next_category}** ({multi_audit.current_index + 1} of {len(multi_audit.categories)})\n\n{result.get('message', '')}"
    
#     return result

def continue_to_next_category(user_id: str = "clyde") -> Dict[str, Any]:
    """Continue to the next category in a multi-category audit"""
    print(f"DEBUG: continue_to_next_category called for user {user_id}")
   
    # Find user's multi-category audit
    multi_audit = None
    multi_session_id = None
   
    for session_id, audit in multi_category_sessions.items():
        if audit.user_id == user_id and audit.status == 'active':
            multi_audit = audit
            multi_session_id = session_id
            break
   
    if not multi_audit:
        return {"error": "No active multi-category audit found"}
   
    # Get next category
    next_category = multi_audit.get_next_category()
    print(f"DEBUG: Next category: {next_category}")
   
    if not next_category:
        return {"error": "No more categories to audit"}
    
    # Increment the index
    multi_audit.current_index += 1
    print(f"DEBUG: Incremented current_index to: {multi_audit.current_index}")
   
    # Start audit for next category
    result = start_audit_session(next_category, user_id)
   
    if 'error' not in result:
        # Update multi-audit tracking
        multi_audit.active_session_id = result['session_id']
        multi_audit.session_mapping[next_category] = result['session_id']
       
        # CRITICAL: Use the same action as category selection for consistent UI handling
        response = {
            "action": "category_selected",  # This is what Streamlit expects!
            "session_id": result['session_id'],
            "category": next_category,
            "current_question": result.get('current_question'),
            "progress": result.get('progress'),
            "multi_session_id": multi_session_id,
            "multi_audit_progress": multi_audit.get_progress_summary(),
            "previous_category": multi_audit.categories[multi_audit.current_index - 1] if multi_audit.current_index > 0 else None,
            "message": f"**Transitioning to Next Category**\n\nPrevious category completed! Now starting: **{next_category}** ({multi_audit.current_index} of {len(multi_audit.categories)})\n\n---\n\n{result.get('message', '')}",
            # Debug fields
            "transition": True,
            "from_continue": True
        }
        
        print(f"DEBUG: Returning response with action={response['action']}")
        print(f"DEBUG: Has current_question={bool(response.get('current_question'))}")
        print(f"DEBUG: Session ID={response.get('session_id')}")
        
        return response
   
    return result


    """Continue to the next category in a multi-category audit"""
    debug_info = []
    debug_info.append(f"🔍 DEBUG: continue_to_next_category called for user {user_id}")
   
    # Find user's multi-category audit
    multi_audit = None
    multi_session_id = None
   
    for session_id, audit in multi_category_sessions.items():
        if audit.user_id == user_id and audit.status == 'active':
            multi_audit = audit
            multi_session_id = session_id
            break
   
    if not multi_audit:
        return {"error": "No active multi-category audit found"}
   
    # Get next category
    next_category = multi_audit.get_next_category()
    debug_info.append(f"🔍 DEBUG: Next category: {next_category}")
    debug_info.append(f"🔍 DEBUG: Current index before increment: {multi_audit.current_index}")
   
    if not next_category:
        return {"error": "No more categories to audit"}
    
    # NOW increment the index since we're actually moving to next category
    multi_audit.current_index += 1
    debug_info.append(f"🔍 DEBUG: Incremented current_index to: {multi_audit.current_index}")
   
    # Start audit for next category
    result = start_audit_session(next_category, user_id)
   
    if 'error' not in result:
        # Update multi-audit tracking
        multi_audit.active_session_id = result['session_id']
        multi_audit.session_mapping[next_category] = result['session_id']
       
        # Preserve the original session result but add multi-category context
        result['action'] = 'next_category_started'
        result['multi_session_id'] = multi_session_id
        result['multi_audit_progress'] = multi_audit.get_progress_summary()
        result['previous_category'] = multi_audit.categories[multi_audit.current_index - 1] if multi_audit.current_index > 0 else None
        
        # IMPORTANT: Preserve the original message from start_audit_session but add context
        original_message = result.get('message', '')
        result['message'] = f"**Transitioning to Next Category**\n\nPrevious category completed! Now starting: **{next_category}** ({multi_audit.current_index} of {len(multi_audit.categories)})\n\n---\n\n{original_message}"
        
        # Make sure we have the current question available for the UI
        if 'current_question' not in result and 'session_id' in result:
            current_q_result = get_current_question(result['session_id'])
            if 'current_question' in current_q_result:
                result['current_question'] = current_q_result['current_question']
   
    return result


    """Continue to the next category in a multi-category audit"""
    debug_info = []
    debug_info.append(f"🔍 DEBUG: continue_to_next_category called for user {user_id}")
    
    # DEBUG: Show all multi-category sessions
    debug_info.append(f"🔍 DEBUG: All multi_category_sessions: {list(multi_category_sessions.keys())}")
    for session_id, audit in multi_category_sessions.items():
        debug_info.append(f"🔍 DEBUG: Session {session_id}: user='{audit.user_id}', status='{audit.status}', categories={audit.categories}")
        debug_info.append(f"🔍 DEBUG: Session {session_id}: current_index={audit.current_index}, completed={audit.completed_categories}")
    
    # Find user's multi-category audit
    multi_audit = None
    multi_session_id = None
    
    for session_id, audit in multi_category_sessions.items():
        debug_info.append(f"🔍 DEBUG: Checking session {session_id}: user_id match={audit.user_id == user_id}, status_active={audit.status == 'active'}")
        if audit.user_id == user_id and audit.status == 'active':
            multi_audit = audit
            multi_session_id = session_id
            debug_info.append(f"🔍 DEBUG: Found matching multi-audit: {session_id}")
            break
    
    if not multi_audit:
        debug_info.append(f"🔍 DEBUG: No active multi-category audit found for user {user_id}")
        return {
            "error": "No active multi-category audit found",
            "message": "\n".join(debug_info) + "\n\n❌ **Error:** No active multi-category audit found"
        }
    
    # Get next category
    next_category = multi_audit.get_next_category()
    debug_info.append(f"🔍 DEBUG: Next category from multi_audit.get_next_category(): {next_category}")
    debug_info.append(f"🔍 DEBUG: Current index: {multi_audit.current_index}, Total categories: {len(multi_audit.categories)}")
    debug_info.append(f"🔍 DEBUG: All categories: {multi_audit.categories}")
    
    if not next_category:
        debug_info.append(f"🔍 DEBUG: No more categories - current_index={multi_audit.current_index}, categories={multi_audit.categories}")
        return {
            "error": "No more categories to audit",
            "message": "\n".join(debug_info) + "\n\n❌ **Error:** No more categories to audit"
        }
    multi_audit.current_index += 1  # Move to next category index
    
    # Start audit for next category
    debug_info.append(f"🔍 DEBUG: Starting audit for next category: {next_category}")
    result = start_audit_session(next_category, user_id)
    
    if 'error' not in result:
        # Update multi-audit tracking
        multi_audit.active_session_id = result['session_id']
        multi_audit.session_mapping[next_category] = result['session_id']
        
        # Add transition info to response
        result['action'] = 'next_category_started'
        result['multi_session_id'] = multi_session_id
        result['multi_audit_progress'] = multi_audit.get_progress_summary()
        result['previous_category'] = multi_audit.categories[multi_audit.current_index - 1] if multi_audit.current_index > 0 else None
        
        # Add debug info to the message
        debug_message = "\n".join(debug_info) + f"\n\n✅ **Successfully set up next category transition**"
        result['message'] = f"{debug_message}\n\n**Starting Next Category**\n\nNow auditing: **{next_category}** ({multi_audit.current_index + 1} of {len(multi_audit.categories)})\n\n{result.get('message', '')}"
        
        debug_info.append(f"🔍 DEBUG: Successfully set up next category transition")
    else:
        debug_info.append(f"🔍 DEBUG: Error starting next category: {result}")
        result['message'] = "\n".join(debug_info) + f"\n\n❌ **Error starting next category:** {result}"
    
    return result



def get_user_multi_category_audit(category: str, user_id: str = "default") -> Optional[MultiCategoryAudit]:
    """Find multi-category audit that contains the given category"""
    for multi_audit in multi_category_sessions.values():
        if (category in multi_audit.categories and 
            multi_audit.status == 'active' and
            multi_audit.user_id == user_id):
            return multi_audit
    return None


# def process_chat_message(message: str, context: Dict[str, Any]) -> Dict[str, Any]:
#     """Process a conversational message and determine the appropriate action"""
#     message_lower = message.lower()
#     user_id = context.get('user_id', 'default')
   
#     print(f"DEBUG: Processing message: '{message}' for user: {user_id}")
   
#     # Check for continuation commands for multi-category audits
#     continue_keywords = ["continue", "next", "proceed", "move on", "next category"]
#     if any(keyword in message_lower for keyword in continue_keywords):
#         print(f"DEBUG: Detected continuation command")
#         return continue_to_next_category(user_id)
   
#     # Check for multi-category audit request
#     if any(keyword in message_lower for keyword in ["multi", "multiple", "several", "all categories", "batch"]):
#         detected_categories = []
#         nist_categories = get_nist_categories()
       
#         # Improved category detection
#         for category in nist_categories:
#             category_lower = category.lower()
#             if category_lower in message_lower:
#                 detected_categories.append(category)
#             elif "explainable" in message_lower and "explainable and interpretable" in category_lower:
#                 detected_categories.append(category)
#             elif "interpretable" in message_lower and "explainable and interpretable" in category_lower:
#                 detected_categories.append(category)
#             elif ("fair" in message_lower or "bias" in message_lower) and "fair – with harmful bias managed" in category_lower:
#                 detected_categories.append(category)
#             elif "privacy" in message_lower and "privacy-enhanced" in category_lower:
#                 detected_categories.append(category)
#             elif ("valid" in message_lower and "reliable" in message_lower) and "valid & reliable" in category_lower:
#                 detected_categories.append(category)
#             elif "safe" in message_lower and category_lower == "safe":
#                 detected_categories.append(category)
#             elif ("secure" in message_lower or "resilient" in message_lower) and "secure & resilient" in category_lower:
#                 detected_categories.append(category)
#             elif ("accountable" in message_lower or "transparent" in message_lower) and "accountable & transparent" in category_lower:
#                 detected_categories.append(category)
       
#         # Remove duplicates while preserving order
#         detected_categories = list(dict.fromkeys(detected_categories))
       
#         if len(detected_categories) >= 2:
#             print(f"DEBUG: Starting multi-category audit for: {detected_categories}")
#             return start_multi_category_audit(detected_categories, user_id)
   
#     # Single category detection
#     detected_category = None
#     if "privacy-enhanced" in message_lower or "privacy" in message_lower:
#         detected_category = "Privacy-Enhanced"
#     elif "valid" in message_lower and "reliable" in message_lower:
#         detected_category = "Valid & Reliable"
#     elif "safe" in message_lower:
#         detected_category = "Safe"
#     elif "secure" in message_lower or "resilient" in message_lower:
#         detected_category = "Secure & Resilient"
#     elif "accountable" in message_lower or "transparent" in message_lower:
#         detected_category = "Accountable & Transparent"
#     elif "explainable" in message_lower or "interpretable" in message_lower:
#         detected_category = "Explainable and Interpretable"
#     elif "fair" in message_lower or "bias" in message_lower:
#         detected_category = "Fair – With Harmful Bias Managed"
   
#     if detected_category:
#         print(f"DEBUG: Starting audit for: {detected_category}")
#         return start_audit_session(detected_category, user_id)
   
#     # Check if there's an active session and continue with it
#     active_session_id = user_sessions.get(user_id)
#     if active_session_id and active_session_id in audit_sessions:
#         session = audit_sessions[active_session_id]
       
#         if session.status == "completed":
#             return {
#                 "action": "audit_completed",
#                 "message": f"🎉 **Audit Completed!**\n\nYou have successfully completed the NIST AI RMF audit for **{session.category}**."
#             }
       
#         current_q = session.get_current_question()
#         if current_q:
#             if session.state == "waiting_for_question_answer":
#                 return submit_answer(active_session_id, message)
#             elif session.state == "waiting_for_evidence":
#                 return submit_evidence(active_session_id, message, user_id)
   
#     # Default help response
#     return {
#         "action": "help",
#         "message": "I'm here to help you conduct NIST AI RMF audits. You can:\n\n" +
#                   "• Select a single category to audit\n" +
#                   "• Start a multi-category audit by saying 'multi-category audit for Privacy-Enhanced and Safe'\n" +
#                   "• Continue an existing audit session\n\n" +
#                   "Available categories:\n" + "\n".join([f"• {cat}" for cat in get_nist_categories()]) +
#                   "\n\nWhich category would you like to audit?"
#     }
def process_chat_message(message: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Process a conversational message and determine the appropriate action"""
    message_lower = message.lower()
    user_id = context.get('user_id', 'default')
   
    print(f"DEBUG: Processing message: '{message}' for user: {user_id}")
   
    # Check for continuation commands for multi-category audits
    continue_keywords = ["continue", "next", "proceed", "move on", "next category"]
    if any(keyword in message_lower for keyword in continue_keywords):
        print(f"DEBUG: Detected continuation command")
        return continue_to_next_category(user_id)
   
    # Check for multi-category audit request
    if any(keyword in message_lower for keyword in ["multi", "multiple", "several", "all categories", "batch"]):
        print(f"DEBUG: Detected multi-category request in message: '{message}'")
        detected_categories = []
        nist_categories = get_nist_categories()
       
        # Improved category detection
        for category in nist_categories:
            category_lower = category.lower()
            if category_lower in message_lower:
                detected_categories.append(category)
            elif "explainable" in message_lower and "explainable and interpretable" in category_lower:
                detected_categories.append(category)
            elif "interpretable" in message_lower and "explainable and interpretable" in category_lower:
                detected_categories.append(category)
            elif ("fair" in message_lower or "bias" in message_lower) and "fair – with harmful bias managed" in category_lower:
                detected_categories.append(category)
            elif "privacy" in message_lower and "privacy-enhanced" in category_lower:
                detected_categories.append(category)
            elif ("valid" in message_lower and "reliable" in message_lower) and "valid & reliable" in category_lower:
                detected_categories.append(category)
            elif "safe" in message_lower and category_lower == "safe":
                detected_categories.append(category)
            elif ("secure" in message_lower or "resilient" in message_lower) and "secure & resilient" in category_lower:
                detected_categories.append(category)
            elif ("accountable" in message_lower or "transparent" in message_lower) and "accountable & transparent" in category_lower:
                detected_categories.append(category)
       
        # Remove duplicates while preserving order
        detected_categories = list(dict.fromkeys(detected_categories))
        print(f"DEBUG: Detected categories from message: {detected_categories}")
       
        if len(detected_categories) >= 2:
            print(f"DEBUG: Starting multi-category audit for: {detected_categories}")
            return start_multi_category_audit(detected_categories, user_id)
        else:
            print(f"DEBUG: Not enough categories detected for multi-category audit: {len(detected_categories)}")
   
    # Single category detection
    detected_category = None
    if "privacy-enhanced" in message_lower or "privacy" in message_lower:
        detected_category = "Privacy-Enhanced"
    elif "valid" in message_lower and "reliable" in message_lower:
        detected_category = "Valid & Reliable"
    elif "safe" in message_lower:
        detected_category = "Safe"
    elif "secure" in message_lower or "resilient" in message_lower:
        detected_category = "Secure & Resilient"
    elif "accountable" in message_lower or "transparent" in message_lower:
        detected_category = "Accountable & Transparent"
    elif "explainable" in message_lower or "interpretable" in message_lower:
        detected_category = "Explainable and Interpretable"
    elif "fair" in message_lower or "bias" in message_lower:
        detected_category = "Fair – With Harmful Bias Managed"
   
    if detected_category:
        print(f"DEBUG: Starting audit for single category: {detected_category}")
        return start_audit_session(detected_category, user_id)
   
    # Check if there's an active session and continue with it
    active_session_id = user_sessions.get(user_id)
    if active_session_id and active_session_id in audit_sessions:
        session = audit_sessions[active_session_id]
       
        if session.status == "completed":
            return {
                "action": "audit_completed",
                "message": f"🎉 **Audit Completed!**\n\nYou have successfully completed the NIST AI RMF audit for **{session.category}**."
            }
       
        current_q = session.get_current_question()
        if current_q:
            if session.state == "waiting_for_question_answer":
                return submit_answer(active_session_id, message)
            elif session.state == "waiting_for_evidence":
                return submit_evidence(active_session_id, message, user_id)
   
    # Default help response
    return {
        "action": "help",
        "message": "I'm here to help you conduct NIST AI RMF audits. You can:\n\n" +
                  "• Select a single category to audit\n" +
                  "• Start a multi-category audit by saying 'multi-category audit for Privacy-Enhanced and Safe'\n" +
                  "• Continue an existing audit session\n\n" +
                  "Available categories:\n" + "\n".join([f"• {cat}" for cat in get_nist_categories()]) +
                  "\n\nWhich category would you like to audit?"
    }


# Main routing function
def run_tool(action: str, **kwargs) -> Dict[str, Any]:
    """Main tool function that routes different audit actions"""
    try:
        if action == "get_categories":
            return get_audit_categories()
        elif action == "start_session":
            return start_audit_session(kwargs.get('category'), kwargs.get('user_id', 'default'))
        elif action == "get_current_question":
            return get_current_question(kwargs.get('session_id'))
        elif action == "submit_answer":
            return submit_answer(kwargs.get('session_id'), kwargs.get('answer'))
        elif action == "submit_evidence":
            return submit_evidence(kwargs.get('session_id'), kwargs.get('evidence'), kwargs.get('user_id', 'clyde'))
        elif action == "process_chat":
            return process_chat_message(kwargs.get('message', ''), kwargs.get('context', {}))
        elif action == "start_multi_category_audit":
            return start_multi_category_audit(kwargs.get('categories', []), kwargs.get('user_id', 'clyde'))
        elif action == "continue_to_next_category":
            return continue_to_next_category(kwargs.get('user_id', 'clyde'))
        else:
            return {"error": f"Unknown action: {action}"}
    except Exception as e:
        return {"error": f"Tool execution failed: {str(e)}"}


# Capabilities for agent introspection
def get_capabilities() -> Dict[str, Any]:
    return {
        "capabilities": [
            "NIST AI RMF Category Selection",
            "Structured Audit Questioning",
            "Evidence Evaluation",
            "Conformity Assessment",
            "Audit Progress Tracking",
            "Multi-Category Sequential Audits with Manual Transitions"
        ],
        "actions": [
            "get_categories",
            "start_session",
            "get_current_question",
            "submit_answer",
            "submit_evidence",
            "start_multi_category_audit",
            "continue_to_next_category"
        ]
    }
