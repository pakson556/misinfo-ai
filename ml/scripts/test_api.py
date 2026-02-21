#!/usr/bin/env python3
"""
Simple test script for the ML API.
No path dependencies - just calls the running API.
"""
import requests
import json
import sys

API_URL = "http://localhost:8000"

def test_health():
    """Test health endpoint."""
    try:
        resp = requests.get(f"{API_URL}/health")
        print(f"Health: {resp.json()}")
        return resp.status_code == 200
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to API. Is it running?")
        print("   Start with: uvicorn ml.api.main:app --reload")
        return False

def test_predict(text):
    """Test prediction endpoint."""
    resp = requests.post(
        f"{API_URL}/predict/auto",
        json={"text": text}
    )
    data = resp.json()
    print(f"\n📝 Text: {text[:100]}..." if len(text) > 100 else f"\n📝 Text: {text}")
    print(f"   Verdict: {data['verdict']}")
    print(f"   Confidence: {data['confidence']:.3f}")
    print(f"   Risk Band: {data['risk_band']}")
    return data

def main():
    """Run tests."""
    print("🧪 Testing ML API...")
    print("=" * 50)
    
    if not test_health():
        sys.exit(1)
    
    # Test cases
    test_cases = [
        "Breaking: Scientists discover that drinking coffee cures cancer!",
        "The weather today is sunny with a high of 75 degrees.",
        "They don't want you to know the truth about what really happened.",
        "FDA approves new vaccine for COVID-19 after clinical trials.",
    ]
    
    for text in test_cases:
        test_predict(text)
    
    print("\n" + "=" * 50)
    print("✅ Tests complete")

if __name__ == "__main__":
    main()