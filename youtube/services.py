import logging
from datetime import date, timedelta
from django.conf import settings
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
import requests
from django.core.exceptions import ObjectDoesNotExist
from google.auth.transport import requests as google_requests

from .models import YouTubeChannel, YoutubeDailyStats, YouTubeVideo, YoutubeAudienceDemographics

logger = logging.getLogger(__name__)

def get_youtube_service(creds_obj):
    creds_info = {
        'token': creds_obj.access_token,
        'refresh_token': creds_obj.refresh_token,
        'token_uri': creds_obj.token_uri,
        'client_id': creds_obj.client_id,
        'client_secret': creds_obj.client_secret,
        'scopes': creds_obj.scopes.split(' '),
        'universe_domain': 'googleapis.com'
    }
    creds = Credentials.from_authorized_user_info(info=creds_info)
    
    if not creds.valid:
        creds.refresh(google_requests.Request())

    return build('youtube', 'v3', credentials=creds)


def get_youtube_analytics_service(creds_obj):
    creds_info = {
        'token': creds_obj.access_token,
        'refresh_token': creds_obj.refresh_token,
        'token_uri': creds_obj.token_uri,
        'client_id': creds_obj.client_id,
        'client_secret': creds_obj.client_secret,
        'scopes': creds_obj.scopes.split(' '),
        'universe_domain': 'googleapis.com'
    }
    creds = Credentials.from_authorized_user_info(info=creds_info)
    
    if not creds.valid:
        creds.refresh(google_requests.Request())

    return build('youtubeAnalytics', 'v2', credentials=creds)


def fetch_own_channel_id(creds_obj):
    try:
        youtube = get_youtube_service(creds_obj)
        response = youtube.channels().list(
            part='id',
            mine=True
        ).execute()
        
        if 'items' in response and len(response['items']) > 0:
            return response['items'][0]['id']
        else:
            logger.error("No channels found for the authenticated user.")
            return None
    except HttpError as e:
        logger.error(f"HTTP Error fetching own channel ID: {e}")
        return None
    except Exception as e:
        logger.error(f"Error fetching own channel ID: {e}")
        return None


def fetch_and_save_analytics_data(creds_obj, channel_id):
    try:
        youtube_analytics = get_youtube_analytics_service(creds_obj)

        start_date = (date.today() - timedelta(days=30)).isoformat()
        end_date = date.today().isoformat()

        response = youtube_analytics.reports().query(
            startDate=start_date,
            endDate=end_date,
            metrics='views,subscribersGained,subscribersLost',
            dimensions='day',
            ids=f'channel=={channel_id}'
        ).execute()

        channel = YouTubeChannel.objects.get(channel_id=channel_id)
        
        if 'rows' in response:
            for row in response['rows']:
                report_date, views, subs_gained, subs_lost = row
                YoutubeDailyStats.objects.update_or_create(
                    channel=channel,
                    date=report_date,
                    defaults={
                        'views': views,
                        'subscribers_gained': subs_gained,
                        'subscribers_lost': subs_lost
                    }
                )

        demographics_response = youtube_analytics.reports().query(
            startDate=start_date,
            endDate=end_date,
            metrics='viewerPercentage',
            dimensions='ageGroup,gender',
            ids=f'channel=={channel_id}'
        ).execute()
        
        YoutubeAudienceDemographics.objects.filter(channel=channel).delete()
        if 'rows' in demographics_response:
            for row in demographics_response['rows']:
                age_group, gender, viewer_percentage = row
                YoutubeAudienceDemographics.objects.create(
                    channel=channel,
                    age_group=age_group,
                    gender=gender,
                    viewer_percentage=viewer_percentage
                )

    except HttpError as e:
        logger.error(f"HTTP Error during analytics fetch: {e}")
    except Exception as e:
        logger.error(f"Error fetching and saving analytics data: {e}")

def update_all_videos(creds_obj):
    try:
        youtube = get_youtube_service(creds_obj)
        channel_id = fetch_own_channel_id(creds_obj)
        if not channel_id:
            return

        channel = YouTubeChannel.objects.get(channel_id=channel_id)
        
        request = youtube.search().list(
            part='snippet',
            channelId=channel_id,
            maxResults=20,
            order='date',
            type='video'
        )

        response = request.execute()
        
        for item in response['items']:
            video_id = item['id']['videoId']
            title = item['snippet']['title']
            published_at = item['snippet']['publishedAt']

            stats_response = youtube.videos().list(
                part='statistics',
                id=video_id
            ).execute()
            
            if 'items' in stats_response and len(stats_response['items']) > 0:
                stats = stats_response['items'][0]['statistics']
                views = stats.get('viewCount', 0)
                likes = stats.get('likeCount', 0)
                comments = stats.get('commentCount', 0)

                YouTubeVideo.objects.update_or_create(
                    video_id=video_id,
                    defaults={
                        'channel': channel,
                        'title': title,
                        'published_at': published_at,
                        'views': views,
                        'likes': likes,
                        'comments': comments
                    }
                )

    except HttpError as e:
        logger.error(f"HTTP Error during video update: {e}")
    except Exception as e:
        logger.error(f"Error updating videos: {e}")
        
        
def fetch_viewer_activity(creds_obj, channel_id, start_date_str, end_date_str):
    try:
        analytics = get_youtube_analytics_service(creds_obj)

        device_request = analytics.reports().query(
            ids=f'channel=={channel_id}',
            startDate=start_date_str,
            endDate=end_date_str,
            metrics='views',
            dimensions='deviceType',
        )
        device_response = device_request.execute()

        subscribed_request = analytics.reports().query(
            ids=f'channel=={channel_id}',
            startDate=start_date_str,
            endDate=end_date_str,
            metrics='views',
            dimensions='subscribedStatus',
        )
        subscribed_response = subscribed_request.execute()

        return {
            'device_type': device_response.get('rows', []),
            'subscribed_status': subscribed_response.get('rows', [])
        }

    except Exception as e:
        print(f"HTTP Error during viewer activity fetch: {e}")
        return {
            'device_type': [],
            'subscribed_status': []
        }
