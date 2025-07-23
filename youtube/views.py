import requests
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import JsonResponse, HttpResponseRedirect
from django.views import View
from rest_framework import generics, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from urllib.parse import urlencode
from .models import YouTubeChannel, YouTubeToken
from .serializers import YouTubeChannelSerializer, YouTubeChannelStatsSerializer
from .services import update_channel_stats, fetch_own_channel_id, refresh_access_token



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
            "client_id": settings.GOOGLE_CLIENT_ID,
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
        print("🔁 CALLBACK VIEW STARTED")

        code = request.GET.get("code")
        print("➡️ CODE:", code)

        if not code:
            print("⛔️ NO CODE")
            return JsonResponse({"error": "No code provided"}, status=400)

        token_data = {
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        }

        print("📤 SENDING TOKEN REQUEST...")
        token_response = requests.post("https://oauth2.googleapis.com/token", data=token_data)
        token_json = token_response.json()
        print("✅ TOKEN RESPONSE:", token_json)

        if "access_token" not in token_json:
            print("⛔️ NO ACCESS TOKEN IN RESPONSE")
            return JsonResponse({"error": "Failed to get token", "details": token_json}, status=400)

        access_token = token_json["access_token"]

        userinfo_response = requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )

        print("👤 USERINFO STATUS:", userinfo_response.status_code)

        if userinfo_response.status_code != 200:
            return JsonResponse({"error": "Failed to get userinfo"}, status=400)

        userinfo = userinfo_response.json()
        print("👤 USERINFO:", userinfo)

        # ВРЕМЕННО
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.first()
        print("💾 USING USER:", user)

        from youtube.models import YouTubeToken
        from django.utils import timezone
        from datetime import timedelta

        YouTubeToken.objects.update_or_create(
            user=user,
            defaults={
                'access_token': token_json["access_token"],
                'refresh_token': token_json.get("refresh_token"),
                'token_expiry': timezone.now() + timedelta(seconds=int(token_json.get("expires_in", 3600)))
            }
        )

        print("✅ TOKEN SAVED")

        return JsonResponse({
            "access_token": access_token,
            "refresh_token": token_json.get("refresh_token"),
            "email": userinfo.get("email"),
            "name": userinfo.get("name"),
        })


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