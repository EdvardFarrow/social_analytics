import requests
from datetime import timedelta, date
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import render, redirect
from django.views import View
from django.views.decorators.http import require_GET
from django.utils.dateparse import parse_date
from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from urllib.parse import urlencode

from .models import YouTubeChannel, YouTubeToken, YouTubeVideo, ChannelDailyStat
from .serializers import YouTubeChannelSerializer, YouTubeChannelStatsSerializer
from .services import update_channel_stats, fetch_own_channel_id, refresh_access_token, update_channel_and_video_stats




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
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            tokens = request.user.youtube_token
        except YouTubeToken.DoesNotExist:
            return JsonResponse({"error": "YouTube tokens not found"}, status=400)

        try:
            access_token = refresh_access_token(tokens)
            channel_id = fetch_own_channel_id(access_token)
            obj = update_channel_stats(access_token, channel_id)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)

        return Response(YouTubeChannelStatsSerializer(obj).data)
    
class UpdateYouTubeStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            user_token = YouTubeToken.objects.get(user=request.user)
        except YouTubeToken.DoesNotExist:
            return Response({"error": "YouTube tokens not found."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            update_channel_and_video_stats(user_token)
            return Response({"message": "YouTube stats updated successfully"})
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@login_required
def youtube_dashboard(request):
    try:
        tokens = request.user.youtube_token
    except YouTubeToken.DoesNotExist:
        return render(request, 'youtube/no_tokens.html')  # update in future

    try:
        access_token = refresh_access_token(tokens)
        channel_id = fetch_own_channel_id(access_token)
        stats = update_channel_stats(access_token, channel_id)
        videos = YouTubeVideo.objects.filter(channel__user=request.user).order_by('-published_at')
    except Exception as e:
        return render(request, 'youtube/error.html', {'error': str(e)})

    return render(request, 'youtube/dashboard.html', {'stats': stats, 'videos': videos})    


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
            videos = videos.filter(published_at__date__gte=date_from_parsed)
    if date_to:
        date_to_parsed = parse_date(date_to)
        if date_to_parsed:
            videos = videos.filter(published_at__date__lte=date_to_parsed)
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
            'published_at': v.published_at.strftime('%Y-%m-%d'),
            'views': v.views,
            'likes': v.likes,
            'comments': v.comments,
        }
        for v in videos
    ]

    return JsonResponse({'videos': videos_data})


@login_required
@require_GET
def channel_trends(request):
    channel_id = request.GET.get('channel_id')
    if not channel_id:
        return JsonResponse({'error': 'channel_id is required'}, status=400)

    date_from_str = request.GET.get('date_from')
    date_to_str = request.GET.get('date_to')

    if not date_from_str:
        date_from = date.today() - timedelta(days=30)
    else:
        date_from = parse_date(date_from_str)
        if date_from is None:
            return JsonResponse({'error': 'Invalid date_from format'}, status=400)

    if not date_to_str:
        date_to = date.today()
    else:
        date_to = parse_date(date_to_str)
        if date_to is None:
            return JsonResponse({'error': 'Invalid date_to format'}, status=400)

    qs = ChannelDailyStat.objects.filter(channel__channel_id=channel_id, date__range=(date_from, date_to)).order_by('date')

    stats = qs.values('date', 'subscribers', 'views', 'video_count')

    data = {
        'dates': [s['date'].isoformat() for s in stats],
        'subscribers': [s['subscribers'] for s in stats],
        'views': [s['views'] for s in stats],
        'video_count': [s['video_count'] for s in stats],
    }
    return JsonResponse(data)


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
@require_GET
def channel_trends_api(request):
    channel_id = request.GET.get('channel_id')
    if not channel_id:
        return JsonResponse({'error': 'channel_id is required'}, status=400)

    date_from_str = request.GET.get('date_from')
    date_to_str = request.GET.get('date_to')

    date_from = parse_date(date_from_str) if date_from_str else None
    date_to = parse_date(date_to_str) if date_to_str else None

    try:
        channel = YouTubeChannel.objects.get(channel_id=channel_id)
    except YouTubeChannel.DoesNotExist:
        return JsonResponse({'error': 'Channel not found'}, status=404)

    qs = ChannelDailyStat.objects.filter(channel_id=channel)

    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)

    stats = qs.order_by('date').values('date', 'subscribers', 'views', 'video_count')

    data = {
        'dates': [s['date'].isoformat() for s in stats],
        'subscribers': [s['subscribers'] for s in stats],
        'views': [s['views'] for s in stats],
        'video_count': [s['video_count'] for s in stats],
    }
    return JsonResponse(data)