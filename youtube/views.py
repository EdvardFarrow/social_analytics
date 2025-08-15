import requests
import logging
from datetime import date, timedelta
from django.conf import settings
from django.shortcuts import redirect, render
from django.utils import timezone
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
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
    # Теперь этот код будет выполняться только для аутентифицированных пользователей
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




@require_GET
def youtube_callback(request):
    """
    Обрабатывает обратный вызов от Google и обменивает код авторизации на токены.
    """
    print("=" * 60)
    print("ШАГ 1: Начало youtube_callback")
    print("Полный GET-параметры запроса:", dict(request.GET))
    
    code = request.GET.get('code')
    if not code:
        print("ОШИБКА: Нет кода. Возможно, повторный запрос.")
        return JsonResponse({'error': 'No code provided'}, status=400)

    print("ШАГ 2: Пользователь авторизован:", request.user)
    print("Полученный code:", code)

    # redirect_uri нужно вычислять до использования
    full_redirect_uri = request.build_absolute_uri(reverse('youtube_callback'))
    print("redirect_uri, который шлём в Google:", full_redirect_uri)

    token_url = 'https://oauth2.googleapis.com/token'
    token_data = {
        'code': code,
        'client_id': settings.YOUTUBE_CLIENT_ID,
        'client_secret': settings.YOUTUBE_CLIENT_SECRET,
        'redirect_uri': full_redirect_uri,
        'grant_type': 'authorization_code',
    }
    print("ШАГ 3: Данные для обмена токенов:", token_data)

    try:
        token_resp = requests.post(token_url, data=token_data)
        print("HTTP-статус ответа Google:", token_resp.status_code)
        print("Заголовки ответа Google:", dict(token_resp.headers))
        print("Текст ответа Google:", token_resp.text)
        token_json = token_resp.json()
    except Exception as e:
        print(f"ОШИБКА: Не удалось получить токены. Детали: {e}")
        return JsonResponse({'error': 'Failed to get token', 'details': str(e)}, status=400)

    if "access_token" not in token_json:
        print("ОШИБКА: В ответе нет access_token. Полный ответ:", token_json)
        return JsonResponse({'error': 'Failed to get token', 'details': token_json}, status=400)

    print("ШАГ 4: Токены успешно получены.")
    access_token = token_json.get('access_token')
    refresh_token = token_json.get('refresh_token')
    expires_in = token_json.get('expires_in', 3600)

    user = request.user
    print(f"ШАГ 5: Сохранение токенов для пользователя {user}")

    try:
        google_creds_obj = GoogleCredentials.objects.get(user=user)
        google_creds_obj.access_token = access_token
        google_creds_obj.expires_in = timezone.now() + timedelta(seconds=expires_in)
        if refresh_token:
            google_creds_obj.refresh_token = refresh_token
        google_creds_obj.save()
    except ObjectDoesNotExist:
        print("Пользователь не имел GoogleCredentials — создаём новую запись.")
        if not refresh_token:
            print("ОШИБКА: Нет refresh_token для новой записи!")
            return JsonResponse({"error": "No refresh token for a new credentials record. Please try again."}, status=400)
        
        GoogleCredentials.objects.create(
            user=user,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=timezone.now() + timedelta(seconds=expires_in)
        )

    print("ШАГ 6: Подключение к YouTube API.")
    try:
        creds = Credentials(token=access_token, refresh_token=refresh_token)
        youtube_service = build("youtube", "v3", credentials=creds)
        channels_response = youtube_service.channels().list(mine=True, part="id,snippet").execute()

        if not channels_response.get('items'):
            print("ОШИБКА: Пустой список каналов в ответе.")
            return JsonResponse({"error": "Failed to get channel information."}, status=400)
        
        channel_info = channels_response['items'][0]
        channel_id = channel_info.get('id')
        title = channel_info['snippet']['title']
        description = channel_info['snippet'].get('description', '') 
        print(f"Найден канал: {title} (ID: {channel_id})")

        YouTubeChannel.objects.update_or_create(
            user=user,
            channel_id=channel_id,
            defaults={'title': title, 'description': description}
        )
    except Exception as e:
        print(f"ОШИБКА: Не удалось получить ID канала. Детали: {e}")
        return JsonResponse({"error": f"Error fetching channel ID: {e}"}, status=500)
    
    print("ШАГ 7: Получение аналитики.")
    try:
        fetch_and_save_analytics_data(user, channel_id)
        print("Аналитика сохранена.")
    except Exception as e:
        print(f"ОШИБКА: Аналитика не получена. Детали: {e}")

    print("ШАГ 8: Перенаправление на дашборд.")
    print("=" * 60)
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