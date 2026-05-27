import os
import time
import schedule
import threading
import requests
from flask import Flask
import firebase_admin
from firebase_admin import credentials, messaging
import sys
import json
import random

# ---------------------------------------------------------
# CLOUD CONFIGURATION (RENDER)
# Uses Environment Variables in the cloud, falls back to local files for testing
# ---------------------------------------------------------
SERVICE_ACCOUNT_KEY_PATH = os.getenv("SERVICE_ACCOUNT_KEY_PATH", "service-account-key.json")

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://dmytgkvgjeeilsxpohnl.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRteXRna3ZnamVlaWxzeHBvaG5sIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3OTg4MTk2NywiZXhwIjoyMDk1NDU3OTY3fQ.2RKVOLZUsq_AWUqlWtfLovcu4bfvPOaba5EaDbgsOIg")

def initialize_firebase():
    try:
        cred = credentials.Certificate(SERVICE_ACCOUNT_KEY_PATH)
        firebase_admin.initialize_app(cred)
        print("✅ Firebase Admin initialized successfully.")
    except FileNotFoundError:
        print(f"❌ ERROR: Could not find '{SERVICE_ACCOUNT_KEY_PATH}'. Please ensure it is in the same folder as this script.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error initializing Firebase Admin: {e}")
        sys.exit(1)

def load_notifications():
    # Dynamically find the path so it works whether run from root or server/ folder
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(script_dir, 'notifications_data.json')
    try:
        with open(json_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ ERROR: Could not find '{json_path}'. Run 'python generate_mock_data.py' first.")
        return []

def send_notification(notification_data):
    try:
        # Fetch tokens using Supabase REST API instead of the SDK
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}"
        }
        response = requests.get(f"{SUPABASE_URL}/rest/v1/device_tokens?select=token", headers=headers)
        response.raise_for_status()
        
        tokens_data = response.json()
        if not tokens_data:
            print("❌ ERROR: No device tokens found in Supabase.")
            return
            
        device_tokens = [item['token'] for item in tokens_data if item.get('token')]
        
        if not device_tokens:
            print("❌ ERROR: Tokens retrieved from Supabase are empty.")
            return
            
        print(f"Sending message to {len(device_tokens)} device(s)...")

        # Construct the message payload based on the JSON data
        message = messaging.MulticastMessage(
            notification=messaging.Notification(
                title=notification_data['title'],
                body=notification_data['body']
            ),
            data=notification_data['data'],
            tokens=device_tokens,
        )

        try:
            # Send the message
            send_response = messaging.send_each_for_multicast(message)
            print(f"✅ Successfully sent message! {send_response.success_count} messages were sent successfully, {send_response.failure_count} messages failed.")
        except Exception as e:
            print(f"❌ Error sending message via FCM: {e}")
            
    except Exception as e:
        print(f"❌ Error retrieving tokens from Supabase: {e}")

def job():
    print("\n[JOB] Running scheduled notification task...")
    notifications = load_notifications()
    if not notifications:
        print("❌ ERROR: No notifications found. Skipping job.")
        return
        
    selected_notif = random.choice(notifications)
    
    print("--- 🎯 Selected Notification Payload ---")
    print(json.dumps(selected_notif, indent=2))
    print("--------------------------------------")
    
    send_notification(selected_notif)

app = Flask(__name__)

@app.route('/')
def home():
    return "FCM Notification Service is running!"

@app.route('/health')
def health_check():
    return {"status": "healthy", "timestamp": time.time()}

def ping_health():
    # Render automatically sets RENDER_EXTERNAL_URL for web services
    # If not on Render, it falls back to localhost
    url = os.environ.get("RENDER_EXTERNAL_URL", "https://fcmdemo.onrender.com")
    health_url = f"{url}/health"
    try:
        response = requests.get(health_url, timeout=10)
        print(f"[HEALTH-CHECK] Pinged {health_url} - Status Code: {response.status_code}")
    except Exception as e:
        print(f"[HEALTH-CHECK] Failed to ping {health_url}: {e}")

def run_schedule():
    print("\n⏳ Scheduler started in background thread. Waiting 15 minutes for the next notification...")
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    print("--- Android Task Notification Server PoC (Web Service) ---")
    initialize_firebase()
    
    # Run once immediately on startup
    job()
    
    # Schedule to run every 15 minutes (using your 5 minute change)
    schedule.every(5).minutes.do(job)
    
    # Schedule health check every 5 minutes to keep Render awake
    schedule.every(5).minutes.do(ping_health)
    
    # Start the scheduling loop in a separate background daemon thread
    scheduler_thread = threading.Thread(target=run_schedule, daemon=True)
    scheduler_thread.start()
    
    # Start the Flask web server to satisfy Render's port binding requirement
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
