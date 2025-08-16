from django.urls import path
from .views import (
    YouTubeDashboardView,
    youtube_auth, 
    youtube_callback,
    youtube_dashboard,
    channel_trends,
    video_trends,
)

urlpatterns = [
    path('auth/', youtube_auth, name='youtube_auth'),
    path('callback/', youtube_callback, name='youtube_callback'),
    
    path('dashboard/', youtube_dashboard, name='youtube-dashboard'),
    path('trends/channel/', channel_trends, name='channel_trends'),
    path('trends/videos/', video_trends, name='video_trends'),
]