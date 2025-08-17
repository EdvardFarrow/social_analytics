import requests
import logging
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

from google.oauth2.credentials import Credentials
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from googleapiclient.discovery import build

from accounts.models import CustomUser, GoogleCredentials
from .models import YouTubeChannel, YoutubeDailyStats, YouTubeVideo
from .services import fetch_and_save_analytics_data

logger = logging.getLogger(__name__)

User = get_user_model()

# Views для фронтенда
class YouTubeDashboardView(View):
    def get(self, request):
        return render(request, 'youtube/dashboard.html')


class YouTubeLoginView(View):
    def get(self, request):
        return render(request, 'youtube/login.html')

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
    creds_obj.save()

    return redirect('youtube-dashboard')


# Views для фронтенда
@login_required
def youtube_dashboard(request):
    """
    Renders the YouTube dashboard page and passes the user's access token
    to the frontend for making API calls.
    """    
    access_token = None
    if request.user.is_authenticated:
        try:
            creds_obj = GoogleCredentials.objects.get(user=request.user)
            access_token = creds_obj.access_token
        except GoogleCredentials.DoesNotExist:
            pass # No credentials found, access token will remain None.
    
    context = {
        'youtube_access_token': access_token,
    }
    
    return render(request, 'youtube/dashboard.html', context)


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