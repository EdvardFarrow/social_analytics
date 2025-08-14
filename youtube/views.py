import requests
import json

from datetime import timedelta, date, datetime, time
from django.utils import timezone
from django.utils.timezone import make_aware, localtime
from django.utils.dateparse import parse_date
from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils.dateparse import parse_date
from django.utils.safestring import mark_safe
from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from urllib.parse import urlencode

from .models import YouTubeChannel, YouTubeToken, YouTubeVideo, ChannelDailyStat, YouTubeChannelStats, VideoDailyStat
from .serializers import YouTubeChannelSerializer, YouTubeChannelStatsSerializer
from .services import update_channel_stats, fetch_own_channel_id, refresh_access_token, update_channel_and_video_stats, fetch_youtube_channel_stats
import logging

logger = logging.getLogger(__name__)



User = get_user_model()

class YouTubeChannelListView(generics.ListCreateAPIView):
    queryset = YouTubeChannel.objects.all()
    serializer_class = YouTubeChannelSerializer


class YouTubeChannelDetailView(generics.RetrieveAPIView):
    queryset = YouTubeChannel.objects.all()
    serializer_class = YouTubeChannelSerializer


class YouTubeLoginView(View):
    def get(self, request):
        params = {
            "client_id": settings.YOUTUBE_CLIENT_ID,
            "redirect_uri": settings.YOUTUBE_REDIRECT_URI,
            "response_type": "code",
            "scope": "openid email profile https://www.googleapis.com/auth/youtube.readonly",
            "access_type": "offline",
            "prompt": "consent",
        }
        url = f"https://accounts.google.com/o/oauth2/auth?{urlencode(params)}"
        return HttpResponseRedirect(url)


class YouTubeCallbackView(View):
    def get(self, request):
        code = request.GET.get("code")
        if not code:
            return JsonResponse({"error": "No code provided"}, status=400)

        token_data = {
            "code": code,
            "client_id": settings.YOUTUBE_CLIENT_ID,
            "client_secret": settings.YOUTUBE_CLIENT_SECRET,
            "redirect_uri": settings.YOUTUBE_REDIRECT_URI,
            "grant_type": "authorization_code",
        }
        
        token_response = requests.post("https://oauth2.googleapis.com/token", data=token_data)

        token_json = token_response.json()

        if "access_token" not in token_json:
            return JsonResponse({"error": "Failed to get token", "details": token_json}, status=400)

        access_token = token_json["access_token"]

        userinfo_response = requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )

        if userinfo_response.status_code != 200:
            return JsonResponse({"error": "Failed to get userinfo"}, status=400)

        userinfo = userinfo_response.json()

        User = get_user_model()
        user, created = User.objects.get_or_create(
            email=userinfo.get("email"),
            defaults={'full_name': userinfo.get("name")}
        )
        
        login(request, user)

        YouTubeToken.objects.update_or_create(
            user=user,
            defaults={
                'access_token': token_json["access_token"],
                'refresh_token': token_json.get("refresh_token"),
                'token_expiry': timezone.now() + timedelta(seconds=int(token_json.get("expires_in", 3600)))
            }
        )

        next_url = request.GET.get('next') or '/'
        return redirect(next_url)


class AddYouTubeChannelView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            tokens = request.user.youtube_token
        except YouTubeToken.DoesNotExist:
            return JsonResponse({"error": "YouTube tokens not found. Please authenticate."}, status=400)

        try:
            access_token = refresh_access_token(tokens)
        except Exception as e:
            return JsonResponse({"error": f"Token refresh failed: {str(e)}"}, status=400)

        channel_id = request.data.get('channel_id')
        if not channel_id:
            return JsonResponse({"error": "channel_id is required"}, status=400)

        try:
            channel_stats = update_channel_stats(access_token, channel_id)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)

        channel, created = YouTubeChannel.objects.get_or_create(
            user=request.user,
            channel_id=channel_id,
            defaults={'title': channel_stats.title}
        )

        return JsonResponse({"message": "Channel added", "channel": channel.title})
    
    
class YouTubeStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_token = request.user.youtube_token
        access_token = refresh_access_token(user_token)
        channel_id = fetch_own_channel_id(access_token)
        obj = update_channel_stats(access_token, channel_id)
        return Response(YouTubeChannelStatsSerializer(obj).data)
    
class UpdateYouTubeStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user_token = request.user.youtube_token
        update_channel_and_video_stats(user_token)
        return Response({"message": "YouTube stats updated successfully"})



@login_required
def youtube_dashboard(request):

    user_channels = request.user.youtube_channels.all()
    channel_ids = [c.channel_id for c in user_channels]

    stats = YouTubeChannelStats.objects.filter(channel_id__in=channel_ids).order_by('title')

    videos = YouTubeVideo.objects.filter(channel__user=request.user).order_by('-published_at')

    return render(request, 'youtube/dashboard.html', {'stats_list': stats, 'videos': videos})



@login_required
def trends_view(request):
    user_channels = request.user.youtube_channels.all()
    default_channel_id = user_channels[0].channel_id if user_channels else ''
    context = {
        'default_channel_id': default_channel_id,
        'default_date_from': (timezone.now() - timedelta(days=30)).date().isoformat(),
        'default_date_to': timezone.now().date().isoformat(),
    }
    return render(request, 'youtube/trends.html', context)

@login_required
def youtube_dashboard_videos(request):
    user = request.user
    videos = YouTubeVideo.objects.filter(channel__user=user)

    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    min_views = request.GET.get('min_views')
    max_views = request.GET.get('max_views')
    sort_by = request.GET.get('sort_by', '-published_at')

    if date_from:
        date_from_parsed = parse_date(date_from)
        if date_from_parsed:
            dt_from = make_aware(datetime.combine(date_from_parsed, time.min))
            videos = videos.filter(published_at__gte=dt_from)
    if date_to:
        date_to_parsed = parse_date(date_to)
        if date_to_parsed:
            dt_to = make_aware(datetime.combine(date_to_parsed, time.max))
            videos = videos.filter(published_at__lte=dt_to)

    if min_views and min_views.isdigit():
        videos = videos.filter(views__gte=int(min_views))
    if max_views and max_views.isdigit():
        videos = videos.filter(views__lte=int(max_views))

    valid_sort_fields = ['published_at', '-published_at', 'views', '-views']
    if sort_by not in valid_sort_fields:
        sort_by = '-published_at'

    videos = videos.order_by(sort_by)

    videos_data = [
        {
            'title': v.title,
            'published_at': localtime(v.published_at).strftime('%Y-%m-%d %H:%M'),
            'views': v.views,
            'likes': v.likes,
            'comments': v.comments,
        }
        for v in videos
    ]

    return JsonResponse({'videos': videos_data})


@login_required
def youtube_trends_data(request):
    from youtube.models import ChannelDailyStat, YouTubeChannel
    from django.utils.dateparse import parse_date
    from datetime import timedelta, date

    user_channels = YouTubeChannel.objects.filter(user=request.user)
    stats = ChannelDailyStat.objects.filter(channel_id__in=user_channels)

    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    if date_from:
        date_from_parsed = parse_date(date_from)
        if date_from_parsed:
            stats = stats.filter(date__gte=date_from_parsed)
    if date_to:
        date_to_parsed = parse_date(date_to)
        if date_to_parsed:
            stats = stats.filter(date__lte=date_to_parsed)

    data_by_date = {}
    for stat in stats:
        key = stat.date.isoformat()
        if key not in data_by_date:
            data_by_date[key] = {'views': 0, 'subscribers': 0, 'likes': 0}
        data_by_date[key]['views'] += stat.views
        data_by_date[key]['subscribers'] += stat.subscribers
        data_by_date[key]['likes'] += stat.likes

    sorted_dates = sorted(data_by_date.keys())
    labels = sorted_dates
    views = [data_by_date[d]['views'] for d in sorted_dates]
    subscribers = [data_by_date[d]['subscribers'] for d in sorted_dates]
    likes = [data_by_date[d]['likes'] for d in sorted_dates]

    return JsonResponse({'labels': labels, 'views': views, 'subscribers': subscribers, 'likes': likes})



@login_required
@require_GET
def channel_trends(request):
    user_channels = YouTubeChannel.objects.filter(user=request.user)
    if not user_channels.exists():
        return JsonResponse({'error': 'No channels found for this user'}, status=404)

    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    if not date_from:
        date_from = (date.today() - timedelta(days=30)).isoformat()
    if not date_to:
        date_to = date.today().isoformat()

    stats_qs = ChannelDailyStat.objects.filter(
        channel_id__in=user_channels,
        date__range=[date_from, date_to]
    ).order_by('date')

    dates = [stat.date.isoformat() for stat in stats_qs]
    stats = [
        {'views': stat.views, 'subscribers': stat.subscribers, 'video_count': stat.video_count}
        for stat in stats_qs
    ]

    context = {
        'dates_json': mark_safe(json.dumps(dates)),
        'stats_json': mark_safe(json.dumps(stats)),
    }

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'dates': dates, 'stats': stats})

    return render(request, "youtube/trends_data.html", context)




def update_all_videos(user_token: YouTubeToken):
    access_token = refresh_access_token(user_token)

    try:
        channel = YouTubeChannel.objects.get(user=user_token.user)
    except YouTubeChannel.DoesNotExist:
        raise Exception("Канал для этого пользователя не найден. Сначала нужно подтянуть канал.")

    videos = YouTubeVideo.objects.filter(channel=channel)

    video_ids = [video.video_id for video in videos]
    for i in range(0, len(video_ids), 50):
        batch_ids = video_ids[i:i + 50]

        stats_url = 'https://www.googleapis.com/youtube/v3/videos'
        stats_params = {
            'part': 'statistics',
            'id': ','.join(batch_ids)
        }
        headers = {'Authorization': f'Bearer {access_token}'}
        stats_resp = requests.get(stats_url, headers=headers, params=stats_params)
        if stats_resp.status_code != 200:
            raise Exception(f"Failed to fetch video stats: {stats_resp.text}")

        stats_data = stats_resp.json()
        for item in stats_data.get('items', []):
            vid_id = item['id']
            stats = item.get('statistics', {})
            try:
                video_obj = YouTubeVideo.objects.get(video_id=vid_id)
                video_obj.views = int(stats.get('viewCount', 0))
                video_obj.likes = int(stats.get('likeCount', 0))
                video_obj.comments = int(stats.get('commentCount', 0))
                video_obj.save(update_fields=['views', 'likes', 'comments'])
            except YouTubeVideo.DoesNotExist:
                continue  

    return {"message": f"Updated stats for {len(video_ids)} videos."}
    
    
@login_required
@require_POST
def youtube_refresh_all(request):
    try:
        token = YouTubeToken.objects.get(user=request.user)
        result = update_all_videos(token)
        return JsonResponse(result)
    except YouTubeToken.DoesNotExist:
        return JsonResponse({"message": "No YouTube token found for this user."}, status=400)
    except Exception as e:
        return JsonResponse({"message": str(e)}, status=500)
    
    
    
@login_required
@require_GET
def youtube_video_trends(request):
    user = request.user
    channel_ids = YouTubeChannel.objects.filter(user=user).values_list('id', flat=True)

    date_from = parse_date(request.GET.get('date_from')) or (timezone.now().date() - timedelta(days=30))
    date_to = parse_date(request.GET.get('date_to')) or timezone.now().date()

    videos_qs = YouTubeVideo.objects.filter(
        channel_id__in=channel_ids,
        published_at__date__range=[date_from, date_to]
    )

    video_ids = videos_qs.values_list('id', flat=True)

    stats_qs = VideoDailyStat.objects.filter(
        video_id__in=video_ids,
        date__range=[date_from, date_to]
    ).order_by('date')

    data_by_date = {}
    for stat in stats_qs:
        key = stat.date.isoformat()
        if key not in data_by_date:
            data_by_date[key] = {'views': 0, 'likes': 0, 'comments': 0}
        data_by_date[key]['views'] += stat.views
        data_by_date[key]['likes'] += stat.likes
        data_by_date[key]['comments'] += stat.comments

    sorted_dates = sorted(data_by_date.keys())
    views_data = [data_by_date[d]['views'] for d in sorted_dates]
    likes_data = [data_by_date[d]['likes'] for d in sorted_dates]
    comments_data = [data_by_date[d]['comments'] for d in sorted_dates]

    channel_stats_qs = ChannelDailyStat.objects.filter(
        channel_id__in=channel_ids,
        date__range=[date_from, date_to]
    ).order_by('date')

    subscribers_new = 0
    subscribers_lost = 0
    total_subscribers = 0
    prev_total = None

    for stat in channel_stats_qs:
        total = stat.subscribers
        if prev_total is not None:
            delta = total - prev_total
            if delta >= 0:
                subscribers_new += delta
            else:
                subscribers_lost += -delta
        prev_total = total
        total_subscribers = total

    return JsonResponse({
        'dates': sorted_dates,
        'views': views_data,
        'likes': likes_data,
        'comments': comments_data,
        'subscribers': {
            'new': subscribers_new,
            'lost': subscribers_lost,
            'total': total_subscribers
        }
    })