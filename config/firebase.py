import json
import firebase_admin
from firebase_admin import credentials
from django.conf import settings

def init_firebase():
    if firebase_admin._apps:
        return

    if not settings.FIREBASE_CREDENTIALS:
        return

    try:
      cred_dict = json.loads(settings.FIREBASE_CREDENTIALS)
      cred = credentials.Certificate(cred_dict)
      firebase_admin.initialize_app(cred)

    except Exception as e:
      print(f"Firebase init error: {e}")


