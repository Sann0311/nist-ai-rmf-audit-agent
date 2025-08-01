#!/usr/bin/env python3
"""
ADK App for NIST AI RMF Audit Agent
"""

import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from google.adk import App
    from multi_tool_agent.agent import root_agent
    
    # Create the ADK app
    app = App()
    
    # Register the agent if it exists
    if root_agent is not None:
        app.register_agent("nist_ai_rmf_audit_agent", root_agent)
        print("✅ Agent registered successfully")
    else:
        print("❌ Agent not available")
    
    if __name__ == "__main__":
        app.run()
        
except ImportError as e:
    print(f"❌ ADK not available: {e}")
    print("This is normal for development - ADK works inside Docker containers")
except Exception as e:
    print(f"❌ Error creating ADK app: {e}") 