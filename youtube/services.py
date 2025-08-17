import requests
from django.utils import timezone
from datetime import timedelta, date, datetime
from decouple import config
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import logging

from .models import (
    YouTubeChannel,
    YouTubeVideo,
    YoutubeDailyStats,
    YoutubeAudienceDemographics,
    YouTubeVideoDailyStats, 
)
from accounts.models import GoogleCredentials 

logger = logging.getLogger(__name__)



def refresh_access_token(google_credentials_obj):
    """
    Обновляет токен доступа Google, используя refresh_token,
    и сохраняет обновленный токен и срок его действия в модели GoogleCredentials.
    """
    if google_credentials_obj.token_expiry and timezone.now() < google_credentials_obj.token_expiry:
        return google_credentials_obj.access_token

    data = {
        'client_id': config('YOUTUBE_CLIENT_ID'),
        'client_secret': config('YOUTUBE_CLIENT_SECRET'),
        'refresh_token': google_credentials_obj.refresh_token,
        'grant_type': 'refresh_token',
    }

    try:
        response = requests.post('https://oauth2.googleapis.com/token', data=data)
        response.raise_for_status() 
        token_data = response.json()

        google_credentials_obj.access_token = token_data['access_token']
        if 'refresh_token' in token_data:
            google_credentials_obj.refresh_token = token_data['refresh_token']
        google_credentials_obj.token_expiry = timezone.now() + timedelta(seconds=token_data.get('expires_in', 3600))
        google_credentials_obj.save()
        return google_credentials_obj.access_token
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to refresh access token: {e}")
        raise Exception(f"Не удалось обновить токен доступа: {e}")


def fetch_own_channel_id(access_token):
    """
    Получает ID канала авторизованного пользователя с помощью YouTube Data API v3.
    """
    try:
        creds = Credentials(token=access_token)
        youtube = build("youtube", "v3", credentials=creds)
        
        response = youtube.channels().list(mine=True, part="id").execute()
        
        items = response.get('items', [])
        if not items:
            raise Exception("Channel ID not found for the authenticated user.")
        
        return items[0]['id']
    except Exception as e:
        logger.error(f"Error fetching own channel ID: {e}")
        raise Exception(f"Не удалось получить ID канала: {e}")

def fetch_and_save_analytics_data(user, channel_id):
    """
    Получает и сохраняет ежедневные данные аналитики и демографию
    для YouTube-канала с использованием YouTube Analytics API.
    """
    try:
        google_credentials_obj = user.google_credentials
        access_token = refresh_access_token(google_credentials_obj)

        creds = Credentials(token=access_token)
        youtube_analytics = build("youtubeAnalytics", "v2", credentials=creds)

        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)
        
        channel, created = YouTubeChannel.objects.get_or_create(channel_id=channel_id, defaults={'user': user, 'title': 'Unknown Channel'})
        if created:
            logger.info(f"Created new YouTubeChannel entry for ID: {channel_id}")


        daily_stats_response = youtube_analytics.reports().query(
            ids=f"channel=={channel_id}",
            startDate=start_date.isoformat(),
            endDate=end_date.isoformat(),
            metrics="subscribersGained,subscribersLost,views,estimatedMinutesWatched,likes,comments",
            dimensions="day",
        ).execute()
        
        for row in daily_stats_response.get('rows', []):
            stats_date = datetime.strptime(row[0], '%Y-%m-%d').date()
            
            YoutubeDailyStats.objects.update_or_create(
                channel=channel,
                date=stats_date,
                defaults={
                    'subscribers_gained': row[1],
                    'subscribers_lost': row[2],
                    'views': row[3],
                    'estimated_minutes_watched': row[4],
                    'likes': row[5],
                    'comments': row[6]
                }
            )
        logger.info(f"Successfully fetched and saved daily stats for channel {channel_id}.")

        # --- Запрос данных по демографии (Age Group, Gender, Viewer Percentage) ---
        demographics_response = youtube_analytics.reports().query(
            ids=f"channel=={channel_id}",
            startDate=start_date.isoformat(),
            endDate=end_date.isoformat(),
            metrics="viewerPercentage",
            dimensions="ageGroup,gender",
        ).execute()

        YoutubeAudienceDemographics.objects.filter(channel=channel).delete()

        for row in demographics_response.get('rows', []):
            age_group = row[0]
            gender = row[1]
            viewer_percentage = row[2]
            
            YoutubeAudienceDemographics.objects.create( 
                channel=channel,
                age_group=age_group,
                gender=gender,
                viewer_percentage=viewer_percentage
            )
        logger.info(f"Successfully fetched and saved audience demographics for channel {channel_id}.")
        
        return {"message": "Analytics data fetched and saved successfully."}
        
    except GoogleCredentials.DoesNotExist:
        logger.error(f"GoogleCredentials not found for user {user.email}")
        raise Exception("Google credentials not found. Please authenticate with Google first.")
    except Exception as e:
        logger.error(f"Error fetching YouTube Analytics data for user {user.email}, channel {channel_id}: {e}", exc_info=True)
        raise Exception(f"Ошибка при получении или сохранении данных аналитики: {e}")

def update_all_videos(google_credentials_obj):
    """
    Обновляет текущую статистику (просмотры, лайки, комментарии) для всех видео канала
    и сохраняет ежедневный снимок этой статистики в YouTubeVideoDailyStats.
    """
    access_token = refresh_access_token(google_credentials_obj)
    
    try:
        channel = YouTubeChannel.objects.get(user=google_credentials_obj.user)
    except YouTubeChannel.DoesNotExist:
        raise Exception("Канал для этого пользователя не найден. Сначала нужно привязать канал.")

    video_ids = []
    next_page_token = None
    
    youtube = build("youtube", "v3", credentials=Credentials(token=access_token))

    while True:
        playlist_items_response = youtube.playlistItems().list(
            playlistId=channel.channel_id.replace('UC', 'UU'), 
            part='snippet',
            maxResults=50,
            pageToken=next_page_token
        ).execute()

        for item in playlist_items_response.get('items', []):
            video_ids.append(item['snippet']['resourceId']['videoId'])

        next_page_token = playlist_items_response.get('nextPageToken')
        if not next_page_token:
            break

    total_updated = 0
    for i in range(0, len(video_ids), 50):
        batch_ids = video_ids[i:i + 50]
        
        videos_response = youtube.videos().list(
            part='snippet,statistics',
            id=','.join(batch_ids)
        ).execute()

        for item in videos_response.get('items', []):
            vid_id = item['id']
            snippet = item['snippet']
            stats = item.get('statistics', {})

            video_obj, created = YouTubeVideo.objects.update_or_create(
                video_id=vid_id,
                defaults={
                    'channel': channel,
                    'title': snippet.get('title', ''),
                    'published_at': snippet.get('publishedAt'),
                    'views': int(stats.get('viewCount', 0)),
                    'likes': int(stats.get('likeCount', 0)),
                    'comments': int(stats.get('commentCount', 0)),
                }
            )
            
            YouTubeVideoDailyStats.objects.update_or_create(
                video=video_obj,
                date=timezone.now().date(),
                defaults={
                    'views': int(stats.get('viewCount', 0)),
                    'likes': int(stats.get('likeCount', 0)),
                    'comments': int(stats.get('commentCount', 0)),
                }
            )
            total_updated += 1
            
    return {"message": f"Статистика обновлена для {total_updated} видео."}