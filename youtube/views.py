import requests
import logging
from datetime import date, timedelta
from django.conf import settings
from django.shortcuts import redirect, render
from django.utils import timezone
from django.http import JsonResponse
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import ObjectDoesNotExist
from django.utils.dateparse import parse_date
from django.views import View
from django.views.decorators.http import require_GET
from rest_framework.decorators import api_view

from google.oauth2.credentials import Credentials
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from googleapiclient.discovery import build

from accounts.models import CustomUser, GoogleCredentials
from .models import YouTubeChannel, YoutubeDailyStats, YouTubeVideo
from .services import fetch_and_save_analytics_data

logger = logging.getLogger(__name__)


# Views для фронтенда
class YouTubeDashboardView(View):
    def get(self, request):
        return render(request, 'youtube/dashboard.html')


class YouTubeLoginView(View):
    def get(self, request):
        return render(request, 'youtube/login.html')


@require_GET
def youtube_login(request):
    base_url = "https://accounts.google.com/o/oauth2/v2/auth"
    params = {
        "client_id": settings.YOUTUBE_CLIENT_ID,
        "redirect_uri": settings.YOUTUBE_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(settings.YOUTUBE_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
    }
    query_string = "&".join([f"{key}={value}" for key, value in params.items()])
    return redirect(f"{base_url}?{query_string}")


@require_GET
def youtube_callback(request):
    code = request.GET.get('code')
    if not code:
        return JsonResponse({'error': 'No code provided'}, status=400)

    token_url = 'https://oauth2.googleapis.com/token'
    token_data = {
        'code': code,
        'client_id': settings.YOUTUBE_CLIENT_ID,
        'client_secret': settings.YOUTUBE_CLIENT_SECRET,
        'redirect_uri': settings.YOUTUBE_REDIRECT_URI,
        'grant_type': 'authorization_code',
    }

    token_resp = requests.post(token_url, data=token_data)
    token_json = token_resp.json()

    if "access_token" not in token_json:
        return JsonResponse({'error': 'Failed to get token', 'details': token_json}, status=400)

    access_token = token_json.get('access_token')
    refresh_token = token_json.get('refresh_token')
    id_token_str = token_json.get('id_token')
    expires_in = token_json.get('expires_in', 3600)

    try:
        id_info = id_token.verify_oauth2_token(id_token_str, google_requests.Request(), settings.YOUTUBE_CLIENT_ID)
        email = id_info.get('email')
        name = id_info.get('name', '')
    except ValueError as e:
        return JsonResponse({'error': f'Invalid id_token: {e}'}, status=400)

    if not email:
        return JsonResponse({'error': 'Email not found in token'}, status=400)

    user, created = CustomUser.objects.get_or_create(email=email, defaults={'full_name': name})
    
    login(request, user)

    try:
        google_creds_obj = GoogleCredentials.objects.get(user=user)
        google_creds_obj.access_token = access_token
        google_creds_obj.token_expiry = timezone.now() + timedelta(seconds=expires_in)
        google_creds_obj.scopes = settings.YOUTUBE_SCOPES
        if refresh_token:
            google_creds_obj.refresh_token = refresh_token
        google_creds_obj.save()
    except ObjectDoesNotExist:
        if not refresh_token:
            return JsonResponse({"error": "No refresh token for a new credentials record. Please try again."}, status=400)
        
        GoogleCredentials.objects.create(
            user=user,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expiry=timezone.now() + timedelta(seconds=expires_in),
            scopes=settings.YOUTUBE_SCOPES,
        )

    try:
        creds = Credentials(token=access_token)
        youtube_service = build("youtube", "v3", credentials=creds)
        channels_response = youtube_service.channels().list(mine=True, part="id,snippet").execute()
        
        if not channels_response.get('items'):
            return JsonResponse({"error": "Failed to get channel information."}, status=400)
        
        channel_info = channels_response['items'][0]
        channel_id = channel_info.get('id')
        title = channel_info['snippet']['title']
        
        YouTubeChannel.objects.update_or_create(
            user=user,
            channel_id=channel_id,
            defaults={'title': title}
        )
        
    except Exception as e:
        return JsonResponse({"error": f"Error fetching channel ID: {e}"}, status=500)
    
    # 7. Запускаем загрузку данных и перенаправляем на дашборд
    try:
        fetch_and_save_analytics_data(user, channel_id)
    except Exception as e:
        logger.error(f"Failed to fetch initial analytics data: {e}")

    return redirect('youtube-dashboard')


# API Views для получения данных
@api_view(['GET'])
@login_required
@require_GET
def channel_trends(request):
    user = request.user
    user_channels = YouTubeChannel.objects.filter(user=user)
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
@require_GET
def video_trends(request):
    user = request.user

    date_from_str = request.GET.get('date_from')
    date_from = parse_date(date_from_str) if date_from_str else (date.today() - timedelta(days=30))
    date_to = parse_date(request.GET.get('date_to')) if request.GET.get('date_to') else date.today()
    
    sort_by = request.GET.get('sort_by', '-views')

    videos = YouTubeVideo.objects.filter(
        channel__user=user,
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