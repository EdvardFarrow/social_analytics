import requests
from django.utils import timezone
from django.conf import settings
from .models import TikTokToken
from datetime import timedelta

def refresh_access_token(token_obj: TikTokToken):
    url = "https://open-api.tiktokglobalshop.com/api/token/refresh/"
    payload = {
        "client_key": settings.TIKTOK_CLIENT_KEY,
        "client_secret": settings.TIKTOK_CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": token_obj.refresh_token
    }
    r = requests.post(url, data=payload)
    data = r.json()
    if "access_token" not in data:
        raise Exception(f"TikTok token refresh failed: {data}")

    token_obj.access_token = data["access_token"]
    token_obj.token_expiry = timezone.now() + timedelta(seconds=int(data["expires_in"]))
    token_obj.save()
    return token_obj.access_token


def fetch_user_videos(access_token):
    url = "https://open.tiktokapis.com/v2/video/list/"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"max_count": 10}
    r = requests.get(url, headers=headers, params=params)
    return r.json()
