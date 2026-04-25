#!/usr/bin/env python3
"""
Script to set Telegram webhook for the guild bot

Usage:
    python setup_webhook.py <TOKEN> <URL>

Example:
    python setup_webhook.py 123456789:ABCDefGHiJKlmNoPqRsTuvWxYzABCDeFgHiJk https://guild-bot.onrender.com
"""

import sys
import requests
import json

def set_webhook(token, url):
    """Set Telegram webhook"""
    webhook_url = f"https://api.telegram.org/bot{token}/setWebhook"
    
    payload = {
        'url': f"{url}/webhook"
    }
    
    try:
        print(f"🔧 Setting webhook to: {url}/webhook")
        response = requests.post(webhook_url, json=payload)
        result = response.json()
        
        if result.get('ok'):
            print("✅ Webhook set successfully!")
            print(json.dumps(result, indent=2))
        else:
            print(f"❌ Error: {result.get('description')}")
            return False
    except Exception as e:
        print(f"❌ Error setting webhook: {e}")
        return False
    
    return True

def get_webhook_info(token):
    """Get webhook info"""
    info_url = f"https://api.telegram.org/bot{token}/getWebhookInfo"
    
    try:
        print("\n📊 Getting webhook info...")
        response = requests.get(info_url)
        result = response.json()
        
        if result.get('ok'):
            print(json.dumps(result['result'], indent=2))
        else:
            print(f"❌ Error: {result.get('description')}")
    except Exception as e:
        print(f"❌ Error getting webhook info: {e}")

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    
    token = sys.argv[1]
    url = sys.argv[2]
    
    if set_webhook(token, url):
        get_webhook_info(token)
    else:
        sys.exit(1)