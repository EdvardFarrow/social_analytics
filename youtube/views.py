from rest_framework import generics, permissions
from .models import YouTubeChannel, YouTubeChannelStats, YouTubeToken
from .serializers import YouTubeChannelSerializer
import requests
from urllib.parse import urlencode
from django.conf import settings
from django.http import JsonResponse, HttpResponseRedirect
from django.views import View
from django.utils import timezone
from datetime import timedelta
from rest_framework.views import APIView


class YouTubeChannelListView(generics.ListCreateAPIView):
    queryset = YouTubeChannel.objects.all()
    serializer_class = YouTubeChannelSerializer


class YouTubeChannelDetailView(generics.RetrieveAPIView):
    queryset = YouTubeChannel.objects.all()
    serializer_class = YouTubeChannelSerializer


class YouTubeLoginView(View):
    def get(self, request):
        params = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
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
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        }

        token_response = requests.post("https://oauth2.googleapis.com/token", data=token_data)
        token_json = token_response.json()
        
        print("TOKEN JSON:", token_json)

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

        return JsonResponse({
            "access_token": access_token,
            "refresh_token": token_json.get("refresh_token"),
            "email": userinfo.get("email"),
            "name": userinfo.get("name"),
        })

    
    
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


class AddYouTubeChannelView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        channel_id = request.data.get('channel_id')
        if not channel_id:
            return JsonResponse({"error": "channel_id is required"}, status=400)

        try:
            tokens = request.user.youtube_token
        except YouTubeToken.DoesNotExist:
            return JsonResponse({"error": "YouTube tokens not found. Please authenticate."}, status=400)

        try:
            channel_stats = update_channel_stats(tokens.access_token, channel_id)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)

        channel, created = YouTubeChannel.objects.get_or_create(
            user=request.user,
            channel_id=channel_id,
            defaults={'title': channel_stats.title}
        )

        return JsonResponse({"message": "Channel added", "channel": channel.title})