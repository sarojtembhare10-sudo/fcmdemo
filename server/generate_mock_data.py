import json
import random

titles = ["Task Reminder", "Overdue Task", "New Assignment", "Project Update", "Meeting Alert"]
actions = ["Review Code", "Update Documentation", "Client Call", "Weekly Standup", "Fix Bug", "Write Tests", "Deploy to Prod", "Design Review", "Sprint Planning", "1-on-1 Sync"]

notifications = []
for i in range(1, 101):
    action = random.choice(actions)
    title = random.choice(titles)
    
    if title == "Task Reminder":
        body = f"Reminder: '{action}' is due soon. Please check your dashboard."
    elif title == "Overdue Task":
        body = f"URGENT: The task '{action}' is past its deadline! Please update the status immediately."
    elif title == "New Assignment":
        body = f"You have been assigned to a new task: '{action}'. Click to view details."
    elif title == "Project Update":
        body = f"There are new updates and comments on the '{action}' initiative."
    else:
        body = f"Upcoming event: {action} is starting in 15 minutes."

    notif = {
        "id": i,
        "title": f"{title} #{i}",
        "body": body,
        "data": {
            "task_id": f"TASK-{i + 1000}",
            "action": "open_task",
            "priority": random.choice(["high", "medium", "low"])
        }
    }
    notifications.append(notif)

with open('notifications_data.json', 'w') as f:
    json.dump(notifications, f, indent=4)

print("Generated 100 mock notifications in notifications_data.json")
