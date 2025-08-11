# agent.py
try:
    from google.adk.agents import LlmAgent  
    from google.adk.models.lite_llm import LiteLlm  
    from google.genai import types  
    ADK_AVAILABLE = True
except ImportError as e:
    print(f"Google ADK not available: {e}")
    ADK_AVAILABLE = False
    LlmAgent = None
    LiteLlm = None
    types = None

# Import our tool functions
try:
    from .tool import (
        run_tool,
        get_capabilities,
        start_audit_session,
        process_chat_message,
        get_nist_categories,
    )
except ImportError:
    # Define dummy functions if tools are not available
    def run_tool(*args, **kwargs):
        return {}
    def get_capabilities(*args, **kwargs):
        return {}
    def start_audit_session(*args, **kwargs):
        return {}
    def process_chat_message(*args, **kwargs):
        return {}
    def get_nist_categories(*args, **kwargs):
        return [
            "Privacy-Enhanced",
            "Valid & Reliable", 
            "Safe",
            "Secure & Resilient",
            "Accountable & Transparent",
            "Explainable and Interpretable",
            "Fair – With Harmful Bias Managed"
        ]


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
    """NIST AI RMF Audit Tool for conducting structured security assessments with AI-powered assessment generation."""
    print(f"DEBUG audit_tool: message='{message}', category='{category}', kwargs={kwargs}")
   
    # If no message, show help
    if not message:
        return _get_help()
   
    # Check if this is an evidence package submission
    evidence_package = kwargs.get('evidence_package')
    if evidence_package or message == "EVIDENCE_PACKAGE":
        # Route evidence package through process_chat_message with proper context
        context = {
            'user_id': "clyde",
            'evidence_package': evidence_package
        }
        print(f"DEBUG: Processing evidence package with context: {context}")
        result = process_chat_message("EVIDENCE_PACKAGE_SUBMISSION", context)
        print(f"DEBUG: Evidence package result: {result}")
        return result
   
    # ALWAYS route through process_chat_message for proper multi-category detection and assessment generation
    context = {'user_id': "clyde"}
   
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
        # Enhanced LlmAgent creation with comprehensive instructions
        root_agent = LlmAgent(
            name="nist_ai_rmf_audit_agent",
            model=model,
            instruction="""You are an AI Audit Agent designed to conduct security posture assessments based on the NIST AI Risk Management Framework (AI RMF). You guide users through structured audits and generate comprehensive AI-powered assessments with detailed recommendations.

**CRITICAL INSTRUCTION: ALWAYS USE FUNCTION CALLS**
For EVERY user message, you MUST call the audit_tool() function. NEVER respond with plain text or JSON strings. ALWAYS use function calls.

**ENHANCED WORKFLOW:**
1. **Category Selection**: When user selects a category, call audit_tool(message="I want to audit [category]")
2. **Multi-Category Selection**: When user wants multiple categories, call audit_tool(message="I want to start a multi-category audit for [category1], [category2]")  
3. **Question Process**: For each user response, call audit_tool(message="[user_response]")
4. **Evidence Submission**: When user provides evidence, call audit_tool(message="[evidence]")
5. **Continue Multi-Category**: When user wants to continue, call audit_tool(message="continue to next category")
6. **Assessment Generation**: When user requests assessment or results, call audit_tool(message="generate assessment")

**7 NIST AI RMF CATEGORIES:**
- Privacy-Enhanced: Data protection and privacy measures
- Valid & Reliable: Model accuracy and performance validation
- Safe: Safety measures and risk mitigation  
- Secure & Resilient: Security controls and resilience
- Accountable & Transparent: Governance and transparency
- Explainable and Interpretable: Model interpretability
- Fair – With Harmful Bias Managed: Bias mitigation and fairness

**ADVANCED FEATURES:**
- **Multi-Category Support**: Sequential auditing across multiple NIST categories with smooth transitions
- **AI-Powered Assessment Generation**: Comprehensive compliance analysis with personalized recommendations
- **Enhanced Evidence Processing**: Support for files, images, documents, and URLs
- **Risk Analysis**: Automatic identification of high-risk areas with priority-based action items
- **Interactive Progress Tracking**: Real-time progress updates with visual indicators
- **Professional Reporting**: Export capabilities for compliance documentation

Remember: Your role is to be a knowledgeable, helpful audit assistant that guides users through comprehensive NIST AI RMF assessments while generating valuable insights for improving their AI governance posture.""",
            tools=[audit_tool],
        )
        print("✅ Successfully created enhanced LlmAgent with comprehensive audit capabilities")
    except Exception as e:
        print(f"❌ Error creating enhanced LlmAgent: {e}")
        print("⚠️  Trying fallback agent creation...")
        # Fallback: create a minimal agent
        try:
            root_agent = LlmAgent(
                name="nist_ai_rmf_audit_agent",
                model=model,
                instruction="""You are a NIST AI RMF Audit Agent. Always use the audit_tool() function for every user message. Guide users through structured audits and generate comprehensive assessments.""",
                tools=[audit_tool],
            )
            print("✅ Successfully created fallback LlmAgent")
        except Exception as e2:
            print(f"❌ Fallback also failed: {e2}")
            root_agent = None
else:
    print("⚠️  ADK components not available, creating minimal agent structure")
    root_agent = None


# Export for ADK
__all__ = ['root_agent', 'audit_tool', 'run_tool', 'get_capabilities']