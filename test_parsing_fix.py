#!/usr/bin/env python3
"""
Test script to verify the JSON response parsing fix
"""

import requests
import json

def test_backend_parsing():
    """Test the backend API with enhanced parsing"""
    
    # Test payload for category selection
    test_payload = {
        "appName": "NIST-Agent",
        "userId": "clyde",
        "sessionId": "web_session",
        "newMessage": {
            "parts": [{"text": "I want to audit the Privacy-Enhanced category"}],
            "role": "user"
        }
    }
    
    print("🧪 Testing Enhanced Backend Response Parsing...")
    print(f"Payload: {json.dumps(test_payload, indent=2)}")
    
    try:
        response = requests.post("http://localhost:8001/api/run", json=test_payload, timeout=30)
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ API call successful!")
            print(f"Response structure: {json.dumps(result, indent=2)}")
            
            # Check if the response is properly parsed
            if "content" in result:
                content = result["content"]
                if isinstance(content, dict):
                    if "message" in content:
                        print(f"✅ Found user-friendly message: {content['message'][:100]}...")
                    if "action" in content:
                        print(f"✅ Found action: {content['action']}")
                    if "current_question" in content:
                        print(f"✅ Found current question structure")
                    
                    print("\n🎯 Response Analysis:")
                    print(f"   - Type: {type(content)}")
                    print(f"   - Keys: {list(content.keys()) if isinstance(content, dict) else 'Not a dict'}")
                    
                    if content.get("action") in ["start_session", "category_selected", "session_exists"]:
                        print("✅ Successfully parsed structured response!")
                    else:
                        print(f"⚠️ Unexpected action: {content.get('action')}")
                else:
                    print(f"⚠️ Content is not a dict: {type(content)}")
            else:
                print("❌ No 'content' field in response")
            
            return True
        else:
            print(f"❌ API call failed: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to backend. Make sure containers are running.")
        print("   Run: docker compose up --build")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_backend_health():
    """Test if the backend is running"""
    try:
        response = requests.get("http://localhost:8001/health", timeout=5)
        if response.status_code == 200:
            print("✅ Backend is healthy")
            return True
        else:
            print(f"❌ Backend health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Backend not accessible: {e}")
        return False

if __name__ == "__main__":
    print("🔍 NIST AI RMF Audit Agent - Enhanced Response Parsing Test")
    print("=" * 60)
    
    # First check if backend is running
    if test_backend_health():
        # Test the enhanced parsing
        test_backend_parsing()
    else:
        print("\n💡 To start the services:")
        print("   1. cd agent_skeleton")
        print("   2. docker compose up --build")
        print("   3. Run this test again")
