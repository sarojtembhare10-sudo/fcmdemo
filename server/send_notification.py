import os
import time
import schedule
import threading
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
DEVICE_TOKEN = os.getenv("DEVICE_TOKEN", "eDjvQ7d5SwSAyAGgkpU6Fd:APA91bEwXPnNfHPEKOTAyI5UFrHJmfLj_pSScX8DmZy6s_0Pmqx7O6hzpf-i0aoxkcES82oinKJllb86Zk9OhGe60sCcw8EgJhWIw2vnK-hjIuSX-MoGlWk")

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
    try:
        with open('notifications_data.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("❌ ERROR: Could not find 'notifications_data.json'. Run 'python generate_mock_data.py' first.")
        return []

def send_notification(notification_data):
    if DEVICE_TOKEN == "PASTE_YOUR_DEVICE_TOKEN_HERE" or not DEVICE_TOKEN:
        print("❌ ERROR: Please replace DEVICE_TOKEN with your actual FCM token from the app.")
        return

    print(f"Sending message to token: {DEVICE_TOKEN[:15]}...")

    # Construct the message payload based on the JSON data
    message = messaging.Message(
        notification=messaging.Notification(
            title=notification_data['title'],
            body=notification_data['body']
        ),
        data=notification_data['data'],
        token=DEVICE_TOKEN,
    )

    try:
        # Send the message
        response = messaging.send(message)
        print(f"✅ Successfully sent message! Message ID: {response}")
    except Exception as e:
        print(f"❌ Error sending message: {e}")

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
    
    # Schedule to run every 15 minutes
    schedule.every(15).minutes.do(job)
    
    # Start the scheduling loop in a separate background daemon thread
    scheduler_thread = threading.Thread(target=run_schedule, daemon=True)
    scheduler_thread.start()
    
    # Start the Flask web server to satisfy Render's port binding requirement
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
