
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
        'chat_submission_id': 0
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
    
    # Show dashboard content
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
    st.session_state.chat_submission_id += 1
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

def render_audit_questions():
    """Render the audit questions interface with native Streamlit components for reliability"""
    # Show continue button at top if waiting for transition
    if st.session_state.waiting_for_transition:
        st.markdown("### Category Completed!")
        st.info("**Ready to continue to next category - Use the 'Continue to Next Category' button in the sidebar →**")
        st.markdown("---")
        return
    
    # Add spacing before input
    st.markdown("---")
    st.markdown("### Provide Your Response")
    st.markdown("*You can type your response, upload files, or add URLs to documentation*")
    
    # Create tabs for different input methods
    tab1, tab2, tab3 = st.tabs(["💬 Text Response", "📎 Upload Files", "🔗 Add URLs"])
    
    with tab1:
        # Large text area for user response with dynamic key for clearing
        text_area_key = f"user_text_input_{st.session_state.get('text_area_counter', 0)}"
        user_input = st.text_area(
            "Your Response:",
            placeholder="Describe your security measures, provide evidence, or ask questions about the audit...",
            height=150,
            key=text_area_key,
            help="Provide your answer or evidence for the current audit question. You can describe policies, procedures, or any relevant information."
        )
        
        
        
        # Check for submission
        submit_pressed = st.button("**Submit Response**", type="primary", use_container_width=True, key="submit_text")
        
        # Handle submission
        if submit_pressed and user_input.strip():
            # Clear the text area by incrementing counter
            if 'text_area_counter' not in st.session_state:
                st.session_state.text_area_counter = 0
            st.session_state.text_area_counter += 1
            
            handle_user_input(user_input.strip())
            st.rerun()
        elif submit_pressed:
            st.warning("Please enter a response before submitting.")
    
    with tab2:
        st.markdown("**Upload Evidence Files**")
        st.markdown("*Supported formats: PDF, Images (PNG, JPG), Excel (XLSX, XLS), Word (DOCX), Text files*")
        
        uploaded_files = st.file_uploader(
            "Choose files to upload",
            type=['pdf', 'png', 'jpg', 'jpeg', 'xlsx', 'xls', 'docx', 'txt'],
            accept_multiple_files=True,
            key="file_uploader",
            help="Upload documentation, screenshots, policies, or other evidence files"
        )
        
        # Text input for description when uploading files
        file_description = st.text_area(
            "Description (optional):",
            placeholder="Provide context or description for the uploaded files...",
            height=100,
            key=f"file_description_{st.session_state.get('file_desc_counter', 0)}"
        )
        
        if st.button("**Submit Files**", type="primary", use_container_width=True, key="submit_files"):
            if uploaded_files:
                with st.spinner("Processing uploaded files..."):
                    # Clear the description area
                    if 'file_desc_counter' not in st.session_state:
                        st.session_state.file_desc_counter = 0
                    st.session_state.file_desc_counter += 1
                    
                    # Process uploaded files
                    files_data = []
                    total_size = 0
                    
                    for uploaded_file in uploaded_files:
                        try:
                            # Read file content
                            file_content = uploaded_file.read()
                            file_size = len(file_content)
                            total_size += file_size
                            
                            # Encode to base64
                            encoded_content = base64.b64encode(file_content).decode('utf-8')
                            
                            files_data.append({
                                'name': uploaded_file.name,
                                'type': uploaded_file.type,
                                'size': file_size,
                                'content': encoded_content
                            })
                            
                            if st.session_state.debug_mode:
                                st.success(f"✅ Processed: {uploaded_file.name} ({file_size:,} bytes)")
                                
                        except Exception as e:
                            st.error(f"❌ Failed to process {uploaded_file.name}: {str(e)}")
                            continue
                    
                    if files_data:
                        # Show processing summary
                        st.info(f"📄 Processed {len(files_data)} file(s) - Total size: {total_size:,} bytes")
                        
                        # Create evidence package
                        evidence_package = {
                            'text': file_description if file_description.strip() else f"Uploaded {len(files_data)} evidence file(s)",
                            'files': files_data,
                            'urls': []
                        }
                        
                        # Submit the evidence package
                        submit_evidence_package(evidence_package)
                        st.rerun()
                    else:
                        st.error("No files were successfully processed.")
            else:
                st.warning("Please upload at least one file before submitting.")
    
    with tab3:
        st.markdown("**Add Documentation URLs**")
        st.markdown("*Enter URLs to policies, documentation, or compliance resources*")
        
        urls_input = st.text_area(
            "URLs (one per line):",
            placeholder="https://example.com/privacy-policy\nhttps://docs.company.com/ai-security\nhttps://confluence.company.com/governance",
            height=120,
            key=f"urls_input_{st.session_state.get('url_input_counter', 0)}",
            help="Provide URLs to external documentation, policies, or resources relevant to the audit question"
        )
        
        # Text input for description when adding URLs
        url_description = st.text_area(
            "Description (optional):",
            placeholder="Provide context or description for the URLs...",
            height=80,
            key=f"url_description_{st.session_state.get('url_desc_counter', 0)}"
        )
        
        if st.button("**Submit URLs**", type="primary", use_container_width=True, key="submit_urls"):
            if urls_input.strip():
                urls = [url.strip() for url in urls_input.split('\n') if url.strip()]
                if urls:
                    # Clear the input areas
                    if 'url_input_counter' not in st.session_state:
                        st.session_state.url_input_counter = 0
                    if 'url_desc_counter' not in st.session_state:
                        st.session_state.url_desc_counter = 0
                    st.session_state.url_input_counter += 1
                    st.session_state.url_desc_counter += 1
                    
                    # Create evidence package
                    evidence_package = {
                        'text': url_description,
                        'files': [],
                        'urls': urls
                    }
                    submit_evidence_package(evidence_package)
                    st.rerun()
                else:
                    st.warning("Please enter valid URLs before submitting.")
            else:
                st.warning("Please enter at least one URL before submitting.")

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
        files_data = evidence_package.get('files', [])
        urls = evidence_package.get('urls', [])
        text_desc = evidence_package.get('text', '')
        
        # Debug logging
        if st.session_state.debug_mode:
            st.write(f"Debug: Submitting evidence package with {len(files_data)} files and {len(urls)} URLs")
            if text_desc:
                st.write(f"Debug: Text description length: {len(text_desc)}")
        
        # Create the evidence package payload in the correct format expected by the backend
        evidence_package_json = {
            "text": text_desc,
            "files": files_data,
            "urls": urls
        }
        
        # Encode the evidence package as JSON string for the backend
        import json
        evidence_package_encoded = f"EVIDENCE_PACKAGE:{json.dumps(evidence_package_json)}"
        
        # Prepare payload for API
        payload = {
            "appName": "NIST-Agent",
            "userId": "clyde",
            "sessionId": "web_session",
            "newMessage": {
                "parts": [{"text": evidence_package_encoded}],
                "role": "user"
            }
        }
        
        response = call_agent_api(payload)
        
        if "error" not in response and response.get("success"):
            # Show what was submitted
            submitted_parts = []
            if text_desc:
                submitted_parts.append(f"description: {text_desc[:50]}...")
            if files_data:
                submitted_parts.append(f"{len(files_data)} file(s)")
            if urls:
                submitted_parts.append(f"{len(urls)} URL(s)")
            
            submitted_text = f"Evidence package submitted with {', '.join(submitted_parts)}"
            
            add_message("user", submitted_text)
            add_message("assistant", response.get("content", "Evidence processed successfully."), parsed=True)
        else:
            error_msg = response.get('error', 'Unknown error')
            st.error(f"**Failed to process evidence:** {error_msg}")
            if st.session_state.debug_mode:
                st.write(f"Debug: Full error response: {response}")

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

