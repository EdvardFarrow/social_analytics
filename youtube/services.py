import requests
from .models import YouTubeChannel, YouTubeChannelStats, YouTubeToken, YouTubeVideo, ChannelDailyStat, VideoDailyStat
from django.utils import timezone
from datetime import timedelta, date
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
    
    
def save_channel_daily_snapshot(access_token, channel_id):
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
    if user_token.token_expiry and timezone.now() < user_token.token_expiry:
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





def update_channel_and_video_stats(user_token):

    access_token = refresh_access_token(user_token)

    channel_id = fetch_own_channel_id(access_token)

    channel_stats = fetch_youtube_channel_stats(access_token, channel_id)

    channel, created = YouTubeChannel.objects.update_or_create(
        channel_id=channel_id,
        defaults={
            'title': channel_stats['title'],
            'user': user_token.user,
        }
    )

    ChannelDailyStat.objects.update_or_create(
        channel_id=channel,
        date=timezone.now().date(),
        defaults={
            'subscribers': channel_stats['subscriber_count'],
            'views': channel_stats['view_count'],
            'video_count': channel_stats['video_count'],
        }
    )

    videos = []
    next_page_token = None
    while True:
        url = 'https://www.googleapis.com/youtube/v3/search'
        headers = {'Authorization': f'Bearer {access_token}'}
        params = {
            'part': 'snippet',
            'channelId': channel_id,
            'maxResults': 50,
            'order': 'date',
            'type': 'video',
        }
        if next_page_token:
            params['pageToken'] = next_page_token

        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            raise Exception(f"Failed to fetch videos: {response.text}")

        data = response.json()
        videos.extend(data.get('items', []))

        next_page_token = data.get('nextPageToken')
        if not next_page_token:
            break

    video_ids = [video['id']['videoId'] for video in videos]
    for i in range(0, len(video_ids), 50):
        batch_ids = video_ids[i:i+50]
        stats_url = 'https://www.googleapis.com/youtube/v3/videos'
        stats_params = {
            'part': 'snippet,statistics',
            'id': ','.join(batch_ids)
        }
        stats_resp = requests.get(stats_url, headers=headers, params=stats_params)
        if stats_resp.status_code != 200:
            raise Exception(f"Failed to fetch video stats: {stats_resp.text}")

        stats_data = stats_resp.json()
        for item in stats_data.get('items', []):
            vid = item['id']
            snippet = item['snippet']
            stats = item.get('statistics', {})

            video_obj, created = YouTubeVideo.objects.update_or_create(
                video_id=vid,
                defaults={
                    'channel': channel,
                    'title': snippet['title'],
                    'published_at': snippet['publishedAt'],
                    'views': int(stats.get('viewCount', 0)),
                    'likes': int(stats.get('likeCount', 0)),
                    'comments': int(stats.get('commentCount', 0)),
                }
            )

            VideoDailyStat.objects.update_or_create(
                video_id=video_obj,
                date=timezone.now().date(),
                defaults={
                    'channel_id': channel_id,
                    'title': snippet['title'],
                    'views': int(stats.get('viewCount', 0)),
                    'likes': int(stats.get('likeCount', 0)),
                    'comments': int(stats.get('commentCount', 0)),
                }
            )

def update_channel_stats(access_token, channel_id):
    return save_channel_daily_snapshot(access_token, channel_id)
