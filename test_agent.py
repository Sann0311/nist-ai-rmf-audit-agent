#!/usr/bin/env python3
"""
Test script to verify the NIST AI RMF Audit Agent functionality
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'agent_skeleton', 'agent', 'multi_tool_agent'))

try:
    from tool import run_tool, get_nist_categories, load_audit_data
except ImportError as e:
    print(f"Import error: {e}")
    print("Note: This test requires the agent dependencies to be installed")
    print("Run this test inside the Docker container for full functionality")
    
    # Create mock functions for development
    def run_tool(*args, **kwargs):
        return "Mock response - run inside Docker container for real functionality"
    
    def get_nist_categories():
        return ["Privacy-Enhanced", "Valid & Reliable", "Safe", "Secure & Resilient", 
                "Accountable & Transparent", "Explainable and Interpretable", 
                "Fair – With Harmful Bias Managed"]
    
    def load_audit_data():
        print("Mock data loading - full functionality available in Docker container")
        return None

def test_data_loading():
    """Test that the audit data loads correctly"""
    print("Testing audit data loading...")
    df = load_audit_data()
    if df is not None:
        print(f"✅ Successfully loaded {len(df)} rows from Audit.xlsx")
        print(f"   Columns: {list(df.columns)}")
        categories = df['Trust-worthiness characteristic'].dropna().unique()
        print(f"   Categories: {list(categories)}")
    else:
        print("❌ Failed to load audit data")
    return df

def test_categories():
    """Test category retrieval"""
    print("\nTesting category retrieval...")
    result = run_tool("get_categories")
    print(f"Result: {result}")
    return result

def test_session_start():
    """Test starting an audit session"""
    print("\nTesting session start...")
    result = run_tool("start_session", category="Privacy-Enhanced")
    print(f"Result: {result}")
    return result

def test_chat_processing():
    """Test chat message processing"""
    print("\nTesting chat processing...")
    result = run_tool("process_chat", message="I want to audit Privacy-Enhanced", context={})
    print(f"Result: {result}")
    return result

if __name__ == "__main__":
    print("🔍 NIST AI RMF Audit Agent - Test Suite")
    print("=" * 50)
    
    # Test data loading
    df = test_data_loading()
    
    # Test categories
    categories_result = test_categories()
    
    # Test session start
    session_result = test_session_start()
    
    # Test chat processing
    chat_result = test_chat_processing()
    
    print("\n" + "=" * 50)
    print("✅ Test suite completed!")
