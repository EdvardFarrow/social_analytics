import requests
from .models import YouTubeChannel, YouTubeChannelStats, YouTubeToken
from django.utils import timezone
from datetime import timedelta
from decouple import config

def fetch_youtube_channel_stats(access_token, channel_id):
    url = 'https://www.googleapis.com/youtube/v3/channels'
    headers = {'Authorization': f'Bearer {access_token}'}
    params = {
        'part': 'snippet,statistics',
        'id': channel_id,
    }
    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch data: {response.text}")
    data = response.json()
    items = data.get('items', [])
    if not items:
        raise Exception("Channel not found")
    item = items[0]
    stats = item['statistics']
    snippet = item['snippet']
    return {
        'channel_id': channel_id,
        'title': snippet['title'],
        'subscriber_count': int(stats.get('subscriberCount', 0)),
        'view_count': int(stats.get('viewCount', 0)),
        'video_count': int(stats.get('videoCount', 0)),
    }
    
    
def update_channel_stats(access_token, channel_id):
    stats = fetch_youtube_channel_stats(access_token, channel_id)
    obj, created = YouTubeChannelStats.objects.update_or_create(
        channel_id=channel_id,
        defaults={
            'title': stats['title'],
            'subscriber_count': stats['subscriber_count'],
            'view_count': stats['view_count'],
            'video_count': stats['video_count'],
        }
    )
    return obj    


def fetch_own_channel_id(access_token):
    url = 'https://www.googleapis.com/youtube/v3/channels'
    headers = {'Authorization': f'Bearer {access_token}'}
    params = {
        'part': 'id',
        'mine': 'true'
    }
    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch channel ID: {response.text}")
    data = response.json()
    return data['items'][0]['id']


def refresh_access_token(user_token):
    if timezone.now() < user_token.token_expiry:
        return user_token.access_token

    data = {
        'client_id': config('GOOGLE_CLIENT_ID'),
        'client_secret': config('GOOGLE_CLIENT_SECRET'),
        'refresh_token': user_token.refresh_token,
        'grant_type': 'refresh_token',
    }

    response = requests.post('https://oauth2.googleapis.com/token', data=data)
    if response.status_code != 200:
        raise Exception("Failed to refresh access token")

    token_data = response.json()
    user_token.access_token = token_data['access_token']
    user_token.token_expiry = timezone.now() + timedelta(seconds=token_data.get('expires_in', 3600))
    user_token.save()
    return user_token.access_token
