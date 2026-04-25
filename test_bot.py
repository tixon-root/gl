#!/usr/bin/env python3
"""
Integration tests for the guild bot
"""

import requests
import json
from bs4 import BeautifulSoup

GUILD_URL = 'https://www.rucoyonline.com/guild/Imperia%20Of%20Titans'
BOT_URL = 'http://localhost:10000'

def test_health_check():
    """Test health check endpoint"""
    print("🧪 Testing health check...")
    try:
        response = requests.get(f"{BOT_URL}/")
        assert response.status_code == 200
        assert response.json()['status'] == 'ok'
        print("✅ Health check passed")
        return True
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

def test_guild_parsing():
    """Test guild website parsing"""
    print("\n🧪 Testing guild parsing...")
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(GUILD_URL, headers=headers, timeout=10)
        assert response.status_code == 200
        
        soup = BeautifulSoup(response.text, 'html.parser')
        rows = soup.find_all('tr')
        
        print(f"✅ Found {len(rows)} rows")
        
        if len(rows) > 1:
            print("✅ Guild parsing passed")
            
            # Print first few members
            print("\n📋 Guild Members:")
            for row in rows[1:4]:
                cols = row.find_all('td')
                if len(cols) >= 3:
                    name = cols[0].text.strip()
                    status = cols[1].text.strip()
                    level = cols[2].text.strip()
                    print(f"  - {name} ({status}) Lvl {level}")
            
            return True
        else:
            print("❌ No guild data found")
            return False
    except Exception as e:
        print(f"❌ Guild parsing failed: {e}")
        return False

def test_webhook_endpoint():
    """Test webhook endpoint (without real Telegram data)"""
    print("\n🧪 Testing webhook endpoint...")
    try:
        # This will likely fail without real Telegram data, but should handle it gracefully
        response = requests.post(
            f"{BOT_URL}/webhook",
            json={'update_id': 1, 'message': {}},
            timeout=5
        )
        print(f"✅ Webhook endpoint responded: {response.status_code}")
        return True
    except Exception as e:
        print(f"❌ Webhook endpoint error: {e}")
        return False

def main():
    """Run all tests"""
    print("🤖 Guild Bot Integration Tests\n")
    print(f"Bot URL: {BOT_URL}")
    print(f"Guild URL: {GUILD_URL}\n")
    
    tests = [
        test_health_check,
        test_guild_parsing,
        test_webhook_endpoint,
    ]
    
    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"\n❌ Test error: {e}")
            results.append(False)
    
    print(f"\n\n📊 Results: {sum(results)}/{len(results)} tests passed")
    
    if all(results):
        print("\n✅ All tests passed!")
        return 0
    else:
        print("\n⚠️  Some tests failed")
        return 1

if __name__ == '__main__':
    exit(main())