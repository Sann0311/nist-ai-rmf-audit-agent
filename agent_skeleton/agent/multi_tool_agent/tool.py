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
        result["message"] = f"**Evidence Evaluation:**\n\n**Conformity Level:** {evaluation['conformity']}\n\n**Justification:** {evaluation['justification']}\n\n**Next Sub-Question:**\n{next_question['sub_question']}\n\nPlease provide your observation/answer for this question."
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
        else:
            return {"error": f"Unknown action: {action}"}
    except Exception as e:
        return {"error": f"Tool execution failed: {str(e)}"}

def process_chat_message(message: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Process a conversational message and determine the appropriate action"""
    message_lower = message.lower()
    user_id = context.get('user_id', 'default')
    
    print(f"DEBUG: Processing message: '{message}'")
    
    # SIMPLE DIRECT CATEGORY DETECTION - check if any category name is in the message
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
        "message": "I'm here to help you conduct a NIST AI RMF audit. Please select one of the 7 categories to begin:\n\n" +
                  "\n".join([f"• {cat}" for cat in get_nist_categories()]) +
                  "\n\nWhich category would you like to audit?"
    }
    
    # No category detected, check for active session continuation
    active_session_id = user_sessions.get(user_id)
    if active_session_id and active_session_id in audit_sessions:
        session = audit_sessions[active_session_id]
        
        if session.status == "completed":
            print(f"DEBUG: Session completed")
            return {
                "action": "audit_completed",
                "message": f"🎉 **Audit Completed!**\n\nYou have successfully completed the NIST AI RMF audit for **{session.category}**."
            }
        
        current_q = session.get_current_question()
        
        print(f"DEBUG: Found active session {active_session_id}, state: {session.state}")
        
        if current_q:
            # Check session state to determine what we're waiting for
            if session.state == "waiting_for_question_answer":
                print(f"DEBUG: Treating as answer/observation")
                return submit_answer(active_session_id, message)
            elif session.state == "waiting_for_evidence":
                print(f"DEBUG: Treating as evidence submission")
                return submit_evidence(active_session_id, message)
        else:
            print(f"DEBUG: Session completed")
            return {
                "action": "audit_completed",
                "message": f"🎉 **Audit Completed!**\n\nYou have successfully completed the NIST AI RMF audit for **{session.category}**."
            }
    
    # Default response for unrecognized input
    return {
        "action": "help",
        "message": "I'm here to help you conduct a NIST AI RMF audit. Please select one of the 7 categories to begin:\n\n" +
                  "\n".join([f"• {cat}" for cat in get_nist_categories()]) +
                  "\n\nWhich category would you like to audit?"
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
            "Multi-session Management"
        ],
        "actions": [
            "get_categories",
            "start_session", 
            "get_current_question",
            "submit_answer",
            "submit_evidence"
        ]
    }
