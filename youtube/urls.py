from django.urls import path
from .views import (
    youtube_auth, 
    youtube_callback,
    youtube_dashboard,
    channel_trends,
    video_trends,
    audience_demographics,
    viewer_activity
)

urlpatterns = [
    path('auth/', youtube_auth, name='youtube_auth'),   
    path('callback/', youtube_callback, name='youtube_callback'),
    
    path('dashboard/', youtube_dashboard, name='youtube-dashboard'),
    path('trends/audience_demographic/', audience_demographics, name='audience_demographics'),
    path('trends/channel/', channel_trends, name='channel_trends'),
    path('trends/videos/', video_trends, name='video_trends'),
    path('api/viewer_activity/', viewer_activity, name='viewer_activity'), 
]