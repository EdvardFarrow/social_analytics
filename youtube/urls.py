from django.urls import path
from .views import YouTubeChannelListView, YouTubeChannelDetailView, YouTubeLoginView, YouTubeCallbackView

urlpatterns = [
    path('channels/', YouTubeChannelListView.as_view(), name='youtube-channel-list'),
    path('channels/<int:pk>/', YouTubeChannelDetailView.as_view(), name='youtube-channel-detail'),
    path("login/", YouTubeLoginView.as_view(), name="youtube-login"),
    path("callback/", YouTubeCallbackView.as_view(), name="youtube-callback"),
]

