#!/usr/bin/env python3
"""
Test script to verify the API fix for the NIST AI RMF Audit Agent
"""

import httpx
import json

def test_backend_api():
    """Test the backend API with the correct payload format"""
    
    # Test payload that should work with the fixed backend
    test_payload = {
        "user_id": "test_user",
        "session_id": "test_session",
        "message": "I want to audit the Privacy-Enhanced category",
        "context": {
            "action": "start_session",
            "category": "Privacy-Enhanced"
        }
    }
    
    print("🧪 Testing Backend API...")
    print(f"Payload: {json.dumps(test_payload, indent=2)}")
    
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post("http://localhost:8001/api/run", json=test_payload)
            
            print(f"Status Code: {response.status_code}")
            print(f"Response: {response.text}")
            
            if response.status_code == 200:
                result = response.json()
                print("✅ API call successful!")
                print(f"Result: {json.dumps(result, indent=2)}")
                return True
            else:
                print(f"❌ API call failed with status {response.status_code}")
                return False
                
    except httpx.ConnectError:
        print("❌ Could not connect to backend. Make sure the services are running.")
        print("   Run: cd agent_skeleton && docker compose up --build")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_backend_health():
    """Test if the backend is running"""
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get("http://localhost:8001/health")
            if response.status_code == 200:
                print("✅ Backend is running")
                return True
            else:
                print(f"❌ Backend health check failed: {response.status_code}")
                return False
    except Exception as e:
        print(f"❌ Backend not accessible: {e}")
        return False

if __name__ == "__main__":
    print("🔍 NIST AI RMF Audit Agent API Test")
    print("=" * 40)
    
    # First check if backend is running
    if test_backend_health():
        # Test the API
        test_backend_api()
    else:
        print("\n💡 To start the services:")
        print("   1. cd agent_skeleton")
        print("   2. docker compose up --build")
        print("   3. Run this test again") 