try:
    from google.adk.agents import LlmAgent  
    from google.adk.models.lite_llm import LiteLlm  
    from google.genai import types  
    from .tool import (
        run_tool,
        get_capabilities,
        start_audit_session,
        process_chat_message,
        get_nist_categories,
    )
    ADK_AVAILABLE = True
except ImportError as e:
    print(f"Google ADK not available: {e}")
    ADK_AVAILABLE = False
    LlmAgent = None
    LiteLlm = None
    types = None
    # Define dummy functions if ADK is not available
    def run_tool(*args, **kwargs):
        return {}
    def get_capabilities(*args, **kwargs):
        return {}
    def start_audit_session(*args, **kwargs):
        return {}
    def process_chat_message(*args, **kwargs):
        return {}
    def get_nist_categories(*args, **kwargs):
        return []

def _get_help():
    """Returns the help message for the agent."""
    return {
        "action": "help",
        "message": "I'm here to help you conduct a NIST AI RMF audit. Please select one of the 7 categories to begin:\n\n" +
                   "\n".join([f"• {cat}" for cat in get_nist_categories()]) +
                   "\n\nWhich category would you like to audit?"
    }

# Create the audit tool function for the agent
def audit_tool(message: str = "", category: str = "", **kwargs):
    """NIST AI RMF Audit Tool for conducting structured security assessments."""
    print(f"DEBUG audit_tool: message='{message}', category='{category}', kwargs={kwargs}")
    
    # If a category is provided directly, start a new session
    if category:
        print(f"DEBUG: Starting session with provided category: {category}")
        return start_audit_session(category, user_id=kwargs.get("user_id", "default"))
    
    # If no category and no message, show help
    if not message:
        return _get_help()
    
    # Create minimal context and directly process the message
    context = {'user_id': kwargs.get("user_id", "default")}
    
    print(f"DEBUG: Calling process_chat_message with message='{message}'")
    result = process_chat_message(message, context)
    print(f"DEBUG: Got result: {result}")
    return result

# Create model if available
if LiteLlm is not None:
    model = LiteLlm(
        model="ollama/llama3.2:3b",
        api_base="http://host.docker.internal:11434",
    )
else:
    model = None

# Create agent if components are available
if LlmAgent is not None and model is not None:
    try:
        # Basic LlmAgent creation with only essential parameters
        root_agent = LlmAgent(
            name="nist_ai_rmf_audit_agent",
            model=model,
            instruction="""You are an AI Audit Agent designed to conduct security posture assessments based on the NIST AI Risk Management Framework (AI RMF). You guide users through structured audits for one of the 7 NIST AI RMF trustworthy characteristics.

**CRITICAL INSTRUCTION: ALWAYS USE FUNCTION CALLS**
For EVERY user message, you MUST call the audit_tool() function. NEVER respond with plain text or JSON strings. ALWAYS use function calls.

**WORKFLOW:**
1. **Category Selection**: When user selects a category, call audit_tool(message="I want to audit [category]", category="[category]")
2. **Question Process**: For each user response, call audit_tool(message="[user_response]", category="[current_category]")
3. **Evidence Submission**: When user provides evidence, call audit_tool(message="[evidence]", category="[current_category]")

**7 NIST AI RMF CATEGORIES:**
- Privacy-Enhanced
- Valid & Reliable
- Safe
- Secure & Resilient
- Accountable & Transparent
- Explainable and Interpretable
- Fair – With Harmful Bias Managed
""",
            tools=[audit_tool],
        )
        print("✅ Successfully created LlmAgent")
    except Exception as e:
        print(f"❌ Error creating LlmAgent: {e}")
        print("⚠️  Trying fallback agent creation...")
        # Fallback: create a minimal agent
        try:
            root_agent = LlmAgent(
                model=model,
                tools=[audit_tool],
            )
            print("✅ Successfully created fallback LlmAgent")
        except Exception as e2:
            print(f"❌ Fallback also failed: {e2}")
            root_agent = None
else:
    root_agent = None

# Export for ADK
__all__ = ['root_agent', 'audit_tool', 'run_tool', 'get_capabilities']
