# agent_skeleton/backend/main.py

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
import json
import re
import base64



app = FastAPI()

ADK_API_URL = "http://agent:8000"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def get_health():
    return {"status": "healthy"}

@app.get("/api/status")
async def get_status():
    return {"message": "NIST AI RMF Audit Agent Backend - OK"}

def parse_agent_response_enhanced(response):
    """Enhanced response parsing for agent responses"""
    try:
        # Handle array responses
        if isinstance(response, list) and len(response) > 0:
            for message in reversed(response):
                if isinstance(message, dict) and "content" in message:
                    content = message["content"]
                    if "parts" in content:
                        for part in content["parts"]:
                            if "functionResponse" in part:
                                func_response = part["functionResponse"]
                                if "response" in func_response:
                                    return func_response["response"]
                            elif "text" in part:
                                text_content = part["text"]
                                try:
                                    return json.loads(text_content)
                                except json.JSONDecodeError:
                                    return {"message": text_content, "action": "text_response"}
            return response[-1] if response else None
        
        # Handle dict responses
        elif isinstance(response, dict):
            if "content" in response:
                return parse_agent_response_enhanced([response])
            elif "message" in response:
                return response
            elif "response" in response:
                return response["response"]
            else:
                return response
        
        return {"message": str(response), "action": "unknown"}
        
    except Exception as e:
        print(f"Error parsing response: {e}")
        return {"message": f"Parse error: {e}", "action": "error"}

@app.post("/api/run")
async def run_agent(request: dict):
    try:
        print(f"🔍 DEBUG BACKEND: Received request")
       
        # Handle frontend request format - extract text and evidence package
        user_message = ""
        evidence_package = None
        
        if "newMessage" in request and "parts" in request["newMessage"]:
            for part in request["newMessage"]["parts"]:
                if "text" in part:
                    user_message = part["text"]
                if "evidence_package" in part:
                    evidence_package = part["evidence_package"]
                    print(f"🔍 DEBUG BACKEND: Found evidence package")
                    print(f"  - Text: '{evidence_package.get('text', '')}'")
                    print(f"  - Files: {len(evidence_package.get('files', []))}")
                    print(f"  - URLs: {len(evidence_package.get('urls', []))}")
                    break
       
        # Fallback to direct message field
        if not user_message:
            user_message = request.get("message", "")
            print(f"🔍 DEBUG BACKEND: Using fallback message: {user_message}")
       
        user_id = request.get("userId", "clyde")
        session_id = request.get("sessionId", "web_session")
        app_name = "nist_ai_rmf_audit_agent"
       
        async with httpx.AsyncClient(timeout=120.0) as client:
            if evidence_package:
                # Format evidence package as a special message that includes the package data
                evidence_message = f"EVIDENCE_PACKAGE:{json.dumps(evidence_package)}"
                payload = {
                    "appName": app_name,
                    "userId": user_id,
                    "sessionId": session_id,
                    "newMessage": {
                        "parts": [{"text": evidence_message}],
                        "role": "user"
                    },
                    "streaming": False
                }
                print(f"🔍 DEBUG BACKEND: Sending evidence package as encoded message")
            else:
                # Regular message
                payload = {
                    "appName": app_name,
                    "userId": user_id,
                    "sessionId": session_id,
                    "newMessage": {
                        "parts": [{"text": user_message}],
                        "role": "user"
                    },
                    "streaming": False
                }
            
            print(f"🔍 DEBUG BACKEND: Sending to agent...")
            response = await client.post(f"{ADK_API_URL}/run", json=payload)
           
            print(f"🔍 DEBUG BACKEND: Agent response status: {response.status_code}")
           
            if response.status_code == 200:
                result = response.json()
                print(f"🔍 DEBUG BACKEND: Processing agent response...")
                
                parsed_content = parse_agent_response_enhanced(result)
                
                if parsed_content:
                    return {"content": parsed_content, "success": True}
                else:
                    return {"content": {"message": "No response from agent", "action": "error"}, "success": False}
            else:
                error_message = f"Agent request failed with status {response.status_code}: {response.text}"
                print(f"🔍 DEBUG BACKEND: {error_message}")
                return {"error": error_message, "success": False}
               
    except httpx.TimeoutException:
        print(f"🔍 DEBUG BACKEND: Request timeout")
        return {"error": "Agent request timed out", "success": False}
    except httpx.RequestError as e:
        print(f"🔍 DEBUG BACKEND: Request error: {e}")
        return {"error": f"Could not connect to agent: {str(e)}", "success": False}
    except Exception as e:
        print(f"🔍 DEBUG BACKEND: Unexpected error: {e}")
        return {"error": f"Backend error: {str(e)}", "success": False}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)