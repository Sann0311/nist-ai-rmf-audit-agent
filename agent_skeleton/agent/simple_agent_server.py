#!/usr/bin/env python3
"""
Simple Agent Server
This bypasses Google ADK and creates a direct FastAPI server for the NIST AI RMF Audit Agent
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import sys
import os
import json

# Add the current directory to Python path
sys.path.append('/workspace')
sys.path.append('/workspace/multi_tool_agent')

# Import the agent tools
try:
    from multi_tool_agent.tool import run_tool, get_capabilities, load_audit_data
    from multi_tool_agent.agent import audit_tool
    print("✅ Successfully imported agent components")
except ImportError as e:
    print(f"❌ Error importing agent components: {e}")
    run_tool = None
    audit_tool = None

app = FastAPI(title="NIST AI RMF Audit Agent")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class AgentRequest(BaseModel):
    appName: str
    userId: str
    sessionId: str
    newMessage: Dict[str, Any]
    streaming: Optional[bool] = False

class MessagePart(BaseModel):
    text: str

class NewMessage(BaseModel):
    parts: List[MessagePart]
    role: str

@app.get("/health")
async def health_check():
    return {"status": "healthy", "agent": "nist_ai_rmf_audit_agent"}

@app.post("/run")
async def run_agent(request: AgentRequest):
    """
    Main endpoint for running the NIST AI RMF Audit Agent
    """
    try:
        print(f"Received request: {request.dict()}")
        
        # Extract the message text from the parts
        message_text = ""
        if request.newMessage and "parts" in request.newMessage:
            for part in request.newMessage["parts"]:
                if "text" in part:
                    message_text += part["text"] + " "
        
        message_text = message_text.strip()
        print(f"Extracted message: {message_text}")
        
        # Determine if this is a category selection
        category = None
        categories = [
            "Privacy-Enhanced",
            "Valid & Reliable", 
            "Safe",
            "Secure & Resilient",
            "Accountable & Transparent",
            "Explainable and Interpretable", 
            "Fair – With Harmful Bias Managed"
        ]
        
        for cat in categories:
            if cat.lower() in message_text.lower():
                category = cat
                break
        
        # Use the audit tool if available
        if audit_tool:
            try:
                result = audit_tool(message=message_text, category=category or "")
                print(f"Audit tool result: {result}")
                
                # Return in Google ADK response format
                return [{
                    "content": {
                        "parts": [{
                            "functionResponse": {
                                "id": "audit_response",
                                "name": "audit_tool",
                                "response": result if isinstance(result, dict) else {"message": str(result)}
                            }
                        }],
                        "role": "model"
                    },
                    "partial": False,
                    "usageMetadata": {
                        "candidatesTokenCount": 100,
                        "promptTokenCount": 50,
                        "totalTokenCount": 150
                    },
                    "invocationId": f"audit-{request.sessionId}",
                    "author": "nist_ai_rmf_audit_agent",
                    "actions": {
                        "stateDelta": {},
                        "artifactDelta": {},
                        "requestedAuthConfigs": {}
                    },
                    "id": f"response-{request.sessionId}",
                    "timestamp": 1753940000.0
                }]
            except Exception as e:
                print(f"Error running audit tool: {e}")
                raise HTTPException(status_code=500, detail=f"Audit tool error: {str(e)}")
        
        # Fallback response if audit_tool is not available
        return [{
            "content": {
                "parts": [{
                    "text": f"NIST AI RMF Audit Agent received: {message_text}. System is in development mode."
                }],
                "role": "model"
            },
            "partial": False,
            "usageMetadata": {
                "candidatesTokenCount": 50,
                "promptTokenCount": 25,
                "totalTokenCount": 75
            },
            "invocationId": f"audit-{request.sessionId}",
            "author": "nist_ai_rmf_audit_agent",
            "actions": {
                "stateDelta": {},
                "artifactDelta": {},
                "requestedAuthConfigs": {}
            },
            "id": f"response-{request.sessionId}",
            "timestamp": 1753940000.0
        }]
        
    except Exception as e:
        print(f"Error in run_agent: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/status")
async def get_status():
    """Get agent status"""
    audit_data = load_audit_data() if load_audit_data else None
    return {
        "status": "running",
        "agent": "nist_ai_rmf_audit_agent",
        "capabilities": get_capabilities() if get_capabilities else "Development mode",
        "audit_data_loaded": audit_data is not None,
        "audit_data_rows": len(audit_data) if audit_data is not None else 0
    }

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting NIST AI RMF Audit Agent Server")
    print("📊 Loading audit data...")
    
    # Test loading audit data
    if load_audit_data:
        audit_data = load_audit_data()
        if audit_data is not None:
            print(f"✅ Audit data loaded: {len(audit_data)} rows")
        else:
            print("❌ Failed to load audit data")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)