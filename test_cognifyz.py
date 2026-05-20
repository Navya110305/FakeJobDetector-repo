#!/usr/bin/env python3
"""Test script to validate fake job detection on specific URLs."""

import json
import requests
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

def test_url_scan(url: str):
    """Test the scan-url endpoint."""
    print(f"\n{'='*70}")
    print(f"Testing URL: {url}")
    print(f"{'='*70}")
    
    # Make request to backend
    try:
        response = requests.post(
            "http://127.0.0.1:5000/scan-url",
            json={"url": url},
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        
        print(f"\n✓ Response received")
        print(f"  Result: {result.get('result')}")
        print(f"  Risk Score: {result.get('risk_score')} / 100")
        print(f"  Confidence: {result.get('confidence')}")
        
        if "company_verification" in result:
            cv = result["company_verification"]
            print(f"\n  Company Verification:")
            print(f"    - Name: {cv.get('name')}")
            print(f"    - Verified: {cv.get('is_verified')}")
            print(f"    - Legitimate Indicators: {cv.get('legitimate_indicators')}")
            print(f"    - Scam Indicators: {cv.get('scam_indicators')}")
            print(f"    - Signals:")
            for signal in cv.get('signals', []):
                print(f"      • {signal}")
        
        if "domain" in result:
            d = result["domain"]
            print(f"\n  Domain Analysis:")
            print(f"    - Hostname: {d.get('hostname')}")
            print(f"    - Trusted: {d.get('is_trusted')}")
            print(f"    - Signals:")
            for signal in d.get('signals', []):
                print(f"      • {signal}")
        
        return result
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        return None

if __name__ == "__main__":
    # Test URLs
    test_urls = [
        "https://cognifyz.com/internships/",  # The problematic URL
        "https://www.linkedin.com/jobs/view/1234567890/",  # Genuine job platform
        "https://careers.google.com/",  # Trusted company
    ]
    
    print("\n" + "="*70)
    print("FAKE JOB DETECTOR - URL SCAN TEST")
    print("="*70)
    print("\nNote: Make sure the Flask backend is running on http://127.0.0.1:5000")
    print("Run: python backend/app.py in another terminal")
    
    results = {}
    for url in test_urls:
        result = test_url_scan(url)
        if result:
            results[url] = result
    
    print(f"\n{'='*70}")
    print("TEST SUMMARY")
    print(f"{'='*70}")
    for url, result in results.items():
        status = "✓ CORRECT" if (
            (result.get('result') == 'FAKE' and result.get('risk_score', 100) < 50) or
            (result.get('result') == 'GENUINE' and result.get('risk_score', 0) >= 50)
        ) else "✗ INCORRECT"
        
        print(f"{status}: {url}")
        print(f"       Result={result.get('result')}, Score={result.get('risk_score')}")
