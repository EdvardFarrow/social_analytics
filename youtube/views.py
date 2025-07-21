from rest_framework import generics
from .models import YouTubeChannel
from .serializers import YouTubeChannelSerializer
import requests
from urllib.parse import urlencode
from django.conf import settings
from django.http import JsonResponse, HttpResponseRedirect
from django.views import View


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
            "scope": "https://www.googleapis.com/auth/youtube.readonly",
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

        data = {
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        }

        token_url = "https://oauth2.googleapis.com/token"
        r = requests.post(token_url, data=data)
        token_data = r.json()

        if "error" in token_data:
            return JsonResponse({"error": token_data}, status=400)

        # access_token = token_data["access_token"]
        # refresh_token = token_data.get("refresh_token")

        return JsonResponse(token_data)