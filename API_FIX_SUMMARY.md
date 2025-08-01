# API Fix Summary

## Problem

The NIST AI RMF Audit Agent was failing with a 422 error when trying to start an audit:

```
Failed to start audit: API call failed with status 500: {"detail":"Internal server error: 422: Agent request failed: {"detail":[{"type":"missing","loc":["body","appName"],"msg":"Field required","input":{"tool":"audit_tool","arguments":{"message":"I want to audit the Privacy-Enhanced category","category":"Privacy-Enhanced"}},"url":"https://errors.pydantic.dev/2.11/v/missing"},{"type":"missing","loc":["body","userId"],"msg":"Field required","input":{"tool":"audit_tool","arguments":{"message":"I want to audit the Privacy-Enhanced category","category":"Privacy-Enhanced"}},"url":"https://errors.pydantic.dev/2.11/v/missing"},{"type":"missing","loc":["body","sessionId"],"msg":"Field required","input":{"tool":"audit_tool","arguments":{"message":"I want to audit the Privacy-Enhanced category","category":"Privacy-Enhanced"}},"url":"https://errors.pydantic.dev/2.11/v/missing"},{"type":"missing","loc":["body","newMessage"],"msg":"Field required","input":{"tool":"audit_tool","arguments":{"message":"I want to audit the Privacy-Enhanced category","category":"Privacy-Enhanced"}},"url":"https://errors.pydantic.dev/2.11/v/missing"}]}"}
```

## Root Cause

The backend (`agent_skeleton/backend/main.py`) was sending the wrong payload format to the Google ADK API. The ADK expects specific fields:

- `appName`
- `userId`
- `sessionId`
- `newMessage`

But the backend was sending:

```json
{
  "tool": "audit_tool",
  "arguments": {
    "message": "...",
    "category": "..."
  }
}
```

## Solution

Updated `agent_skeleton/backend/main.py` to use the correct ADK API format:

### Changes Made:

1. **Fixed App Name**: Changed from `"multi_tool_agent"` to `"nist_ai_rmf_audit_agent"` to match the agent configuration in `agent.py`

2. **Updated Payload Format**: Changed from the old tool-based format to the correct ADK format:

```python
# OLD (incorrect) format:
payload = {
    "tool": "audit_tool",
    "arguments": {
        "message": message,
        "category": context.get("category", "")
    }
}

# NEW (correct) format:
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
```

3. **Added Session Management**: Added proper session creation before sending messages to the ADK

4. **Updated Response Handling**: Updated the response parsing to handle the ADK response format correctly

## Files Modified

- `agent_skeleton/backend/main.py` - Updated to use correct ADK API format

## Testing

Created `test_api_fix.py` to verify the fix works correctly.

## How to Test

1. Start the services: `cd agent_skeleton && docker compose up --build`
2. Run the test: `python test_api_fix.py`
3. Or access the frontend: http://localhost:8501

## Expected Result

The audit agent should now work correctly without the 422 error, allowing users to select categories and conduct NIST AI RMF audits successfully.
