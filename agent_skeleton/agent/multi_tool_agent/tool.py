from pydantic import BaseModel
from typing import Any, Dict, List, Optional
import pandas as pd
import os
import hashlib
import logging
import uuid
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

# Configuration
DEFAULT_USER_ID = "clyde"
AUDIT_KEYWORDS = {
    'policy', 'documentation', 'config', 'screenshot', 'logs', 'audit',
    'compliance', 'review', 'approval', 'signed', 'attestation', 'report',
    'testing', 'validation', 'monitoring', 'procedure', 'checklist'
}

def load_audit_data():
    """Load and structure the audit data from the Excel file"""
    try:
        # Environment-aware file paths
        possible_paths = [
            os.getenv('AUDIT_FILE_PATH', '/app/Audit.xlsx'),  # Docker/production
            Path.cwd() / 'Audit.xlsx',  # Current directory
            Path.cwd() / 'data' / 'Audit.xlsx',  # Data subdirectory
        ]
        
        df = None
        for path in possible_paths:
            try:
                df = pd.read_excel(path, sheet_name="GenAI Security Audit Sheet")
                logger.info(f"Successfully loaded audit data from: {path}")
                logger.info(f"Data shape: {df.shape}, Columns: {list(df.columns)}")
                break
            except FileNotFoundError:
                continue
            except Exception as e:
                logger.warning(f"Error reading {path}: {e}")
                continue
        
        if df is None:
            logger.error(f"Could not find Audit.xlsx in any of these paths: {possible_paths}")
            return None
            
        return df
    except Exception as e:
        logger.error(f"Error loading audit data: {e}")
        return None

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

# Global session storage
audit_sessions = {}
user_sessions = {}
multi_category_sessions = {}

class MultiCategoryAudit:
    """Clean multi-category audit state management"""
    
    def __init__(self, user_id: str, categories: List[str]):
        self.user_id = user_id
        self.categories = categories
        self.current_index = 0
        self.completed_categories = []
        self.active_session_id = None
        self.status = 'active'
        self.session_mapping = {}
    
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
    
    def advance_to_next_category(self):
        """Move the index to the next category"""
        self.current_index += 1
    
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

def generate_session_id(category: str, user_id: str) -> str:
    """Generate a secure session ID"""
    base_string = f"{user_id}_{category}_{uuid.uuid4().hex[:8]}"
    return f"audit_{hashlib.md5(base_string.encode()).hexdigest()[:16]}"

class AuditSession:
    def __init__(self, session_id: str, category: str):
        self.session_id = session_id
        self.category = category
        self.questions = []
        self.current_question_idx = 0
        self.observations = []
        self.evidence_evaluations = []
        self.status = "started"
        self.state = "waiting_for_question_answer"
        self._load_category_questions()
    
    def _load_category_questions(self):
        """Load questions for the selected category"""
        df = load_audit_data()
        if df is not None:
            category_data = df[df['Trust-worthiness characteristic'] == self.category]
            logger.info(f"Found {len(category_data)} rows for category: {self.category}")
            
            for _, row in category_data.iterrows():
                if pd.notna(row['Sub Question']) and row['Sub Question'].strip():
                    question = {
                        'sub_question': row['Sub Question'],
                        'baseline_evidence': row['Baseline Evidence '] if pd.notna(row['Baseline Evidence ']) else '',
                        'nist_control': row['NIST AI RMF Control'] if pd.notna(row['NIST AI RMF Control']) else '',
                        'question_id': row['Question ID'] if pd.notna(row['Question ID']) else ''
                    }
                    self.questions.append(question)
            
            logger.info(f"Loaded {len(self.questions)} sub-questions for {self.category}")
    
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
        """Enhanced evidence evaluation against baseline"""
        current_q = self.get_current_question()
        if not current_q:
            return {"error": "No current question"}
        
        baseline_evidence = current_q['baseline_evidence']
        
        # Enhanced evaluation logic
        evidence_lower = evidence.lower()
        baseline_lower = baseline_evidence.lower()
        
        # Extract meaningful words (length > 3)
        evidence_words = set(
            word.strip('.,!?()[]{}":;') 
            for word in evidence_lower.split() 
            if len(word) > 3
        )
        baseline_words = set(
            word.strip('.,!?()[]{}":;') 
            for word in baseline_lower.split() 
            if len(word) > 3
        )
        
        # Find audit-specific terms
        evidence_audit_terms = evidence_words.intersection(AUDIT_KEYWORDS)
        baseline_audit_terms = baseline_words.intersection(AUDIT_KEYWORDS)
        
        # Calculate overlap scores
        word_overlap = len(evidence_words.intersection(baseline_words))
        audit_overlap = len(evidence_audit_terms.intersection(baseline_audit_terms))
        
        # Evidence quality metrics
        evidence_length = len(evidence.strip())
        baseline_requirements = baseline_evidence.count('\n') + baseline_evidence.count('.')
        
        # Calculate conformity score
        total_score = (
            (word_overlap * 0.4) + 
            (audit_overlap * 0.4) + 
            (min(evidence_length/200, 1) * 0.2)
        )
        
        # Determine conformity level
        if total_score >= 0.8 and evidence_length > 100 and audit_overlap >= 2:
            conformity = "Full Conformity"
            justification = (
                f"Provided evidence comprehensively addresses baseline requirements "
                f"with {audit_overlap} key audit elements and strong content overlap "
                f"({word_overlap} matching terms)."
            )
        elif total_score >= 0.5 and evidence_length > 50 and audit_overlap >= 1:
            conformity = "Partial Conformity"
            justification = (
                f"Provided evidence partially meets baseline requirements with "
                f"{audit_overlap} audit elements. Consider providing additional "
                f"documentation or details to achieve full conformity."
            )
        else:
            conformity = "No Conformity"
            justification = (
                f"Provided evidence does not adequately match baseline requirements. "
                f"Missing key audit elements and insufficient detail. Please review "
                f"baseline evidence requirements and provide comprehensive documentation."
            )
        
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

def start_audit_session(category: str, user_id: str = DEFAULT_USER_ID) -> Dict[str, Any]:
    """Start a new audit session for the selected category"""
    if category not in get_nist_categories():
        return {
            "error": f"Invalid category. Please select from: {', '.join(get_nist_categories())}"
        }
    
    # Generate unique session ID
    session_id = generate_session_id(category, user_id)
    
    # Check if user already has an active session for this category
    existing_session_id = None
    for sid, session in audit_sessions.items():
        if (session.category == category and 
            sid.startswith(f"audit_") and 
            session.status != "completed"):
            existing_session_id = sid
            break
    
    if existing_session_id:
        existing_session = audit_sessions[existing_session_id]
        current_question = existing_session.get_current_question()
        
        return {
            "action": "session_exists",
            "session_id": existing_session_id,
            "category": category,
            "message": (
                f"You already have an active audit session for **{category}**. "
                f"Continuing from where you left off.\n\n"
                f"**Current Sub-Question:**\n{current_question['sub_question']}\n\n"
                f"Please provide your observation/answer for this question."
            ),
            "current_question": current_question,
            "progress": existing_session.get_progress()
        }
    
    # Create new session
    session = AuditSession(session_id, category)
    audit_sessions[session_id] = session
    user_sessions[user_id] = session_id
    
    current_question = session.get_current_question()
    
    return {
        "action": "category_selected",
        "session_id": session_id,
        "category": category,
        "message": (
            f"Excellent! I've started your NIST AI RMF audit for **{category}**.\n\n"
            f"**Current Sub-Question:**\n{current_question['sub_question']}\n\n"
            f"Please provide your observation/answer for this question."
        ),
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
    baseline_evidence = current_question['baseline_evidence']
    
    return {
        "action": "observation_recorded",
        "observation": answer,
        "baseline_evidence": baseline_evidence,
        "message": (
            f"**Observation Recorded:** {answer}\n\n"
            f"**Baseline Evidence Requirements:**\n{baseline_evidence}\n\n"
            f"Please provide evidence that demonstrates compliance with these baseline requirements."
        )
    }

def submit_evidence(session_id: str, evidence: str, user_id: str = DEFAULT_USER_ID) -> Dict[str, Any]:
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
        # Continue with next question in same category
        result["next_question"] = next_question
        result["message"] = (
            f"**Evidence Evaluation:**\n\n"
            f"**Conformity Level:** {evaluation['conformity']}\n\n"
            f"**Justification:** {evaluation['justification']}"
        )
        result["completed"] = False
    else:
        # Category completed - check if this is part of a multi-category audit
        multi_audit = get_user_multi_category_audit(session.category, user_id)
        
        if multi_audit:
            logger.info(f"Category '{session.category}' completed for multi-audit")
            multi_audit.mark_current_completed()
            
            if multi_audit.is_completed():
                # All categories completed
                result["action"] = "multi_audit_completed"
                result["message"] = (
                    f"**Evidence Evaluation:**\n\n"
                    f"**Conformity Level:** {evaluation['conformity']}\n\n"
                    f"**Justification:** {evaluation['justification']}\n\n"
                    f"🎉 **Multi-Category Audit Completed!**\n\n"
                    f"You have successfully completed all {len(multi_audit.categories)} categories!"
                )
                result["multi_audit_summary"] = multi_audit.get_progress_summary()
                result["completed"] = True
            else:
                # More categories to go - show transition option
                next_category = multi_audit.get_next_category()
                result["action"] = "category_completed_multi"
                result["message"] = (
                    f"**Evidence Evaluation:**\n\n"
                    f"**Conformity Level:** {evaluation['conformity']}\n\n"
                    f"**Justification:** {evaluation['justification']}\n\n"
                    f"🎉 **Category '{session.category}' Completed!**\n\n"
                    f"Next category: **{next_category}**\n\n"
                    f"Click 'Continue to Next Category' when you're ready to proceed."
                )
                result["multi_audit_progress"] = multi_audit.get_progress_summary()
                result["next_category"] = next_category
                result["completed"] = False
                result["needs_transition"] = True
        else:
            # Single category audit completed
            result["message"] = (
                f"**Evidence Evaluation:**\n\n"
                f"**Conformity Level:** {evaluation['conformity']}\n\n"
                f"**Justification:** {evaluation['justification']}\n\n"
                f"🎉 **Audit Completed!**\n\n"
                f"You have successfully completed the NIST AI RMF audit for **{session.category}**.\n\n"
                f"**Summary:**\n"
                f"• Total Questions: {session.get_progress()['total']}\n"
                f"• Observations Recorded: {len(session.observations)}\n"
                f"• Evidence Evaluations: {len(session.evidence_evaluations)}"
            )
            result["status"] = "completed"
            result["completed"] = True
    
    return result

def start_multi_category_audit(categories: List[str], user_id: str = DEFAULT_USER_ID) -> Dict[str, Any]:
    """Start a multi-category audit session"""
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
    
    logger.info(f"Created multi-category session {multi_session_id} for categories: {categories}")
    
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
        result['message'] = (
            f"**Multi-Category Audit Started**\n\n"
            f"Total categories: {len(categories)}\n"
            f"Starting with: **{first_category}** (1 of {len(categories)})\n\n"
            f"{result.get('message', '')}"
        )
    
    return result

def continue_to_next_category(user_id: str = DEFAULT_USER_ID) -> Dict[str, Any]:
    """Continue to the next category in a multi-category audit"""
    logger.info(f"Continue to next category requested for user: {user_id}")
    
    # Find user's active multi-category audit
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
    if not next_category:
        return {"error": "No more categories to audit"}
    
    # Advance to next category
    multi_audit.advance_to_next_category()
    
    # Start audit for next category
    result = start_audit_session(next_category, user_id)
    
    if 'error' not in result:
        # Update multi-audit tracking
        multi_audit.active_session_id = result['session_id']
        multi_audit.session_mapping[next_category] = result['session_id']
        
        # Get updated progress after transition
        updated_multi_progress = multi_audit.get_progress_summary()
        
        # Add transition info to response
        result['action'] = 'category_selected'  # Use consistent action for UI
        result['multi_session_id'] = multi_session_id
        result['multi_audit_progress'] = updated_multi_progress
        result['from_continue'] = True
        result['message'] = (
            f"**Transitioning to Next Category**\n\n"
            f"Previous category completed! Now starting: **{next_category}** "
            f"({multi_audit.current_index} of {len(multi_audit.categories)})\n\n"
            f"---\n\n{result.get('message', '')}"
        )
        
        logger.info(f"Successfully transitioned to category: {next_category}")
        logger.info(f"Updated multi-audit progress: {updated_multi_progress}")
    
    return result

def get_user_multi_category_audit(category: str, user_id: str = DEFAULT_USER_ID) -> Optional[MultiCategoryAudit]:
    """Find multi-category audit that contains the given category for the user"""
    for multi_audit in multi_category_sessions.values():
        if (category in multi_audit.categories and 
            multi_audit.status == 'active' and
            multi_audit.user_id == user_id):
            return multi_audit
    return None

def process_chat_message(message: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Process a conversational message and determine the appropriate action"""
    message_lower = message.lower()
    user_id = context.get('user_id', DEFAULT_USER_ID)
    
    logger.info(f"Processing message: '{message}' for user: {user_id}")
    
    # Check for continuation commands for multi-category audits
    continue_keywords = ["continue", "next", "proceed", "move on", "next category"]
    if any(keyword in message_lower for keyword in continue_keywords):
        logger.info("Detected continuation command")
        return continue_to_next_category(user_id)
    
    # Check for multi-category audit request
    if any(keyword in message_lower for keyword in ["multi", "multiple", "several", "all categories", "batch"]):
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
        
        if len(detected_categories) >= 2:
            logger.info(f"Starting multi-category audit for: {detected_categories}")
            return start_multi_category_audit(detected_categories, user_id)
    
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
        logger.info(f"Starting audit for single category: {detected_category}")
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
        "message": (
            "I'm here to help you conduct NIST AI RMF audits. You can:\n\n"
            "• Select a single category to audit\n"
            "• Start a multi-category audit by saying 'multi-category audit for Privacy-Enhanced and Safe'\n"
            "• Continue an existing audit session\n\n"
            "Available categories:\n" + 
            "\n".join([f"• {cat}" for cat in get_nist_categories()]) +
            "\n\nWhich category would you like to audit?"
        )
    }

def run_tool(action: str, **kwargs) -> Dict[str, Any]:
    """Main tool function that routes different audit actions"""
    try:
        if action == "get_categories":
            return get_audit_categories()
        elif action == "start_session":
            return start_audit_session(kwargs.get('category'), kwargs.get('user_id', DEFAULT_USER_ID))
        elif action == "get_current_question":
            return get_current_question(kwargs.get('session_id'))
        elif action == "submit_answer":
            return submit_answer(kwargs.get('session_id'), kwargs.get('answer'))
        elif action == "submit_evidence":
            return submit_evidence(kwargs.get('session_id'), kwargs.get('evidence'), kwargs.get('user_id', DEFAULT_USER_ID))
        elif action == "process_chat":
            return process_chat_message(kwargs.get('message', ''), kwargs.get('context', {}))
        elif action == "start_multi_category_audit":
            return start_multi_category_audit(kwargs.get('categories', []), kwargs.get('user_id', DEFAULT_USER_ID))
        elif action == "continue_to_next_category":
            return continue_to_next_category(kwargs.get('user_id', DEFAULT_USER_ID))
        else:
            return {"error": f"Unknown action: {action}"}
    except Exception as e:
        logger.error(f"Tool execution failed: {str(e)}")
        return {"error": f"Tool execution failed: {str(e)}"}

def get_capabilities() -> Dict[str, Any]:
    """Capabilities for agent introspection"""
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
