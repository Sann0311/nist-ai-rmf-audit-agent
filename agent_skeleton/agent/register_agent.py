#!/usr/bin/env python3
"""
Direct agent registration script for ADK
"""

import sys
import os

# Add the workspace to Python path
sys.path.insert(0, '/workspace')

try:
    from google.adk import App
    from multi_tool_agent.agent import root_agent
    
    print("🔧 Registering agent with ADK...")
    
    # Create the ADK app
    app = App()
    
    # Register the agent if it exists
    if root_agent is not None:
        app.register_agent("nist_ai_rmf_audit_agent", root_agent)
        print("✅ Agent registered successfully")
        print(f"   Agent name: nist_ai_rmf_audit_agent")
        print(f"   Agent type: {type(root_agent)}")
        print(f"   Tools: {len(root_agent.tools) if hasattr(root_agent, 'tools') else 'N/A'}")
    else:
        print("❌ Agent not available")
        sys.exit(1)
    
    # Start the server
    print("🚀 Starting ADK server...")
    app.run(host="0.0.0.0", port=8000)
    
except ImportError as e:
    print(f"❌ ADK not available: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error registering agent: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1) 