#frontend_streamlit.py
import streamlit as st
import streamlit.components.v1 as components
import httpx
import json
from typing import Dict, Any, List
import logging
import base64

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Streamlit page
st.set_page_config(
    page_title="NIST AI RMF Audit Agent",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Backend API URL - use backend service name in Docker
BACKEND_URL = "http://backend:8001"

# Initialize session state with defaults
def initialize_session_state():
    """Initialize all session state variables with default values"""
    defaults = {
        'audit_session_id': None,
        'current_step': 'category_selection',
        'messages': [],
        'audit_progress': None,
        'debug_mode': False,
        'multi_category_mode': False,
        'waiting_for_transition': False,
        'multi_audit_progress': None,
        'show_results': False,
        'assessment_data': None,
        'chat_input_key': 0  # For forcing input refresh
    }
    
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

# Initialize session state
initialize_session_state()

def parse_agent_response(raw_response):
    """Parse the nested JSON response from the agent to extract user-friendly content"""
    try:
        if st.session_state.debug_mode:
            logger.info(f"Parsing response type: {type(raw_response)}")
        
        # Handle Google ADK response format - array of message objects
        if isinstance(raw_response, list) and len(raw_response) > 0:
            for message in reversed(raw_response):
                if isinstance(message, dict) and "content" in message:
                    content = message["content"]
                    if "parts" in content:
                        for part in content["parts"]:
                            # Check for function response with tool result
                            if "functionResponse" in part:
                                func_response = part["functionResponse"]
                                if "response" in func_response:
                                    tool_result = func_response["response"]
                                    if st.session_state.debug_mode:
                                        logger.info(f"Found function response: {tool_result}")
                                    return tool_result
                            # Check for plain text responses
                            elif "text" in part:
                                text_content = part["text"]
                                try:
                                    json_content = json.loads(text_content)
                                    if st.session_state.debug_mode:
                                        logger.info(f"Parsed JSON from text: {json_content}")
                                    return json_content
                                except json.JSONDecodeError:
                                    if st.session_state.debug_mode:
                                        logger.info(f"Plain text response: {text_content}")
                                    return {"message": text_content, "action": "text_response"}
            
            # Fallback - return the complete last message
            if raw_response:
                last_message = raw_response[-1]
                if st.session_state.debug_mode:
                    logger.info(f"Using fallback - last message: {last_message}")
                return last_message
        
        # Handle single object format
        elif isinstance(raw_response, dict):
            if "content" in raw_response:
                if st.session_state.debug_mode:
                    logger.info("Processing single object with content")
                return parse_agent_response([raw_response])
            elif "message" in raw_response:
                if st.session_state.debug_mode:
                    logger.info(f"Direct message response: {raw_response}")
                return raw_response
            elif "response" in raw_response:
                if st.session_state.debug_mode:
                    logger.info(f"Response wrapper: {raw_response['response']}")
                return raw_response["response"]
            elif "toolCalls" in raw_response and raw_response["toolCalls"]:
                tool_result = raw_response["toolCalls"][0].get("result", {})
                if isinstance(tool_result, dict) and "message" in tool_result:
                    if st.session_state.debug_mode:
                        logger.info(f"Tool call result: {tool_result}")
                    return tool_result
                else:
                    if st.session_state.debug_mode:
                        logger.info(f"Tool call result (string): {tool_result}")
                    return {"message": str(tool_result), "action": "tool_response"}
            else:
                if st.session_state.debug_mode:
                    logger.info(f"Direct object response: {raw_response}")
                return raw_response
        else:
            if st.session_state.debug_mode:
                logger.warning(f"Unknown response format: {raw_response}")
            return {"message": str(raw_response), "action": "unknown_response"}
        
        return None
    except Exception as e:
        logger.error(f"Error parsing agent response: {e}")
        return {"message": f"Error parsing response: {e}", "action": "error"}

def call_agent_api(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Call the agent API through the backend with proper error handling"""
    try:
        with httpx.Client(timeout=120.0) as client:  # Increased timeout for file processing
            response = client.post(f"{BACKEND_URL}/api/run", json=payload)
            
            if response.status_code == 200:
                result = response.json()
                
                if st.session_state.debug_mode:
                    logger.info(f"Frontend received from backend: {result}")
                
                # Backend has already parsed the response
                if result.get("success") and "content" in result:
                    return {"content": result["content"], "success": True}
                else:
                    # Fallback parsing if backend parsing failed
                    parsed_content = parse_agent_response(result)
                    if parsed_content is not None:
                        return {"content": parsed_content, "success": True}
                    else:
                        return {"content": result, "success": True}
            else:
                error_msg = f"API call failed with status {response.status_code}"
                if response.text:
                    error_msg += f": {response.text}"
                return {"error": error_msg}
                
    except httpx.TimeoutException:
        return {"error": "Request timed out. Please try again."}
    except httpx.ConnectError:
        return {"error": "Failed to connect to backend service. Please check if the service is running."}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}

def add_message(role: str, content: str, parsed: bool = False):
    """Add a message to the chat history"""
    st.session_state.messages.append({
        "role": role, 
        "content": content, 
        "parsed": parsed
    })

def display_chat_history():
    """Display the chat history with proper formatting"""
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message.get("parsed") and isinstance(message["content"], dict):
                render_agent_response(message["content"])
            else:
                st.write(message["content"])

def render_progress_bar(progress: Dict[str, Any], title: str = "Progress"):
    """Render a progress bar with proper bounds checking"""
    current = progress.get('current', 0)
    total = progress.get('total', 0)
    
    if total > 0:
        progress_pct = min(max(current / total, 0.0), 1.0)
        category = progress.get('category', 'Current Category')
        st.progress(progress_pct, text=f"{category}: Question {current} of {total}")
        return progress_pct
    return 0

def render_results_dashboard():
    """Render a comprehensive results dashboard with beautiful styling"""
    if not st.session_state.assessment_data:
        st.error("No assessment data available. Please complete an audit first.")
        return
    
    assessment = st.session_state.assessment_data
    
    # Quick navigation
    st.markdown("### Quick Actions")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("💬 Back to Chat", type="secondary", use_container_width=True, key="top_back_to_chat"):
            st.session_state.show_results = False
            st.rerun()
    
    with col2:
        if st.button("🔄 Start New Audit", type="secondary", use_container_width=True, key="top_new_audit"):
            st.session_state.show_results = False
            st.session_state.current_step = 'category_selection'
            # Reset session state
            st.session_state.messages = []
            st.session_state.audit_progress = None
            st.session_state.multi_audit_progress = None
            st.session_state.waiting_for_transition = False
            st.rerun()
    
    st.markdown("---")
    
    # Custom CSS for better styling
    st.markdown("""
    <style>
    .metric-card {
        background-color: #f8f9fa;
        padding: 20px;
        border-radius: 10px;
        border-left: 4px solid #007bff;
        margin: 10px 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .risk-card {
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
        border-left: 4px solid;
    }
    .risk-high { border-left-color: #dc3545; background-color: #f8d7da; }
    .risk-medium { border-left-color: #ffc107; background-color: #fff3cd; }
    .risk-low { border-left-color: #28a745; background-color: #d4edda; }
    .strength-card {
        background-color: #d4edda;
        border-left: 4px solid #28a745;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
    }
    .compliance-box {
        text-align: center;
        padding: 20px;
        border-radius: 10px;
        margin: 10px;
        color: white;
        font-weight: bold;
    }
    .full-compliance { background: linear-gradient(135deg, #28a745, #20c997); }
    .partial-compliance { background: linear-gradient(135deg, #ffc107, #fd7e14); }
    .no-compliance { background: linear-gradient(135deg, #dc3545, #e83e8c); }
    </style>
    """, unsafe_allow_html=True)
    
    # Header with gradient background
    st.markdown("""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                padding: 30px; border-radius: 15px; margin-bottom: 30px;">
        <h1 style="color: white; text-align: center; margin: 0;">
            NIST AI RMF Audit Results Dashboard
        </h1>
        <p style="color: #e8e8e8; text-align: center; margin: 10px 0 0 0; font-size: 18px;">
            Comprehensive Security Posture Assessment
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Key Metrics Row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        score = assessment['overall_compliance_score']
        delta = score - 80
        st.metric(
            "Overall Compliance Score",
            f"{score}%",
            delta=f"{delta:+.1f}% vs Target (80%)",
            delta_color="normal" if delta >= 0 else "inverse"
        )
    
    with col2:
        risk_level = assessment['risk_level']
        risk_color = assessment['risk_color']
        st.markdown(f"""
        <div class="metric-card" style="border-left-color: {risk_color};">
            <h3 style="margin: 0; color: #333;">Risk Level</h3>
            <h1 style="color: {risk_color}; margin: 5px 0; font-size: 2.5em;">{risk_level}</h1>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        categories_count = len(assessment['categories_audited'])
        st.metric(
            "Categories Audited",
            f"{categories_count}/7",
            delta=f"{categories_count} completed",
            delta_color="normal"
        )
    
    with col4:
        st.metric(
            "Total Evaluations",
            assessment['total_evaluations'],
            delta=f"{assessment['total_questions']} questions",
            delta_color="normal"
        )
    
    # Show more dashboard content (you can expand this as needed)
    st.markdown("### Compliance Distribution")
    st.info("Dashboard content continues here...")

def render_agent_response(agent_response: dict):
    """Render the agent's response with proper UI"""
    if not isinstance(agent_response, dict):
        if isinstance(agent_response, str):
            st.markdown(agent_response)
        else:
            st.markdown("Response received successfully.")
        return
    
    action = agent_response.get("action", "").lower()
    message = agent_response.get("message", "")
    
    # Handle assessment generation
    if action == "assessment_generated":
        st.session_state.assessment_data = agent_response.get("assessment")
        st.success("Assessment Generated Successfully!")
        st.info("Use the **'View Results Dashboard'** button in the sidebar to see your comprehensive analysis.")
        return
    
    # Handle progress display
    if "progress" in agent_response:
        progress = agent_response["progress"]
        render_progress_bar(progress)
        st.session_state.audit_progress = progress
    
    # Handle multi-category progress display
    if "multi_audit_progress" in agent_response:
        multi_progress = agent_response["multi_audit_progress"]
        st.session_state.multi_audit_progress = multi_progress
        
        total_cats = multi_progress.get('total_categories', 0)
        completed_count = multi_progress.get('completed_count', 0)
        
        if total_cats > 0:
            multi_progress_pct = min(max(completed_count / total_cats, 0.0), 1.0)
            st.progress(
                multi_progress_pct, 
                text=f"Multi-Category Progress: {completed_count}/{total_cats} categories completed"
            )
            
            # Show category status
            col1, col2 = st.columns(2)
            with col1:
                completed_categories = multi_progress.get('completed_categories', [])
                if completed_categories:
                    st.success(f"**Completed:** {', '.join(completed_categories)}")
            with col2:
                remaining_categories = multi_progress.get('remaining_categories', [])
                if remaining_categories:
                    display_remaining = remaining_categories[:2]
                    if len(remaining_categories) > 2:
                        display_remaining.append("...")
                    st.info(f"**Remaining:** {', '.join(display_remaining)}")
    
    # Display message
    if message:
        if not (action in ["category_selected", "session_exists", "multi_category_started", "next_category_started"] and "current_question" in agent_response):
            st.markdown(message)
    
    # Handle specific actions
    if action in ["category_selected", "session_exists", "multi_category_started", "next_category_started"]:
        if action in ["multi_category_started", "next_category_started"] or agent_response.get("from_continue"):
            st.session_state.multi_category_mode = True
        
        if action == "category_selected" and agent_response.get("from_continue"):
            logger.info("Resetting waiting_for_transition due to category transition")
            st.session_state.waiting_for_transition = False
        elif action in ["next_category_started", "category_selected"]:
            st.session_state.waiting_for_transition = False
        
        current_question = agent_response.get("current_question")
        if current_question:
            render_current_question(current_question)
    
    elif action == "evidence_evaluated":
        render_evidence_evaluation(agent_response)
    
    elif action == "category_completed_multi":
        handle_category_completion_multi(agent_response)
    
    elif action == "multi_audit_completed":
        handle_multi_audit_completion(agent_response)
    
    elif action == "help":
        pass  # Help message already displayed above
    
    elif action == "error":
        st.error(f"**Error:** {message}")
    
    # Show results button when audit is completed
    if agent_response.get("show_results_button") or (action == "multi_audit_completed"):
        if not st.session_state.assessment_data:
            with st.spinner("Generating comprehensive AI assessment..."):
                generate_assessment()
        
        st.markdown("---")
        st.markdown("### 🎉 Audit Completed Successfully!")
        st.success("**Assessment Generated!** Use the '**View Results Dashboard**' button in the sidebar to see your detailed analysis.")
        
        if st.session_state.assessment_data:
            st.info("**📊 Results Dashboard is now available in the sidebar →**")
    
    # Debug information
    if st.session_state.debug_mode:
        render_debug_info(agent_response)

def render_current_question(current_question: dict):
    """Render the current audit question with enhanced styling"""
    nist_control = current_question.get("nist_control", "N/A")
    
    st.markdown("""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                padding: 20px; border-radius: 10px; margin: 20px 0;">
        <h3 style="color: white; margin: 0;">Current Audit Question</h3>
    </div>
    """, unsafe_allow_html=True)
    
    if nist_control != "N/A":
        st.markdown(f"**NIST Control:** `{nist_control}`")
    
    audit_question = current_question.get("audit_question") or current_question.get("sub_question", "")
    
    st.markdown(f"""
    <div style="background-color: #2d3748; color: white; padding: 20px; border-radius: 10px; 
                border-left: 4px solid #007bff; margin: 10px 0;">
        <strong style="color: #90cdf4;">Question:</strong><br>
        <span style="color: white; font-size: 16px; line-height: 1.5;">{audit_question}</span>
    </div>
    """, unsafe_allow_html=True)

def render_evidence_evaluation(agent_response: dict):
    """Render evidence evaluation results with enhanced styling"""
    evaluation = agent_response.get("evaluation", {})
    
    conformity = evaluation.get("conformity")
    justification = evaluation.get("justification")
    
    if conformity:
        conformity_colors = {
            'Full Conformity': '#28a745',
            'Partial Conformity': '#ffc107',
            'No Conformity': '#dc3545'
        }
        
        conformity_icons = {
            'Full Conformity': '✅',
            'Partial Conformity': '⚠️',
            'No Conformity': '❌'
        }
        
        color = conformity_colors.get(conformity, '#6c757d')
        icon = conformity_icons.get(conformity, '📋')
        
        st.markdown(f"""
        <div style="border: 2px solid {color}; border-radius: 15px; padding: 20px; margin: 20px 0; 
                    background: linear-gradient(135deg, {color}15, {color}05);">
            <h4 style="color: {color}; margin: 0 0 15px 0; display: flex; align-items: center;">
                {icon} Evidence Assessment Result
            </h4>
            <div style="background-color: #f8f9fa; color: #333; padding: 15px; border-radius: 8px; border-left: 4px solid {color};">
                <p style="margin: 5px 0;"><strong>Conformity Level:</strong> 
                   <span style="color: {color}; font-weight: bold;">{conformity}</span></p>
                <p style="margin: 5px 0 0 0;"><strong>Justification:</strong> {justification}</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Show next question if available
    next_question = agent_response.get("next_question")
    if next_question:
        st.markdown("### Next Audit Question")
        render_current_question(next_question)
    
    # Handle completion or transition needs
    if agent_response.get("needs_transition"):
        st.session_state.waiting_for_transition = True
        next_category = agent_response.get("next_category")
        if next_category:
            st.info(f"**Ready to start next category:** **{next_category}**")
            st.info("**Use the 'Continue to Next Category' button in the sidebar to proceed**")
    elif agent_response.get("completed"):
        if st.session_state.multi_category_mode:
            st.session_state.multi_category_mode = False
        st.session_state.current_step = 'completed'

def handle_category_completion_multi(agent_response: dict):
    """Handle category completion in multi-audit"""
    st.session_state.waiting_for_transition = True
    next_category = agent_response.get("next_category")
    if next_category:
        st.success(f"**Category completed!** Ready to start next category: **{next_category}**")
        st.info("**Use the 'Continue to Next Category' button in the sidebar to proceed**")

def handle_multi_audit_completion(agent_response: dict):
    """Handle multi-category audit completion"""
    st.success("**Multi-Category Audit Completed Successfully!**")
    st.session_state.multi_category_mode = False
    st.session_state.waiting_for_transition = False
    st.session_state.current_step = 'completed'
    
    # Display summary if available
    multi_audit_summary = agent_response.get("multi_audit_summary")
    if multi_audit_summary:
        completed_categories = multi_audit_summary.get('completed_categories', [])
        st.markdown("### Audit Summary")
        st.markdown(f"**Completed Categories:** {len(completed_categories)}")
        for cat in completed_categories:
            st.markdown(f"✅ {cat}")

def render_debug_info(agent_response: dict):
    """Render debug information"""
    with st.expander("Debug: Raw Response Data", expanded=False):
        st.json(agent_response)
        st.write(f"waiting_for_transition: {st.session_state.waiting_for_transition}")
        st.write(f"current_step: {st.session_state.current_step}")

def generate_assessment():
    """Generate AI assessment report"""
    payload = {
        "appName": "NIST-Agent",
        "userId": "clyde",
        "sessionId": "web_session",
        "newMessage": {
            "parts": [{"text": "generate assessment"}],
            "role": "user"
        }
    }
    
    try:
        with st.spinner("Generating comprehensive AI assessment..."):
            response = call_agent_api(payload)
        
        if "error" not in response and response.get("success"):
            content = response.get("content", {})
            if isinstance(content, dict) and content.get("action") == "assessment_generated":
                st.session_state.assessment_data = content.get("assessment")
                st.success("**Assessment completed!** Use the 'View Results Dashboard' button in the sidebar.")
                st.rerun()
        else:
            error_msg = response.get('error', 'Unknown error')
            st.error(f"**Failed to generate assessment:** {error_msg}")
    except Exception as e:
        st.error(f"**Error generating assessment:** {str(e)}")

def handle_continue_transition():
    """Handle the continue to next category action"""
    payload = {
        "appName": "NIST-Agent",
        "userId": "clyde",
        "sessionId": "web_session",
        "newMessage": {
            "parts": [{"text": "continue to next category"}],
            "role": "user"
        }
    }
    
    with st.spinner("Starting next category..."):
        response = call_agent_api(payload)
    
    if "error" not in response and response.get("success"):
        add_message("user", "Continue to next category")
        add_message("assistant", response.get("content", "Next category started successfully."), parsed=True)
        
        # Check if this completed the entire multi-audit
        content = response.get("content", {})
        if isinstance(content, dict):
            if content.get("action") == "multi_audit_completed":
                st.session_state.multi_category_mode = False
                st.session_state.waiting_for_transition = False
                st.session_state.current_step = 'completed'
            elif content.get("action") in ["category_selected", "next_category_started"]:
                st.session_state.waiting_for_transition = False
                
                if "progress" in content:
                    st.session_state.audit_progress = content["progress"]
                if "multi_audit_progress" in content:
                    st.session_state.multi_audit_progress = content["multi_audit_progress"]
        
        st.rerun()
    else:
        error_msg = response.get('error', 'Unknown error')
        st.error(f"**Failed to continue to next category:** {error_msg}")

def render_sidebar():
    """Render the sidebar with audit information"""
    with st.sidebar:
        st.markdown("""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    padding: 15px; border-radius: 10px; margin-bottom: 20px;">
            <h2 style="color: white; margin: 0; text-align: center;">Audit Control</h2>
        </div>
        """, unsafe_allow_html=True)
        
        # Show continue button at top if waiting for transition
        if st.session_state.waiting_for_transition:
            st.markdown("### Ready for Next Category")
            if st.button("**Continue to Next Category**", type="primary", key="sidebar_continue_btn", use_container_width=True):
                handle_continue_transition()
            st.markdown("---")
        
        # Show results button if assessment data is available OR if audit is completed
        if st.session_state.assessment_data or st.session_state.current_step == 'completed':
            st.markdown("### Results Available")
            if st.button("**View Results Dashboard**", type="primary", key="view_results_btn", use_container_width=True):
                if not st.session_state.assessment_data:
                    with st.spinner("Generating assessment..."):
                        generate_assessment()
                st.session_state.show_results = True
                st.rerun()
            if st.button("**Back to Chat**", type="secondary", key="back_to_chat_btn", use_container_width=True):
                st.session_state.show_results = False
                st.rerun()
            st.markdown("---")
        
        # Show current audit progress
        if st.session_state.audit_progress:
            progress = st.session_state.audit_progress
            current = progress.get('current', 0)
            total = progress.get('total', 0)
            category = progress.get('category', 'None')
            status = progress.get('status', 'Not Started')
            
            if status == "completed" or (current >= total and total > 0):
                display_status = "Completed"
            elif current > 0:
                display_status = "In Progress"
            else:
                display_status = "Not Started"
            
            st.markdown("### Current Progress")
            st.metric("Questions", f"{current}/{total}")
            st.metric("Category", category)
            st.metric("Status", display_status)
            
            if total > 0:
                progress_pct = min(max(current / total, 0.0), 1.0)
                st.progress(progress_pct, text=f"Question {current} of {total} ({int(progress_pct * 100)}%)")
        
        # Show multi-category progress
        if st.session_state.multi_audit_progress:
            multi_progress = st.session_state.multi_audit_progress
            total_cats = multi_progress.get('total_categories', 0)
            completed_count = multi_progress.get('completed_count', 0)
            
            st.markdown("---")
            st.markdown("### Multi-Category Progress")
            
            if completed_count >= total_cats and total_cats > 0:
                st.metric("Categories", f"{total_cats}/{total_cats}")
                st.success("All categories completed!")
            else:
                st.metric("Categories", f"{completed_count}/{total_cats}")
            
            if total_cats > 0:
                multi_progress_pct = min(max(completed_count / total_cats, 0.0), 1.0)
                st.progress(multi_progress_pct, text=f"{completed_count} of {total_cats} completed")
            
            completed_categories = multi_progress.get('completed_categories', [])
            remaining_categories = multi_progress.get('remaining_categories', [])
            
            if completed_categories:
                st.success(f"**Completed:** {', '.join(completed_categories)}")
            if remaining_categories:
                st.info(f"**Remaining:** {', '.join(remaining_categories)}")
        
        if not st.session_state.audit_progress and not st.session_state.multi_audit_progress:
            st.info("No active audit session")
        
        st.markdown("---")
        st.markdown("### NIST AI RMF Categories")
        categories = [
            "1. Privacy-Enhanced",
            "2. Valid & Reliable",
            "3. Safe",
            "4. Secure & Resilient",
            "5. Accountable & Transparent",
            "6. Explainable and Interpretable",
            "7. Fair – With Harmful Bias Managed"
        ]
        for cat in categories:
            st.markdown(f"• {cat}")
        
        st.markdown("---")
        
        # Debug toggle
        st.session_state.debug_mode = st.checkbox("Debug Mode", value=st.session_state.debug_mode)
        
        if st.button("**Reset Audit**", type="secondary", use_container_width=True):
            reset_audit_session()

def reset_audit_session():
    """Reset the audit session to initial state"""
    st.session_state.audit_session_id = None
    st.session_state.current_step = 'category_selection'
    st.session_state.messages = []
    st.session_state.audit_progress = None
    st.session_state.multi_category_mode = False
    st.session_state.waiting_for_transition = False
    st.session_state.multi_audit_progress = None
    st.session_state.show_results = False
    st.session_state.assessment_data = None
    st.session_state.chat_input_key += 1  # Force input refresh
    st.success("**Audit session reset successfully!**")
    st.rerun()

def render_category_selection():
    """Render the category selection interface"""
    if not st.session_state.messages:
        welcome_message = """
        **Welcome to the NIST AI Risk Management Framework Audit Agent!**
        
        I will guide you through a structured security posture assessment based on the 7 NIST AI RMF trustworthy characteristics.
        
        **Choose your audit approach:**
        
        • **Single Category Audit** - Focus on one specific category for detailed assessment
        • **Multi-Category Audit** - Audit multiple categories sequentially with comprehensive reporting
        
        **Available Categories:**
        1. **Privacy-Enhanced** - Data protection and privacy measures
        2. **Valid & Reliable** - Model accuracy and performance validation  
        3. **Safe** - Safety measures and risk mitigation
        4. **Secure & Resilient** - Security controls and resilience
        5. **Accountable & Transparent** - Governance and transparency
        6. **Explainable and Interpretable** - Model interpretability
        7. **Fair – With Harmful Bias Managed** - Bias mitigation and fairness
        """
        add_message("assistant", welcome_message)
        st.rerun()

    render_multi_category_selection()
    st.markdown("---")
    render_single_category_selection()

def render_multi_category_selection():
    """Render multi-category audit selection"""
    st.markdown("### Multi-Category Audit")
    st.info("**Recommended for comprehensive organizational assessment** - Select multiple categories for sequential auditing with combined reporting")

    selected_categories = []
    col1, col2 = st.columns(2)
    
    categories = [
        ("Privacy-Enhanced", "🔒"),
        ("Valid & Reliable", "✅"),
        ("Safe", "🛡️"),
        ("Secure & Resilient", "🔐"),
        ("Accountable & Transparent", "📊"),
        ("Explainable and Interpretable", "🔍"),
        ("Fair – With Harmful Bias Managed", "⚖️")
    ]

    for i, (category, icon) in enumerate(categories):
        column = col1 if i % 2 == 0 else col2
        if column.checkbox(f"{icon} **{category}**", key=f"multi_checkbox_{i}"):
            selected_categories.append(category)

    # Show selected categories feedback
    if selected_categories:
        if len(selected_categories) == 1:
            st.warning(f"**Selected:** {selected_categories[0]}. Consider selecting additional categories for a comprehensive multi-category audit, or use the single-category option below.")
        else:
            st.success(f"**Selected {len(selected_categories)} categories:** {', '.join(selected_categories)}")
            st.info("**Benefits:** Combined risk assessment, comprehensive recommendations, and executive-level reporting")
    
    # Start multi-category audit button
    if st.button("**Start Multi-Category Audit**", disabled=len(selected_categories) < 2, type="primary", use_container_width=True):
        start_multi_category_audit_flow(selected_categories)

def start_multi_category_audit_flow(selected_categories: List[str]):
    """Start the multi-category audit flow"""
    st.session_state.multi_category_mode = True
    
    categories_text = ", ".join(selected_categories)
    message_text = f"I want to start a multi-category audit for {categories_text}"
    
    payload = {
        "appName": "NIST-Agent",
        "userId": "clyde",
        "sessionId": "web_session",
        "newMessage": {
            "parts": [{"text": message_text}],
            "role": "user"
        }
    }

    with st.spinner(f"Starting multi-category audit for {len(selected_categories)} categories..."):
        response = call_agent_api(payload)

    if "error" not in response and response.get("success"):
        add_message("user", f"Starting multi-category audit: {categories_text}")
        add_message("assistant", response.get('content', 'Multi-category audit started successfully.'), parsed=True)
        st.session_state.current_step = 'audit_questions'
        st.rerun()
    else:
        error_msg = response.get('error', 'Unknown error')
        st.error(f"**Failed to start multi-category audit:** {error_msg}")

def render_single_category_selection():
    """Render single category audit selection"""
    st.markdown("### Single Category Audit")
    st.info("**Perfect for focused assessment** - Deep dive into one specific NIST AI RMF category")
    
    col1, col2 = st.columns(2)

    categories = [
        ("Privacy-Enhanced", "🔒"),
        ("Valid & Reliable", "✅"),
        ("Safe", "🛡️"),
        ("Secure & Resilient", "🔐"),
        ("Accountable & Transparent", "📊"),
        ("Explainable and Interpretable", "🔍"),
        ("Fair – With Harmful Bias Managed", "⚖️")
    ]

    for i, (category, icon) in enumerate(categories):
        column = col1 if i % 2 == 0 else col2
        if column.button(f"{icon} **{category}**", key=f"single_cat_{i}", use_container_width=True):
            start_single_category_audit(category)

def start_single_category_audit(category: str):
    """Start a single category audit"""
    st.session_state.multi_category_mode = False
    
    payload = {
        "appName": "NIST-Agent",
        "userId": "clyde",
        "sessionId": "web_session",
        "newMessage": {
            "parts": [{"text": f"I want to audit the {category} category"}],
            "role": "user"
        }
    }

    with st.spinner(f"Starting audit for {category}..."):
        response = call_agent_api(payload)

    if "error" not in response and response.get("success"):
        add_message("user", f"I want to audit the {category} category")
        add_message("assistant", response.get("content", "Audit session started successfully."), parsed=True)
        st.session_state.current_step = 'audit_questions'
        st.rerun()
    else:
        error_msg = response.get('error', 'Unknown error')
        st.error(f"**Failed to start audit:** {error_msg}")

def render_chatgpt_style_input():
    """Render improved ChatGPT-style input using native Streamlit components"""
    
    # Create the unified input interface using columns for layout
    st.markdown("""
    <style>
    .unified-input-container {
        background: white;
        border: 2px solid #e5e7eb;
        border-radius: 24px;
        padding: 8px;
        margin: 20px 0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    .attachment-indicators {
        margin-bottom: 8px;
        min-height: 24px;
    }
    .attachment-badge {
        display: inline-flex;
        align-items: center;
        background-color: #e3f2fd;
        border: 1px solid #90caf9;
        border-radius: 12px;
        padding: 4px 12px;
        margin: 2px 4px 2px 0;
        font-size: 12px;
        color: #1976d2;
        font-weight: 500;
    }
    .url-badge {
        background-color: #f3e5f5;
        border-color: #ce93d8;
        color: #7b1fa2;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Attachment indicators
    attachment_html = ""
    show_files = st.session_state.get('show_file_uploader', False)
    show_urls = st.session_state.get('show_url_input', False)
    
    # File upload section (collapsible)
    if show_files:
        uploaded_files = st.file_uploader(
            "Attach evidence files:",
            type=['pdf', 'png', 'jpg', 'jpeg', 'xlsx', 'xls', 'docx', 'txt'],
            accept_multiple_files=True,
            key=f"chat_files_{st.session_state.chat_input_key}",
            help="PDF, Images, Excel, Word, or Text files"
        )
        
        if uploaded_files:
            for file in uploaded_files:
                attachment_html += f'<span class="attachment-badge">📄 {file.name}</span>'
    else:
        uploaded_files = None
    
    # URL input section (collapsible)
    if show_urls:
        urls_input = st.text_area(
            "Add URLs to documentation:",
            placeholder="https://example.com/policy\nhttps://docs.company.com/security",
            height=80,
            key=f"urls_chat_input_{st.session_state.chat_input_key}",
            help="Enter URLs to online documentation (one per line)"
        )
        
        if urls_input:
            urls_list = [url.strip() for url in urls_input.split('\n') if url.strip()]
            for i, url in enumerate(urls_list[:2]):
                domain = url.replace('https://', '').replace('http://', '').split('/')[0]
                attachment_html += f'<span class="attachment-badge url-badge">🔗 {domain}</span>'
            if len(urls_list) > 2:
                attachment_html += f'<span class="attachment-badge url-badge">🔗 +{len(urls_list)-2} more</span>'
    else:
        urls_input = ""
    
    # Show attachment indicators
    if attachment_html:
        st.markdown(f'<div class="attachment-indicators">{attachment_html}</div>', unsafe_allow_html=True)
    
    # Main input area with controls
    col1, col2, col3, col4 = st.columns([1, 1, 10, 1])
    
    with col1:
        # Plus button for file upload
        if st.button("📄", key="file_toggle", help="Attach files", use_container_width=True):
            st.session_state.show_file_uploader = not st.session_state.get('show_file_uploader', False)
            st.rerun()
    
    with col2:
        # Link button for URLs
        if st.button("🔗", key="url_toggle", help="Add URLs", use_container_width=True):
            st.session_state.show_url_input = not st.session_state.get('show_url_input', False)
            st.rerun()
    
    with col3:
        # Main text input
        user_input = st.text_area(
            "Message",
            placeholder="Message NIST AI RMF Audit Agent...",
            height=120,
            key=f"main_chat_input_{st.session_state.chat_input_key}",
            label_visibility="collapsed"
        )
    
    with col4:
        # Send button
        send_button = st.button("↑", key="send_main", help="Send message", type="primary", use_container_width=True)
    
    # Handle send action
    if send_button and (user_input.strip() or uploaded_files or urls_input.strip()):
        # Prepare URLs list
        urls_list = [url.strip() for url in urls_input.split('\n') if url.strip()] if urls_input else []
        
        if uploaded_files or urls_list:
            # Submit as evidence package
            evidence_package = {
                'text': user_input,
                'files': uploaded_files or [],
                'urls': urls_list
            }
            submit_evidence_package(evidence_package)
        else:
            # Submit as regular text
            handle_user_input(user_input)
        
        # Clear and refresh input
        clear_input_state()
        st.rerun()
    elif send_button:
        st.error("Please enter a message or attach files before sending.")

def clear_input_state():
    """Clear input state and refresh"""
    st.session_state.chat_input_key += 1
    st.session_state.show_file_uploader = False
    st.session_state.show_url_input = False

def render_audit_questions():
    """Render the audit questions interface with improved chat input"""
    # Show continue button at top if waiting for transition
    if st.session_state.waiting_for_transition:
        st.markdown("### Category Completed!")
        st.info("**Ready to continue to next category - Use the 'Continue to Next Category' button in the sidebar →**")
        st.markdown("---")
        return
    
    # Improved chat input interface
    st.markdown("---")
    render_chatgpt_style_input()

def handle_user_input(prompt: str):
    """Handle user input during audit"""
    add_message("user", prompt)

    payload = {
        "appName": "NIST-Agent",
        "userId": "clyde",
        "sessionId": "web_session",
        "newMessage": {
            "parts": [{"text": prompt}],
            "role": "user"
        }
    }

    with st.spinner("Processing your response..."):
        response = call_agent_api(payload)

    if "error" not in response and response.get("success"):
        content = response.get("content", "Response received successfully.")
        add_message("assistant", content, parsed=True)

        # Check for completion or transition needs
        if isinstance(content, dict):
            if content.get("action") == "multi_audit_completed":
                st.session_state.current_step = 'completed'
                st.session_state.multi_category_mode = False
                st.session_state.waiting_for_transition = False
            elif content.get("needs_transition"):
                st.session_state.waiting_for_transition = True
            elif content.get("completed") and not st.session_state.multi_category_mode:
                st.session_state.current_step = 'completed'
    else:
        error_msg = response.get('error', 'Unknown error occurred')
        st.error(f"**Error:** {error_msg}")
        add_message("assistant", f"I encountered an error: {error_msg}")

def render_completed_state():
    """Render the completed audit state"""
    st.success("**Audit session completed successfully!**")
    
    # Automatically generate assessment and show results availability
    if not st.session_state.assessment_data:
        with st.spinner("Generating comprehensive AI assessment..."):
            generate_assessment()
    
    if st.session_state.assessment_data:
        st.info("**Assessment completed!** Use the '**View Results Dashboard**' button in the sidebar to see your detailed analysis.")
    else:
        st.error("Failed to generate assessment. Please try again.")

def submit_evidence_package(evidence_package):
    """Process and submit the evidence package"""
    with st.spinner("Processing evidence package..."):
        # Convert files to base64 for API transmission
        files_data = []
        if evidence_package.get('files'):
            for file in evidence_package['files']:
                if file is not None:
                    file_content = file.read()
                    file_data = {
                        'name': file.name,
                        'type': file.type,
                        'size': file.size,
                        'content': base64.b64encode(file_content).decode('utf-8')
                    }
                    files_data.append(file_data)
                    file.seek(0)  # Reset file pointer
        
        # Prepare payload for API
        payload = {
            "appName": "NIST-Agent",
            "userId": "clyde",
            "sessionId": "web_session",
            "newMessage": {
                "parts": [{
                    "text": "EVIDENCE_PACKAGE",
                    "evidence_package": {
                        "text": evidence_package.get('text', ''),
                        "files": files_data,
                        "urls": evidence_package.get('urls', [])
                    }
                }],
                "role": "user"
            }
        }
        
        response = call_agent_api(payload)
        
        if "error" not in response and response.get("success"):
            # Show what was submitted
            submitted_text = f"Evidence submitted"
            if files_data:
                submitted_text += f" with {len(files_data)} file(s)"
            if evidence_package.get('urls'):
                submitted_text += f" and {len(evidence_package.get('urls'))} URL(s)"
            
            add_message("user", submitted_text)
            add_message("assistant", response.get("content", "Evidence processed successfully."), parsed=True)
        else:
            error_msg = response.get('error', 'Unknown error')
            st.error(f"**Failed to process evidence:** {error_msg}")

def main():
    """Main application function"""
    # Check if we should show results dashboard
    if st.session_state.show_results and st.session_state.assessment_data:
        render_results_dashboard()
        return
    
    # Header with gradient background
    st.markdown("""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                padding: 30px; border-radius: 15px; margin-bottom: 30px;">
        <h1 style="color: white; text-align: center; margin: 0;">
            NIST AI RMF Audit Agent
        </h1>
        <p style="color: #e8e8e8; text-align: center; margin: 10px 0 0 0; font-size: 18px;">
            Security Posture Assessment Based on NIST AI Risk Management Framework
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Render sidebar
    render_sidebar()
    
    # Main chat interface
    st.header("Audit Conversation")
    
    # Display chat history
    chat_container = st.container()
    with chat_container:
        display_chat_history()
    
    # Handle different steps of the audit process
    if st.session_state.current_step == 'category_selection':
        render_category_selection()
    elif st.session_state.current_step == 'audit_questions':
        render_audit_questions()
    elif st.session_state.current_step == 'completed':
        render_completed_state()
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666; padding: 20px;'>
        <small>
            <strong>NIST AI Risk Management Framework Audit Agent</strong> | 
            Built with Streamlit | 
            AI-Powered Assessment & Recommendations | 
            Enhanced File Processing Support
        </small>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()