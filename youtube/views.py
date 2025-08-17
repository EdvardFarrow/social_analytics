import requests
import logging
import json
from datetime import date, timedelta
from django.conf import settings
from django.shortcuts import redirect, render
from django.utils import timezone
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model, login
from django.db.models import ObjectDoesNotExist
from django.utils.dateparse import parse_date
from django.views import View
from django.views.decorators.http import require_GET
from django.urls import reverse
from django.utils.decorators import method_decorator
from rest_framework.decorators import api_view
from rest_framework.response import Response

from google.oauth2.credentials import Credentials
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from googleapiclient.discovery import build

from accounts.models import CustomUser, GoogleCredentials
from .models import YouTubeChannel, YoutubeDailyStats, YouTubeVideo, YoutubeAudienceDemographics
from .services import fetch_and_save_analytics_data, fetch_own_channel_id, update_all_videos, fetch_viewer_activity

logger = logging.getLogger(__name__)

User = get_user_model()


@login_required
@require_GET
def youtube_auth(request):
    base_url = "https://accounts.google.com/o/oauth2/v2/auth"
    full_redirect_uri = request.build_absolute_uri(reverse('youtube_callback'))
    params = {
        "client_id": settings.YOUTUBE_CLIENT_ID,
        "redirect_uri": full_redirect_uri,
        "response_type": "code",
        "scope": " ".join(settings.YOUTUBE_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
    }
    query_string = "&".join([f"{key}={value}" for key, value in params.items()])
    return redirect(f"{base_url}?{query_string}")


def youtube_callback(request):
    code = request.GET.get('code')

    if not code:
        return redirect('/')

    full_redirect_uri = request.build_absolute_uri(reverse('youtube_callback'))
    token_data = {
        'code': code,
        'client_id': settings.YOUTUBE_CLIENT_ID,
        'client_secret': settings.YOUTUBE_CLIENT_SECRET,
        'redirect_uri': full_redirect_uri,
        'grant_type': 'authorization_code',
    }

    try:
        token_resp = requests.post('https://oauth2.googleapis.com/token', data=token_data)
        token_resp.raise_for_status()
        token_json = token_resp.json()
    except requests.exceptions.HTTPError as e:
        return redirect('google_login')

    access_token = token_json.get('access_token')
    refresh_token = token_json.get('refresh_token')
    expires_in = token_json.get('expires_in', 3600)
    scopes = token_json.get('scope')

    try:
        userinfo_resp = requests.get(
            'https://www.googleapis.com/oauth2/v3/userinfo',
            headers={'Authorization': f'Bearer {access_token}'}
        )
        userinfo_resp.raise_for_status()
        user_data = userinfo_resp.json()
        email = user_data.get('email')
    except requests.exceptions.HTTPError as e:
        return redirect('google_login')

    if not email:
        return redirect('google_login')

    try:
        user = CustomUser.objects.get(email=email)
    except CustomUser.DoesNotExist:
        return redirect('google_login')

    login(request, user)

    creds_obj, created = GoogleCredentials.objects.get_or_create(user=user)
    creds_obj.access_token = access_token
    if refresh_token:
        creds_obj.refresh_token = refresh_token
    creds_obj.token_expiry = timezone.now() + timedelta(seconds=expires_in)
    creds_obj.scopes = scopes
    creds_obj.client_id = settings.YOUTUBE_CLIENT_ID
    creds_obj.client_secret = settings.YOUTUBE_CLIENT_SECRET
    creds_obj.token_uri = 'https://oauth2.googleapis.com/token'
    creds_obj.save()

    return redirect('youtube-dashboard')


@login_required
def youtube_dashboard(request):
    try:
        creds_obj = GoogleCredentials.objects.get(user=request.user)

        channel_id = fetch_own_channel_id(creds_obj)
        if not channel_id:
            return render(request, 'youtube/error_page.html', {'error_message': 'No channels found for this user.'})

        channel_obj, created = YouTubeChannel.objects.get_or_create(
            channel_id=channel_id,
            defaults={'user': request.user, 'title': 'My YouTube Channel'}
        )

        last_update = channel_obj.last_updated if channel_obj else None

        if not last_update or (timezone.now() - last_update) > timedelta(hours=24):
            print("Updating YouTube analytics data...")
            try:
                fetch_and_save_analytics_data(creds_obj, channel_id)
                update_all_videos(creds_obj)
                channel_obj.last_updated = timezone.now()
                channel_obj.save()
            except Exception as e:
                print(f"Error during data update: {e}")

        start_date_str = request.GET.get('start_date')
        end_date_str = request.GET.get('end_date')
        if not start_date_str or not end_date_str:
            end_date = date.today()
            start_date = end_date - timedelta(days=30)
            start_date_str = start_date.isoformat()
            end_date_str = end_date.isoformat()

        viewer_activity_data = fetch_viewer_activity(
            creds_obj, 
            channel_id, 
            start_date_str, 
            end_date_str
        )

        context = {
            'youtube_access_token': creds_obj.access_token,
            'channel_title': channel_obj.title,
            'channel_id': channel_id,
            'viewer_activity_data': json.dumps(viewer_activity_data),
            'start_date': start_date_str,
            'end_date': end_date_str,
            'viewer_activity_data': json.dumps(viewer_activity_data),
        }
        return render(request, 'youtube/dashboard.html', context)

    except GoogleCredentials.DoesNotExist:
        return redirect('youtube_auth')
    except Exception as e:
        return render(request, 'youtube/error_page.html', {'error_message': str(e)})

# API views
@api_view(['GET'])
@login_required
def channel_trends(request):
    try:
        creds_obj = GoogleCredentials.objects.get(user=request.user)

        if creds_obj.token_expiry <= timezone.now() + timedelta(minutes=5):
            if not creds_obj.refresh_token:
                return JsonResponse({'error': 'Token expired. Please re-authenticate.'}, status=401)

            token_data = {
                'grant_type': 'refresh_token',
                'client_id': settings.YOUTUBE_CLIENT_ID,
                'client_secret': settings.YOUTUBE_CLIENT_SECRET,
                'refresh_token': creds_obj.refresh_token,
            }
            token_resp = requests.post('https://oauth2.googleapis.com/token', data=token_data)
            token_resp.raise_for_status()
            token_json = token_resp.json()

            creds_obj.access_token = token_json['access_token']
            creds_obj.token_expiry = timezone.now() + timedelta(seconds=token_json['expires_in'])
            creds_obj.save()

    except ObjectDoesNotExist:
        return JsonResponse({'error': 'No credentials found for this user'}, status=401)
    except requests.exceptions.HTTPError:
        return JsonResponse({'error': 'Token refresh failed'}, status=401)

    user_channels = YouTubeChannel.objects.filter(user=request.user)
    channel_id = request.GET.get('channel_id') or (user_channels.first().channel_id if user_channels else None)

    if not channel_id:
        return JsonResponse({'error': 'No channels found for this user'}, status=404)

    date_from_str = request.GET.get('date_from')
    date_from = parse_date(date_from_str) if date_from_str else (date.today() - timedelta(days=30))
    date_to = parse_date(request.GET.get('date_to')) if request.GET.get('date_to') else date.today()

    stats_qs = YoutubeDailyStats.objects.filter(
        channel__channel_id=channel_id,
        date__range=[date_from, date_to]
    ).order_by('date')

    dates = [stat.date.isoformat() for stat in stats_qs]
    views = [stat.views for stat in stats_qs]
    subscribers_gained = [stat.subscribers_gained for stat in stats_qs]
    subscribers_lost = [stat.subscribers_lost for stat in stats_qs]

    return JsonResponse({
        'dates': dates,
        'views': views,
        'subscribers_gained': subscribers_gained,
        'subscribers_lost': subscribers_lost
    })


@api_view(['GET'])
@login_required
def video_trends(request):
    try:
        creds_obj = GoogleCredentials.objects.get(user=request.user)

        if creds_obj.token_expiry <= timezone.now() + timedelta(minutes=5):
            if not creds_obj.refresh_token:
                return JsonResponse({'error': 'Token expired. Please re-authenticate.'}, status=401)

            token_data = {
                'grant_type': 'refresh_token',
                'client_id': settings.YOUTUBE_CLIENT_ID,
                'client_secret': settings.YOUTUBE_CLIENT_SECRET,
                'refresh_token': creds_obj.refresh_token,
            }
            token_resp = requests.post('https://oauth2.googleapis.com/token', data=token_data)
            token_resp.raise_for_status()
            token_json = token_resp.json()

            creds_obj.access_token = token_json['access_token']
            creds_obj.token_expiry = timezone.now() + timedelta(seconds=token_json['expires_in'])
            creds_obj.save()

    except ObjectDoesNotExist:
        return JsonResponse({'error': 'No credentials found for this user'}, status=401)
    except requests.exceptions.HTTPError:
        return JsonResponse({'error': 'Token refresh failed'}, status=401)

    date_from_str = request.GET.get('date_from')
    date_from = parse_date(date_from_str) if date_from_str else (date.today() - timedelta(days=30))
    date_to = parse_date(request.GET.get('date_to')) if request.GET.get('date_to') else date.today()

    sort_by = request.GET.get('sort_by', '-views')

    videos = YouTubeVideo.objects.filter(
        channel__user=request.user,
        published_at__date__range=[date_from, date_to]
    ).order_by(sort_by)

    videos_data = [
        {
            'title': v.title,
            'published_at': v.published_at.date().isoformat(),
            'views': v.views,
            'likes': v.likes,
            'comments': v.comments,
        }
        for v in videos
    ]

    return JsonResponse({'videos': videos_data})


@api_view(['GET'])
def audience_demographics(request):
    channel_id = request.query_params.get('channel_id')

    if not channel_id:
        return Response({'error': 'Channel ID is required'}, status=400)

    try:
        channel = YouTubeChannel.objects.get(channel_id=channel_id)

        demographics_data = YoutubeAudienceDemographics.objects.filter(channel=channel)

        if not demographics_data.exists():
            return JsonResponse({'demographics': {'age_groups': {}, 'genders': {}}})

        age_groups_dict = {}
        genders_dict = {}

        for item in demographics_data:
            if item.age_group:
                age_groups_dict[item.age_group] = item.viewer_percentage
            if item.gender:
                genders_dict[item.gender] = item.viewer_percentage

        response_data = {
            'demographics': {
                'age_groups': age_groups_dict,
                'genders': genders_dict,
            }
        }

        return JsonResponse(response_data)

    except YouTubeChannel.DoesNotExist:
        return Response({'error': 'Channel not found'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=500)
    
    
@api_view(['GET'])
@login_required
def viewer_activity(request):
    try:
        creds_obj = GoogleCredentials.objects.get(user=request.user)
    except ObjectDoesNotExist:
        return JsonResponse({'error': 'No credentials found for this user'}, status=401)
    
    date_from_str = request.GET.get('date_from')
    date_to_str = request.GET.get('date_to')

    if not date_from_str or not date_to_str:
        return JsonResponse({'error': 'start_date and end_date are required'}, status=400)

    user_channels = YouTubeChannel.objects.filter(user=request.user)
    channel_id = request.GET.get('channel_id') or (user_channels.first().channel_id if user_channels else None)

    if not channel_id:
        return JsonResponse({'error': 'No channels found for this user'}, status=404)

    activity_data = fetch_viewer_activity(
        creds_obj, 
        channel_id, 
        date_from_str, 
        date_to_str
    )

    return JsonResponse(activity_data)    