from firebase_admin import messaging

def send_fcm_notification(device_token, title, body, data=None):
    message = messaging.Message(
        notification=messaging.Notification(
            title=title,
            body=body,
        ),
        token=device_token,
        data=data or {},
    )

    response = messaging.send(message)
    print("Notification FCM envoyée :", response)
