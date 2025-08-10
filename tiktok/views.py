import requests
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from django.http import JsonResponse, HttpResponseRedirect
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from .models import TikTokToken, TikTokVideo
from .serializers import TikTokVideoSerializer
from .services import fetch_user_videos, refresh_access_token


class TikTokLoginView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        params = {
            "client_key": settings.TIKTOK_CLIENT_KEY,
            "response_type": "code",
            "scope": "user.info.basic video.list",
            "redirect_uri": settings.TIKTOK_REDIRECT_URI,
            "state": "secure_random_state",
        }
        url = "https://www.tiktok.com/auth/authorize/?" + "&".join([f"{k}={v}" for k, v in params.items()])
        return HttpResponseRedirect(url)


class TikTokCallbackView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        code = request.GET.get("code")
        if not code:
            return JsonResponse({"error": "No code provided"}, status=400)

        token_url = "https://open.tiktokapis.com/v2/oauth/token/"
        token_data = {
            "client_key": settings.TIKTOK_CLIENT_KEY,
            "client_secret": settings.TIKTOK_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": settings.TIKTOK_REDIRECT_URI,
        }

        r = requests.post(token_url, data=token_data)
        data = r.json()

        if "access_token" not in data:
            return JsonResponse({"error": "Failed to get token", "details": data}, status=400)

        TikTokToken.objects.update_or_create(
            user=request.user,
            defaults={
                "access_token": data["access_token"],
                "refresh_token": data.get("refresh_token"),
                "token_expiry": timezone.now() + timedelta(seconds=int(data.get("expires_in", 3600)))
            }
        )
        return JsonResponse({"message": "TikTok account connected"})


class TikTokVideosView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            tokens = request.user.tiktok_token
        except TikTokToken.DoesNotExist:
            return JsonResponse({"error": "No TikTok account connected"}, status=400)

        if tokens.token_expiry < timezone.now():
            access_token = refresh_access_token(tokens)
        else:
            access_token = tokens.access_token

        data = fetch_user_videos(access_token)

        for item in data.get("data", []):
            TikTokVideo.objects.update_or_create(
                user=request.user,
                video_id=item["id"],
                defaults={
                    "description": item.get("description", ""),
                    "create_time": timezone.datetime.fromtimestamp(item["create_time"], tz=timezone.utc),
                    "views": item.get("stats", {}).get("play_count", 0),
                    "likes": item.get("stats", {}).get("like_count", 0),
                    "comments": item.get("stats", {}).get("comment_count", 0),
                    "shares": item.get("stats", {}).get("share_count", 0),
                }
            )

        videos = TikTokVideo.objects.filter(user=request.user)
        return JsonResponse(TikTokVideoSerializer(videos, many=True).data, safe=False)
