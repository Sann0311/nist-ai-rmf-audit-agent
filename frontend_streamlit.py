import streamlit as st
import httpx
import json
from typing import Dict, Any, List
import logging

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
        'multi_audit_progress': None
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
        with httpx.Client(timeout=60.0) as client:
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

def render_agent_response(agent_response: dict):
    """Render the agent's response with improved parsing and user-friendly display"""
    if not isinstance(agent_response, dict):
        if isinstance(agent_response, str):
            st.markdown(agent_response)
        else:
            st.markdown("Response received successfully.")
        return
    
    action = agent_response.get("action", "").lower()
    message = agent_response.get("message", "")
    
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
                    st.success(f"✅ Completed: {', '.join(completed_categories)}")
            with col2:
                remaining_categories = multi_progress.get('remaining_categories', [])
                if remaining_categories:
                    display_remaining = remaining_categories[:2]
                    if len(remaining_categories) > 2:
                        display_remaining.append("...")
                    st.info(f"⏳ Remaining: {', '.join(display_remaining)}")
    
    # Display message if present
    if message:
        st.markdown(message)
    
    # Handle specific actions
    if action in ["category_selected", "session_exists", "multi_category_started", "next_category_started"]:
        # Set multi-category mode if this is a multi-category audit
        if action in ["multi_category_started", "next_category_started"] or agent_response.get("from_continue"):
            st.session_state.multi_category_mode = True
        
        # Reset waiting_for_transition when starting new category
        if action == "category_selected" and agent_response.get("from_continue"):
            logger.info("Resetting waiting_for_transition due to category transition")
            st.session_state.waiting_for_transition = False
        elif action in ["next_category_started", "category_selected"]:
            st.session_state.waiting_for_transition = False
        
        # Display current question
        current_question = agent_response.get("current_question")
        if current_question:
            render_current_question(current_question)
    
    elif action == "observation_recorded":
        render_baseline_evidence(agent_response.get("baseline_evidence"))
    
    elif action == "evidence_evaluated":
        render_evidence_evaluation(agent_response)
    
    elif action == "category_completed_multi":
        handle_category_completion_multi(agent_response)
    
    elif action == "multi_audit_completed":
        handle_multi_audit_completion(agent_response)
    
    elif action == "help":
        pass  # Help message already displayed above
    
    elif action == "error":
        st.error(f"Error: {message}")
    
    # Debug information
    if st.session_state.debug_mode:
        render_debug_info(agent_response)

def render_current_question(current_question: dict):
    """Render the current audit question"""
    nist_control = current_question.get("nist_control", "N/A")
    
    st.markdown("### 📋 Current Audit Question")
    if nist_control != "N/A":
        st.markdown(f"**NIST Control:** {nist_control}")
    
    audit_question = current_question.get("audit_question") or current_question.get("sub_question", "")
    st.markdown(f"**Question:** {audit_question}")

def render_baseline_evidence(baseline_evidence: str):
    """Render baseline evidence requirements"""
    if baseline_evidence:
        st.markdown("### 📋 Baseline Evidence Requirements")
        st.markdown(baseline_evidence)

def render_evidence_evaluation(agent_response: dict):
    """Render evidence evaluation results"""
    evaluation = agent_response.get("evaluation", {})
    
    conformity = evaluation.get("conformity")
    justification = evaluation.get("justification")
    
    if conformity:
        conformity_colors = {
            'Full Conformity': '#28a745',
            'Partial Conformity': '#ffc107',
            'No Conformity': '#dc3545'
        }
        
        color = conformity_colors.get(conformity, '#6c757d')
        
        st.markdown(f"""
        <div style="border: 2px solid {color}; border-radius: 10px; padding: 15px; margin: 10px 0;">
            <h4 style="color: {color}; margin: 0 0 10px 0;">📋 Evidence Assessment Result</h4>
            <p style="margin: 5px 0;"><strong>Conformity Level:</strong> <span style="color: {color};">{conformity}</span></p>
            <p style="margin: 5px 0;"><strong>Justification:</strong> {justification}</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Show next question if available
    next_question = agent_response.get("next_question")
    if next_question:
        st.markdown("### ➡️ Next Audit Question")
        render_current_question(next_question)
    
    # Handle completion or transition needs
    if agent_response.get("needs_transition"):
        st.session_state.waiting_for_transition = True
        next_category = agent_response.get("next_category")
        if next_category:
            st.info(f"🎯 Ready to start next category: **{next_category}**")
            st.info("👆 **Use the 'Continue to Next Category' button in the sidebar to proceed**")
    elif agent_response.get("completed"):
        if st.session_state.multi_category_mode:
            st.session_state.multi_category_mode = False
        st.session_state.current_step = 'completed'

def handle_category_completion_multi(agent_response: dict):
    """Handle category completion in multi-audit"""
    st.session_state.waiting_for_transition = True
    next_category = agent_response.get("next_category")
    if next_category:
        st.info(f"🎯 Ready to start next category: **{next_category}**")
        st.info("👆 **Use the 'Continue to Next Category' button in the sidebar to proceed**")

def handle_multi_audit_completion(agent_response: dict):
    """Handle multi-category audit completion"""
    st.success("🎉 Multi-Category Audit Completed Successfully!")
    st.session_state.multi_category_mode = False
    st.session_state.waiting_for_transition = False
    st.session_state.current_step = 'completed'
    
    # Display summary if available
    multi_audit_summary = agent_response.get("multi_audit_summary")
    if multi_audit_summary:
        completed_categories = multi_audit_summary.get('completed_categories', [])
        st.markdown("### 📊 Audit Summary")
        st.markdown(f"**Completed Categories:** {len(completed_categories)}")
        for cat in completed_categories:
            st.markdown(f"✅ {cat}")

def render_debug_info(agent_response: dict):
    """Render debug information"""
    with st.expander("🐛 Debug: Raw Response Data", expanded=False):
        st.json(agent_response)
        st.write(f"waiting_for_transition: {st.session_state.waiting_for_transition}")
        st.write(f"current_step: {st.session_state.current_step}")

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
                # Reset transition state and update progress
                st.session_state.waiting_for_transition = False
                
                # Update progress from the response
                if "progress" in content:
                    st.session_state.audit_progress = content["progress"]
                if "multi_audit_progress" in content:
                    st.session_state.multi_audit_progress = content["multi_audit_progress"]
        
        st.rerun()
    else:
        error_msg = response.get('error', 'Unknown error')
        st.error(f"Failed to continue to next category: {error_msg}")

def render_sidebar():
    """Render the sidebar with audit information"""
    with st.sidebar:
        st.header("Audit Information")
        
        # Show continue button at top if waiting for transition
        if st.session_state.waiting_for_transition:
            st.markdown("### 🎯 Ready for Next Category")
            if st.button("🚀 Continue to Next Category", type="primary", key="sidebar_continue_btn", use_container_width=True):
                handle_continue_transition()
            st.markdown("---")
        
        # Show current audit progress
        if st.session_state.audit_progress:
            progress = st.session_state.audit_progress
            current = progress.get('current', 0)
            total = progress.get('total', 0)
            category = progress.get('category', 'None')
            status = progress.get('status', 'Not Started').title()
            
            st.metric("Current Progress", f"{current}/{total}")
            st.metric("Category", category)
            st.metric("Status", status)
            
            if total > 0:
                progress_pct = min(max(current / total, 0.0), 1.0)
                st.progress(progress_pct, text=f"Question {current} of {total} ({int(progress_pct * 100)}%)")
        
        # Show multi-category progress
        if st.session_state.multi_audit_progress:
            multi_progress = st.session_state.multi_audit_progress
            total_cats = multi_progress.get('total_categories', 0)
            completed_count = multi_progress.get('completed_count', 0)
            
            st.markdown("---")
            st.subheader("Multi-Category Progress")
            st.metric("Categories Progress", f"{completed_count}/{total_cats}")
            
            if total_cats > 0:
                multi_progress_pct = min(max(completed_count / total_cats, 0.0), 1.0)
                st.progress(multi_progress_pct, text=f"{completed_count} of {total_cats} completed")
            
            completed_categories = multi_progress.get('completed_categories', [])
            remaining_categories = multi_progress.get('remaining_categories', [])
            
            if completed_categories:
                st.success(f"✅ Completed: {', '.join(completed_categories)}")
            if remaining_categories:
                st.info(f"⏳ Remaining: {', '.join(remaining_categories)}")
        
        if not st.session_state.audit_progress and not st.session_state.multi_audit_progress:
            st.info("No active audit session")
        
        st.markdown("---")
        st.subheader("NIST AI RMF Categories")
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
            st.write(f"• {cat}")
        
        st.markdown("---")
        
        if st.button("🔄 Reset Audit", type="secondary"):
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
    st.rerun()

def render_category_selection():
    """Render the category selection interface"""
    if not st.session_state.messages:
        welcome_message = """
        Welcome to the NIST AI Risk Management Framework Audit Agent!
        
        I will guide you through a structured security posture assessment based on the 7 NIST AI RMF trustworthy characteristics.
        
        **Choose your audit approach:**
        
        🔹 **Single Category Audit** - Focus on one specific category
        🔹 **Multi-Category Audit** - Audit multiple categories sequentially
        
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
    st.subheader("Multi-Category Audit")
    st.info("Select multiple categories for sequential auditing")

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
        if column.checkbox(f"{icon} {category}", key=f"multi_checkbox_{i}"):
            selected_categories.append(category)

    # Show selected categories feedback
    if selected_categories:
        if len(selected_categories) == 1:
            st.warning(f"Selected 1 category: {selected_categories[0]}. Consider selecting more for multi-category audit or use single-category option below.")
        else:
            st.success(f"Selected {len(selected_categories)} categories: {', '.join(selected_categories)}")
    
    # Start multi-category audit button
    if st.button("Start Multi-Category Audit", disabled=len(selected_categories) < 2):
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
        st.error(f"Failed to start multi-category audit: {error_msg}")

def render_single_category_selection():
    """Render single category audit selection"""
    st.subheader("Single Category Audit")
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
        if column.button(f"{icon} {category}", key=f"single_cat_{i}"):
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
        st.error(f"Failed to start audit: {error_msg}")

def render_audit_questions():
    """Render the audit questions interface"""
    # Show continue button at top if waiting for transition
    if st.session_state.waiting_for_transition:
        st.markdown("### 🎯 Category Completed!")
        st.info("**Ready to continue to next category - Use the button in the sidebar →**")
        st.markdown("---")
    
    # Chat input for ongoing audit (only show if not waiting for transition)
    if not st.session_state.waiting_for_transition:
        if prompt := st.chat_input("Type your response..."):
            handle_user_input(prompt)

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
        st.error(f"Error: {error_msg}")
        add_message("assistant", f"I encountered an error: {error_msg}")

    st.rerun()

def render_completed_state():
    """Render the completed audit state"""
    st.success("🎉 Audit session completed successfully!")
    st.info("You can start a new audit session by clicking the Reset Audit button in the sidebar.")

def main():
    """Main application function"""
    # Header
    st.title("NIST AI RMF Audit Agent")
    st.markdown("### Security Posture Assessment Based on NIST AI Risk Management Framework")
    
    # Render sidebar
    render_sidebar()
    
    # Main chat interface
    st.header("💬 Audit Conversation")
    
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
    <div style='text-align: center; color: #666;'>
        <small>NIST AI Risk Management Framework Audit Agent | Built with Streamlit</small>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()

# import streamlit as st
# import httpx
# import json
# from typing import Dict, Any


# # Configure Streamlit page
# st.set_page_config(
#     page_title="NIST AI RMF Audit Agent",
#     page_icon="🔍",
#     layout="wide",
#     initial_sidebar_state="expanded"
# )

# # Backend API URL - use backend service name in Docker
# BACKEND_URL = "http://backend:8001"  # Use Docker service name

# # Initialize session state
# if 'audit_session_id' not in st.session_state:
#     st.session_state.audit_session_id = None
# if 'current_step' not in st.session_state:
#     st.session_state.current_step = 'category_selection'
# if 'messages' not in st.session_state:
#     st.session_state.messages = []
# if 'audit_progress' not in st.session_state:
#     st.session_state.audit_progress = None
# if 'debug_mode' not in st.session_state:
#     st.session_state.debug_mode = False
# if 'multi_category_mode' not in st.session_state:
#     st.session_state.multi_category_mode = False
# if 'waiting_for_transition' not in st.session_state:
#     st.session_state.waiting_for_transition = False
# if 'multi_audit_progress' not in st.session_state:
#     st.session_state.multi_audit_progress = None


# def parse_agent_response(raw_response):
#     """Parse the nested JSON response from the agent to extract user-friendly content"""
#     try:
#         # Debug logging for development
#         if st.session_state.get('debug_mode', False):
#             print(f"🔍 Parsing response type: {type(raw_response)}")
#             print(f"🔍 Raw response: {raw_response}")
       
#         # Handle Google ADK response format - it returns an array of message objects
#         if isinstance(raw_response, list) and len(raw_response) > 0:
#             # Look for the latest message with function response (tool result)
#             for message in reversed(raw_response):
#                 if isinstance(message, dict) and "content" in message:
#                     content = message["content"]
#                     if "parts" in content:
#                         for part in content["parts"]:
#                             # Check for function response with tool result
#                             if "functionResponse" in part:
#                                 func_response = part["functionResponse"]
#                                 if "response" in func_response:
#                                     tool_result = func_response["response"]
#                                     if st.session_state.get('debug_mode', False):
#                                         print(f"✅ Found function response: {tool_result}")
#                                     return tool_result
#                             # Check for plain text responses
#                             elif "text" in part:
#                                 text_content = part["text"]
#                                 # Try to parse if it's JSON
#                                 try:
#                                     import json
#                                     json_content = json.loads(text_content)
#                                     if st.session_state.get('debug_mode', False):
#                                         print(f"✅ Parsed JSON from text: {json_content}")
#                                     return json_content
#                                 except json.JSONDecodeError:
#                                     if st.session_state.get('debug_mode', False):
#                                         print(f"✅ Plain text response: {text_content}")
#                                     return {"message": text_content, "action": "text_response"}
           
#             # Fallback - return the complete last message for frontend parsing
#             if raw_response and len(raw_response) > 0:
#                 last_message = raw_response[-1]
#                 if st.session_state.get('debug_mode', False):
#                     print(f"⚠️ Using fallback - last message: {last_message}")
#                 return last_message
       
#         # Handle single object format
#         elif isinstance(raw_response, dict):
#             # Check for Google ADK response format
#             if "content" in raw_response:
#                 if st.session_state.get('debug_mode', False):
#                     print(f"🔄 Processing single object with content")
#                 return parse_agent_response([raw_response])  # Convert to list and reprocess
#             elif "message" in raw_response:
#                 if st.session_state.get('debug_mode', False):
#                     print(f"✅ Direct message response: {raw_response}")
#                 return raw_response
#             elif "response" in raw_response:
#                 if st.session_state.get('debug_mode', False):
#                     print(f"✅ Response wrapper: {raw_response['response']}")
#                 return raw_response["response"]
#             # Check for tool call results
#             elif "toolCalls" in raw_response and raw_response["toolCalls"]:
#                 tool_result = raw_response["toolCalls"][0].get("result", {})
#                 if isinstance(tool_result, dict) and "message" in tool_result:
#                     if st.session_state.get('debug_mode', False):
#                         print(f"✅ Tool call result: {tool_result}")
#                     return tool_result
#                 else:
#                     if st.session_state.get('debug_mode', False):
#                         print(f"⚠️ Tool call result (string): {tool_result}")
#                     return {"message": str(tool_result), "action": "tool_response"}
#             else:
#                 if st.session_state.get('debug_mode', False):
#                     print(f"✅ Direct object response: {raw_response}")
#                 return raw_response
#         else:
#             if st.session_state.get('debug_mode', False):
#                 print(f"⚠️ Unknown response format: {raw_response}")
#             return {"message": str(raw_response), "action": "unknown_response"}
       
#         return None
#     except Exception as e:
#         print(f"❌ Error parsing agent response: {e}")
#         print(f"Raw response type: {type(raw_response)}")
#         print(f"Raw response: {raw_response}")
#         return {"message": f"Error parsing response: {e}", "action": "error"}


# def call_agent_api(payload: Dict[str, Any]) -> Dict[str, Any]:
#     """Call the agent API through the backend"""
#     try:
#         with httpx.Client(timeout=60.0) as client:
#             response = client.post(f"{BACKEND_URL}/api/run", json=payload)
#             if response.status_code == 200:
#                 result = response.json()
               
#                 # Debug logging
#                 if st.session_state.get('debug_mode', False):
#                     print(f"🔍 Frontend received from backend: {result}")
               
#                 # Backend has already parsed the response, just extract the content
#                 if result.get("success") and "content" in result:
#                     return {"content": result["content"], "success": True}
#                 else:
#                     # Fallback to try parsing the entire result if backend parsing failed
#                     parsed_content = parse_agent_response(result)
#                     if parsed_content is not None:
#                         return {"content": parsed_content, "success": True}
#                     else:
#                         return {"content": result, "success": True}
#             else:
#                 return {"error": f"API call failed with status {response.status_code}: {response.text}"}
#     except Exception as e:
#         return {"error": f"Failed to connect to backend: {str(e)}"}


# def add_message(role: str, content: str, parsed: bool = False):
#     """Add a message to the chat history. If parsed=True, content is a dict to be rendered nicely."""
#     st.session_state.messages.append({"role": role, "content": content, "parsed": parsed})


# def display_chat_history():
#     """Display the chat history with pretty formatting for agent responses."""
#     for message in st.session_state.messages:
#         with st.chat_message(message["role"]):
#             if message.get("parsed") and isinstance(message["content"], dict):
#                 render_agent_response(message["content"])
#             else:
#                 st.write(message["content"])


# def render_agent_response(agent_response: dict):
#     """Render the agent's response with improved parsing and user-friendly display"""
   
#     # Ensure we're working with a dictionary
#     if not isinstance(agent_response, dict):
#         if isinstance(agent_response, str):
#             st.markdown(agent_response)
#         else:
#             st.markdown("Response received successfully.")
#         return
   
#     # Get action and message
#     action = agent_response.get("action", "").lower()
#     message = agent_response.get("message", "")
   
#     # Handle progress display
#     if "progress" in agent_response:
#         progress = agent_response["progress"]
#         current = progress.get('current', 0)
#         total = progress.get('total', 0)
       
#         if total > 0:
#             progress_pct = min(max(current / total, 0.0), 1.0)
#             category = progress.get('category', 'Current Category')
#             st.progress(progress_pct, text=f"{category}: Question {current} of {total}")
#             st.session_state.audit_progress = progress
   
#     # Handle multi-category progress display
#     if "multi_audit_progress" in agent_response:
#         multi_progress = agent_response["multi_audit_progress"]
#         st.session_state.multi_audit_progress = multi_progress
       
#         total_cats = multi_progress.get('total_categories', 0)
#         completed_count = multi_progress.get('completed_count', 0)
       
#         if total_cats > 0:
#             multi_progress_pct = min(max(completed_count / total_cats, 0.0), 1.0)
#             st.progress(multi_progress_pct, text=f"Multi-Category Progress: {completed_count}/{total_cats} categories completed")
           
#             # Show category status
#             col1, col2 = st.columns(2)
#             with col1:
#                 completed_categories = multi_progress.get('completed_categories', [])
#                 if completed_categories:
#                     st.success(f"✅ Completed: {', '.join(completed_categories)}")
#             with col2:
#                 remaining_categories = multi_progress.get('remaining_categories', [])
#                 if remaining_categories:
#                     st.info(f"⏳ Remaining: {', '.join(remaining_categories[:2])}{'...' if len(remaining_categories) > 2 else ''}")
   
#     # Display message if present
#     if message:
#         st.markdown(message)
   
#     # Handle specific actions
#     if action in ["category_selected", "session_exists", "multi_category_started", "next_category_started"]:
#         # Set multi-category mode if this is a multi-category audit
#         if action in ["multi_category_started", "next_category_started"] or agent_response.get("from_continue"):
#             st.session_state.multi_category_mode = True
           
#         # CRITICAL FIX: Reset waiting_for_transition when starting new category
#         if action == "category_selected" and agent_response.get("from_continue"):
#             print("DEBUG UI: Resetting waiting_for_transition due to category transition")
#             st.session_state.waiting_for_transition = False
#         elif action in ["next_category_started", "category_selected"]:
#             st.session_state.waiting_for_transition = False
       
#         # Display current question
#         current_question = agent_response.get("current_question")
#         if current_question:
#             nist_control = current_question.get("nist_control", "N/A")
           
#             st.markdown(f"### 📋 Current Audit Question")
#             if nist_control != "N/A":
#                 st.markdown(f"**NIST Control:** {nist_control}")
           
#             audit_question = current_question.get("audit_question") or current_question.get("sub_question", "")
#             st.markdown(f"**Question:** {audit_question}")
   
#     elif action == "observation_recorded":
#         # Display baseline evidence requirements
#         baseline_evidence = agent_response.get("baseline_evidence")
#         if baseline_evidence:
#             st.markdown("### 📋 Baseline Evidence Requirements")
#             st.markdown(baseline_evidence)
   
#     elif action == "evidence_evaluated":
#         # Display evaluation results
#         evaluation = agent_response.get("evaluation", {})
       
#         conformity = evaluation.get("conformity")
#         justification = evaluation.get("justification")
       
#         if conformity:
#             # Color coding for conformity
#             conformity_colors = {
#                 'Full Conformity': '#28a745',
#                 'Partial Conformity': '#ffc107',
#                 'No Conformity': '#dc3545'
#             }
           
#             color = conformity_colors.get(conformity, '#6c757d')
           
#             with st.container():
#                 st.markdown(f"""
#                 <div style="border: 2px solid {color}; border-radius: 10px; padding: 15px; margin: 10px 0;">
#                     <h4 style="color: {color}; margin: 0 0 10px 0;">📋 Evidence Assessment Result</h4>
#                     <p style="margin: 5px 0;"><strong>Conformity Level:</strong> <span style="color: {color};">{conformity}</span></p>
#                     <p style="margin: 5px 0;"><strong>Justification:</strong> {justification}</p>
#                 </div>
#                 """, unsafe_allow_html=True)
       
#         # Show next question if available
#         next_question = agent_response.get("next_question")
#         if next_question:
#             nist_control = next_question.get("nist_control", "N/A")
           
#             st.markdown(f"### ➡️ Next Audit Question")
#             if nist_control != "N/A":
#                 st.markdown(f"**NIST Control:** {nist_control}")
           
#             audit_question = next_question.get("audit_question") or next_question.get("sub_question", "")
#             st.markdown(f"**Question:** {audit_question}")
       
#         # Handle completion or transition needs
#         if agent_response.get("needs_transition"):
#             # Category completed in multi-audit, show transition button
#             st.session_state.waiting_for_transition = True
#             next_category = agent_response.get("next_category")
#             if next_category:
#                 st.info(f"🎯 Ready to start next category: **{next_category}**")
#         elif agent_response.get("completed"):
#             # Audit fully completed
#             if st.session_state.multi_category_mode:
#                 st.session_state.multi_category_mode = False
#             st.session_state.current_step = 'completed'
   
#     elif action == "category_completed_multi":
#         # Category completed in multi-audit, show transition controls
#         st.session_state.waiting_for_transition = True
#         next_category = agent_response.get("next_category")
#         if next_category:
#             st.info(f"🎯 Ready to start next category: **{next_category}**")
   
#     elif action == "multi_audit_completed":
#         # Multi-category audit fully completed
#         st.success("🎉 Multi-Category Audit Completed Successfully!")
#         st.session_state.multi_category_mode = False
#         st.session_state.waiting_for_transition = False
#         st.session_state.current_step = 'completed'
       
#         # Display summary if available
#         multi_audit_summary = agent_response.get("multi_audit_summary")
#         if multi_audit_summary:
#             completed_categories = multi_audit_summary.get('completed_categories', [])
#             st.markdown(f"### 📊 Audit Summary")
#             st.markdown(f"**Completed Categories:** {len(completed_categories)}")
#             for cat in completed_categories:
#                 st.markdown(f"✅ {cat}")
   
#     elif action == "help":
#         # Help message already displayed above
#         pass
   
#     elif action == "error":
#         st.error(f"Error: {message}")
   
#     # Debug information
#     if st.session_state.get('debug_mode', False):
#         with st.expander("🐛 Debug: Raw Response Data", expanded=False):
#             st.json(agent_response)
#             st.write(f"waiting_for_transition: {st.session_state.waiting_for_transition}")
#             st.write(f"current_step: {st.session_state.current_step}")


# def handle_continue_transition():
#     """Handle the continue to next category action"""
#     payload = {
#         "appName": "NIST-Agent",
#         "userId": "clyde",
#         "sessionId": "web_session",
#         "newMessage": {
#             "parts": [{"text": "continue to next category"}],
#             "role": "user"
#         }
#     }
   
#     with st.spinner("Starting next category..."):
#         response = call_agent_api(payload)
   
#     if "error" not in response and response.get("success"):
#         add_message("user", "Continue to next category")
#         add_message("assistant", response.get("content", "Next category started successfully."), parsed=True)
       
#         # Check if this completed the entire multi-audit
#         content = response.get("content", {})
#         if isinstance(content, dict):
#             if content.get("action") == "multi_audit_completed":
#                 st.session_state.multi_category_mode = False
#                 st.session_state.waiting_for_transition = False
#                 st.session_state.current_step = 'completed'
#             elif content.get("action") in ["category_selected", "next_category_started"]:
#                 # The render_agent_response will handle resetting waiting_for_transition
#                 pass
       
#         st.rerun()
#     else:
#         st.error(f"Failed to continue to next category: {response.get('error', 'Unknown error')}")


# def main():
#     # Header
#     st.title("NIST AI RMF Audit Agent")
#     st.markdown("### Security Posture Assessment Based on NIST AI Risk Management Framework")
   
#     # Sidebar with audit information
#     with st.sidebar:
#         st.header("Audit Information")
       
#         # Show current audit progress
#         if st.session_state.audit_progress:
#             progress = st.session_state.audit_progress
#             current = progress.get('current', 0)
#             total = progress.get('total', 0)
#             category = progress.get('category', 'None')
#             status = progress.get('status', 'Not Started').title()
           
#             st.metric("Current Progress", f"{current}/{total}")
#             st.metric("Category", category)
#             st.metric("Status", status)
           
#             if total > 0:
#                 progress_pct = min(max(current / total, 0.0), 1.0)
#                 st.progress(progress_pct, text=f"Question {current} of {total} ({int(progress_pct * 100)}%)")
       
#         # Show multi-category progress
#         if st.session_state.multi_audit_progress:
#             multi_progress = st.session_state.multi_audit_progress
#             total_cats = multi_progress.get('total_categories', 0)
#             completed_count = multi_progress.get('completed_count', 0)
           
#             st.markdown("---")
#             st.subheader("Multi-Category Progress")
#             st.metric("Categories Progress", f"{completed_count}/{total_cats}")
           
#             if total_cats > 0:
#                 multi_progress_pct = min(max(completed_count / total_cats, 0.0), 1.0)
#                 st.progress(multi_progress_pct, text=f"{completed_count} of {total_cats} completed")
           
#             completed_categories = multi_progress.get('completed_categories', [])
#             remaining_categories = multi_progress.get('remaining_categories', [])
           
#             if completed_categories:
#                 st.success(f"✅ Completed: {', '.join(completed_categories)}")
#             if remaining_categories:
#                 st.info(f"⏳ Remaining: {', '.join(remaining_categories)}")
       
#         if not st.session_state.audit_progress and not st.session_state.multi_audit_progress:
#             st.info("No active audit session")
       
#         st.markdown("---")
#         st.subheader("NIST AI RMF Categories")
#         categories = [
#             "1. Privacy-Enhanced",
#             "2. Valid & Reliable",
#             "3. Safe",
#             "4. Secure & Resilient",
#             "5. Accountable & Transparent",
#             "6. Explainable and Interpretable",
#             "7. Fair – With Harmful Bias Managed"
#         ]
#         for cat in categories:
#             st.write(f"• {cat}")
       
#         st.markdown("---")
       
#         if st.button("🔄 Reset Audit", type="secondary"):
#             st.session_state.audit_session_id = None
#             st.session_state.current_step = 'category_selection'
#             st.session_state.messages = []
#             st.session_state.audit_progress = None
#             st.session_state.multi_category_mode = False
#             st.session_state.waiting_for_transition = False
#             st.session_state.multi_audit_progress = None
#             st.rerun()
   
#     # Main chat interface
#     st.header("💬 Audit Conversation")
   
#     # Show continue button if waiting for transition
#     if st.session_state.waiting_for_transition:
#         st.info("🎯 Category completed! Ready to continue to next category.")
#         col1, col2 = st.columns([1, 3])
#         with col1:
#             if st.button("Continue to Next Category", type="primary", key="continue_btn"):
#                 handle_continue_transition()
#         with col2:
#             st.markdown("*Click to start the next category in your multi-category audit*")
#         st.markdown("---")
   
#     # Display chat history
#     chat_container = st.container()
#     with chat_container:
#         display_chat_history()
   
#     # Handle different steps of the audit process
#     if st.session_state.current_step == 'category_selection':
#         if not st.session_state.messages:
#             add_message("assistant", """
#             Welcome to the NIST AI Risk Management Framework Audit Agent!
           
#             I will guide you through a structured security posture assessment based on the 7 NIST AI RMF trustworthy characteristics.
           
#             **Choose your audit approach:**
           
#             🔹 **Single Category Audit** - Focus on one specific category
#             🔹 **Multi-Category Audit** - Audit multiple categories sequentially
           
#             **Available Categories:**
#             1. **Privacy-Enhanced** - Data protection and privacy measures
#             2. **Valid & Reliable** - Model accuracy and performance validation  
#             3. **Safe** - Safety measures and risk mitigation
#             4. **Secure & Resilient** - Security controls and resilience
#             5. **Accountable & Transparent** - Governance and transparency
#             6. **Explainable and Interpretable** - Model interpretability
#             7. **Fair – With Harmful Bias Managed** - Bias mitigation and fairness
#             """)
#             st.rerun()

#         # Multi-category selection section
#         st.subheader("Multi-Category Audit")
#         st.info("Select multiple categories for sequential auditing")

#         # Multi-category selection with checkboxes
#         selected_categories = []
#         col1, col2 = st.columns(2)
       
#         categories = [
#             ("Privacy-Enhanced", "🔒"),
#             ("Valid & Reliable", "✅"),
#             ("Safe", "🛡️"),
#             ("Secure & Resilient", "🔐"),
#             ("Accountable & Transparent", "📊"),
#             ("Explainable and Interpretable", "🔍"),
#             ("Fair – With Harmful Bias Managed", "⚖️")
#         ]

#         for i, (category, icon) in enumerate(categories):
#             column = col1 if i % 2 == 0 else col2
           
#             if column.checkbox(f"{icon} {category}", key=f"multi_checkbox_{i}"):
#                 selected_categories.append(category)

#         # Show selected categories
#         if selected_categories:
#             if len(selected_categories) == 1:
#                 st.warning(f"Selected 1 category: {selected_categories[0]}. Consider selecting more for multi-category audit or use single-category option below.")
#             else:
#                 st.success(f"Selected {len(selected_categories)} categories: {', '.join(selected_categories)}")
       
#         # Start multi-category audit button
#         if st.button("Start Multi-Category Audit", disabled=len(selected_categories) < 2):
#             st.session_state.multi_category_mode = True
           
#             categories_text = ", ".join(selected_categories)
#             message_text = f"I want to start a multi-category audit for {categories_text}"
           
#             payload = {
#                 "appName": "NIST-Agent",
#                 "userId": "clyde",
#                 "sessionId": "web_session",
#                 "newMessage": {
#                     "parts": [{"text": message_text}],
#                     "role": "user"
#                 }
#             }

#             with st.spinner(f"Starting multi-category audit for {len(selected_categories)} categories..."):
#                 response = call_agent_api(payload)

#             if "error" not in response and response.get("success"):
#                 add_message("user", f"Starting multi-category audit: {categories_text}")
#                 add_message("assistant", response.get('content', 'Multi-category audit started successfully.'), parsed=True)

#                 st.session_state.current_step = 'audit_questions'
#                 st.rerun()
#             else:
#                 st.error(f"Failed to start multi-category audit: {response.get('error', 'Unknown error')}")

#         st.markdown("---")

#         # Single category selection buttons
#         st.subheader("Single Category Audit")
#         col1, col2 = st.columns(2)

#         for i, (category, icon) in enumerate(categories):
#             if i % 2 == 0:
#                 column = col1
#             else:
#                 column = col2

#             if column.button(f"{icon} {category}", key=f"single_cat_{i}"):
#                 st.session_state.multi_category_mode = False
               
#                 payload = {
#                     "appName": "NIST-Agent",
#                     "userId": "clyde",
#                     "sessionId": "web_session",
#                     "newMessage": {
#                         "parts": [{"text": f"I want to audit the {category} category"}],
#                         "role": "user"
#                     }
#                 }

#                 with st.spinner(f"Starting audit for {category}..."):
#                     response = call_agent_api(payload)

#                 if "error" not in response and response.get("success"):
#                     add_message("user", f"I want to audit the {category} category")
#                     add_message("assistant", response.get("content", "Audit session started successfully."), parsed=True)

#                     st.session_state.current_step = 'audit_questions'
#                     st.rerun()
#                 else:
#                     st.error(f"Failed to start audit: {response.get('error', 'Unknown error')}")
   
#     elif st.session_state.current_step == 'audit_questions':
#         # Chat input for ongoing audit (only show if not waiting for transition)
#         if not st.session_state.waiting_for_transition:
#             if prompt := st.chat_input("Type your response..."):
#                 add_message("user", prompt)

#                 payload = {
#                     "appName": "NIST-Agent",
#                     "userId": "clyde",
#                     "sessionId": "web_session",
#                     "newMessage": {
#                         "parts": [{"text": prompt}],
#                         "role": "user"
#                     }
#                 }

#                 with st.spinner("Processing your response..."):
#                     response = call_agent_api(payload)

#                 if "error" not in response and response.get("success"):
#                     content = response.get("content", "Response received successfully.")
#                     add_message("assistant", content, parsed=True)

#                     # Check for completion or transition needs
#                     if isinstance(content, dict):
#                         if content.get("action") == "multi_audit_completed":
#                             st.session_state.current_step = 'completed'
#                             st.session_state.multi_category_mode = False
#                             st.session_state.waiting_for_transition = False
#                         elif content.get("needs_transition"):
#                             st.session_state.waiting_for_transition = True
#                         elif content.get("completed") and not st.session_state.multi_category_mode:
#                             st.session_state.current_step = 'completed'
#                 else:
#                     error_msg = response.get('error', 'Unknown error occurred')
#                     st.error(f"Error: {error_msg}")
#                     add_message("assistant", f"I encountered an error: {error_msg}")

#                 st.rerun()
   
#     elif st.session_state.current_step == 'completed':
#         st.success("🎉 Audit session completed successfully!")
#         st.info("You can start a new audit session by clicking the Reset Audit button in the sidebar.")
   
#     # Footer
#     st.markdown("---")
#     st.markdown("""
#     <div style='text-align: center; color: #666;'>
#         <small>NIST AI Risk Management Framework Audit Agent | Built with Streamlit</small>
#     </div>
#     """, unsafe_allow_html=True)


# if __name__ == "__main__":
#     main()

