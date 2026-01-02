# apps/orders/utils_ws.py
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

channel_layer = get_channel_layer()

def send_order_event_to_user(user_id, event, data):
    group = f"user_{user_id}"
    async_to_sync(channel_layer.group_send)(
        group,
        {
            "type": "order.event",
            "event": event,
            "data": data,
        }
    )

def send_order_event_to_pharmacy(pharmacy_id, event, data):
    group = f"pharmacy_{pharmacy_id}"
    async_to_sync(channel_layer.group_send)(
        group,
        {
            "type": "order.event",
            "event": event,
            "data": data,
        }
    )
