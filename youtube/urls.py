from django.urls import path
from .views import YouTubeChannelListView, YouTubeChannelDetailView, YouTubeLoginView, YouTubeCallbackView, AddYouTubeChannelView, YouTubeStatsView, youtube_dashboard, youtube_dashboard_videos, UpdateYouTubeStatsView, trends_view, channel_trends, update_all_videos, youtube_refresh_all, youtube_video_trends

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
    path('trends/data/', channel_trends, name='youtube_channel_trends'),
    path('update_videos/', update_all_videos, name='youtube_update_all_videos'),
    path('youtube/refresh_all/', youtube_refresh_all, name='youtube_refresh_all'),
    path('video-trends/', youtube_video_trends, name='youtube_video_trends'),
    
]

