# from fastapi import FastAPI, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# import httpx
# import os
# import json
# import re

# app = FastAPI()

# ADK_API_URL = "http://agent:8000"

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# @app.get("/health")
# async def get_health():
#     return {"status": "healthy"}

# @app.get("/api/status")
# async def get_status():
#     return {"message": "NIST AI RMF Audit Agent Backend - OK"}

# @app.post("/api/run")
# async def run_agent(request: dict):
#     try:
#         print(f"🔍 DEBUG BACKEND: Received request: {request}")
        
#         # Handle frontend request format - extract text from newMessage.parts
#         user_message = ""
#         if "newMessage" in request and "parts" in request["newMessage"]:
#             for part in request["newMessage"]["parts"]:
#                 if "text" in part:
#                     user_message = part["text"]
#                     break
        
#         print(f"🔍 DEBUG BACKEND: Extracted user_message: '{user_message}'")
        
#         # Fallback to direct message field
#         if not user_message:
#             user_message = request.get("message", "")
        
#         user_id = request.get("userId", "clyde")
#         session_id = request.get("sessionId", "web_session")
#         app_name = "nist_ai_rmf_audit_agent"
        
#         print(f"🔍 DEBUG BACKEND: Final user_message: '{user_message}', user_id: '{user_id}'")
        
#         async with httpx.AsyncClient(timeout=60.0) as client:
#             # Format payload for Google ADK API (proper Content format)
#             payload = {
#                 "appName": app_name,
#                 "userId": user_id,
#                 "sessionId": session_id,
#                 "newMessage": {
#                     "parts": [
#                         {
#                             "text": user_message  # Pass the original message unchanged
#                         }
#                     ],
#                     "role": "user"
#                 },
#                 "streaming": False
#             }
            
#             print(f"Sending to ADK: {payload}")
            
#             # Use the correct Google ADK /run endpoint
#             response = await client.post(
#                 f"{ADK_API_URL}/run",
#                 json=payload
#             )
            
#             print(f"ADK Response status: {response.status_code}")
#             print(f"ADK Response: {response.text}")
            
#             if response.status_code == 200:
#                 result = response.json()
#                 print(f"Parsed result: {result}")
                
#                 # Handle Google ADK response format - it returns an array of message objects
#                 if isinstance(result, list) and len(result) > 0:
#                     # Look for the latest message with function response (tool result)
#                     for message in reversed(result):
#                         if isinstance(message, dict) and "content" in message:
#                             content = message["content"]
#                             if "parts" in content:
#                                 for part in content["parts"]:
#                                     # Check for function response with tool result
#                                     if "functionResponse" in part:
#                                         func_response = part["functionResponse"]
#                                         if "response" in func_response:
#                                             tool_result = func_response["response"]
#                                             # Return the complete tool result for frontend parsing
#                                             return {"content": tool_result, "success": True}
#                                     # Check for plain text responses
#                                     elif "text" in part:
#                                         text_content = part["text"]
#                                         # Try to parse if it's JSON
#                                         try:
#                                             json_content = json.loads(text_content)
#                                             return {"content": json_content, "success": True}
#                                         except json.JSONDecodeError:
#                                             return {"content": text_content, "success": True}
                    
#                     # Fallback - return the complete last message for frontend parsing
#                     if result and len(result) > 0:
#                         return {"content": result[-1], "success": True}
                
#                 # Handle single object format
#                 elif isinstance(result, dict):
#                     # Check for Google ADK response format
#                     if "content" in result:
#                         return {"content": result["content"], "success": True}
#                     elif "message" in result:
#                         return {"content": result["message"], "success": True}
#                     elif "response" in result:
#                         return {"content": result["response"], "success": True}
#                     # Check for tool call results
#                     elif "toolCalls" in result and result["toolCalls"]:
#                         tool_result = result["toolCalls"][0].get("result", {})
#                         if isinstance(tool_result, dict) and "message" in tool_result:
#                             return {"content": tool_result["message"], "success": True}
#                         else:
#                             return {"content": str(tool_result), "success": True}
#                     else:
#                         return {"content": str(result), "success": True}
#                 else:
#                     return {"content": str(result), "success": True}
#             else:
#                 raise HTTPException(
#                     status_code=response.status_code,
#                     detail=f"Agent request failed: {response.text}"
#                 )
                
#     except httpx.TimeoutException:
#         raise HTTPException(status_code=504, detail="Agent request timed out")
#     except httpx.RequestError as e:
#         print(f"Request error: {e}")
#         raise HTTPException(status_code=503, detail=f"Could not connect to agent: {str(e)}")
#     except Exception as e:
#         print(f"Unexpected error: {e}")
#         raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8001)


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
        print(f"🔍 DEBUG BACKEND: Received request: {request}")
       
        # Handle frontend request format - extract text from newMessage.parts
        user_message = ""
        if "newMessage" in request and "parts" in request["newMessage"]:
            for part in request["newMessage"]["parts"]:
                if "text" in part:
                    user_message = part["text"]
                    break
       
        print(f"🔍 DEBUG BACKEND: Extracted user_message: '{user_message}'")
       
        # Fallback to direct message field
        if not user_message:
            user_message = request.get("message", "")
       
        user_id = request.get("userId", "clyde")
        session_id = request.get("sessionId", "web_session")
        app_name = "nist_ai_rmf_audit_agent"
       
        print(f"🔍 DEBUG BACKEND: Final user_message: '{user_message}', user_id: '{user_id}'")
       
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
           
            print(f"🔍 DEBUG BACKEND: Sending to ADK: {payload}")
           
            # Use the correct Google ADK /run endpoint
            response = await client.post(
                f"{ADK_API_URL}/run",
                json=payload
            )
           
            print(f"🔍 DEBUG BACKEND: ADK Response status: {response.status_code}")
            print(f"🔍 DEBUG BACKEND: ADK Response: {response.text}")
           
            if response.status_code == 200:
                result = response.json()
                print(f"🔍 DEBUG BACKEND: Parsed result: {result}")
               
                # Handle Google ADK response format - it returns an array of message objects
                if isinstance(result, list) and len(result) > 0:
                    # Look for the latest message with function response (tool result)
                    for message in reversed(result):
                        if isinstance(message, dict) and "content" in message:
                            content = message["content"]
                            if "parts" in content:
                                for part in content["parts"]:
                                    # Check for function response with tool result
                                    if "functionResponse" in part:
                                        func_response = part["functionResponse"]
                                        if "response" in func_response:
                                            tool_result = func_response["response"]
                                            print(f"🔍 DEBUG BACKEND: Found tool result: {tool_result}")
                                            # Return the complete tool result for frontend parsing
                                            return {"content": tool_result, "success": True}
                                    # Check for plain text responses
                                    elif "text" in part:
                                        text_content = part["text"]
                                        print(f"🔍 DEBUG BACKEND: Found text content: {text_content}")
                                        # Try to parse if it's JSON
                                        try:
                                            json_content = json.loads(text_content)
                                            print(f"🔍 DEBUG BACKEND: Parsed JSON content: {json_content}")
                                            return {"content": json_content, "success": True}
                                        except json.JSONDecodeError:
                                            print(f"🔍 DEBUG BACKEND: Plain text response: {text_content}")
                                            return {"content": text_content, "success": True}
                   
                    # Fallback - return the complete last message for frontend parsing
                    if result and len(result) > 0:
                        print(f"🔍 DEBUG BACKEND: Using fallback - last message: {result[-1]}")
                        return {"content": result[-1], "success": True}
               
                # Handle single object format
                elif isinstance(result, dict):
                    # Check for Google ADK response format
                    if "content" in result:
                        print(f"🔍 DEBUG BACKEND: Single object with content: {result['content']}")
                        return {"content": result["content"], "success": True}
                    elif "message" in result:
                        print(f"🔍 DEBUG BACKEND: Single object with message: {result['message']}")
                        return {"content": result["message"], "success": True}
                    elif "response" in result:
                        print(f"🔍 DEBUG BACKEND: Single object with response: {result['response']}")
                        return {"content": result["response"], "success": True}
                    # Check for tool call results
                    elif "toolCalls" in result and result["toolCalls"]:
                        tool_result = result["toolCalls"][0].get("result", {})
                        if isinstance(tool_result, dict) and "message" in tool_result:
                            print(f"🔍 DEBUG BACKEND: Tool call with message: {tool_result['message']}")
                            return {"content": tool_result["message"], "success": True}
                        else:
                            print(f"🔍 DEBUG BACKEND: Tool call result: {tool_result}")
                            return {"content": str(tool_result), "success": True}
                    else:
                        print(f"🔍 DEBUG BACKEND: Direct single object: {result}")
                        return {"content": str(result), "success": True}
                else:
                    print(f"🔍 DEBUG BACKEND: Unknown format, converting to string: {result}")
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

