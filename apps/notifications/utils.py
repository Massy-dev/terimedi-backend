from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

def send_ws_notification(user_id: str, message: str, extra=None):
    if extra is None:
        extra = {}

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"notifications_{user_id}",
        {
            "type": "send_notification",
            "content": {
                "message": message,
                "extra": extra
            }
        }
    )
