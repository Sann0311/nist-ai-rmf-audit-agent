# from pydantic import BaseModel
# from typing import Any, Dict, List, Optional
# import pandas as pd
# import os

# # Define schemas for the audit tool
# class SelectCategoryParams(BaseModel):
#     category: str

# class AnswerQuestionParams(BaseModel):
#     session_id: str
#     answer: str

# class ProvideEvidenceParams(BaseModel):
#     session_id: str
#     evidence: str

# class GetCurrentQuestionParams(BaseModel):
#     session_id: str

# # Load the audit data from Excel
# def load_audit_data():
#     """Load and structure the audit data from the Excel file"""
#     try:
#         # Try multiple possible paths for the Excel file
#         possible_paths = [
#             '/app/Audit.xlsx',  # Docker container path
#             'c:/Users/bhala/Downloads/agent_skeleton/Audit.xlsx',  # Local development path
#             'Audit.xlsx',  # Current directory
#             'agent_skeleton/agent/multi_tool_agent/app/Audit.xlsx'  # Relative path
#         ]
        
#         df = None
#         for path in possible_paths:
#             try:
#                 df = pd.read_excel(path)
#                 print(f"✅ Successfully loaded audit data from: {path}")
#                 print(f"   Data shape: {df.shape}")
#                 break
#             except FileNotFoundError:
#                 continue
        
#         if df is None:
#             print(f"❌ Could not find Audit.xlsx in any of these paths: {possible_paths}")
#             return None
            
#         return df
#     except Exception as e:
#         print(f"Error loading audit data: {e}")
#         return None

# # Get available NIST AI RMF categories
# def get_nist_categories() -> List[str]:
#     """Get the 7 NIST AI RMF categories"""
#     return [
#         "Privacy-Enhanced",
#         "Valid & Reliable", 
#         "Safe",
#         "Secure & Resilient",
#         "Accountable & Transparent",
#         "Explainable and Interpretable", 
#         "Fair – With Harmful Bias Managed"
#     ]

# # Session storage for audit progress
# audit_sessions = {}

# def cleanup_old_sessions():
#     """Remove completed sessions to prevent memory buildup"""
#     global audit_sessions
#     completed_sessions = [sid for sid, session in audit_sessions.items() if session.status == "completed"]
#     for sid in completed_sessions[-5:]:  # Keep only last 5 completed sessions
#         if len([s for s in audit_sessions.values() if s.status == "completed"]) > 5:
#             del audit_sessions[sid]

# class AuditSession:
#     def __init__(self, session_id: str, category: str):
#         self.session_id = session_id
#         self.category = category
#         self.questions = []
#         self.current_question_idx = 0
#         self.observations = []
#         self.evidence_evaluations = []
#         self.status = "started"
#         self.state = "waiting_for_question_answer"  # Track conversation state
#         self._load_category_questions()
    
#     def _load_category_questions(self):
#         """Load questions for the selected category"""
#         df = load_audit_data()
#         if df is not None:
#             # Filter by category using the correct column name
#             category_data = df[df['Trust-worthiness characteristic'] == self.category]
#             print(f"Found {len(category_data)} rows for category: {self.category}")
            
#             # Group by main questions
#             current_main_question = None
#             current_question_group = []
#             current_nist_control = None
            
#             for _, row in category_data.iterrows():
#                 # Check if this is a new main question
#                 if pd.notna(row['Question']) and row['Question'].strip() and row['Question'] != self.category:
#                     # Save previous group if exists
#                     if current_main_question and current_question_group:
#                         self.questions.append({
#                             'main_question': current_main_question,
#                             'nist_control': current_nist_control or '',
#                             'sub_questions': current_question_group
#                         })
                    
#                     # Start new group
#                     current_main_question = row['Question']
#                     current_nist_control = row['NIST AI RMF Control'] if pd.notna(row['NIST AI RMF Control']) else ''
#                     current_question_group = []
                
#                 # Add sub-question if it exists
#                 if pd.notna(row['Sub Question']) and row['Sub Question'].strip():
#                     current_question_group.append({
#                         'sub_question': row['Sub Question'],
#                         'baseline_evidence': row['Baseline Evidence '] if pd.notna(row['Baseline Evidence ']) else '',
#                         'nist_control': row['NIST AI RMF Control'] if pd.notna(row['NIST AI RMF Control']) else current_nist_control
#                     })
            
#             # Add final group
#             if current_main_question and current_question_group:
#                 self.questions.append({
#                     'main_question': current_main_question,
#                     'nist_control': current_nist_control or '',
#                     'sub_questions': current_question_group
#                 })
            
#             print(f"Loaded {len(self.questions)} main questions for {self.category}")
    
#     def get_current_question(self):
#         """Get the current question in the audit"""
#         if self.current_question_idx < len(self.questions):
#             return self.questions[self.current_question_idx]
#         return None
    
#     def add_observation(self, answer: str):
#         """Add user's answer as an observation"""
#         self.observations.append({
#             'question_idx': self.current_question_idx,
#             'observation': answer
#         })
#         self.state = "waiting_for_evidence"
    
#     def evaluate_evidence(self, evidence: str) -> Dict[str, Any]:
#         """Evaluate provided evidence against baseline"""
#         current_q = self.get_current_question()
#         if not current_q:
#             return {"error": "No current question"}
        
#         # Collect all baseline evidence for current question
#         baseline_evidence = ""
#         for sub_q in current_q['sub_questions']:
#             if sub_q['baseline_evidence']:
#                 baseline_evidence += sub_q['baseline_evidence'] + "\n"
        
#         # Enhanced evaluation logic using keyword matching and content analysis
#         evidence_lower = evidence.lower()
#         baseline_lower = baseline_evidence.lower()
        
#         # Extract key terms and requirements from baseline
#         evidence_words = set(word.strip('.,!?()[]{}":;') for word in evidence_lower.split() if len(word) > 3)
#         baseline_words = set(word.strip('.,!?()[]{}":;') for word in baseline_lower.split() if len(word) > 3)
        
#         # Look for specific audit keywords
#         audit_keywords = {'policy', 'documentation', 'config', 'screenshot', 'logs', 'audit', 
#                          'compliance', 'review', 'approval', 'signed', 'attestation', 'report',
#                          'testing', 'validation', 'monitoring', 'procedure', 'checklist'}
        
#         evidence_audit_terms = evidence_words.intersection(audit_keywords)
#         baseline_audit_terms = baseline_words.intersection(audit_keywords)
        
#         # Calculate overlap scores
#         word_overlap = len(evidence_words.intersection(baseline_words))
#         audit_overlap = len(evidence_audit_terms.intersection(baseline_audit_terms))
        
#         # Calculate evidence completeness score
#         evidence_length = len(evidence.strip())
#         baseline_requirements = baseline_evidence.count('\n') + baseline_evidence.count('.')
        
#         # Determine conformity level based on multiple factors
#         total_score = (word_overlap * 0.4) + (audit_overlap * 0.4) + (min(evidence_length/200, 1) * 0.2)
        
#         if total_score >= 0.8 and evidence_length > 100 and audit_overlap >= 2:
#             conformity = "Full Conformity"
#             justification = f"Provided evidence comprehensively addresses baseline requirements with {audit_overlap} key audit elements and strong content overlap ({word_overlap} matching terms)."
#         elif total_score >= 0.5 and evidence_length > 50 and audit_overlap >= 1:
#             conformity = "Partial Conformity"
#             justification = f"Provided evidence partially meets baseline requirements with {audit_overlap} audit elements. Consider providing additional documentation or details to achieve full conformity."
#         else:
#             conformity = "No Conformity"
#             justification = f"Provided evidence does not adequately match baseline requirements. Missing key audit elements and insufficient detail. Please review baseline evidence requirements and provide comprehensive documentation."
        
#         evaluation = {
#             'question_idx': self.current_question_idx,
#             'evidence': evidence,
#             'conformity': conformity,
#             'justification': justification,
#             'baseline_evidence': baseline_evidence,
#             'overlap_score': word_overlap,
#             'audit_terms_found': list(evidence_audit_terms)
#         }
        
#         self.evidence_evaluations.append(evaluation)
#         return evaluation
    
#     def move_to_next_question(self):
#         """Move to the next question"""
#         self.current_question_idx += 1
#         if self.current_question_idx >= len(self.questions):
#             self.status = "completed"
#         else:
#             self.state = "waiting_for_question_answer"
    
#     def get_progress(self):
#         """Get audit progress"""
#         return {
#             'current': self.current_question_idx + 1,
#             'total': len(self.questions),
#             'status': self.status,
#             'category': self.category
#         }

# # Tool functions
# def start_audit_session(category: str, user_id: str = "default") -> Dict[str, Any]:
#     """Start a new audit session for the selected category"""
#     if category not in get_nist_categories():
#         return {
#             "error": f"Invalid category. Please select from: {', '.join(get_nist_categories())}"
#         }
    
#     # Clean up old sessions
#     cleanup_old_sessions()
    
#     session_id = f"audit_{len(audit_sessions) + 1}"
#     session = AuditSession(session_id, category)
#     audit_sessions[session_id] = session
    
#     current_question = session.get_current_question()
    
#     return {
#         "action": "category_selected",
#         "session_id": session_id,
#         "category": category,
#         "message": f"Excellent! I've started your NIST AI RMF audit for **{category}**.\n\n**Current Question ({current_question.get('nist_control', 'N/A')}):**\n{current_question['main_question']}\n\n**Sub-questions to address:**\n" + 
#                  "\n".join([f"• {sq['sub_question']}" for sq in current_question['sub_questions']]) +
#                  f"\n\nPlease provide your observation/answer for this question. I will then show you the baseline evidence requirements.",
#         "current_question": current_question,
#         "progress": session.get_progress()
#     }

# def get_current_question(session_id: str) -> Dict[str, Any]:
#     """Get the current question for the audit session"""
#     if session_id not in audit_sessions:
#         return {"error": "Invalid session ID"}
    
#     session = audit_sessions[session_id]
#     current_question = session.get_current_question()
    
#     if not current_question:
#         return {
#             "message": "Audit completed!",
#             "status": "completed",
#             "progress": session.get_progress(),
#             "summary": {
#                 "total_questions": len(session.questions),
#                 "observations": len(session.observations),
#                 "evaluations": len(session.evidence_evaluations)
#             }
#         }
    
#     return {
#         "session_id": session_id,
#         "current_question": current_question,
#         "progress": session.get_progress()
#     }

# def submit_answer(session_id: str, answer: str) -> Dict[str, Any]:
#     """Submit an answer/observation for the current question"""
#     if session_id not in audit_sessions:
#         return {"error": "Invalid session ID"}
    
#     session = audit_sessions[session_id]
#     current_question = session.get_current_question()
    
#     if not current_question:
#         return {"error": "No current question to answer"}
    
#     session.add_observation(answer)
    
#     # Return baseline evidence for user to provide matching evidence
#     baseline_evidence_list = []
#     for sub_q in current_question['sub_questions']:
#         if sub_q['baseline_evidence']:
#             baseline_evidence_list.append({
#                 'sub_question': sub_q['sub_question'],
#                 'baseline_evidence': sub_q['baseline_evidence']
#             })
    
#     return {
#         "action": "observation_recorded",
#         "observation": answer,
#         "baseline_evidence": baseline_evidence_list,
#         "message": f"**Observation Recorded:** {answer}\n\n**Baseline Evidence Requirements:**\n\n" +
#                   "\n".join([f"**{i+1}. {be['sub_question']}**\nRequired Evidence: {be['baseline_evidence']}\n" 
#                            for i, be in enumerate(baseline_evidence_list)]) +
#                   f"\nPlease provide evidence that demonstrates compliance with these baseline requirements."
#     }

# def submit_evidence(session_id: str, evidence: str) -> Dict[str, Any]:
#     """Submit evidence and get evaluation"""
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
#         result["next_question"] = next_question
#         result["message"] = f"**Evidence Evaluation:**\n\n**Conformity Level:** {evaluation['conformity']}\n\n**Justification:** {evaluation['justification']}\n\n**Next Question ({next_question.get('nist_control', 'N/A')}):**\n{next_question['main_question']}\n\n**Sub-questions to address:**\n" + "\n".join([f"• {sq['sub_question']}" for sq in next_question['sub_questions']]) + f"\n\nPlease provide your observation/answer for this question."
#         result["completed"] = False
#     else:
#         result["message"] = f"**Evidence Evaluation:**\n\n**Conformity Level:** {evaluation['conformity']}\n\n**Justification:** {evaluation['justification']}\n\n🎉 **Audit Completed!**\n\nYou have successfully completed the NIST AI RMF audit for **{session.category}**.\n\n**Summary:**\n• Total Questions: {result['progress']['total']}\n• Observations Recorded: {len(session.observations)}\n• Evidence Evaluations: {len(session.evidence_evaluations)}"
#         result["completed"] = True
    
#     return result

# def get_audit_categories() -> Dict[str, Any]:
#     """Get the list of available NIST AI RMF categories"""
#     return {
#         "categories": get_nist_categories(),
#         "description": "7 NIST AI Risk Management Framework trustworthy characteristics"
#     }

# # Main routing function
# def run_tool(action: str, **kwargs) -> Dict[str, Any]:
#     """
#     Main tool function that routes different audit actions
#     """
#     try:
#         if action == "get_categories":
#             return get_audit_categories()
#         elif action == "start_session":
#             return start_audit_session(kwargs.get('category'))
#         elif action == "get_current_question":
#             return get_current_question(kwargs.get('session_id'))
#         elif action == "submit_answer":
#             return submit_answer(kwargs.get('session_id'), kwargs.get('answer'))
#         elif action == "submit_evidence":
#             return submit_evidence(kwargs.get('session_id'), kwargs.get('evidence'))
#         elif action == "process_chat":
#             return process_chat_message(kwargs.get('message', ''), kwargs.get('context', {}))
#         else:
#             return {"error": f"Unknown action: {action}"}
#     except Exception as e:
#         return {"error": f"Tool execution failed: {str(e)}"}

# def process_chat_message(message: str, context: Dict[str, Any]) -> Dict[str, Any]:
#     """Process a conversational message and determine the appropriate action"""
#     message_lower = message.lower()
    
#     print(f"DEBUG: Processing message: '{message}'")
#     print(f"DEBUG: Context: {context}")
#     print(f"DEBUG: Current audit_sessions: {list(audit_sessions.keys())}")
    
#     # Check if category is explicitly provided in context (for new sessions)
#     if 'category' in context and context.get('action') == 'start_session':
#         category = context['category']
#         print(f"DEBUG: Starting new session for category: {category}")
#         if category in get_nist_categories():
#             return start_audit_session(category)
    
#     # Check for category selection via message text
#     categories = get_nist_categories()
#     detected_category = None
    
#     # Try exact category name matching first
#     for category in categories:
#         if category.lower() in message_lower:
#             detected_category = category
#             break
    
#     # If no exact match, try keyword matching
#     if not detected_category:
#         category_keywords = {
#             "Privacy-Enhanced": ["privacy", "enhanced", "data protection"],
#             "Valid & Reliable": ["valid", "reliable", "accuracy", "validation", "performance"],
#             "Safe": ["safe", "safety", "risk mitigation"],
#             "Secure & Resilient": ["secure", "resilient", "security", "resilience"],
#             "Accountable & Transparent": ["accountable", "transparent", "governance", "transparency"],
#             "Explainable and Interpretable": ["explainable", "interpretable", "explanation", "interpretability"],
#             "Fair – With Harmful Bias Managed": ["fair", "bias", "fairness", "harmful bias"]
#         }
        
#         for category, keywords in category_keywords.items():
#             if any(keyword in message_lower for keyword in keywords):
#                 detected_category = category
#                 break
    
#     if detected_category:
#         print(f"DEBUG: Detected category selection: {detected_category}")
#         return start_audit_session(detected_category)
    
#     # Check if there's an active session and this is a continuation
#     active_session = None
#     for session_id, session in audit_sessions.items():
#         if session.status != "completed":
#             active_session = session_id
#             break
    
#     if active_session:
#         session = audit_sessions[active_session]
#         current_q = session.get_current_question()
        
#         print(f"DEBUG: Found active session {active_session}, state: {session.state}")
        
#         if current_q:
#             # Check session state to determine what we're waiting for
#             if session.state == "waiting_for_question_answer":
#                 print(f"DEBUG: Treating as answer/observation")
#                 return submit_answer(active_session, message)
#             elif session.state == "waiting_for_evidence":
#                 print(f"DEBUG: Treating as evidence submission")
#                 return submit_evidence(active_session, message)
#         else:
#             print(f"DEBUG: Session completed")
#             return {
#                 "action": "audit_completed",
#                 "message": f"🎉 **Audit Completed!**\n\nYou have successfully completed the NIST AI RMF audit for **{session.category}**."
#             }
    
#     # Default response for unrecognized input
#     return {
#         "action": "help",
#         "message": "I'm here to help you conduct a NIST AI RMF audit. Please select one of the 7 categories to begin:\n\n" +
#                   "\n".join([f"• {cat}" for cat in get_nist_categories()]) +
#                   "\n\nWhich category would you like to audit?"
#     }

# # Capabilities for agent introspection
# def get_capabilities() -> Dict[str, Any]:
#     return {
#         "capabilities": [
#             "NIST AI RMF Category Selection",
#             "Structured Audit Questioning", 
#             "Evidence Evaluation",
#             "Conformity Assessment",
#             "Audit Progress Tracking",
#             "Multi-session Management"
#         ],
#         "actions": [
#             "get_categories",
#             "start_session", 
#             "get_current_question",
#             "submit_answer",
#             "submit_evidence"
#         ]
#     }
