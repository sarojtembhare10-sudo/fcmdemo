import os
import time
import schedule
import threading
import requests
from flask import Flask
import firebase_admin
from firebase_admin import credentials, messaging, firestore
import sys
import json
import random

# ---------------------------------------------------------
# CLOUD CONFIGURATION (RENDER)
# Uses Environment Variables in the cloud, falls back to local files for testing
# ---------------------------------------------------------
SERVICE_ACCOUNT_KEY_PATH = os.getenv("SERVICE_ACCOUNT_KEY_PATH", "service-account-key.json")

# Firestore collection where Flutter devices self-register their FCM tokens
DEVICE_TOKENS_COLLECTION = "device_tokens"

# FCM MulticastMessage limit per API call
FCM_MULTICAST_BATCH_SIZE = 500

db = None  # Firestore client — initialized after Firebase Admin is ready


def initialize_firebase():
    global db
    try:
        cred = credentials.Certificate(SERVICE_ACCOUNT_KEY_PATH)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("✅ Firebase Admin + Firestore initialized successfully.")
    except FileNotFoundError:
        print(f"❌ ERROR: Could not find '{SERVICE_ACCOUNT_KEY_PATH}'. Please ensure it is in the same folder as this script.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error initializing Firebase Admin: {e}")
        sys.exit(1)


def get_all_device_tokens() -> list[str]:
    """Reads all FCM tokens registered by Flutter devices from Firestore."""
    try:
        docs = db.collection(DEVICE_TOKENS_COLLECTION).stream()
        tokens = []
        for doc in docs:
            data = doc.to_dict()
            token = data.get("token")
            if token:
                tokens.append(token)
        print(f"📋 Found {len(tokens)} registered device(s) in Firestore.")
        return tokens
    except Exception as e:
        print(f"❌ Error fetching device tokens from Firestore: {e}")
        return []


def load_notifications():
    """Loads notification payloads from the local JSON file.
    Supports both:
      - New format: {"notifications": [{notification, category, description, id}, ...]}
      - Legacy format: [{title, body, data}, ...]
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(script_dir, 'notifications_data.json')
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            raw = json.load(f)

        # Support new format with wrapper key
        if isinstance(raw, dict) and 'notifications' in raw:
            return raw['notifications']
        # Legacy: plain list
        if isinstance(raw, list):
            return raw

        print("❌ ERROR: Unrecognized notifications_data.json format.")
        return []
    except FileNotFoundError:
        print(f"❌ ERROR: Could not find '{json_path}'. Add your notifications_data.json to the server/ folder.")
        return []
    except json.JSONDecodeError as e:
        print(f"❌ ERROR: Invalid JSON in notifications_data.json: {e}")
        return []


def build_fcm_payload(notification_data: dict) -> tuple[str, str, dict]:
    """
    Converts a notification entry to (title, body, data) for FCM.
    Handles both the new schema and the legacy mock schema.
    """
    # --- New schema: {notification, category, description, id} ---
    if 'notification' in notification_data:
        title = notification_data.get('category', 'Notification')
        body  = notification_data.get('notification', '')
        data  = {
            'id':          str(notification_data.get('id', '')),
            'category':    notification_data.get('category', ''),
            'description': notification_data.get('description', ''),
        }
        return title, body, data

    # --- Legacy schema: {title, body, data} ---
    return (
        notification_data.get('title', 'Notification'),
        notification_data.get('body', ''),
        notification_data.get('data', {}),
    )


def send_multicast_notification(notification_data: dict, tokens: list[str]):
    """
    Sends a notification to all provided tokens using FCM MulticastMessage.
    Automatically batches into groups of FCM_MULTICAST_BATCH_SIZE (max 500).
    """
    if not tokens:
        print("⚠️  No device tokens found. Skipping send.")
        return

    title, body, data = build_fcm_payload(notification_data)

    total_success = 0
    total_failure = 0

    # Split into batches of 500 (FCM hard limit per multicast call)
    for i in range(0, len(tokens), FCM_MULTICAST_BATCH_SIZE):
        batch_tokens = tokens[i:i + FCM_MULTICAST_BATCH_SIZE]
        batch_num = (i // FCM_MULTICAST_BATCH_SIZE) + 1

        print(f"📤 Sending batch {batch_num} to {len(batch_tokens)} device(s)...")

        message = messaging.MulticastMessage(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=data,
            tokens=batch_tokens,
        )

        try:
            response = messaging.send_each_for_multicast(message)
            total_success += response.success_count
            total_failure += response.failure_count

            # Log individual failures so stale tokens can be identified
            for idx, result in enumerate(response.responses):
                if not result.success:
                    failed_token = batch_tokens[idx]
                    print(f"  ❌ Failed for token [...{failed_token[-10:]}]: {result.exception}")

        except Exception as e:
            print(f"❌ Error sending batch {batch_num}: {e}")
            total_failure += len(batch_tokens)

    print(f"✅ Multicast complete — Success: {total_success}, Failed: {total_failure}")


def job():
    print("\n[JOB] Running scheduled notification task...")

    # Step 1: Fetch all registered device tokens from Firestore
    tokens = get_all_device_tokens()
    if not tokens:
        print("⚠️  No devices registered yet. Skipping job.")
        return

    # Step 2: Pick a random notification payload
    notifications = load_notifications()
    if not notifications:
        print("❌ ERROR: No notifications found. Skipping job.")
        return

    selected_notif = random.choice(notifications)

    print("--- 🎯 Selected Notification Payload ---")
    print(json.dumps(selected_notif, indent=2))
    print("--------------------------------------")

    # Step 3: Send to all devices
    send_multicast_notification(selected_notif, tokens)


app = Flask(__name__)

@app.route('/')
def home():
    return "FCM Notification Service is running! (Multi-device mode)"

@app.route('/health')
def health_check():
    return {"status": "healthy", "timestamp": time.time()}

@app.route('/devices')
def list_devices():
    """Diagnostic endpoint — lists all registered device tokens."""
    tokens = get_all_device_tokens()
    return {"device_count": len(tokens), "tokens": [t[-15:] + "..." for t in tokens]}


def ping_health():
    url = os.environ.get("RENDER_EXTERNAL_URL", "https://fcmdemo.onrender.com")
    health_url = f"{url}/health"
    try:
        response = requests.get(health_url, timeout=10)
        print(f"[HEALTH-CHECK] Pinged {health_url} - Status Code: {response.status_code}")
    except Exception as e:
        print(f"[HEALTH-CHECK] Failed to ping {health_url}: {e}")


def run_schedule():
    print("\n⏳ Scheduler started in background thread. Waiting for next run...")
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    print("--- Android Task Notification Server PoC (Multi-Device Mode) ---")
    initialize_firebase()

    # Run once immediately on startup
    job()

    # Schedule to run every 5 minutes
    schedule.every(5).minutes.do(job)

    # Schedule health check every 5 minutes to keep Render awake
    schedule.every(5).minutes.do(ping_health)

    # Start the scheduling loop in a separate background daemon thread
    scheduler_thread = threading.Thread(target=run_schedule, daemon=True)
    scheduler_thread.start()

    # Start the Flask web server to satisfy Render's port binding requirement
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
