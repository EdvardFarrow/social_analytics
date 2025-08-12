from django.utils import timezone
from datetime import timedelta
from decouple import config
import requests
from .models import GoogleCredentials

def refresh_google_access_token(credentials: GoogleCredentials) -> str:
    if timezone.now() < credentials.token_expiry - timedelta(minutes=5):
        return credentials.access_token

    token_url = "https://oauth2.googleapis.com/token"
    data = {
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'refresh_token': credentials.refresh_token,
        'grant_type': 'refresh_token',
    }

    resp = requests.post(token_url, data=data)
    if resp.status_code != 200:
        raise Exception(f"Failed to refresh token: {resp.text}")

    token_data = resp.json()
    new_access_token = token_data['access_token']
    expires_in = token_data.get('expires_in', 3600)

    credentials.access_token = new_access_token
    credentials.token_expiry = timezone.now() + timedelta(seconds=expires_in)
    credentials.save()

    return new_access_token


def get_valid_access_token_for_user(user):
    creds = getattr(user, 'google_credentials', None)
    if not creds:
        raise Exception("Google credentials not found for user")

    return refresh_google_access_token(creds)
