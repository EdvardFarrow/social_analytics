from django.urls import path
from .views import (
    YouTubeDashboardView,
    YouTubeLoginView,
    youtube_login, 
    youtube_callback,
    channel_trends,
    video_trends,
)

urlpatterns = [
    # Маршруты для аутентификации
    path("login/", YouTubeLoginView.as_view(), name="youtube-login"),
    path('auth/google/login/', youtube_login, name='google_login'),
    path('callback/', youtube_callback, name='youtube_callback'),
    
    # Маршруты для дашборда и аналитики
    path('dashboard/', YouTubeDashboardView.as_view(), name='youtube-dashboard'),
    path('trends/channel/', channel_trends, name='youtube_channel_trends'),
    path('trends/videos/', video_trends, name='youtube_video_trends'),
]