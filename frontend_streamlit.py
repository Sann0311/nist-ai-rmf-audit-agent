import streamlit as st
import httpx
import json
from typing import Dict, Any

# Configure Streamlit page
st.set_page_config(
    page_title="NIST AI RMF Audit Agent",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Backend API URL - use backend service name in Docker
BACKEND_URL = "http://backend:8001"  # Use Docker service name

# Initialize session state
if 'audit_session_id' not in st.session_state:
    st.session_state.audit_session_id = None
if 'current_step' not in st.session_state:
    st.session_state.current_step = 'category_selection'
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'audit_progress' not in st.session_state:
    st.session_state.audit_progress = None
if 'debug_mode' not in st.session_state:
    st.session_state.debug_mode = False

def parse_agent_response(raw_response):
    """Parse the nested JSON response from the agent to extract user-friendly content"""
    try:
        # Debug logging for development
        if st.session_state.get('debug_mode', False):
            print(f"🔍 Parsing response type: {type(raw_response)}")
            print(f"🔍 Raw response: {raw_response}")
        
        # Handle Google ADK response format - it returns an array of message objects
        if isinstance(raw_response, list) and len(raw_response) > 0:
            # Look for the latest message with function response (tool result)
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
                                    if st.session_state.get('debug_mode', False):
                                        print(f"✅ Found function response: {tool_result}")
                                    return tool_result
                            # Check for plain text responses
                            elif "text" in part:
                                text_content = part["text"]
                                # Try to parse if it's JSON
                                try:
                                    import json
                                    json_content = json.loads(text_content)
                                    if st.session_state.get('debug_mode', False):
                                        print(f"✅ Parsed JSON from text: {json_content}")
                                    return json_content
                                except json.JSONDecodeError:
                                    if st.session_state.get('debug_mode', False):
                                        print(f"✅ Plain text response: {text_content}")
                                    return {"message": text_content, "action": "text_response"}
            
            # Fallback - return the complete last message for frontend parsing
            if raw_response and len(raw_response) > 0:
                last_message = raw_response[-1]
                if st.session_state.get('debug_mode', False):
                    print(f"⚠️ Using fallback - last message: {last_message}")
                return last_message
        
        # Handle single object format
        elif isinstance(raw_response, dict):
            # Check for Google ADK response format
            if "content" in raw_response:
                if st.session_state.get('debug_mode', False):
                    print(f"🔄 Processing single object with content")
                return parse_agent_response([raw_response])  # Convert to list and reprocess
            elif "message" in raw_response:
                if st.session_state.get('debug_mode', False):
                    print(f"✅ Direct message response: {raw_response}")
                return raw_response
            elif "response" in raw_response:
                if st.session_state.get('debug_mode', False):
                    print(f"✅ Response wrapper: {raw_response['response']}")
                return raw_response["response"]
            # Check for tool call results
            elif "toolCalls" in raw_response and raw_response["toolCalls"]:
                tool_result = raw_response["toolCalls"][0].get("result", {})
                if isinstance(tool_result, dict) and "message" in tool_result:
                    if st.session_state.get('debug_mode', False):
                        print(f"✅ Tool call result: {tool_result}")
                    return tool_result
                else:
                    if st.session_state.get('debug_mode', False):
                        print(f"⚠️ Tool call result (string): {tool_result}")
                    return {"message": str(tool_result), "action": "tool_response"}
            else:
                if st.session_state.get('debug_mode', False):
                    print(f"✅ Direct object response: {raw_response}")
                return raw_response
        else:
            if st.session_state.get('debug_mode', False):
                print(f"⚠️ Unknown response format: {raw_response}")
            return {"message": str(raw_response), "action": "unknown_response"}
        
        return None
    except Exception as e:
        print(f"❌ Error parsing agent response: {e}")
        print(f"Raw response type: {type(raw_response)}")
        print(f"Raw response: {raw_response}")
        return {"message": f"Error parsing response: {e}", "action": "error"}

def call_agent_api(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Call the agent API through the backend"""
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(f"{BACKEND_URL}/api/run", json=payload)
            if response.status_code == 200:
                result = response.json()
                
                # Debug logging
                if st.session_state.get('debug_mode', False):
                    print(f"🔍 Frontend received from backend: {result}")
                
                # Backend has already parsed the response, just extract the content
                if result.get("success") and "content" in result:
                    return {"content": result["content"], "success": True}
                else:
                    # Fallback to try parsing the entire result if backend parsing failed
                    parsed_content = parse_agent_response(result)
                    if parsed_content is not None:
                        return {"content": parsed_content, "success": True}
                    else:
                        return {"content": result, "success": True}
            else:
                return {"error": f"API call failed with status {response.status_code}: {response.text}"}
    except Exception as e:
        return {"error": f"Failed to connect to backend: {str(e)}"}

def add_message(role: str, content: str, parsed: bool = False):
    """Add a message to the chat history. If parsed=True, content is a dict to be rendered nicely."""
    st.session_state.messages.append({"role": role, "content": content, "parsed": parsed})

def display_chat_history():
    """Display the chat history with pretty formatting for agent responses."""
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message.get("parsed") and isinstance(message["content"], dict):
                render_agent_response(message["content"])
            else:
                st.write(message["content"])

def render_agent_response(response: dict):
    """
    Render the agent's response with improved parsing and user-friendly display.
    Handles the structured response format from the NIST AI RMF Audit Agent.
    """
    
    # Ensure we're working with a dictionary
    if not isinstance(response, dict):
        if isinstance(response, str):
            st.markdown(response)
        else:
            st.markdown("Response received successfully.")
            # Show raw data in debug mode
            if st.session_state.get('debug_mode', False):
                with st.expander("🐛 Debug: Non-dict Response", expanded=False):
                    st.code(str(response))
        return
    
    # Extract the core response data (should already be parsed by parse_agent_response)
    resp = response
    
    # Get action and message
    action = resp.get("action", "").lower()
    message = resp.get("message", "")
    
    # Always display the main message if available
    if message:
        st.markdown(message)
    
    # Handle specific actions
    if action in {"session_exists", "start_session", "category_selected"}:
        # Display current question if available
        if "current_question" in resp:
            current_q = resp["current_question"]
            
            # Display main question
            main_question = current_q.get("main_question")
            nist_control = current_q.get("nist_control", "N/A")
            
            if main_question:
                st.markdown(f"### 📋 Current Question ({nist_control})")
                st.markdown(main_question)
            
            # Display sub-questions
            sub_questions = current_q.get("sub_questions", [])
            if sub_questions:
                st.markdown("#### Sub-questions to address:")
                for i, sq in enumerate(sub_questions, 1):
                    if isinstance(sq, dict):
                        sub_q_text = sq.get("sub_question", "")
                        if sub_q_text:
                            st.markdown(f"**{i}.** {sub_q_text}")
                    elif isinstance(sq, str):
                        st.markdown(f"**{i}.** {sq}")
        
        # Show progress if available
        progress = resp.get("progress", {})
        if progress and progress.get("current") and progress.get("total"):
            current = progress["current"]
            total = progress["total"]
            progress_pct = current / total
            st.progress(progress_pct, text=f"Question {current} of {total}")
            
            # Update session state with progress
            st.session_state.audit_progress = progress

    elif action == "observation_recorded":
        # Display baseline evidence
        baseline_evidence = resp.get("baseline_evidence")
        if baseline_evidence:
            st.markdown("### 📖 Baseline Evidence Requirements")
            if isinstance(baseline_evidence, list):
                for item in baseline_evidence:
                    if isinstance(item, dict):
                        sub_q = item.get('sub_question', '')
                        evidence = item.get('baseline_evidence', '')
                        if sub_q and evidence:
                            st.markdown(f"**{sub_q}:**")
                            st.markdown(f"_{evidence}_")
                    else:
                        st.markdown(f"• {item}")
            else:
                st.markdown(baseline_evidence)

    elif action == "evidence_evaluated":
        # Display evaluation results
        evaluation = resp.get("evaluation", {})
        
        conformity = evaluation.get("conformity")
        justification = evaluation.get("justification")
        
        if conformity:
            st.markdown(f"### ✅ Conformity Assessment")
            st.markdown(f"**Level:** {conformity}")
            
        if justification:
            st.markdown(f"**Justification:** {justification}")
        
        # Show next question if available
        next_question = resp.get("next_question", {})
        if isinstance(next_question, dict) and next_question.get("sub_question"):
            st.markdown(f"### ➡️ Next Question")
            st.markdown(next_question["sub_question"])
        
        # Check for audit completion
        if resp.get("completed") or resp.get("status") == "completed":
            st.success("🎉 Audit Completed Successfully!")
            st.session_state.current_step = "completed"

    elif action == "help":
        # Just display the message (already handled above)
        pass
    
    elif action == "audit_completed" or resp.get("completed") or resp.get("status") == "completed":
        st.success("🎉 Audit Completed Successfully!")
        st.session_state.current_step = "completed"
    
    elif action == "error":
        st.error(f"Agent Error: {message}")
        
    elif action == "text_response":
        # Pure text response - already displayed above
        pass
        
    elif action == "unknown_response":
        st.warning("Received an unusual response format. See debug info for details.")
        
    else:
        # Fallback for unrecognized actions
        if not message:
            # Try to display current question if no message
            if "current_question" in resp:
                current_q = resp["current_question"]
                main_question = current_q.get("main_question")
                if main_question:
                    st.markdown(f"**Question:** {main_question}")
                elif current_q.get("sub_question"):
                    st.markdown(f"**Question:** {current_q['sub_question']}")
            else:
                st.markdown("Response received successfully.")
        
        # Show any session information
        if "session_id" in resp:
            if st.session_state.get('debug_mode', False):
                st.caption(f"Session ID: {resp['session_id']}")
    
    # Debug information (controlled by global debug mode)
    if st.session_state.get('debug_mode', False):
        with st.expander("🐛 Debug: Raw Response Data", expanded=False):
            st.json(resp)


def main():
    # Header
    st.title("NIST AI RMF Audit Agent")
    st.markdown("### Security Posture Assessment Based on NIST AI Risk Management Framework")
    
    # Sidebar with audit information
    with st.sidebar:
        st.header("Audit Information")
        
        if st.session_state.audit_progress:
            progress = st.session_state.audit_progress
            st.metric("Current Progress", f"{progress.get('current', 0)}/{progress.get('total', 0)}")
            st.metric("Category", progress.get('category', 'None'))
            st.metric("Status", progress.get('status', 'Not Started').title())
            
            # Progress bar
            if progress.get('total', 0) > 0:
                progress_pct = progress.get('current', 0) / progress.get('total', 0)
                st.progress(progress_pct)
        
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
        
        # Debug mode toggle
        debug_toggle = st.checkbox("🐛 Show Debug Info", value=st.session_state.debug_mode, key="global_debug_toggle")
        if debug_toggle != st.session_state.debug_mode:
            st.session_state.debug_mode = debug_toggle
        
        if st.button("🔄 Reset Audit", type="secondary"):
            st.session_state.audit_session_id = None
            st.session_state.current_step = 'category_selection'
            st.session_state.messages = []
            st.session_state.audit_progress = None
            st.rerun()
    
    # Main chat interface
    st.header("💬 Audit Conversation")
    
    # Display chat history
    chat_container = st.container()
    with chat_container:
        display_chat_history()
    
    # Handle different steps of the audit process
    if st.session_state.current_step == 'category_selection':
        if not st.session_state.messages:
            add_message("assistant", """
            Welcome to the NIST AI Risk Management Framework Audit Agent! 
            
            I will guide you through a structured security posture assessment based on the 7 NIST AI RMF trustworthy characteristics.
            
            Please select one of the following categories to begin your audit:
            
            1. **Privacy-Enhanced** - Data protection and privacy measures
            2. **Valid & Reliable** - Model accuracy and performance validation  
            3. **Safe** - Safety measures and risk mitigation
            4. **Secure & Resilient** - Security controls and resilience
            5. **Accountable & Transparent** - Governance and transparency
            6. **Explainable and Interpretable** - Model interpretability
            7. **Fair – With Harmful Bias Managed** - Bias mitigation and fairness
            
            Which category would you like to audit?
            """)
            st.rerun()

        # Category selection buttons
        st.subheader("Select Category to Audit")
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
            if i % 2 == 0:
                column = col1
            else:
                column = col2

            if column.button(f"{icon} {category}", key=f"cat_{i}"):
                # Start audit session with improved message
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
                    # Add parsed agent response for pretty rendering
                    add_message("assistant", response.get("content", "Audit session started successfully."), parsed=True)

                    # Move to audit questions step
                    st.session_state.current_step = 'audit_questions'
                    st.rerun()
                else:
                    st.error(f"Failed to start audit: {response.get('error', 'Unknown error')}")
    
    elif st.session_state.current_step == 'audit_questions':
        # Chat input for ongoing audit
        if prompt := st.chat_input("Type your response..."):
            add_message("user", prompt)

            # Check if this is a category selection message even during audit phase
            categories = [
                "Privacy-Enhanced", "Valid & Reliable", "Safe", "Secure & Resilient",
                "Accountable & Transparent", "Explainable and Interpretable", 
                "Fair – With Harmful Bias Managed"
            ]
            
            is_category_selection = False
            for category in categories:
                if category.lower() in prompt.lower() and ("audit" in prompt.lower() or "want" in prompt.lower()):
                    is_category_selection = True
                    break

            # Process the user input
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
                # Extract and display the response content
                content = response.get("content", "Response received successfully.")
                add_message("assistant", content, parsed=True)

                # Check if this is an audit completion
                try:
                    # Check for completion in structured response
                    if isinstance(content, dict):
                        # Check direct response structure
                        if content.get("completed") or content.get("action") == "audit_completed":
                            st.session_state.current_step = 'completed'
                            st.success("🎉 Audit Completed Successfully!")
                    # Check string content for completion indicators
                    elif isinstance(content, str) and ("audit completed" in content.lower() or "🎉" in content):
                        st.session_state.current_step = 'completed'
                        st.success("🎉 Audit Completed Successfully!")
                except Exception as e:
                    # Don't fail if completion check fails, just continue
                    pass
            else:
                error_msg = response.get('error', 'Unknown error occurred')
                st.error(f"Error: {error_msg}")
                add_message("assistant", f"I encountered an error: {error_msg}")

            st.rerun()
    
    elif st.session_state.current_step == 'completed':
        st.success("🎉 Audit session completed successfully!")
        st.info("You can start a new audit session by clicking the Reset Audit button in the sidebar.")
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666;'>
        <small>NIST AI Risk Management Framework Audit Agent | Built with Streamlit</small>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
