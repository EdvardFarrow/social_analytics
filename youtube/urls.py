from django.urls import path
from .views import (
    YouTubeDashboardView,
    youtube_auth, 
    youtube_callback,
    channel_trends,
    video_trends,
)

urlpatterns = [
    path('auth/', youtube_auth, name='youtube_auth'),
    path('callback/', youtube_callback, name='youtube_callback'),
    
    path('dashboard/', YouTubeDashboardView.as_view(), name='youtube-dashboard'),
    path('trends/channel/', channel_trends, name='youtube_channel_trends'),
    path('trends/videos/', video_trends, name='youtube_video_trends'),
]