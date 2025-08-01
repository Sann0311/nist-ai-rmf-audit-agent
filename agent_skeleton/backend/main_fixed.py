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

def parse_agent_response(raw_response):
    """Parse the nested JSON response from the agent to extract user-friendly content"""
    try:
        print(f"🔍 Backend parsing response type: {type(raw_response)}")
        print(f"🔍 Backend raw response: {raw_response}")
        
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
                                    print(f"✅ Backend found function response: {tool_result}")
                                    return tool_result
                            # Check for plain text responses
                            elif "text" in part:
                                text_content = part["text"]
                                # Try to parse if it's JSON
                                try:
                                    json_content = json.loads(text_content)
                                    print(f"✅ Backend parsed JSON from text: {json_content}")
                                    return json_content
                                except json.JSONDecodeError:
                                    print(f"✅ Backend plain text response: {text_content}")
                                    return {"message": text_content, "action": "text_response"}
            
            # Fallback - return the complete last message for frontend parsing
            if raw_response and len(raw_response) > 0:
                last_message = raw_response[-1]
                print(f"⚠️ Backend using fallback - last message: {last_message}")
                return last_message
        
        # Handle single object format
        elif isinstance(raw_response, dict):
            # Check for Google ADK response format
            if "content" in raw_response:
                print(f"🔄 Backend processing single object with content")
                return parse_agent_response([raw_response])  # Convert to list and reprocess
            elif "message" in raw_response:
                print(f"✅ Backend direct message response: {raw_response}")
                return raw_response
            elif "response" in raw_response:
                print(f"✅ Backend response wrapper: {raw_response['response']}")
                return raw_response["response"]
            # Check for tool call results
            elif "toolCalls" in raw_response and raw_response["toolCalls"]:
                tool_result = raw_response["toolCalls"][0].get("result", {})
                if isinstance(tool_result, dict) and "message" in tool_result:
                    print(f"✅ Backend tool call result: {tool_result}")
                    return tool_result
                else:
                    print(f"⚠️ Backend tool call result (string): {tool_result}")
                    return {"message": str(tool_result), "action": "tool_response"}
            else:
                print(f"✅ Backend direct object response: {raw_response}")
                return raw_response
        else:
            print(f"⚠️ Backend unknown response format: {raw_response}")
            return {"message": str(raw_response), "action": "unknown_response"}
        
        return None
    except Exception as e:
        print(f"❌ Backend error parsing agent response: {e}")
        return {"message": f"Error parsing response: {e}", "action": "error"}

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
        
        # Handle frontend request format - extract text from newMessage.parts
        user_message = ""
        if "newMessage" in request and "parts" in request["newMessage"]:
            for part in request["newMessage"]["parts"]:
                if "text" in part:
                    user_message = part["text"]
                    break
        
        # Fallback to direct message field
        if not user_message:
            user_message = request.get("message", "")
        
        print(f"🔍 Backend extracted user_message: '{user_message}'")
        
        user_id = request.get("userId", "clyde")
        session_id = request.get("sessionId", "web_session")
        app_name = "nist_ai_rmf_audit_agent"
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Format payload for Google ADK API (proper Content format)
            payload = {
                "appName": app_name,
                "userId": user_id,
                "sessionId": session_id,
                "newMessage": {
                    "parts": [
                        {
                            "text": user_message  # Pass the original message unchanged
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
                
                # Parse the response to extract user-friendly content
                parsed_response = parse_agent_response(result)
                
                print(f"🔍 Backend parsed_response: {parsed_response}")
                
                if parsed_response is not None:
                    final_result = {"content": parsed_response, "success": True}
                    print(f"✅ Backend returning: {final_result}")
                    return final_result
                else:
                    # Fallback to original result
                    fallback_result = {"content": result, "success": True}
                    print(f"⚠️ Backend fallback returning: {fallback_result}")
                    return fallback_result
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
