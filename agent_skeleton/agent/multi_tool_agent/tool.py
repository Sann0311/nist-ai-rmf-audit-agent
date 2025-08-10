
#tool.py 

from pydantic import BaseModel
from typing import Any, Dict, List, Optional
import pandas as pd
import os
import hashlib
import logging
import uuid
from pathlib import Path
import json
from datetime import datetime

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

class GenerateAssessmentParams(BaseModel):
    user_id: str

# Configuration
DEFAULT_USER_ID = "clyde"
AUDIT_KEYWORDS = {
    'policy', 'documentation', 'config', 'screenshot', 'logs', 'audit',
    'compliance', 'review', 'approval', 'signed', 'attestation', 'report',
    'testing', 'validation', 'monitoring', 'procedure', 'checklist',
    'implemented', 'established', 'deployed', 'configured', 'verified',
    'process', 'framework', 'standard', 'guideline', 'control', 'measure'
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
            logger.info(f"Marked category '{current_category}' as completed. Total completed: {len(self.completed_categories)}")
    
    def advance_to_next_category(self):
        """Move the index to the next category"""
        old_index = self.current_index
        self.current_index += 1
        logger.info(f"Advanced category index from {old_index} to {self.current_index}")
    
    def is_completed(self) -> bool:
        """Check if all categories are completed"""
        is_complete = len(self.completed_categories) >= len(self.categories)
        logger.info(f"Multi-audit completion check: {len(self.completed_categories)}/{len(self.categories)} = {is_complete}")
        return is_complete
    
    def get_remaining_categories(self) -> List[str]:
        """Get list of remaining categories"""
        return self.categories[self.current_index + 1:]
    
    def get_progress_summary(self) -> Dict[str, Any]:
        """FIXED: Get progress summary with correct completion tracking"""
        progress = {
            'total_categories': len(self.categories),
            'completed_count': len(self.completed_categories),
            'current_category': self.get_current_category(),
            'remaining_categories': self.get_remaining_categories(),
            'completed_categories': self.completed_categories.copy(),
            'status': 'completed' if self.is_completed() else 'active'
        }
        logger.info(f"Multi-audit progress summary: {progress}")
        return progress

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
        self.start_time = datetime.now()
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
        """STRICT evidence evaluation - 'yes' responses get No Conformity"""
        current_q = self.get_current_question()
        if not current_q:
            return {"error": "No current question"}
        
        baseline_evidence = current_q['baseline_evidence']
        
        # Enhanced evaluation logic with STRICT scoring
        evidence_lower = evidence.lower().strip()
        baseline_lower = baseline_evidence.lower()
        
        # STRICT: Short responses without substance should fail
        is_insufficient_response = evidence_lower in [
            'yes', 'y', 'yep', 'yeah', 'yeh', 'yers', 'ok', 'okay', 'sure', 
            'correct', 'true', 'no', 'n', 'nope', 'false', 'none', 'na', 'n/a'
        ] or len(evidence.strip()) < 10
        
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
        
        # STRICT SCORING: No leniency for insufficient responses
        if is_insufficient_response:
            total_score = 0.0  # Automatic fail for insufficient responses
        else:
            # Detailed analysis for substantial responses
            # Base score from word overlap (stricter thresholds)
            overlap_score = min(word_overlap / max(len(baseline_words), 5), 1.0) * 0.3
            
            # Audit terms score (requires meaningful audit terms)
            audit_score = min(audit_overlap / max(len(baseline_audit_terms), 2), 1.0) * 0.4
            
            # Length and detail score (requires substantial content)
            length_score = min(evidence_length / 200, 1.0) * 0.2
            
            # Quality indicators (substantive documentation terms)
            quality_indicators = [
                'document', 'documentation', 'policy', 'procedure', 'process',
                'implemented', 'established', 'configured', 'deployed', 'verified',
                'testing', 'validation', 'monitoring', 'audit', 'compliance',
                'screenshot', 'logs', 'report', 'checklist', 'review'
            ]
            quality_count = sum(1 for indicator in quality_indicators if indicator in evidence_lower)
            quality_score = min(quality_count / 3, 1.0) * 0.1
            
            total_score = overlap_score + audit_score + length_score + quality_score
        
        # STRICT conformity determination - high standards required
        if total_score >= 0.8 and evidence_length >= 100 and audit_overlap >= 3 and word_overlap >= 5:
            conformity = "Full Conformity"
            justification = (
                f"Evidence comprehensively demonstrates compliance with baseline requirements. "
                f"Contains {audit_overlap} key audit elements, {word_overlap} relevant terms, "
                f"and substantial documentation ({evidence_length} characters)."
            )
        elif total_score >= 0.6 and evidence_length >= 50 and audit_overlap >= 2 and word_overlap >= 3:
            conformity = "Partial Conformity"
            justification = (
                f"Evidence shows partial compliance with baseline requirements. "
                f"Contains {audit_overlap} audit elements and {word_overlap} relevant terms. "
                f"Additional documentation needed for full compliance."
            )
        else:
            conformity = "No Conformity"
            if is_insufficient_response:
                justification = (
                    f"Insufficient evidence provided. Simple affirmative/negative responses "
                    f"do not demonstrate compliance. Please provide detailed documentation, "
                    f"screenshots, policies, or other substantive evidence as specified in baseline requirements."
                )
            else:
                justification = (
                    f"Evidence does not adequately demonstrate compliance with baseline requirements. "
                    f"Missing key audit elements and insufficient detail. Found {audit_overlap} audit terms "
                    f"and {word_overlap} relevant terms, but requires more comprehensive documentation."
                )
        
        evaluation = {
            'question_idx': self.current_question_idx,
            'evidence': evidence,
            'conformity': conformity,
            'justification': justification,
            'baseline_evidence': baseline_evidence,
            'overlap_score': word_overlap,
            'audit_terms_found': list(evidence_audit_terms),
            'score': total_score
        }
        
        self.evidence_evaluations.append(evaluation)
        return evaluation
    
    def move_to_next_question(self):
        """Move to the next question"""
        self.current_question_idx += 1
        if self.current_question_idx >= len(self.questions):
            self.status = "completed"
            self.completion_time = datetime.now()
        else:
            self.state = "waiting_for_question_answer"
    
    def get_progress(self):
        """FIXED: Get audit progress with proper current question tracking"""
        return {
            'current': min(self.current_question_idx + 1, len(self.questions)),
            'total': len(self.questions),
            'status': self.status,
            'category': self.category
        }
    
    def get_category_summary(self) -> Dict[str, Any]:
        """Get detailed category summary for assessment"""
        conformity_counts = {"Full Conformity": 0, "Partial Conformity": 0, "No Conformity": 0}
        total_score = 0
        
        for eval in self.evidence_evaluations:
            conformity_counts[eval['conformity']] += 1
            total_score += eval.get('score', 0)
        
        avg_score = total_score / len(self.evidence_evaluations) if self.evidence_evaluations else 0
        
        return {
            'category': self.category,
            'total_questions': len(self.questions),
            'conformity_counts': conformity_counts,
            'average_score': avg_score,
            'completion_rate': len(self.evidence_evaluations) / len(self.questions) * 100,
            'evaluations': self.evidence_evaluations,
            'observations': self.observations,
            'start_time': self.start_time.isoformat() if hasattr(self, 'start_time') else None,
            'completion_time': self.completion_time.isoformat() if hasattr(self, 'completion_time') else None
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
                f"Continuing from where you left off."
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
            
            # FIXED: Mark current category as completed BEFORE checking completion status
            multi_audit.mark_current_completed()
            
            # FIXED: Get updated progress tracking with correct completed count
            updated_progress = multi_audit.get_progress_summary()
            
            if multi_audit.is_completed():
                # All categories completed
                result["action"] = "multi_audit_completed"
                result["message"] = (
                    f"**Evidence Evaluation:**\n\n"
                    f"**Conformity Level:** {evaluation['conformity']}\n\n"
                    f"**Justification:** {evaluation['justification']}\n\n"
                    f"**Multi-Category Audit Completed!**\n\n"
                    f"You have successfully completed all {len(multi_audit.categories)} categories!"
                )
                result["multi_audit_summary"] = updated_progress
                result["completed"] = True
                result["show_results_button"] = True
            else:
                # More categories to go - show transition option
                next_category = multi_audit.get_next_category()
                result["action"] = "category_completed_multi"
                result["message"] = (
                    f"**Evidence Evaluation:**\n\n"
                    f"**Conformity Level:** {evaluation['conformity']}\n\n"
                    f"**Justification:** {evaluation['justification']}\n\n"
                    f"**Category '{session.category}' Completed!**\n\n"
                    f"Next category: **{next_category}**\n\n"
                    f"Use the 'Continue to Next Category' button in the sidebar."
                )
                result["multi_audit_progress"] = updated_progress
                result["next_category"] = next_category
                result["completed"] = False
                result["needs_transition"] = True
        else:
            # Single category audit completed
            result["message"] = (
                f"**Evidence Evaluation:**\n\n"
                f"**Conformity Level:** {evaluation['conformity']}\n\n"
                f"**Justification:** {evaluation['justification']}\n\n"
                f"**Audit Completed!**\n\n"
                f"You have successfully completed the NIST AI RMF audit for **{session.category}**."
            )
            result["status"] = "completed"
            result["completed"] = True
            result["show_results_button"] = True
    
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
            f"Please provide your observation/answer for this question."
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
            f"Please provide your observation/answer for this question."
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

def generate_audit_assessment(user_id: str = DEFAULT_USER_ID) -> Dict[str, Any]:
    """Generate comprehensive AI-powered audit assessment"""
    logger.info(f"Generating audit assessment for user: {user_id}")
    
    # Collect all completed audit sessions for the user
    completed_sessions = []
    for session_id, session in audit_sessions.items():
        if session.status == "completed":
            completed_sessions.append(session)
    
    if not completed_sessions:
        return {"error": "No completed audit sessions found"}
    
    # Aggregate data for assessment
    assessment_data = {
        'categories_audited': [],
        'total_questions': 0,
        'overall_conformity': {"Full Conformity": 0, "Partial Conformity": 0, "No Conformity": 0},
        'category_summaries': [],
        'risk_areas': [],
        'strengths': [],
        'recommendations': []
    }
    
    for session in completed_sessions:
        category_summary = session.get_category_summary()
        assessment_data['categories_audited'].append(session.category)
        assessment_data['total_questions'] += category_summary['total_questions']
        assessment_data['category_summaries'].append(category_summary)
        
        # Aggregate conformity counts
        for conformity, count in category_summary['conformity_counts'].items():
            assessment_data['overall_conformity'][conformity] += count
    
    # Calculate overall compliance score
    total_evaluations = sum(assessment_data['overall_conformity'].values())
    if total_evaluations > 0:
        # Weighted scoring: Full=100%, Partial=70%, None=0%
        compliance_score = (
            (assessment_data['overall_conformity']['Full Conformity'] * 100 +
             assessment_data['overall_conformity']['Partial Conformity'] * 70) / total_evaluations
        )
    else:
        compliance_score = 0
    
    # Generate risk areas with proper thresholds
    for category_summary in assessment_data['category_summaries']:
        category = category_summary['category']
        conformity_counts = category_summary['conformity_counts']
        total_questions = sum(conformity_counts.values())
        
        # Calculate percentages for better analysis
        no_conformity_pct = (conformity_counts['No Conformity'] / total_questions * 100) if total_questions > 0 else 0
        full_conformity_pct = (conformity_counts['Full Conformity'] / total_questions * 100) if total_questions > 0 else 0
        
        # Risk areas (categories with concerning non-conformity rates)
        if no_conformity_pct >= 70:  # 70% or more non-conformity
            priority = 'High'
        elif no_conformity_pct >= 50:  # 50-69% non-conformity
            priority = 'Medium'
        elif no_conformity_pct >= 30:  # 30-49% non-conformity
            priority = 'Low'
        else:
            priority = None
            
        if priority:
            assessment_data['risk_areas'].append({
                'category': category,
                'reason': f"Non-conformity rate of {no_conformity_pct:.1f}% ({conformity_counts['No Conformity']} out of {total_questions} questions)",
                'priority': priority
            })
        
        # Strengths (categories with high conformity rates)
        if full_conformity_pct >= 60:  # 60% or more full conformity
            assessment_data['strengths'].append({
                'category': category,
                'reason': f"Strong compliance with {full_conformity_pct:.1f}% full conformity rate ({conformity_counts['Full Conformity']} out of {total_questions} questions)"
            })
    
    # Generate AI-powered recommendations
    assessment_data['recommendations'] = generate_recommendations(assessment_data)
    
    # Calculate risk level with proper thresholds
    if compliance_score >= 75:
        risk_level = "Low"
        risk_color = "#28a745"
    elif compliance_score >= 50:
        risk_level = "Medium" 
        risk_color = "#ffc107"
    else:
        risk_level = "High"
        risk_color = "#dc3545"
    
    return {
        'action': 'assessment_generated',
        'assessment': {
            'overall_compliance_score': round(compliance_score, 1),
            'risk_level': risk_level,
            'risk_color': risk_color,
            'categories_audited': assessment_data['categories_audited'],
            'total_questions': assessment_data['total_questions'],
            'total_evaluations': total_evaluations,
            'conformity_distribution': assessment_data['overall_conformity'],
            'category_summaries': assessment_data['category_summaries'],
            'risk_areas': assessment_data['risk_areas'],
            'strengths': assessment_data['strengths'],
            'recommendations': assessment_data['recommendations'],
            'generated_at': datetime.now().isoformat()
        }
    }

def generate_recommendations(assessment_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate tailored recommendations based on audit results"""
    recommendations = []
    
    # Enhanced recommendations based on risk areas
    for risk_area in assessment_data['risk_areas']:
        category = risk_area['category']
        
        if category == "Privacy-Enhanced":
            recommendations.append({
                'category': category,
                'title': 'Strengthen Privacy Controls & Data Protection',
                'description': 'Implement comprehensive data protection measures including data minimization, encryption, and user consent mechanisms.',
                'priority': risk_area['priority'],
                'actions': [
                    'Conduct privacy impact assessments for AI systems',
                    'Implement data encryption at rest and in transit',
                    'Establish clear data retention and deletion policies',
                    'Deploy user consent management systems',
                    'Regular privacy compliance audits'
                ]
            })
        elif category == "Safe":
            recommendations.append({
                'category': category,
                'title': 'Enhance AI Safety & Risk Mitigation',
                'description': 'Implement robust safety testing and monitoring systems to prevent harmful AI system outputs.',
                'priority': risk_area['priority'],
                'actions': [
                    'Establish comprehensive safety testing protocols',
                    'Implement real-time safety monitoring systems',
                    'Create AI incident response procedures',
                    'Deploy automated safety guardrails',
                    'Conduct regular safety risk assessments'
                ]
            })
        elif category == "Secure & Resilient":
            recommendations.append({
                'category': category,
                'title': 'Strengthen Security Posture & Resilience',
                'description': 'Implement comprehensive security controls to protect AI systems from threats and ensure operational resilience.',
                'priority': risk_area['priority'],
                'actions': [
                    'Deploy multi-factor authentication for AI systems',
                    'Establish network segmentation for AI infrastructure',
                    'Conduct regular penetration testing',
                    'Implement automated threat detection',
                    'Create comprehensive disaster recovery procedures'
                ]
            })
        elif category == "Accountable & Transparent":
            recommendations.append({
                'category': category,
                'title': 'Improve Governance & Transparency Framework',
                'description': 'Establish clear accountability frameworks and transparent reporting mechanisms for AI systems.',
                'priority': risk_area['priority'],
                'actions': [
                    'Define clear AI governance roles and responsibilities',
                    'Implement comprehensive audit logging systems',
                    'Create transparent AI decision reporting processes',
                    'Establish regular governance review cycles',
                    'Deploy stakeholder communication frameworks'
                ]
            })
        elif category == "Explainable and Interpretable":
            recommendations.append({
                'category': category,
                'title': 'Enhance Model Interpretability & Explainability',
                'description': 'Implement explainability tools and documentation to improve AI system transparency and user understanding.',
                'priority': risk_area['priority'],
                'actions': [
                    'Deploy advanced model explanation tools (SHAP, LIME)',
                    'Create user-friendly explanation interfaces',
                    'Document AI decision-making processes comprehensively',
                    'Provide feature importance analysis and visualizations',
                    'Train staff on AI explainability concepts'
                ]
            })
        elif category == "Fair – With Harmful Bias Managed":
            recommendations.append({
                'category': category,
                'title': 'Address Bias & Ensure AI Fairness',
                'description': 'Implement comprehensive bias detection and mitigation strategies to ensure fair AI system outcomes across all demographics.',
                'priority': risk_area['priority'],
                'actions': [
                    'Conduct systematic bias testing across demographics',
                    'Implement real-time fairness metrics monitoring',
                    'Diversify and balance training datasets',
                    'Establish bias review and remediation processes',
                    'Deploy automated fairness constraint enforcement'
                ]
            })
        elif category == "Valid & Reliable":
            recommendations.append({
                'category': category,
                'title': 'Improve Model Validation & Reliability',
                'description': 'Strengthen model testing and validation processes to ensure consistent reliability and accuracy in production.',
                'priority': risk_area['priority'],
                'actions': [
                    'Implement comprehensive model testing protocols',
                    'Establish continuous performance monitoring',
                    'Create robust model versioning and rollback systems',
                    'Conduct regular model revalidation cycles',
                    'Deploy automated model drift detection'
                ]
            })
    
    # Add general best practice recommendations if no specific risk areas
    if not assessment_data['risk_areas']:
        recommendations.append({
            'category': 'General',
            'title': 'Continuous AI Governance Improvement',
            'description': 'Maintain and enhance your strong compliance posture through continuous monitoring and improvement of AI governance practices.',
            'priority': 'Medium',
            'actions': [
                'Establish regular AI audit schedules',
                'Implement continuous compliance monitoring',
                'Stay updated with emerging AI regulations',
                'Conduct regular AI governance training programs',
                'Benchmark against industry best practices'
            ]
        })
    
    return recommendations

def process_chat_message(message: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Process a conversational message and determine the appropriate action"""
    message_lower = message.lower()
    user_id = context.get('user_id', DEFAULT_USER_ID)
    
    logger.info(f"Processing message: '{message}' for user: {user_id}")
    
    # Check for assessment generation request
    if any(keyword in message_lower for keyword in ["generate assessment", "assessment", "results", "report"]):
        logger.info("Detected assessment generation request")
        return generate_audit_assessment(user_id)
    
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
                "message": f"**Audit Completed!**\n\nYou have successfully completed the NIST AI RMF audit for **{session.category}**."
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
            "• Continue an existing audit session\n"
            "• Generate an assessment report by saying 'generate assessment'\n\n"
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
        elif action == "generate_assessment":
            return generate_audit_assessment(kwargs.get('user_id', DEFAULT_USER_ID))
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
            "STRICT Evidence Evaluation with High Standards",
            "Accurate Conformity Assessment",
            "Audit Progress Tracking",
            "Multi-Category Sequential Audits with Manual Transitions",
            "AI-Powered Assessment Generation with Professional Analytics",
            "Comprehensive Risk Analysis and Recommendations"
        ],
        "actions": [
            "get_categories",
            "start_session",
            "get_current_question",
            "submit_answer",
            "submit_evidence",
            "start_multi_category_audit",
            "continue_to_next_category",
            "generate_assessment"
        ]
    }

# Update the agent.py file to include assessment generation
def audit_tool(message: str = "", category: str = "", **kwargs):
    """NIST AI RMF Audit Tool for conducting structured security assessments with AI-powered assessment generation."""
    print(f"DEBUG audit_tool: message='{message}', category='{category}', kwargs={kwargs}")
   
    # If no message, show help
    if not message:
        return _get_help()
   
    # ALWAYS route through process_chat_message for proper multi-category detection and assessment generation
    context = {'user_id': "clyde"}
   
    print(f"DEBUG: Calling process_chat_message with message='{message}'")
    result = process_chat_message(message, context)
    print(f"DEBUG: Got result: {result}")
    return result

def _get_help():
    """Returns the help message for the agent."""
    return {
        "action": "help",
        "message": "I'm here to help you conduct a NIST AI RMF audit. Please select one of the 7 categories to begin:\n\n" +
                   "\n".join([f"• {cat}" for cat in get_nist_categories()]) +
                   "\n\nWhich category would you like to audit?"
    }