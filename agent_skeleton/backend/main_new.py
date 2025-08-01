from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
import json
import re

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

@app.post("/api/run")
async def run_agent(request: dict):
    try:
        print(f"Received request: {request}")
        
        # Extract message and context from the frontend request
        message = request.get("message", "")
        context = request.get("context", {})
        user_id = request.get("user_id", "clyde")
        session_id = request.get("session_id", "web_session")
        app_name = "multi_tool_agent"
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            # First, try to create/ensure session exists
            session_url = f"{ADK_API_URL}/apps/{app_name}/users/{user_id}/sessions/{session_id}"
            session_response = await client.post(session_url, json={})
            print(f"Session creation response: {session_response.status_code}")
            
            # Format payload for Google ADK API (proper Content format)
            payload = {
                "appName": app_name,
                "userId": user_id,
                "sessionId": session_id,
                "newMessage": {
                    "parts": [
                        {
                            "text": f"Please audit the {context.get('category', 'general')} category. {message}"
                        }
                    ],
                    "role": "user"
                },
                "streaming": False
            }
            
            print(f"Sending to ADK: {payload}")
            
            # Use the correct Google ADK /run endpoint
            response = await client.post(
                f"{ADK_API_URL}/run",
                json=payload
            )
            
            print(f"ADK Response status: {response.status_code}")
            print(f"ADK Response: {response.text}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"Parsed result: {result}")
                
                # Handle Google ADK response format
                if isinstance(result, dict):
                    # Check for Google ADK response format
                    if "content" in result:
                        return {"content": result["content"], "success": True}
                    elif "message" in result:
                        return {"content": result["message"], "success": True}
                    elif "response" in result:
                        return {"content": result["response"], "success": True}
                    # Check for tool call results
                    elif "toolCalls" in result and result["toolCalls"]:
                        tool_result = result["toolCalls"][0].get("result", {})
                        if isinstance(tool_result, dict) and "message" in tool_result:
                            return {"content": tool_result["message"], "success": True}
                        else:
                            return {"content": str(tool_result), "success": True}
                    else:
                        return {"content": str(result), "success": True}
                else:
                    return {"content": str(result), "success": True}
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Agent request failed: {response.text}"
                )
                
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Agent request timed out")
    except httpx.RequestError as e:
        print(f"Request error: {e}")
        raise HTTPException(status_code=503, detail=f"Could not connect to agent: {str(e)}")
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
