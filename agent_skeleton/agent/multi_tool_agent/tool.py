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

def cleanup_old_sessions():
    """Remove completed sessions to prevent memory buildup"""
    global audit_sessions, user_sessions
    completed_sessions = [sid for sid, session in audit_sessions.items() if session.status == "completed"]
    for sid in completed_sessions[-5:]:  # Keep only last 5 completed sessions
        if len([s for s in audit_sessions.values() if s.status == "completed"]) > 5:
            del audit_sessions[sid]

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
    
    # Clean up old sessions
    cleanup_old_sessions()
    
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

def submit_evidence(session_id: str, evidence: str) -> Dict[str, Any]:
    """Submit evidence and get evaluation"""
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
        result["next_question"] = next_question
        result["message"] = f"**Evidence Evaluation:**\n\n**Conformity Level:** {evaluation['conformity']}\n\n**Justification:** {evaluation['justification']}"
        result["completed"] = False
    else:
        result["message"] = f"**Evidence Evaluation:**\n\n**Conformity Level:** {evaluation['conformity']}\n\n**Justification:** {evaluation['justification']}\n\n🎉 **Audit Completed!**\n\nYou have successfully completed the NIST AI RMF audit for **{session.category}**.\n\n**Summary:**\n• Total Questions: {session.get_progress()['total']}\n• Observations Recorded: {len(session.observations)}\n• Evidence Evaluations: {len(session.evidence_evaluations)}"
        result["status"] = "completed"
        result["completed"] = True
    
    return result

# Main routing function
def run_tool(action: str, **kwargs) -> Dict[str, Any]:
    """
    Main tool function that routes different audit actions
    """
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
            return submit_evidence(kwargs.get('session_id'), kwargs.get('evidence'))
        elif action == "process_chat":
            return process_chat_message(kwargs.get('message', ''), kwargs.get('context', {}))
        elif action == "start_multi_category_audit":
            return start_multi_category_audit(kwargs.get('categories', []), kwargs.get('user_id', 'default'))
        elif action == "complete_category_and_next":
            return complete_category_and_next(kwargs.get('multi_session_id'))
        elif action == "get_multi_category_status":
            return get_multi_category_status(kwargs.get('multi_session_id'))
        else:
            return {"error": f"Unknown action: {action}"}
    except Exception as e:
        return {"error": f"Tool execution failed: {str(e)}"}

def process_chat_message(message: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Process a conversational message and determine the appropriate action"""
    message_lower = message.lower()
    user_id = context.get('user_id', 'default')
    
    print(f"DEBUG: Processing message: '{message}'")
    
    # Check for multi-category audit request FIRST
    if any(keyword in message_lower for keyword in ["multi", "multiple", "several", "all categories", "batch"]):
        detected_categories = []
        nist_categories = get_nist_categories()
        
        # Look for multiple categories mentioned in the message
        for category in nist_categories:
            if category.lower() in message_lower:
                detected_categories.append(category)
        
        # If multiple categories detected, start multi-category audit
        if len(detected_categories) >= 2:
            print(f"DEBUG: Starting multi-category audit for: {detected_categories}")
            return start_multi_category_audit(detected_categories, user_id)
        elif len(detected_categories) == 1:
            # Only one category detected with multi keyword, ask for clarification
            return {
                "action": "clarification_needed",
                "message": f"I detected you want a multi-category audit, but only found one category: **{detected_categories[0]}**.\n\nPlease specify which additional categories you'd like to include in your multi-category audit from:\n" + 
                          "\n".join([f"• {cat}" for cat in nist_categories if cat != detected_categories[0]])
            }
        elif "multi" in message_lower or "multiple" in message_lower:
            # Multi requested but no specific categories found
            return {
                "action": "help", 
                "message": "I can help you start a multi-category audit! Please specify which categories you'd like to audit from:\n\n" +
                          "\n".join([f"• {cat}" for cat in nist_categories]) +
                          "\n\nFor example: 'I want to audit Privacy-Enhanced, Safe, and Secure & Resilient categories'"
            }
    
    # EXISTING SINGLE CATEGORY DETECTION (unchanged)
    categories = get_nist_categories()
    detected_category = None
    
    # Direct simple matching - just check if category name appears anywhere in message
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
    elif "general" in message_lower and "audit" in message_lower:
        detected_category = "Privacy-Enhanced"  # Default to first category
    
    print(f"DEBUG: Detected category: {detected_category}")
    
    # If we found a category, start the audit session immediately
    if detected_category:
        print(f"DEBUG: Starting audit for: {detected_category}")
        return start_audit_session(detected_category, user_id)
    
    # Check if there's an active session and continue with it
    active_session_id = user_sessions.get(user_id)
    if active_session_id and active_session_id in audit_sessions:
        session = audit_sessions[active_session_id]
        
        if session.status == "completed":
            # Check if this was part of a multi-category audit
            for multi_id, multi_session in multi_category_sessions.items():
                if (multi_session['user_id'] == user_id and 
                    multi_session['status'] == 'active' and
                    active_session_id in multi_session['sessions'].values()):
                    print(f"DEBUG: Category completed, moving to next in multi-audit: {multi_id}")
                    return complete_category_and_next(multi_id)
            
            # Single category audit completed
            return {
                "action": "audit_completed",
                "message": f"🎉 **Audit Completed!**\n\nYou have successfully completed the NIST AI RMF audit for **{session.category}**."
            }
        
        current_q = session.get_current_question()
        if current_q:
            # Check session state to determine what we're waiting for
            if session.state == "waiting_for_question_answer":
                return submit_answer(active_session_id, message)
            elif session.state == "waiting_for_evidence":
                return submit_evidence(active_session_id, message)
    
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

# Multi-category audit session management
multi_category_sessions = {}

def start_multi_category_audit(categories: List[str], user_id: str = "default") -> Dict[str, Any]:
    """Start a multi-category audit session - NEW FUNCTION"""
    if not categories:
        return {"error": "No categories provided"}
    
    if len(categories) < 2:
        return {"error": "Multi-category audit requires at least 2 categories"}
    
    # Validate categories using existing function
    valid_categories = get_nist_categories()
    invalid_categories = [cat for cat in categories if cat not in valid_categories]
    if invalid_categories:
        return {"error": f"Invalid categories: {invalid_categories}"}
    
    # Create a multi-category session tracker
    multi_session_id = f"multi_audit_{user_id}_{hashlib.md5('_'.join(categories).encode()).hexdigest()[:8]}"
    
    # Store multi-category session info
    multi_category_sessions[multi_session_id] = {
        'user_id': user_id,
        'categories': categories,
        'current_category_index': 0,
        'completed_categories': [],
        'sessions': {},
        'status': 'active'
    }
    
    # Start first category using existing function
    first_category = categories[0]
    result = start_audit_session(first_category, user_id)
    
    if 'error' not in result:
        multi_category_sessions[multi_session_id]['sessions'][first_category] = result['session_id']
        result['multi_session_id'] = multi_session_id
        result['total_categories'] = len(categories)
        result['current_category_index'] = 1
        result['remaining_categories'] = categories[1:]
        result['action'] = 'multi_category_started'
        result['message'] = f"**Multi-Category Audit Started**\n\nTotal categories: {len(categories)}\nCurrent: **{first_category}** (1 of {len(categories)})\n\n{result.get('message', '')}"
    
    return result

def complete_category_and_next(multi_session_id: str) -> Dict[str, Any]:
    """Complete current category and move to next one"""
    if multi_session_id not in multi_category_sessions:
        return {"error": "Invalid multi-session ID"}
    
    multi_session = multi_category_sessions[multi_session_id]
    current_index = multi_session['current_category_index']
    categories = multi_session['categories']
    
    # Mark current category as completed
    if current_index <= len(categories):
        completed_category = categories[current_index - 1]
        multi_session['completed_categories'].append(completed_category)
    
    # Check if all categories are completed
    if current_index >= len(categories):
        multi_session['status'] = 'completed'
        return {
            "action": "multi_audit_completed",
            "message": f"🎉 **Multi-Category Audit Completed!**\n\nCompleted all {len(categories)} categories:\n" + 
                      "\n".join([f"✅ {cat}" for cat in multi_session['completed_categories']]),
            "completed_categories": multi_session['completed_categories'],
            "total_categories": len(categories),
            "status": "completed"
        }
    
    # Start next category
    next_category = categories[current_index]
    user_id = multi_session['user_id']
    
    result = start_audit_session(next_category, user_id)
    
    if 'error' not in result:
        multi_session['current_category_index'] = current_index + 1
        multi_session['sessions'][next_category] = result['session_id']
        
        result['multi_session_id'] = multi_session_id
        result['total_categories'] = len(categories)
        result['current_category_index'] = current_index + 1
        result['completed_categories'] = multi_session['completed_categories']
        result['remaining_categories'] = categories[current_index + 1:]
        result['action'] = 'next_category_started'
        result['message'] = f"**Category Completed!** ✅ {multi_session['completed_categories'][-1]}\n\n**Next Category:** **{next_category}** ({current_index + 1} of {len(categories)})\n\n{result.get('message', '')}"
    
    return result

def get_multi_category_status(multi_session_id: str) -> Dict[str, Any]:
    """Get status of multi-category audit"""
    if multi_session_id not in multi_category_sessions:
        return {"error": "Invalid multi-session ID"}
    
    session = multi_category_sessions[multi_session_id]
    return {
        "multi_session_id": multi_session_id,
        "categories": session['categories'],
        "current_category_index": session['current_category_index'],
        "completed_categories": session['completed_categories'],
        "status": session['status'],
        "total_categories": len(session['categories'])
    }

# Capabilities for agent introspection
def get_capabilities() -> Dict[str, Any]:
    return {
        "capabilities": [
            "NIST AI RMF Category Selection",
            "Structured Audit Questioning", 
            "Evidence Evaluation",
            "Conformity Assessment",
            "Audit Progress Tracking",
            "Multi-session Management",
            "Multi-Category Sequential Audits"
        ],
        "actions": [
            "get_categories",
            "start_session", 
            "get_current_question",
            "submit_answer",
            "submit_evidence",
            "start_multi_category_audit",
            "complete_category_and_next"
        ]
    }
