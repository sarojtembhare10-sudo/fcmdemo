import firebase_admin
from firebase_admin import credentials, messaging
import sys
import json
import random

# ---------------------------------------------------------
# 1. DOWNLOAD YOUR SERVICE ACCOUNT KEY
# Place your service-account-key.json in the same directory.
# ---------------------------------------------------------
SERVICE_ACCOUNT_KEY_PATH = "service-account-key.json"

# ---------------------------------------------------------
# 2. PASTE THE DEVICE TOKEN HERE
# Copy the token printed in your Flutter app's debug console 
# or from the app UI directly.
# ---------------------------------------------------------
DEVICE_TOKEN = "eDjvQ7d5SwSAyAGgkpU6Fd:APA91bEwXPnNfHPEKOTAyI5UFrHJmfLj_pSScX8DmZy6s_0Pmqx7O6hzpf-i0aoxkcES82oinKJllb86Zk9OhGe60sCcw8EgJhWIw2vnK-hjIuSX-MoGlWk"

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

if __name__ == "__main__":
    print("--- Android Task Notification Server PoC ---")
    initialize_firebase()
    
    # 1. Load the 100 notifications from the JSON file
    notifications = load_notifications()
    if not notifications:
        sys.exit(1)
        
    print(f"📦 Loaded {len(notifications)} task notifications from database.")
    
    # 2. Pick a random notification from the list (Simulating a backend event)
    selected_notif = random.choice(notifications)
    
    print("\n--- 🎯 Selected Notification Payload ---")
    print(json.dumps(selected_notif, indent=2))
    print("--------------------------------------\n")
    
    # 3. Dispatch the notification to FCM
    send_notification(selected_notif)
