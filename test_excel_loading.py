#!/usr/bin/env python3
"""
Test script to verify Excel file loading with the updated agent
"""

import sys
import os

# Add the agent path
sys.path.append('agent_skeleton/agent/multi_tool_agent')

try:
    from tool import load_audit_data, get_nist_categories, start_audit_session
    
    print("🧪 Testing Excel File Loading...")
    print("=" * 40)
    
    # Test loading audit data
    print("1. Testing audit data loading...")
    df = load_audit_data()
    
    if df is not None:
        print(f"✅ Excel file loaded successfully!")
        print(f"   Shape: {df.shape}")
        print(f"   Columns: {list(df.columns)}")
        
        # Test getting categories
        print("\n2. Testing category retrieval...")
        categories = get_nist_categories()
        print(f"✅ Found {len(categories)} categories:")
        for cat in categories:
            print(f"   • {cat}")
        
        # Test starting a session for Privacy-Enhanced
        print("\n3. Testing session creation...")
        result = start_audit_session("Privacy-Enhanced", "test_user")
        
        if "error" not in result:
            print(f"✅ Session created successfully!")
            print(f"   Session ID: {result.get('session_id')}")
            print(f"   Category: {result.get('category')}")
            print(f"   Message: {result.get('message', '')[:100]}...")
        else:
            print(f"❌ Session creation failed: {result.get('error')}")
    else:
        print("❌ Failed to load Excel file")
        
except ImportError as e:
    print(f"❌ Import error: {e}")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc() 