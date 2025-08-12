from django.urls import path
from .views import YouTubeChannelListView, YouTubeChannelDetailView, YouTubeLoginView, YouTubeCallbackView, AddYouTubeChannelView, YouTubeStatsView, youtube_dashboard, youtube_dashboard_videos, UpdateYouTubeStatsView, trends_view, channel_trends_api

urlpatterns = [
    path('channels/', YouTubeChannelListView.as_view(), name='youtube-channel-list'),
    path('channels/<int:pk>/', YouTubeChannelDetailView.as_view(), name='youtube-channel-detail'),
    path("login/", YouTubeLoginView.as_view(), name="youtube-login"),
    path("callback/", YouTubeCallbackView.as_view(), name="youtube-callback"),
    path('add-channel/', AddYouTubeChannelView.as_view(), name='add_youtube_channel'),
    path('stats/', YouTubeStatsView.as_view(), name='youtube-stats'),
    path('dashboard/', youtube_dashboard, name='youtube_dashboard'),
    path('update-stats/', UpdateYouTubeStatsView.as_view(), name='update_youtube_stats'),
    path('dashboard/videos/', youtube_dashboard_videos, name='youtube_dashboard_videos'),
    path('trends/', trends_view, name='youtube_trends_page'),  
    path('trends/data/', channel_trends_api, name='youtube_channel_trends'),
    
]

